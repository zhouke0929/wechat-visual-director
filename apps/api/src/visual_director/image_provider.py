from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Protocol
from urllib.parse import urlparse

from PIL import Image, ImageDraw, UnidentifiedImageError


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{6,}(?!\d)")
SENSITIVE_LABEL_RE = re.compile(
    r"(?:身份证|手机号|手机号码|电话号码|学号|邮箱|电子邮箱|客户资料|内部经营|未公开数据)",
    re.IGNORECASE,
)
DEFAULT_AGNES_ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"
DEFAULT_AGNES_MODEL = "agnes-image-2.1-flash"
IMAGE_PROMPT_VERSION = "v3-article-routed-no-text"
ALLOWED_RATIOS = {"4:3", "16:9"}
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class GeneratedImage:
    provider: str
    model: str
    prompt: str
    content: bytes
    content_type: str
    width: int
    height: int
    latency_ms: int
    machine_checks: dict[str, Any]


class ImageProvider(Protocol):
    provider: str
    model: str
    configured: bool

    def generate(self, *, prompt: str, aspect_ratio: str, candidate_index: int) -> GeneratedImage: ...


class ImageProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        public_message: str,
        *,
        retryable: bool,
        http_status: int = 503,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.retryable = retryable
        self.http_status = http_status
        self.details = details or {}


def sanitize_subject(value: str) -> str:
    sanitized = EMAIL_RE.sub("[redacted]", value)
    sanitized = PHONE_RE.sub("[redacted]", sanitized)
    sanitized = LONG_NUMBER_RE.sub("[redacted]", sanitized)
    sanitized = SENSITIVE_LABEL_RE.sub("[redacted]", sanitized)
    return sanitized.strip()[:120]


def validate_provider_prompt(prompt: str) -> None:
    if not prompt.strip() or len(prompt) > 1000:
        raise ImageProviderError(
            "provider_prompt_invalid",
            "图片提示词为空或超过安全长度，已停止外发。",
            retryable=False,
            http_status=422,
        )
    if EMAIL_RE.search(prompt) or PHONE_RE.search(prompt) or LONG_NUMBER_RE.search(prompt) or SENSITIVE_LABEL_RE.search(prompt):
        raise ImageProviderError(
            "provider_prompt_sensitive",
            "图片提示词可能包含敏感信息，已改为人工处理。",
            retryable=False,
            http_status=422,
        )


def _visual_concept(subject: str, article_type: str) -> str:
    normalized = sanitize_subject(subject)
    routes = [
        (r"位次|分数|数据|核对|官方|政策", "careful comparison, verification, and evidence-based educational choices"),
        (r"冲|稳|保|梯度|排序|路径", "a clear three-tier decision path from ambitious to secure choices"),
        (r"步骤|提交|检查|清单|复核", "a calm step-by-step review and confirmation process"),
        (r"玩|兴趣|项目|动手|机器人|实践", "hands-on learning, playful exploration, and student-made projects"),
        (r"AI|人工智能|科技|未来", "human-centered learning and creativity in an AI-enabled future"),
    ]
    for pattern, concept in routes:
        if re.search(pattern, normalized, re.IGNORECASE):
            return concept
    return {
        "data_policy": "careful educational decision-making based on verified public information",
        "tutorial_steps": "a reliable step-by-step educational decision workflow",
        "lively_growth": "curiosity, hands-on learning, and personal growth",
        "viewpoint_trend": "a thoughtful editorial perspective on learning and future choices",
    }.get(article_type, "a thoughtful editorial perspective on learning and future choices")


def build_provider_prompt(image_slot: dict[str, Any], article_type: str = "viewpoint_trend") -> str:
    intent = image_slot["visual_intent"]
    concept = _visual_concept(intent["subject"], article_type)
    article_styles = {
        "data_policy": (
            "restrained premium editorial illustration with precise geometric rhythm",
            "warm ivory, deep navy, muted teal, and a restrained amber accent",
        ),
        "tutorial_steps": (
            "clear modern editorial illustration with orderly cards and tactile paper depth",
            "warm ivory, forest green, clay orange, and muted gold",
        ),
        "lively_growth": (
            "playful but polished educational editorial illustration with tactile crafted forms",
            "warm ivory, fresh teal, coral, and optimistic yellow",
        ),
        "viewpoint_trend": (
            "thoughtful magazine-style editorial illustration with spacious composition",
            "warm ivory, ink blue, muted cyan, and a small coral accent",
        ),
    }
    style, palette = article_styles.get(article_type, article_styles["viewpoint_trend"])
    composition_labels = {
        "branching": "a clear branching relationship with calm separation between nodes",
        "layered": "layered forms with an obvious visual hierarchy",
        "wide_scene": "one coherent wide scene with a single visual focus and generous margins",
        "centered": "one balanced central metaphor with uncluttered margins",
    }
    negative_space_labels = {
        "none": "balanced negative space",
        "lower_right": "an uninterrupted warm-white lower-right area",
        "lower_third": "an uninterrupted warm-white lower third",
    }
    prohibited = (
        "STRICT IMAGE-ONLY RULE: no text, no letters, no Chinese characters, no numbers, "
        "no tables, no charts, no document, no poster, no interface, no logo, no watermark, "
        "no QR code, no barcode, and no signage. Do not imitate any promotional material."
    )
    if image_slot["purpose"] == "structured_infographic":
        node_count = len(image_slot["fact_bindings"]["item_refs"])
        task = (
            f"Create a low-detail background plate for a later deterministic {node_count}-node text overlay. "
            f"Show exactly {node_count} large empty rounded content zones connected by a simple visual path. "
            "Keep every zone interior plain, bright, and fully empty; reserve at least 60 percent of the image for overlay."
        )
    else:
        task = (
            "Create one full-bleed editorial illustration, not an infographic or layout template. "
            "Use a concrete visual metaphor instead of generic decorative shapes; keep one dominant scene and avoid clutter."
        )
    return " ".join(
        [
            task,
            f"Editorial context: {concept}.",
            f"Composition: {composition_labels[intent['composition']]}; {negative_space_labels[intent['negative_space']] }.",
            f"Art direction: {style}. Palette: {palette}.",
            prohibited,
        ]
    )


def build_cover_prompt(cover_brief: dict[str, Any]) -> str:
    """Build a provider-safe, image-only prompt from the full-article editorial brief."""
    article_type = str(cover_brief.get("article_type") or "viewpoint_trend")
    subject = sanitize_subject(
        " ".join(
            value
            for value in (
                str(cover_brief.get("title") or ""),
                str(cover_brief.get("narrative") or ""),
                str(cover_brief.get("reader_task") or ""),
            )
            if value
        )
    )
    concept = _visual_concept(subject, article_type)
    style, palette = {
        "data_policy": (
            "precise editorial paper-cut illustration with a clear evidence motif",
            "warm ivory, deep navy, muted teal, and one amber accent",
        ),
        "tutorial_steps": (
            "orderly tactile editorial illustration with a clear path and calm depth",
            "warm ivory, forest green, clay orange, and muted gold",
        ),
        "lively_growth": (
            "warm human-centered educational illustration with crafted playful forms",
            "warm ivory, fresh teal, coral, and optimistic yellow",
        ),
        "viewpoint_trend": (
            "thoughtful magazine cover illustration with one strong visual metaphor",
            "warm ivory, ink blue, muted cyan, and a small coral accent",
        ),
    }.get(article_type, (
        "thoughtful magazine cover illustration with one strong visual metaphor",
        "warm ivory, ink blue, muted cyan, and a small coral accent",
    ))
    return " ".join(
        [
            "Create a premium editorial cover background for an education-focused WeChat article.",
            f"Editorial concept: {concept}.",
            f"Art direction: {style}. Palette: {palette}.",
            "Use one dominant scene, strong silhouette, restrained detail, and generous breathing room.",
            "Keep the upper-left and central area visually calm as a safe title zone; important subjects stay inside the middle 70 percent.",
            "STRICT IMAGE-ONLY RULE: no text, no letters, no Chinese characters, no numbers, no tables, no charts, no document, no interface, no logo, no watermark, no QR code, no barcode, no official seal, and no signage.",
        ]
    )


class MockImageProvider:
    provider = "mock"
    model = "deterministic-shapes-v1"
    configured = True

    def generate(self, *, prompt: str, aspect_ratio: str, candidate_index: int) -> GeneratedImage:
        started = time.perf_counter()
        width, height = (1152, 864) if aspect_ratio == "4:3" else (1312, 736)
        digest = hashlib.sha256(f"{prompt}:{candidate_index}".encode("utf-8")).digest()
        palettes = [
            ("#FFFCF4", "#0D988E", "#F16E59", "#F2C84B"),
            ("#FFFDF8", "#315E68", "#E8886D", "#EEC55B"),
            ("#F9FCF8", "#12837A", "#E76F51", "#72B7D6"),
        ]
        background, primary, accent, secondary = palettes[(candidate_index - 1) % len(palettes)]
        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)
        margin = int(width * 0.08)
        center_x, center_y = int(width * 0.46), int(height * 0.5)
        path_width = max(18, width // 42)
        offsets = (-int(height * 0.28), 0, int(height * 0.28))
        colors = (primary, accent, secondary)
        for index, (offset, color) in enumerate(zip(offsets, colors, strict=True)):
            wobble = digest[index] % max(20, height // 12)
            end_y = max(margin, min(height - margin, center_y + offset + wobble - 20))
            points = [
                (margin, center_y),
                (center_x - width // 6, center_y),
                (center_x, center_y),
                (center_x + width // 7, end_y),
                (width - margin, end_y),
            ]
            draw.line(points, fill=color, width=path_width, joint="curve")
            radius = 38 + digest[index + 4] % 34
            draw.ellipse(
                (width - margin - radius, end_y - radius, width - margin + radius, end_y + radius),
                fill=color,
            )
        hub_radius = max(54, width // 17)
        draw.ellipse(
            (center_x - hub_radius, center_y - hub_radius, center_x + hub_radius, center_y + hub_radius),
            fill="#FFF7DB",
            outline=primary,
            width=max(6, width // 150),
        )
        for index in range(7):
            x = margin + digest[8 + index] * (width - 2 * margin) // 255
            y = margin + digest[16 + index] * (height - 2 * margin) // 255
            radius = 8 + digest[24 + index] % 14
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=colors[index % 3])
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        content = buffer.getvalue()
        latency_ms = max(1, round((time.perf_counter() - started) * 1000))
        return GeneratedImage(
            provider=self.provider,
            model=self.model,
            prompt=prompt,
            content=content,
            content_type="image/png",
            width=width,
            height=height,
            latency_ms=latency_ms,
            machine_checks={
                "file_valid": True,
                "ratio_valid": True,
                "qr_risk": "unknown",
                "text_risk": "unknown",
                "logo_risk": "unknown",
                "person_risk": "unknown",
            },
        )


class AgnesImageProvider:
    provider = "agnes"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = DEFAULT_AGNES_ENDPOINT,
        model: str = DEFAULT_AGNES_MODEL,
        size: str = "1K",
        timeout_seconds: int = 180,
        max_attempts: int = 2,
        retry_delay_seconds: float = 1.0,
        urlopen: Any = urllib.request.urlopen,
        sleep: Any = time.sleep,
        resolve_host: Any = socket.getaddrinfo,
    ) -> None:
        self.api_key = api_key.strip()
        self.endpoint = endpoint.strip()
        self.model = model.strip()
        self.size = size.strip()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self._urlopen = urlopen
        self._sleep = sleep
        self._resolve_host = resolve_host
        self.configured = bool(self.api_key)
        parsed_endpoint = urlparse(self.endpoint)
        if parsed_endpoint.scheme != "https" or not parsed_endpoint.hostname:
            raise ValueError("Agnes endpoint 必须是有效的 HTTPS URL")
        if self.size != "1K":
            raise ValueError("V0.5 真实 Provider 固定使用 1K")
        if not 60 <= self.timeout_seconds <= 360:
            raise ValueError("Agnes timeout 必须在 60–360 秒之间")
        if self.max_attempts != 2:
            raise ValueError("V0.5 固定首次失败后最多自动重试 1 次")

    def _payload(self, *, prompt: str, aspect_ratio: str) -> dict[str, Any]:
        if aspect_ratio not in ALLOWED_RATIOS:
            raise ImageProviderError(
                "unsupported_image_ratio",
                "当前真实生图只支持 4:3 和 16:9。",
                retryable=False,
                http_status=422,
            )
        return {
            "model": self.model,
            "prompt": prompt,
            "size": self.size,
            "ratio": aspect_ratio,
            "extra_body": {"response_format": "url"},
        }

    @staticmethod
    def _http_error(status: int) -> ImageProviderError:
        if status in {401, 403}:
            return ImageProviderError(
                "agnes_auth_failed",
                "Agnes 凭据无效或当前账号没有模型权限，请检查本机 Key。",
                retryable=False,
                http_status=503,
                details={"upstream_status": status},
            )
        if status == 402:
            return ImageProviderError(
                "agnes_quota_exhausted",
                "Agnes 当前额度不足，仍可跳过图片或上传替换。",
                retryable=False,
                http_status=503,
                details={"upstream_status": status},
            )
        if status == 429:
            return ImageProviderError(
                "agnes_rate_limited",
                "Agnes 请求过于频繁，自动重试仍未成功，请稍后再试。",
                retryable=True,
                http_status=503,
                details={"upstream_status": status},
            )
        if status in {408, 504}:
            return ImageProviderError(
                "agnes_timeout",
                "Agnes 生成超时，自动重试仍未成功，可稍后重试或跳过。",
                retryable=True,
                http_status=504,
                details={"upstream_status": status},
            )
        if status >= 500:
            return ImageProviderError(
                "agnes_unavailable",
                "Agnes 服务暂时不可用，自动重试仍未成功。",
                retryable=True,
                http_status=503,
                details={"upstream_status": status},
            )
        return ImageProviderError(
            "agnes_request_rejected",
            "Agnes 拒绝了本次图片请求，请检查模型配置或改为人工上传。",
            retryable=False,
            http_status=502,
            details={"upstream_status": status},
        )

    def _read_with_retry(self, request: urllib.request.Request, *, max_bytes: int) -> tuple[bytes, str]:
        last_error: ImageProviderError | None = None
        for attempt in range(self.max_attempts):
            try:
                with self._urlopen(request, timeout=self.timeout_seconds) as response:
                    content = response.read(max_bytes + 1)
                    if len(content) > max_bytes:
                        raise ImageProviderError(
                            "agnes_response_too_large",
                            "Agnes 返回内容超过安全大小限制。",
                            retryable=False,
                            http_status=502,
                        )
                    return content, response.headers.get("Content-Type", "")
            except urllib.error.HTTPError as error:
                last_error = self._http_error(error.code)
            except (urllib.error.URLError, TimeoutError, socket.timeout):
                last_error = ImageProviderError(
                    "agnes_network_error",
                    "Agnes 网络连接失败，自动重试仍未成功。",
                    retryable=True,
                    http_status=503,
                )
            if not last_error.retryable or attempt + 1 >= self.max_attempts:
                raise last_error
            self._sleep(self.retry_delay_seconds)
        raise last_error or RuntimeError("unreachable")

    def _validate_image_url(self, image_url: str) -> None:
        parsed = urlparse(image_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ImageProviderError(
                "agnes_image_url_invalid",
                "Agnes 返回的图片地址不符合 HTTPS 安全要求。",
                retryable=False,
                http_status=502,
            )
        try:
            addresses = self._resolve_host(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        except OSError as error:
            raise ImageProviderError(
                "agnes_image_host_unresolved",
                "Agnes 图片地址暂时无法解析。",
                retryable=True,
                http_status=502,
            ) from error
        try:
            ipaddress.ip_address(parsed.hostname)
            hostname_is_ip_literal = True
        except ValueError:
            hostname_is_ip_literal = False
        proxy_fake_ip_network = ipaddress.ip_network("198.18.0.0/15")
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            # Some desktop proxy/TUN clients map public hostnames to RFC 2544
            # benchmarking addresses. Permit only that exact range and only
            # when Agnes returned a hostname, never an IP literal. RFC1918,
            # loopback, link-local and all other non-public ranges stay blocked.
            if ip in proxy_fake_ip_network and not hostname_is_ip_literal:
                continue
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ImageProviderError(
                    "agnes_image_url_blocked",
                    "Agnes 返回了不允许访问的内部图片地址。",
                    retryable=False,
                    http_status=502,
                )

    @staticmethod
    def _inspect_image(content: bytes, expected_ratio: str) -> tuple[str, str, int, int, bool]:
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                image_format = (image.format or "").upper()
        except (UnidentifiedImageError, OSError) as error:
            raise ImageProviderError(
                "agnes_invalid_image",
                "Agnes 返回成功，但下载内容不是有效图片。",
                retryable=False,
                http_status=502,
            ) from error
        format_map = {
            "PNG": ("image/png", ".png"),
            "JPEG": ("image/jpeg", ".jpg"),
            "WEBP": ("image/webp", ".webp"),
        }
        if image_format not in format_map:
            raise ImageProviderError(
                "agnes_unsupported_image",
                "Agnes 返回了当前不支持的图片格式。",
                retryable=False,
                http_status=502,
            )
        expected = 4 / 3 if expected_ratio == "4:3" else 16 / 9
        ratio_valid = abs(width / height - expected) / expected <= 0.08
        content_type, extension = format_map[image_format]
        return content_type, extension, width, height, ratio_valid

    def generate(self, *, prompt: str, aspect_ratio: str, candidate_index: int) -> GeneratedImage:
        del candidate_index
        if not self.configured:
            raise ImageProviderError(
                "agnes_not_configured",
                "本机尚未配置 Agnes API Key，请先运行安全启动脚本。",
                retryable=False,
                http_status=503,
            )
        validate_provider_prompt(prompt)
        payload = self._payload(prompt=prompt, aspect_ratio=aspect_ratio)
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        response_bytes, _ = self._read_with_retry(request, max_bytes=MAX_JSON_BYTES)
        try:
            response_payload = json.loads(response_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ImageProviderError(
                "agnes_invalid_response",
                "Agnes 返回了无法解析的响应。",
                retryable=False,
                http_status=502,
            ) from error
        items = response_payload.get("data") if isinstance(response_payload, dict) else None
        image_url = items[0].get("url") if isinstance(items, list) and items and isinstance(items[0], dict) else None
        if not isinstance(image_url, str):
            raise ImageProviderError(
                "agnes_missing_image_url",
                "Agnes 返回成功，但没有提供可下载的图片。",
                retryable=False,
                http_status=502,
            )
        self._validate_image_url(image_url)
        download_request = urllib.request.Request(
            image_url,
            headers={"Accept": "image/png,image/jpeg,image/webp"},
            method="GET",
        )
        content, _ = self._read_with_retry(download_request, max_bytes=MAX_IMAGE_BYTES)
        content_type, _, width, height, ratio_valid = self._inspect_image(content, aspect_ratio)
        latency_ms = max(1, round((time.perf_counter() - started) * 1000))
        return GeneratedImage(
            provider=self.provider,
            model=self.model,
            prompt=prompt,
            content=content,
            content_type=content_type,
            width=width,
            height=height,
            latency_ms=latency_ms,
            machine_checks={
                "file_valid": True,
                "ratio_valid": ratio_valid,
                "qr_risk": "unknown",
                "text_risk": "unknown",
                "logo_risk": "unknown",
                "person_risk": "unknown",
            },
        )


def create_image_provider_from_env(environ: dict[str, str] | None = None) -> ImageProvider:
    values = environ if environ is not None else os.environ
    mode = values.get("VISUAL_DIRECTOR_IMAGE_PROVIDER", "mock").strip().lower()
    if mode == "mock":
        return MockImageProvider()
    if mode != "agnes":
        raise ValueError("VISUAL_DIRECTOR_IMAGE_PROVIDER 只允许 mock 或 agnes")
    try:
        timeout_seconds = int(values.get("AGNES_IMAGE_TIMEOUT_SECONDS", "180"))
        retry_delay_seconds = float(values.get("AGNES_IMAGE_RETRY_DELAY_SECONDS", "1"))
    except ValueError as error:
        raise ValueError("Agnes timeout 和 retry delay 必须是数字") from error
    return AgnesImageProvider(
        api_key=values.get("AGNES_API_KEY", ""),
        endpoint=values.get("AGNES_IMAGE_ENDPOINT", DEFAULT_AGNES_ENDPOINT),
        model=values.get("AGNES_IMAGE_MODEL", DEFAULT_AGNES_MODEL),
        size=values.get("AGNES_IMAGE_SIZE", "1K"),
        timeout_seconds=timeout_seconds,
        retry_delay_seconds=retry_delay_seconds,
    )
