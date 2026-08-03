from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import time
import base64
import binascii
import urllib.error
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Protocol
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{6,}(?!\d)")
SENSITIVE_LABEL_RE = re.compile(
    r"(?:身份证|手机号|手机号码|电话号码|联系电话|学号|邮箱|电子邮箱|客户资料|内部经营|未公开数据)",
    re.IGNORECASE,
)
DEFAULT_IMAGES_API_ENDPOINT = "https://api.openai.com/v1/images/generations"
DEFAULT_IMAGES_API_MODEL = "gpt-image-2"
DEFAULT_IMAGES_API_PROTOCOL = "openai"
DEFAULT_GEMINI_IMAGE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"
DEFAULT_AGNES_ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"
DEFAULT_AGNES_MODEL = "agnes-image-2.1-flash"
IMAGE_PROVIDER_SETTINGS_SCHEMA_VERSION = "image_provider_settings.v0.2"
IMAGE_PROMPT_VERSION = "v5-seedream-safe-infographic"
ALLOWED_RATIOS = {"4:3", "16:9"}
# OpenAI and Gemini can return the generated image inline as Base64. A 4K
# image can make the JSON envelope much larger than a normal API response.
MAX_JSON_BYTES = 18 * 1024 * 1024
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
    sanitized = re.sub(r"扫码(?:了解|查看)?", "了解", sanitized)
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
        (r"位次|分数|数据|核对|官方|政策", "基于公开信息核验、比较并谨慎做出教育选择"),
        (r"冲|稳|保|梯度|排序|路径", "从冲刺到稳妥选择的清晰决策路径"),
        (r"步骤|提交|检查|清单|复核", "平静、可靠的分步核对流程"),
        (r"玩|兴趣|项目|动手|机器人|实践", "动手学习、兴趣探索与学生自主创作"),
        (r"AI|人工智能|科技|未来", "人工智能时代以人为本的学习与创造力"),
    ]
    for pattern, concept in routes:
        if re.search(pattern, normalized, re.IGNORECASE):
            return concept
    return {
        "data_policy": "基于已核验公开信息做出谨慎的教育决策",
        "tutorial_steps": "可靠、清楚的教育决策步骤",
        "lively_growth": "好奇心、动手学习与个人成长",
        "viewpoint_trend": "关于学习与未来选择的编辑视角",
    }.get(article_type, "关于学习与未来选择的编辑视角")


def _structured_layout(item_count: int) -> str:
    if item_count == 2:
        return "两条内容上下排列，形成一条清楚的纵向对照动线，不使用左右分栏"
    if item_count == 3:
        return "三条内容上下排列成纵向编辑序列，一行一个观点，禁止三列并排"
    return "四条内容使用两段纵向序列，每段两条上下排列，禁止四列并排"


def build_provider_prompt(
    image_slot: dict[str, Any],
    article_type: str = "viewpoint_trend",
    *,
    infographic_title: str | None = None,
    infographic_items: list[str] | None = None,
) -> str:
    intent = image_slot["visual_intent"]
    concept = _visual_concept(intent["subject"], article_type)
    style_labels = {
        "editorial_paper_cut": "精致的编辑纸雕拼贴风，具有杂志感、轻微纸张层次和克制的装饰细节",
        "soft_flat_illustration": "柔和扁平编辑插画风，图形简洁但不幼稚，边缘清晰",
        "clean_3d_geometry": "干净的轻量三维几何插画风，材质统一，空间层次清楚",
    }
    palette_labels = {
        "deep_navy": "深海军蓝",
        "muted_teal": "低饱和青绿",
        "warm_ivory": "暖象牙白",
        "coral_accent": "珊瑚橙点缀",
        "sunlit_yellow": "日光黄点缀",
        "soft_sky": "柔和天蓝",
    }
    fallback_palettes = {
        "data_policy": ["warm_ivory", "deep_navy", "muted_teal", "sunlit_yellow"],
        "tutorial_steps": ["warm_ivory", "muted_teal", "coral_accent", "sunlit_yellow"],
        "lively_growth": ["warm_ivory", "soft_sky", "coral_accent", "sunlit_yellow"],
        "viewpoint_trend": ["warm_ivory", "deep_navy", "soft_sky", "coral_accent"],
    }
    style = style_labels.get(
        str(intent.get("style_family") or ""),
        style_labels["editorial_paper_cut"],
    )
    palette_roles = intent.get("palette_roles") or fallback_palettes.get(
        article_type,
        fallback_palettes["viewpoint_trend"],
    )
    palette = "、".join(palette_labels.get(str(role), str(role)) for role in palette_roles)
    tone = "、".join(str(value) for value in intent.get("tone") or ["清晰", "可信", "克制"])
    composition_labels = {
        "branching": "用清楚的阅读动线连接各信息节点，节点之间有充分留白",
        "layered": "使用分层结构建立明确的主次关系",
        "wide_scene": "采用一个连贯横向场景，只有一个主要视觉焦点并保留呼吸感",
        "centered": "采用平衡的中心视觉隐喻，四周保持干净留白",
    }
    negative_space_labels = {
        "none": "整体留白均衡",
        "lower_right": "右下区域保持相对安静",
        "lower_third": "下方区域保持相对安静",
    }
    composition = composition_labels.get(str(intent.get("composition")), composition_labels["centered"])
    negative_space = negative_space_labels.get(
        str(intent.get("negative_space")),
        negative_space_labels["none"],
    )
    if image_slot["purpose"] == "structured_infographic":
        title = " ".join((infographic_title or "").replace("**", "").split())
        items = [
            " ".join(str(item).replace("**", "").split())
            for item in (infographic_items or [])
            if str(item).strip()
        ]
        if not title or not 2 <= len(items) <= 4:
            raise ImageProviderError(
                "infographic_copy_missing",
                "结构信息图缺少可锁定的原文标题或节点，已停止生成。",
                retryable=False,
                http_status=422,
            )
        locked_copy = "；".join(f'{index + 1}. “{item}”' for index, item in enumerate(items))
        layout = _structured_layout(len(items))
        prompt = " ".join(
            [
                "设计一张教育类微信公众号使用的横版4:3编辑信息图，像一页有呼吸感的现代教育杂志，不是PPT、后台界面或卡片模板。",
                "画布安全区是中央区域：左右各留12%，上下各留10%；所有标题、正文、编号和图标必须完整位于安全区内，不得贴边、越界或被裁切。",
                f"版式：标题左对齐置于顶部；{layout}；正文使用适合手机阅读的清晰中文字体。",
                f'只呈现以下锁定文字。标题：“{title}”。内容：{locked_copy}。',
                "锁定文字逐字呈现，不改写、不省略；不要添加系统字段名、副标题、说明或虚构数据。",
                f"视觉隐喻只作为小型边缘插画，不占用文字区：{sanitize_subject(str(intent.get('subject') or ''))}。",
                f"风格：{style}；气质：{tone}；配色：{palette}。背景以冷白或极浅灰为主，暖色只做局部点缀，不要大面积米黄或黄色底。",
                "用开放式分区、细线、手绘标记和少量图标建立阅读节奏；避免三列小卡片、重复圆角框、粗重阴影和大面积装饰。",
                "不得出现二维码、Logo、水印、条形码或官方印章。",
            ]
        )
        validate_provider_prompt(prompt)
        return prompt
    prompt = " ".join(
        [
            "为教育类微信公众号正文生成一张完整的横版语义插画，不是信息图、海报或界面模板。所有主体完整留在画面中央80%的安全区内，不贴边、不截断。",
            f"文章语义：{concept}。",
            f"具体视觉隐喻：{sanitize_subject(str(intent.get('subject') or ''))}。",
            f"构图：{composition}；{negative_space}。",
            f"美术方向：{style}。整体气质：{tone}。配色：{palette}；背景以冷白或极浅灰为主，暖色只作局部点缀。",
            "使用一个明确、具体的主要场景，不使用没有信息目的的装饰几何形状，画面有层次但不过度堆砌。",
            "画面中不要出现文字、字母、汉字、数字、表格、图表、文档、界面、Logo、水印、二维码、条形码、官方印章或招牌。",
        ]
    )
    validate_provider_prompt(prompt)
    return prompt


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


class ManualImageProvider:
    provider = "manual"
    model = "manual-upload"
    configured = False

    def generate(self, *, prompt: str, aspect_ratio: str, candidate_index: int) -> GeneratedImage:
        del prompt, aspect_ratio, candidate_index
        raise ImageProviderError(
            "manual_upload_required",
            "当前使用人工上传模式，请上传图片、沿用原图或跳过该图片槽。",
            retryable=False,
            http_status=422,
        )


class ImagesApiProvider:
    """Adapter for OpenAI Images API and closely related image endpoints.

    The product contract remains provider-neutral. ``protocol`` only controls
    the small payload differences required by the upstream service:

    - ``openai``: OpenAI Images API and strict compatible relays.
    - ``ark``: Volcengine Ark pay-as-you-go / Seedream image generation.
    - ``ark_plan``: Volcengine Agent Plan / Seedream dedicated route.
    - ``extended``: legacy relays that accept ``ratio`` and ``extra_body``.
    """

    provider = "images_api"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = DEFAULT_IMAGES_API_ENDPOINT,
        model: str = DEFAULT_IMAGES_API_MODEL,
        protocol: str = DEFAULT_IMAGES_API_PROTOCOL,
        size: str = "auto",
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
        self.protocol = protocol.strip().lower()
        self.size = size.strip()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self._urlopen = urlopen
        self._sleep = sleep
        self._resolve_host = resolve_host
        self.configured = bool(self.api_key)
        parsed_endpoint = urlparse(self.endpoint)
        if (
            parsed_endpoint.scheme != "https"
            or not parsed_endpoint.hostname
            or parsed_endpoint.username
            or parsed_endpoint.password
        ):
            raise ValueError("Images API endpoint 必须是有效的 HTTPS URL")
        endpoint_host = parsed_endpoint.hostname.lower()
        if endpoint_host == "localhost" or endpoint_host.endswith(".local"):
            raise ValueError("Images API endpoint 不允许指向本机或局域网主机")
        try:
            endpoint_ip = ipaddress.ip_address(endpoint_host)
        except ValueError:
            endpoint_ip = None
        if endpoint_ip and (
            endpoint_ip.is_private
            or endpoint_ip.is_loopback
            or endpoint_ip.is_link_local
            or endpoint_ip.is_reserved
            or endpoint_ip.is_multicast
        ):
            raise ValueError("Images API endpoint 不允许指向本机或内部网络地址")
        if self.protocol not in {"openai", "ark", "ark_plan", "extended"}:
            raise ValueError("Images API protocol 只允许 openai、ark、ark_plan 或 extended")
        if not self.model:
            raise ValueError("Images API model 不能为空")
        if not self.size:
            raise ValueError("Images API size 不能为空")
        if not 60 <= self.timeout_seconds <= 360:
            raise ValueError("Images API timeout 必须在 60–360 秒之间")
        if self.max_attempts != 2:
            raise ValueError("Images API 固定首次失败后最多自动重试 1 次")

    def _request_size(self, aspect_ratio: str) -> str:
        if self.size.lower() != "auto":
            return self.size
        if self.protocol == "openai":
            return "1536x1024"
        if self.protocol in {"ark", "ark_plan"}:
            return "2K"
        return "1K"

    def _payload(self, *, prompt: str, aspect_ratio: str) -> dict[str, Any]:
        if aspect_ratio not in ALLOWED_RATIOS:
            raise ImageProviderError(
                "unsupported_image_ratio",
                "当前真实生图只支持 4:3 和 16:9。",
                retryable=False,
                http_status=422,
            )
        base_payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "size": self._request_size(aspect_ratio),
        }
        if self.protocol == "openai":
            return {**base_payload, "n": 1}
        if self.protocol in {"ark", "ark_plan"}:
            return {
                **base_payload,
                "sequential_image_generation": "disabled",
                "response_format": "url",
            }
        return {
            **base_payload,
            "ratio": aspect_ratio,
            "extra_body": {"response_format": "url"},
        }

    @staticmethod
    def _http_error(status: int) -> ImageProviderError:
        if status in {401, 403}:
            return ImageProviderError(
                "image_api_auth_failed",
                "图片服务凭据无效或当前账号没有模型权限，请检查本机 Key。",
                retryable=False,
                http_status=503,
                details={"upstream_status": status},
            )
        if status == 402:
            return ImageProviderError(
                "image_api_quota_exhausted",
                "图片服务当前额度不足，仍可跳过图片或上传替换。",
                retryable=False,
                http_status=503,
                details={"upstream_status": status},
            )
        if status == 429:
            return ImageProviderError(
                "image_api_rate_limited",
                "图片服务请求过于频繁，自动重试仍未成功，请稍后再试。",
                retryable=True,
                http_status=503,
                details={"upstream_status": status},
            )
        if status in {408, 504}:
            return ImageProviderError(
                "image_api_timeout",
                "图片服务生成超时，自动重试仍未成功，可稍后重试或跳过。",
                retryable=True,
                http_status=504,
                details={"upstream_status": status},
            )
        if status >= 500:
            return ImageProviderError(
                "image_api_unavailable",
                "图片服务暂时不可用，自动重试仍未成功。",
                retryable=True,
                http_status=503,
                details={"upstream_status": status},
            )
        return ImageProviderError(
            "image_api_request_rejected",
            "图片服务拒绝了本次请求，请检查接口协议、模型和尺寸配置。",
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
                            "image_api_response_too_large",
                            "图片服务返回内容超过安全大小限制。",
                            retryable=False,
                            http_status=502,
                        )
                    return content, response.headers.get("Content-Type", "")
            except urllib.error.HTTPError as error:
                last_error = self._http_error(error.code)
            except (urllib.error.URLError, TimeoutError, socket.timeout):
                last_error = ImageProviderError(
                    "image_api_network_error",
                    "图片服务网络连接失败，自动重试仍未成功。",
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
                "image_api_url_invalid",
                "图片服务返回的图片地址不符合 HTTPS 安全要求。",
                retryable=False,
                http_status=502,
            )
        try:
            addresses = self._resolve_host(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        except OSError as error:
            raise ImageProviderError(
                "image_api_host_unresolved",
                "图片服务返回的图片地址暂时无法解析。",
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
            # when a provider returned a hostname, never an IP literal. RFC1918,
            # loopback, link-local and all other non-public ranges stay blocked.
            if ip in proxy_fake_ip_network and not hostname_is_ip_literal:
                continue
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ImageProviderError(
                    "image_api_url_blocked",
                    "图片服务返回了不允许访问的内部图片地址。",
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
                "image_api_invalid_image",
                "图片服务返回成功，但内容不是有效图片。",
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
                "image_api_unsupported_image",
                "图片服务返回了当前不支持的图片格式。",
                retryable=False,
                http_status=502,
            )
        expected = 4 / 3 if expected_ratio == "4:3" else 16 / 9
        ratio_valid = abs(width / height - expected) / expected <= 0.08
        content_type, extension = format_map[image_format]
        return content_type, extension, width, height, ratio_valid

    @staticmethod
    def _crop_to_ratio(content: bytes, expected_ratio: str) -> bytes:
        target_ratio = 4 / 3 if expected_ratio == "4:3" else 16 / 9
        with Image.open(BytesIO(content)) as source:
            width, height = source.size
            if width / height > target_ratio:
                target_size = (round(height * target_ratio), height)
            else:
                target_size = (width, round(width / target_ratio))
            fitted = ImageOps.fit(source.convert("RGB"), target_size, method=Image.Resampling.LANCZOS)
            buffer = BytesIO()
            fitted.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()

    def generate(self, *, prompt: str, aspect_ratio: str, candidate_index: int) -> GeneratedImage:
        del candidate_index
        if not self.configured:
            raise ImageProviderError(
                "image_api_not_configured",
                "本机尚未配置当前 Images API 的 Key，请先在本地设置页填写。",
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
                "image_api_invalid_response",
                "图片服务返回了无法解析的响应。",
                retryable=False,
                http_status=502,
            ) from error
        items = response_payload.get("data") if isinstance(response_payload, dict) else None
        first_item = items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else None
        image_url = first_item.get("url") if first_item else None
        encoded_image = first_item.get("b64_json") if first_item else None
        if isinstance(encoded_image, str):
            try:
                content = base64.b64decode(encoded_image, validate=True)
            except (ValueError, binascii.Error) as error:
                raise ImageProviderError(
                    "image_api_invalid_base64",
                    "图片服务返回了无法解析的 Base64 图片。",
                    retryable=False,
                    http_status=502,
                ) from error
        elif isinstance(image_url, str):
            self._validate_image_url(image_url)
            download_request = urllib.request.Request(
                image_url,
                headers={"Accept": "image/png,image/jpeg,image/webp"},
                method="GET",
            )
            content, _ = self._read_with_retry(download_request, max_bytes=MAX_IMAGE_BYTES)
        else:
            raise ImageProviderError(
                "image_api_missing_image",
                "图片服务返回成功，但没有提供 URL 或 Base64 图片。",
                retryable=False,
                http_status=502,
            )
        content_type, _, width, height, ratio_valid = self._inspect_image(content, aspect_ratio)
        if not ratio_valid:
            content = self._crop_to_ratio(content, aspect_ratio)
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


class GeminiImageProvider(ImagesApiProvider):
    """Native Gemini Interactions adapter for Nano Banana image models."""

    provider = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = DEFAULT_GEMINI_IMAGE_ENDPOINT,
        model: str = DEFAULT_GEMINI_IMAGE_MODEL,
        size: str = "1K",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            api_key=api_key,
            endpoint=endpoint,
            model=model,
            protocol="openai",
            size=size,
            **kwargs,
        )
        if self.size not in {"0.5K", "1K", "2K", "4K"}:
            raise ValueError("Gemini image size 只允许 0.5K、1K、2K 或 4K")

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
            "input": [{"type": "text", "text": prompt}],
            "response_format": {
                "type": "image",
                "mime_type": "image/png",
                "aspect_ratio": aspect_ratio,
                "image_size": self.size,
            },
        }

    def generate(self, *, prompt: str, aspect_ratio: str, candidate_index: int) -> GeneratedImage:
        del candidate_index
        if not self.configured:
            raise ImageProviderError(
                "gemini_not_configured",
                "本机尚未配置 Gemini API Key，请先在本地设置页填写。",
                retryable=False,
                http_status=503,
            )
        validate_provider_prompt(prompt)
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(self._payload(prompt=prompt, aspect_ratio=aspect_ratio), ensure_ascii=False).encode("utf-8"),
            headers={
                "X-Goog-Api-Key": self.api_key,
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
                "gemini_invalid_response",
                "Gemini 返回了无法解析的响应。",
                retryable=False,
                http_status=502,
            ) from error

        output_image = response_payload.get("output_image") if isinstance(response_payload, dict) else None
        encoded_image = output_image.get("data") if isinstance(output_image, dict) else None
        if not isinstance(encoded_image, str):
            outputs = response_payload.get("outputs") if isinstance(response_payload, dict) else None
            for item in outputs if isinstance(outputs, list) else []:
                candidate = item.get("data") if isinstance(item, dict) else None
                if isinstance(candidate, str):
                    encoded_image = candidate
                    break
        if not isinstance(encoded_image, str):
            raise ImageProviderError(
                "gemini_missing_image",
                "Gemini 返回成功，但响应中没有图片数据。",
                retryable=False,
                http_status=502,
            )
        try:
            content = base64.b64decode(encoded_image, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ImageProviderError(
                "gemini_invalid_base64",
                "Gemini 返回了无法解析的 Base64 图片。",
                retryable=False,
                http_status=502,
            ) from error
        content_type, _, width, height, ratio_valid = self._inspect_image(content, aspect_ratio)
        if not ratio_valid:
            content = self._crop_to_ratio(content, aspect_ratio)
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


# Backwards-compatible import for older integrations and persisted tests.
AgnesImageProvider = ImagesApiProvider


def create_image_provider_from_env(environ: dict[str, str] | None = None) -> ImageProvider:
    values = environ if environ is not None else os.environ
    mode = values.get("VISUAL_DIRECTOR_IMAGE_PROVIDER", "mock").strip().lower()
    if mode == "manual":
        return ManualImageProvider()
    if mode == "mock":
        return MockImageProvider()
    legacy_agnes = mode == "agnes"
    if mode not in {"images_api", "gemini", "agnes"}:
        raise ValueError("VISUAL_DIRECTOR_IMAGE_PROVIDER 只允许 manual、mock、images_api 或 gemini")
    try:
        timeout_seconds = int(
            values.get("IMAGE_API_TIMEOUT_SECONDS")
            or values.get("AGNES_IMAGE_TIMEOUT_SECONDS")
            or "180"
        )
        retry_delay_seconds = float(
            values.get("IMAGE_API_RETRY_DELAY_SECONDS")
            or values.get("AGNES_IMAGE_RETRY_DELAY_SECONDS")
            or "1"
        )
    except ValueError as error:
        raise ValueError("图片服务 timeout 和 retry delay 必须是数字") from error
    if mode == "gemini":
        return GeminiImageProvider(
            api_key=values.get("GEMINI_API_KEY", ""),
            endpoint=values.get("GEMINI_IMAGE_ENDPOINT", DEFAULT_GEMINI_IMAGE_ENDPOINT),
            model=values.get("GEMINI_IMAGE_MODEL", DEFAULT_GEMINI_IMAGE_MODEL),
            size=values.get("GEMINI_IMAGE_SIZE", "1K"),
            timeout_seconds=timeout_seconds,
            retry_delay_seconds=retry_delay_seconds,
        )
    image_api_key = (
        values.get("IMAGE_API_KEY", "")
        if "IMAGE_API_KEY" in values
        else values.get("AGNES_API_KEY", "")
    )
    return ImagesApiProvider(
        api_key=image_api_key,
        endpoint=(
            values.get("IMAGE_API_ENDPOINT")
            or values.get("AGNES_IMAGE_ENDPOINT")
            or (DEFAULT_AGNES_ENDPOINT if legacy_agnes else DEFAULT_IMAGES_API_ENDPOINT)
        ),
        model=(
            values.get("IMAGE_API_MODEL")
            or values.get("AGNES_IMAGE_MODEL")
            or (DEFAULT_AGNES_MODEL if legacy_agnes else DEFAULT_IMAGES_API_MODEL)
        ),
        protocol=(
            values.get("IMAGE_API_PROTOCOL")
            or ("extended" if legacy_agnes else DEFAULT_IMAGES_API_PROTOCOL)
        ),
        size=(
            values.get("IMAGE_API_SIZE")
            or values.get("AGNES_IMAGE_SIZE")
            or ("1K" if legacy_agnes else "auto")
        ),
        timeout_seconds=timeout_seconds,
        retry_delay_seconds=retry_delay_seconds,
    )
