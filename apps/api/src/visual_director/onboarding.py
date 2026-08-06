from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SETUP_PREFERENCES_SCHEMA_VERSION = "setup_preferences.v0.1"
CAPABILITY_SETTINGS_SCHEMA_VERSION = "capability_settings.v0.1"
WECHAT_SETTINGS_SCHEMA_VERSION = "wechat_publisher_settings.v0.1"
WECHAT_PROBE_SCHEMA_VERSION = "wechat_connection_probe.v0.1"
PUBLIC_IP_PROBE_SCHEMA_VERSION = "public_ip_probe.v0.1"

TARGET_MODES = {"typeset_only", "images", "full_delivery"}
DEFAULT_TARGET_MODE = "typeset_only"
DEFAULT_WECHAT_TOKEN_ENDPOINT = "https://api.weixin.qq.com/cgi-bin/token"
DEFAULT_PUBLIC_IP_ENDPOINTS = (
    "https://api64.ipify.org?format=json",
    "https://ifconfig.me/ip",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_setup_preferences(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(value, dict):
                payload = value
        except (OSError, json.JSONDecodeError):
            payload = {}
    target_mode = str(payload.get("target_mode") or DEFAULT_TARGET_MODE)
    if target_mode not in TARGET_MODES:
        target_mode = DEFAULT_TARGET_MODE
    return {
        "schema_version": SETUP_PREFERENCES_SCHEMA_VERSION,
        "target_mode": target_mode,
        "updated_at": payload.get("updated_at"),
    }


def write_setup_preferences(path: Path, target_mode: str) -> dict[str, Any]:
    if target_mode not in TARGET_MODES:
        raise ValueError(f"Unsupported target mode: {target_mode}")
    payload = {
        "schema_version": SETUP_PREFERENCES_SCHEMA_VERSION,
        "target_mode": target_mode,
        "updated_at": _utc_now(),
    }
    _atomic_write_json(path, payload)
    return payload


def write_probe_status(path: Path, name: str, result: dict[str, Any]) -> None:
    current: dict[str, Any] = {}
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(value, dict):
                current = value
        except (OSError, json.JSONDecodeError):
            current = {}
    entry: dict[str, Any] = {
        "checked_at": (
            None
            if result.get("code") == "not_checked"
            else result.get("checked_at") or _utc_now()
        ),
        "ok": bool(result.get("ok")),
        "code": result.get("code"),
    }
    public_ip = result.get("public_ip")
    if public_ip:
        entry["public_ip_sha256"] = hashlib.sha256(str(public_ip).encode("utf-8")).hexdigest()
    current.update({"schema_version": "provider_probe_status.v0.1", name: entry})
    _atomic_write_json(path, current)


class WechatConnectionProbe:
    """Check credentials without creating media, drafts, or persistent tokens."""

    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_WECHAT_TOKEN_ENDPOINT,
        opener: Callable[..., Any] = urlopen,
        timeout_seconds: int = 15,
    ) -> None:
        self.endpoint = endpoint
        self.opener = opener
        self.timeout_seconds = timeout_seconds

    def probe(self, app_id: str, app_secret: str) -> dict[str, Any]:
        checked_at = _utc_now()
        if not app_id or not app_secret:
            return self._result(False, "wechat_credentials_missing", checked_at)
        query = urlencode(
            {
                "grant_type": "client_credential",
                "appid": app_id,
                "secret": app_secret,
            }
        )
        request = Request(
            f"{self.endpoint}?{query}",
            headers={"Accept": "application/json", "User-Agent": "wechat-visual-director"},
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
            payload = json.loads(raw.decode("utf-8"))
        except HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                return self._result(False, "wechat_http_error", checked_at, retryable=True)
        except (TimeoutError, URLError, OSError):
            return self._result(False, "wechat_network_unavailable", checked_at, retryable=True)
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return self._result(False, "wechat_response_invalid", checked_at, retryable=True)

        if isinstance(payload, dict) and str(payload.get("access_token") or "").strip():
            return self._result(True, "wechat_connection_ready", checked_at)
        try:
            errcode = int(payload.get("errcode") or 0) if isinstance(payload, dict) else 0
        except (TypeError, ValueError):
            errcode = 0
        code = {
            40013: "wechat_app_id_invalid",
            40125: "wechat_app_secret_invalid",
            40164: "wechat_ip_not_whitelisted",
            45009: "wechat_api_rate_limited",
        }.get(errcode, "wechat_credentials_rejected")
        return self._result(
            False,
            code,
            checked_at,
            retryable=code in {"wechat_api_rate_limited"},
            provider_code=errcode or None,
        )

    @staticmethod
    def _result(
        ok: bool,
        code: str,
        checked_at: str,
        *,
        retryable: bool = False,
        provider_code: int | None = None,
    ) -> dict[str, Any]:
        messages = {
            "wechat_connection_ready": "微信公众号凭据有效，当前网络可获取 access token。",
            "wechat_credentials_missing": "请先填写微信公众号 AppID 和 AppSecret。",
            "wechat_app_id_invalid": "微信公众号 AppID 无效，请核对后重试。",
            "wechat_app_secret_invalid": "微信公众号 AppSecret 无效，请重新填写后重试。",
            "wechat_ip_not_whitelisted": "当前公网 IP 尚未加入微信公众号后台白名单。",
            "wechat_api_rate_limited": "微信公众号接口调用频率受限，请稍后重试。",
            "wechat_network_unavailable": "无法连接微信公众号接口，请检查网络后重试。",
            "wechat_http_error": "微信公众号接口返回 HTTP 错误，请稍后重试。",
            "wechat_response_invalid": "微信公众号接口返回了无法识别的响应。",
            "wechat_credentials_rejected": "微信公众号拒绝了当前凭据，请核对配置。",
        }
        return {
            "ok": ok,
            "schema_version": WECHAT_PROBE_SCHEMA_VERSION,
            "code": code,
            "message": messages[code],
            "retryable": retryable,
            "checked_at": checked_at,
            "provider_code": provider_code,
            "access_token_persisted": False,
            "draft_created": False,
        }


class PublicIpProbe:
    def __init__(
        self,
        *,
        endpoints: tuple[str, ...] = DEFAULT_PUBLIC_IP_ENDPOINTS,
        opener: Callable[..., Any] = urlopen,
        timeout_seconds: int = 8,
    ) -> None:
        self.endpoints = endpoints
        self.opener = opener
        self.timeout_seconds = timeout_seconds

    def probe(self) -> dict[str, Any]:
        checked_at = _utc_now()
        for endpoint in self.endpoints:
            request = Request(
                endpoint,
                headers={"Accept": "application/json,text/plain", "User-Agent": "wechat-visual-director"},
            )
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8").strip()
                try:
                    decoded = json.loads(raw)
                    candidate = decoded.get("ip") if isinstance(decoded, dict) else raw
                except json.JSONDecodeError:
                    candidate = raw
                public_ip = str(ipaddress.ip_address(str(candidate).strip()))
                return {
                    "ok": True,
                    "schema_version": PUBLIC_IP_PROBE_SCHEMA_VERSION,
                    "code": "public_ip_detected",
                    "message": "已检测到当前网络的公网出口 IP。",
                    "public_ip": public_ip,
                    "ip_version": ipaddress.ip_address(public_ip).version,
                    "checked_at": checked_at,
                    "external_request_performed": True,
                }
            except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, ValueError):
                continue
        return {
            "ok": False,
            "schema_version": PUBLIC_IP_PROBE_SCHEMA_VERSION,
            "code": "public_ip_unavailable",
            "message": "暂时无法获取公网 IP，请检查网络后重试或手动查询。",
            "public_ip": None,
            "ip_version": None,
            "checked_at": checked_at,
            "external_request_performed": True,
        }
