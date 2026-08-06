from __future__ import annotations

import html as html_module
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml


WENYAN_MINIMUM_VERSION = "2.0.1"
WENYAN_RECOMMENDED_VERSION = "2.0.11"
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-_][0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
MEDIA_ID_PATTERNS = (
    re.compile(r"\bMedia\s*ID\s*[:：=]\s*[\"']?([A-Za-z0-9_-]+)", re.IGNORECASE),
    re.compile(r"[\"'](?:media_id|mediaId)[\"']\s*[:=]\s*[\"']([A-Za-z0-9_-]+)[\"']", re.IGNORECASE),
)
ROOT_MAIN_PATTERN = re.compile(
    r'(<main\b[^>]*\bstyle=")([^"]*)(")',
    flags=re.IGNORECASE,
)


def _version_tuple(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    match = re.search(r"(\d+(?:\.\d+)+)", value)
    return tuple(int(item) for item in match.group(1).split(".")) if match else ()


def _decode_process_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def _extract_media_id(output: str) -> str | None:
    normalized = ANSI_ESCAPE_PATTERN.sub("", output)
    for pattern in MEDIA_ID_PATTERNS:
        match = pattern.search(normalized)
        if match and match.group(1).lower() not in {"null", "none", "undefined"}:
            return match.group(1)
    return None


def _wenyan_diagnostics(
    *,
    stdout: str,
    stderr: str,
    return_code: int | None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Persist enough evidence to compare failures without storing CLI output or credentials."""

    combined = "\n".join(item for item in (stdout, stderr) if item)
    for key in ("WECHAT_APP_ID", "WECHAT_APP_SECRET"):
        value = os.environ.get(key)
        if value:
            combined = combined.replace(value, f"<{key.lower()}_redacted>")
    diagnostics: dict[str, Any] = {
        "return_code": return_code,
        "stdout_chars": len(stdout),
        "stderr_chars": len(stderr),
        "output_sha256": hashlib.sha256(combined.encode("utf-8", errors="replace")).hexdigest(),
        "media_id_detected": _extract_media_id(combined) is not None,
    }
    if timeout_seconds is not None:
        diagnostics["timeout_seconds"] = timeout_seconds
    return diagnostics


def _extract_main(document: str) -> str:
    match = re.search(r"<main\b[^>]*>.*?</main>", document, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("冻结版本缺少可发布的 main 内容")
    return match.group(0)


def _responsive_delivery_document(document: str) -> str:
    """Keep legacy frozen revisions portable without changing component widths."""

    def replace_root_style(match: re.Match[str]) -> str:
        style = re.sub(
            r"(?<!max-)width\s*:\s*390px\s*;?",
            "width:100%;",
            match.group(2),
            count=1,
            flags=re.IGNORECASE,
        )
        style = re.sub(
            r"background-color\s*:\s*#fffefa\s*;?",
            "",
            style,
            count=1,
            flags=re.IGNORECASE,
        )
        style = re.sub(
            r"box-shadow\s*:\s*0\s+12px\s+40px\s+rgba\(27\s*,\s*41\s*,\s*38\s*,\s*\.10\)\s*;?",
            "",
            style,
            count=1,
            flags=re.IGNORECASE,
        )
        style = re.sub(
            r"padding\s*:\s*0\s+24px\s+34px\s*;?",
            "padding:0 0 34px;",
            style,
            count=1,
            flags=re.IGNORECASE,
        )
        return f"{match.group(1)}{style}{match.group(3)}"

    responsive = ROOT_MAIN_PATTERN.sub(replace_root_style, document, count=1)

    def remove_legacy_hero(match: re.Match[str]) -> str:
        hero = match.group(2)
        if "<h1" in hero.lower() and "组件库" in hero:
            return match.group(1)
        return match.group(0)

    return re.sub(
        r"(<main\b[^>]*>)\s*(<header\b[^>]*>.*?</header>)",
        remove_legacy_hero,
        responsive,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _plain_text(document: str) -> str:
    text = re.sub(r"<(br|/p|/section|/h[1-6]|/li|/blockquote)\b[^>]*>", "\n", document, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _frontmatter(metadata: dict[str, Any], cover_path: str) -> str:
    values: dict[str, Any] = {
        "title": metadata["title"],
        "cover": cover_path,
    }
    if metadata.get("author"):
        values["author"] = metadata["author"]
    if metadata.get("content_source_url"):
        values["source_url"] = metadata["content_source_url"]
    return "---\n" + yaml.safe_dump(values, allow_unicode=True, sort_keys=False).strip() + "\n---\n\n"


def build_delivery_files(
    revision: dict[str, Any],
    assets: list[dict[str, Any]],
    read_asset: Callable[[str], tuple[Path, str]],
) -> dict[str, bytes]:
    token_to_relative: dict[str, str] = {}
    files: dict[str, bytes] = {}
    cover_relative: str | None = None
    manifest_items: list[dict[str, Any]] = []
    for asset in assets:
        path, _ = read_asset(asset["id"])
        relative = f'assets/{Path(asset["relative_filename"]).name}'
        token_to_relative[str(asset["asset_token"])] = f"./{relative}"
        files[relative] = path.read_bytes()
        if asset["asset_role"] == "cover":
            cover_relative = f"./{relative}"
        manifest_items.append(
            {
                key: asset[key]
                for key in (
                    "asset_token",
                    "asset_role",
                    "relative_filename",
                    "content_type",
                    "output_sha256",
                    "width",
                    "height",
                )
            }
        )
    if cover_relative is None:
        raise ValueError("冻结版本缺少封面资产")

    portable_html = _responsive_delivery_document(revision["frozen_html"])
    for token, relative in token_to_relative.items():
        portable_html = portable_html.replace(f'src="asset://{token}"', f'src="{relative}"')
    body_html = _extract_main(portable_html)
    article_markdown = _frontmatter(revision["metadata"], cover_relative) + body_html + "\n"
    files["article.md"] = article_markdown.encode("utf-8")
    files["article.html"] = portable_html.encode("utf-8")
    files["visual-director-theme.css"] = (
        "#wenyan{max-width:100%;}\n#wenyan img{max-width:100%;height:auto;}\n"
    ).encode("utf-8")
    files["manifest.json"] = json.dumps(
        {
            "schema_version": "visual_director_delivery.v0.1",
            "revision_id": revision["id"],
            "frozen_html_hash": revision["frozen_html_hash"],
            "asset_manifest_hash": revision["asset_manifest_hash"],
            "title": revision["metadata"]["title"],
            "assets": manifest_items,
            "notes": [
                "article.md is the Wenyan CLI input.",
                "article.html is a portable preview; it does not create a WeChat draft by itself.",
                "Wenyan 2.0.x does not transmit the local digest or show_cover_pic fields.",
            ],
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    return files


def build_delivery_zip(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()


def build_clipboard_payload(
    revision: dict[str, Any],
    assets: list[dict[str, Any]],
    absolute_asset_url: Callable[[str], str],
) -> dict[str, Any]:
    document = _responsive_delivery_document(revision["frozen_html"])
    cover_url: str | None = None
    for asset in assets:
        target = absolute_asset_url(asset["id"])
        document = document.replace(f'src="asset://{asset["asset_token"]}"', f'src="{target}"')
        if asset["asset_role"] == "cover":
            cover_url = target
    body_html = _extract_main(document)
    return {
        "schema_version": "clipboard_payload.v0.1",
        "title": revision["metadata"]["title"],
        "html": body_html,
        "text": _plain_text(body_html),
        "cover_url": cover_url,
        "warnings": ["粘贴后必须保存、重新打开并在手机端检查图片和样式。"],
    }


@dataclass(frozen=True)
class WenyanPublishResult:
    status: str
    media_id: str | None
    error: dict[str, Any] | None


class WenyanPublisher:
    def __init__(
        self,
        root: Path,
        *,
        command: str | None = None,
        env_file: Path | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        timeout_seconds: int = 240,
    ) -> None:
        self.root = root
        self.command_override = command or os.environ.get("VISUAL_DIRECTOR_WENYAN_COMMAND")
        self.env_file_override = env_file
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    def _command(self) -> str | None:
        if self.command_override:
            candidate = Path(self.command_override)
            return str(candidate) if candidate.is_file() else shutil.which(self.command_override)
        return shutil.which("wenyan")

    def _env_file(self) -> Path:
        if self.env_file_override is not None:
            return self.env_file_override
        configured = os.environ.get("VISUAL_DIRECTOR_WECHAT_ENV_FILE")
        return Path(configured).expanduser().resolve() if configured else self.root / ".env.local"

    @staticmethod
    def _configured_env_file(path: Path) -> bool:
        if not path.is_file():
            return False
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return bool(values.get("WECHAT_APP_ID") and values.get("WECHAT_APP_SECRET"))

    def _run_args(self, command: str, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if os.name == "nt" and Path(command).suffix.lower() in {".cmd", ".bat"}:
            command_line = subprocess.list2cmdline([command, *args])
            return self.runner([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line], **kwargs)
        return self.runner([command, *args], **kwargs)

    def quick_status(self) -> dict[str, Any]:
        """Return a non-blocking settings snapshot without spawning Wenyan."""
        command = self._command()
        inherited = bool(os.environ.get("WECHAT_APP_ID") and os.environ.get("WECHAT_APP_SECRET"))
        local_file = self._env_file()
        file_configured = self._configured_env_file(local_file)
        credential_source = "process_environment" if inherited else "local_env_file" if file_configured else "missing"
        return {
            "schema_version": "publisher_quick_status.v0.1",
            "provider": "wenyan",
            "installed": command is not None,
            "credentials_configured": credential_source != "missing",
            "credential_source": credential_source,
            "ready_for_connection_probe": bool(command and credential_source != "missing"),
        }

    def status(self) -> dict[str, Any]:
        command = self._command()
        version: str | None = None
        warnings: list[str] = []
        if command:
            try:
                completed = self._run_args(
                    command,
                    ["--version"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                    check=False,
                )
                version = (completed.stdout or completed.stderr).strip().splitlines()[-1]
            except (OSError, subprocess.SubprocessError):
                warnings.append("检测到 Wenyan，但无法读取版本。")
        else:
            warnings.append("尚未安装 Wenyan CLI。")

        inherited = bool(os.environ.get("WECHAT_APP_ID") and os.environ.get("WECHAT_APP_SECRET"))
        local_file = self._env_file()
        file_configured = self._configured_env_file(local_file)
        credential_source = "process_environment" if inherited else "local_env_file" if file_configured else "missing"
        if credential_source == "missing":
            warnings.append("尚未在本机配置微信公众号 AppID 与 AppSecret。")
        if version and _version_tuple(version) < _version_tuple(WENYAN_MINIMUM_VERSION):
            warnings.append(f"Wenyan 版本低于最低兼容版本 {WENYAN_MINIMUM_VERSION}。")
        elif version and _version_tuple(version) < _version_tuple(WENYAN_RECOMMENDED_VERSION):
            warnings.append(f"建议升级到已审计版本 {WENYAN_RECOMMENDED_VERSION}。")
        return {
            "schema_version": "publisher_status.v0.1",
            "provider": "wenyan",
            "installed": command is not None,
            "version": version,
            "minimum_version": WENYAN_MINIMUM_VERSION,
            "recommended_version": WENYAN_RECOMMENDED_VERSION,
            "credentials_configured": credential_source != "missing",
            "credential_source": credential_source,
            "ip_whitelist": "operator_confirmation_required",
            "ready": bool(command and credential_source != "missing" and _version_tuple(version) >= _version_tuple(WENYAN_MINIMUM_VERSION)),
            "warnings": warnings,
            "install_command": f"npm install -g @wenyan-md/cli@{WENYAN_RECOMMENDED_VERSION}",
        }

    def publish(self, files: dict[str, bytes]) -> WenyanPublishResult:
        status = self.status()
        if not status["ready"]:
            return WenyanPublishResult(
                status="failed",
                media_id=None,
                error={
                    "code": "wenyan_not_ready",
                    "message": "Wenyan 发布器尚未完成本机配置。",
                    "retryable": True,
                },
            )
        command = self._command()
        assert command is not None
        with tempfile.TemporaryDirectory(prefix="visual-director-wenyan-") as directory:
            root = Path(directory)
            for name, content in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            args = [
                "publish",
                "-f",
                str(root / "article.md"),
                "--custom-theme",
                str(root / "visual-director-theme.css"),
                "--no-mac-style",
                "--no-footnote",
            ]
            if status["credential_source"] == "local_env_file":
                args.extend(["--env-file", str(self._env_file())])
            try:
                completed = self._run_args(
                    command,
                    args,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                    check=False,
                    env=os.environ.copy(),
                )
            except subprocess.TimeoutExpired as error:
                timeout_stdout = _decode_process_output(error.stdout)
                timeout_stderr = _decode_process_output(error.stderr)
                timeout_media_id = _extract_media_id(
                    "\n".join(item for item in (timeout_stdout, timeout_stderr) if item)
                )
                if timeout_media_id:
                    return WenyanPublishResult(status="succeeded", media_id=timeout_media_id, error=None)
                return WenyanPublishResult(
                    status="unknown",
                    media_id=None,
                    error={
                        "code": "wenyan_timeout_unknown",
                        "message": "发布请求超时，结果未知。请先到公众号草稿箱核对，避免重复创建。",
                        "retryable": False,
                        "diagnostics": _wenyan_diagnostics(
                            stdout=timeout_stdout,
                            stderr=timeout_stderr,
                            return_code=None,
                            timeout_seconds=self.timeout_seconds,
                        ),
                    },
                )
            except OSError:
                return WenyanPublishResult(
                    status="failed",
                    media_id=None,
                    error={"code": "wenyan_launch_failed", "message": "无法启动 Wenyan CLI。", "retryable": True},
                )

        stdout = _decode_process_output(completed.stdout)
        stderr = _decode_process_output(completed.stderr)
        output = "\n".join(item for item in (stdout, stderr) if item)
        media_id = _extract_media_id(output)
        # A returned Media ID is the authoritative draft receipt. Some shells or
        # wrappers can still exit non-zero after the WeChat request has succeeded.
        if media_id:
            return WenyanPublishResult(status="succeeded", media_id=media_id, error=None)
        lowered = output.lower()
        known_errors = (
            (("invalid ip", "40164"), "wechat_ip_not_whitelisted", "当前公网出口 IP 未加入公众号白名单。"),
            (("invalid appid", "invalid appsecret", "40013", "40125"), "wechat_credentials_invalid", "微信公众号 AppID 或 AppSecret 无效。"),
            (("author size out of limit", "45110"), "wechat_author_too_long", "作者字段超过微信公众号限制，请缩短后重试。"),
            (("未能找到文章标题",), "wenyan_title_missing", "发布文件缺少文章标题。"),
        )
        for markers, code, message in known_errors:
            if any(marker in lowered for marker in markers):
                return WenyanPublishResult(status="failed", media_id=None, error={"code": code, "message": message, "retryable": True})
        return WenyanPublishResult(
            status="unknown",
            media_id=None,
            error={
                "code": "wenyan_result_unknown",
                "message": "Wenyan 未返回可确认的 Media ID。请先到公众号草稿箱核对，避免重复创建。",
                "retryable": False,
                "diagnostics": _wenyan_diagnostics(
                    stdout=stdout,
                    stderr=stderr,
                    return_code=completed.returncode,
                ),
            },
        )
