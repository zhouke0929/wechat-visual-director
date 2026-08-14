from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .delivery import _extract_main, _responsive_delivery_document


TOKEN_ENDPOINT = "https://api.weixin.qq.com/cgi-bin/token"
API_BASE = "https://api.weixin.qq.com/cgi-bin"


@dataclass(frozen=True)
class WechatPublishResult:
    status: str
    media_id: str | None
    error: dict[str, Any] | None


class WechatApiError(RuntimeError):
    def __init__(self, errcode: int | None, errmsg: str, *, stage: str) -> None:
        super().__init__(errmsg)
        self.errcode = errcode
        self.errmsg = errmsg
        self.stage = stage


class WechatDraftPublisher:
    """Publish a frozen revision through the official WeChat API.

    Credentials are read from the process environment or the private local env
    file. Access tokens live in process memory only and are never returned by
    diagnostics or persisted in the task database.
    """

    def __init__(
        self,
        root: Path,
        *,
        env_file: Path | None = None,
        token_endpoint: str | None = None,
        api_base: str | None = None,
        requester: Callable[..., Any] = urllib.request.urlopen,
        timeout_seconds: int = 90,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.root = root
        self.env_file_override = env_file
        self.token_endpoint = token_endpoint or os.environ.get(
            "VISUAL_DIRECTOR_WECHAT_TOKEN_ENDPOINT", TOKEN_ENDPOINT
        )
        self.api_base = (api_base or os.environ.get("VISUAL_DIRECTOR_WECHAT_API_BASE", API_BASE)).rstrip("/")
        self.requester = requester
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        self._token_cache: dict[str, tuple[str, float]] = {}

    def _env_file(self) -> Path:
        if self.env_file_override is not None:
            return self.env_file_override
        configured = os.environ.get("VISUAL_DIRECTOR_ENV_FILE")
        return Path(configured).expanduser().resolve() if configured else self.root / ".env.local"

    @staticmethod
    def _read_env_file(path: Path) -> dict[str, str]:
        if not path.is_file():
            return {}
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def _credentials(self) -> tuple[str | None, str | None, str]:
        app_id = os.environ.get("WECHAT_APP_ID")
        app_secret = os.environ.get("WECHAT_APP_SECRET")
        if app_id and app_secret:
            return app_id, app_secret, "process_environment"
        values = self._read_env_file(self._env_file())
        app_id = values.get("WECHAT_APP_ID")
        app_secret = values.get("WECHAT_APP_SECRET")
        return app_id, app_secret, "local_env_file" if app_id and app_secret else "missing"

    def quick_status(self) -> dict[str, Any]:
        app_id, app_secret, source = self._credentials()
        configured = bool(app_id and app_secret)
        return {
            "schema_version": "publisher_quick_status.v0.3",
            "provider": "wechat_api",
            "transport": "built_in",
            "credentials_configured": configured,
            "credential_source": source,
            "ready_for_connection_probe": configured,
        }

    def status(self) -> dict[str, Any]:
        quick = self.quick_status()
        warnings: list[str] = []
        if not quick["credentials_configured"]:
            warnings.append("尚未在本机配置微信公众号 AppID 和 AppSecret。")
        return {
            "schema_version": "publisher_status.v0.3",
            **{key: quick[key] for key in ("provider", "transport", "credentials_configured", "credential_source")},
            "ready": quick["credentials_configured"],
            "warnings": warnings,
        }

    def _open_json(self, request: urllib.request.Request, *, stage: str) -> dict[str, Any]:
        try:
            response = self.requester(request, timeout=self.timeout_seconds)
            with response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            try:
                raw = error.read()
            except OSError:
                raw = b""
            if raw:
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = {}
                raise WechatApiError(payload.get("errcode"), str(payload.get("errmsg") or "HTTP error"), stage=stage) from error
            raise
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("errcode") not in (None, 0):
            raise WechatApiError(int(payload["errcode"]), str(payload.get("errmsg") or "WeChat API error"), stage=stage)
        return payload

    def _access_token(self, *, force_refresh: bool = False) -> str:
        app_id, app_secret, _ = self._credentials()
        if not app_id or not app_secret:
            raise WechatApiError(None, "微信公众号 AppID 或 AppSecret 未配置", stage="token")
        cached = self._token_cache.get(app_id)
        if cached and not force_refresh and cached[1] > self.clock() + 120:
            return cached[0]
        query = urllib.parse.urlencode(
            {"grant_type": "client_credential", "appid": app_id, "secret": app_secret}
        )
        request = urllib.request.Request(f"{self.token_endpoint}?{query}", method="GET")
        payload = self._open_json(request, stage="token")
        token = str(payload.get("access_token") or "")
        if not token:
            raise WechatApiError(None, "微信接口未返回 access_token", stage="token")
        expires_in = max(300, int(payload.get("expires_in") or 7200))
        self._token_cache[app_id] = (token, self.clock() + expires_in)
        return token

    @staticmethod
    def _multipart_image(filename: str, content_type: str, content: bytes) -> tuple[bytes, str]:
        boundary = f"----VisualDirector{uuid.uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="media"; filename="{Path(filename).name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("ascii")
        return body, f"multipart/form-data; boundary={boundary}"

    def _upload_image(self, token: str, *, filename: str, content_type: str, content: bytes) -> dict[str, Any]:
        body, multipart_type = self._multipart_image(filename, content_type, content)
        endpoint = f"{self.api_base}/material/add_material?{urllib.parse.urlencode({'access_token': token, 'type': 'image'})}"
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": multipart_type, "Content-Length": str(len(body))},
            method="POST",
        )
        return self._open_json(request, stage="upload_image")

    def _upload_image_with_token_refresh(
        self,
        token: str,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> tuple[dict[str, Any], str]:
        try:
            return self._upload_image(
                token, filename=filename, content_type=content_type, content=content
            ), token
        except WechatApiError as error:
            if error.errcode not in {40014, 42001}:
                raise
        refreshed = self._access_token(force_refresh=True)
        return self._upload_image(
            refreshed, filename=filename, content_type=content_type, content=content
        ), refreshed

    def _create_draft(self, token: str, article: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self.api_base}/draft/add?{urllib.parse.urlencode({'access_token': token})}"
        body = json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        return self._open_json(request, stage="create_draft")

    @staticmethod
    def _classified_error(error: BaseException, *, stage: str) -> WechatPublishResult:
        if isinstance(error, WechatApiError):
            mapping = {
                40013: ("wechat_credentials_invalid", "微信公众号 AppID 无效。"),
                40125: ("wechat_credentials_invalid", "微信公众号 AppSecret 无效。"),
                40164: ("wechat_ip_not_whitelisted", "当前公网出口 IP 未加入微信公众号白名单。"),
                45009: ("wechat_rate_limited", "微信公众号接口调用已达到频率限制，请稍后重试。"),
                45110: ("wechat_author_too_long", "作者字段超出微信公众号限制，请缩短后重试。"),
            }
            code, message = mapping.get(
                error.errcode,
                ("wechat_api_error", f"微信公众号接口返回错误（{error.errcode or 'unknown'}）。"),
            )
            return WechatPublishResult(
                status="failed",
                media_id=None,
                error={
                    "code": code,
                    "message": message,
                    "retryable": error.errcode not in {40013, 40125},
                    "details": {"errcode": error.errcode, "stage": error.stage},
                },
            )
        unknown = stage == "create_draft"
        return WechatPublishResult(
            status="unknown" if unknown else "failed",
            media_id=None,
            error={
                "code": "wechat_draft_result_unknown" if unknown else "wechat_network_error",
                "message": (
                    "创建草稿时连接中断，结果未知。请先到公众号后台草稿箱核对，避免重复创建。"
                    if unknown
                    else "连接微信公众号接口失败，请检查网络后重试。"
                ),
                "retryable": not unknown,
                "details": {"stage": stage, "exception_type": type(error).__name__},
            },
        )

    def publish(
        self,
        revision: dict[str, Any],
        assets: list[dict[str, Any]],
        read_asset: Callable[[str], tuple[Path, str]],
    ) -> WechatPublishResult:
        if not self.status()["ready"]:
            return WechatPublishResult(
                status="failed",
                media_id=None,
                error={
                    "code": "wechat_publisher_not_ready",
                    "message": "请先在本地设置中配置微信公众号 AppID 和 AppSecret，并检测连接。",
                    "retryable": True,
                },
            )
        try:
            token = self._access_token()
        except (WechatApiError, urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            return self._classified_error(error, stage="token")

        document = _responsive_delivery_document(revision["frozen_html"])
        uploaded_by_hash: dict[str, dict[str, Any]] = {}
        cover_media_id: str | None = None
        try:
            for asset in assets:
                path, content_type = read_asset(asset["id"])
                digest = str(asset.get("output_sha256") or path)
                uploaded = uploaded_by_hash.get(digest)
                if uploaded is None:
                    uploaded, token = self._upload_image_with_token_refresh(
                        token,
                        filename=str(asset.get("relative_filename") or path.name),
                        content_type=content_type,
                        content=path.read_bytes(),
                    )
                    uploaded_by_hash[digest] = uploaded
                image_url = str(uploaded.get("url") or "")
                if asset["asset_role"] == "cover":
                    cover_media_id = str(uploaded.get("media_id") or "") or None
                elif image_url:
                    document = document.replace(
                        f'src="asset://{asset["asset_token"]}"',
                        f'src="{image_url}"',
                    )
        except (WechatApiError, urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            return self._classified_error(error, stage="upload_image")
        if not cover_media_id:
            return WechatPublishResult(
                status="failed",
                media_id=None,
                error={"code": "cover_upload_failed", "message": "封面上传后未返回 media_id。", "retryable": True},
            )
        if "asset://" in document:
            return WechatPublishResult(
                status="failed",
                media_id=None,
                error={"code": "body_asset_upload_failed", "message": "正文中仍有图片未完成上传。", "retryable": True},
            )

        metadata = revision["metadata"]
        article: dict[str, Any] = {
            "title": metadata["title"],
            "content": _extract_main(document),
            "thumb_media_id": cover_media_id,
            "show_cover_pic": 1 if metadata.get("show_cover_pic") else 0,
        }
        for source, target in (
            ("author", "author"),
            ("digest", "digest"),
            ("content_source_url", "content_source_url"),
        ):
            if metadata.get(source):
                article[target] = metadata[source]
        try:
            try:
                payload = self._create_draft(token, article)
            except WechatApiError as error:
                if error.errcode not in {40014, 42001}:
                    raise
                payload = self._create_draft(self._access_token(force_refresh=True), article)
        except (WechatApiError, urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            return self._classified_error(error, stage="create_draft")
        media_id = str(payload.get("media_id") or "") or None
        if not media_id:
            return WechatPublishResult(
                status="unknown",
                media_id=None,
                error={
                    "code": "wechat_draft_result_unknown",
                    "message": "微信接口未返回草稿 Media ID，请先到公众号后台核对。",
                    "retryable": False,
                    "details": {"stage": "create_draft"},
                },
            )
        return WechatPublishResult(status="succeeded", media_id=media_id, error=None)
