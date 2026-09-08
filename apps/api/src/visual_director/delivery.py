from __future__ import annotations

import html as html_module
import base64
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from typing import Any, Callable

import yaml
from PIL import Image
from .theme_delivery import legacy_drawing_present


ROOT_MAIN_PATTERN = re.compile(r'(<main\b[^>]*\bstyle=")([^"]*)(")', flags=re.IGNORECASE)

# Product-side memory guards, not claimed WeChat platform limits.
CLIPBOARD_IMAGE_MAX_BYTES = 8 * 1024 * 1024
CLIPBOARD_HTML_MAX_BYTES = 24 * 1024 * 1024
CLIPBOARD_MAX_IMAGES = 100
CLIPBOARD_TINY_DECORATION_BYTES = 1024


def _clipboard_static_label_geometry(document: str) -> str:
    """Fixed-width rotated labels can cross the article edge without reserving space.

    Clipboard delivery keeps their borders/type but omits the cosmetic tilt.
    Frozen files and the API publisher retain the original source geometry.
    """
    def normalize(match: re.Match[str]) -> str:
        tag = match.group(0)
        if 'data-theme-static="true"' not in tag:
            return tag
        style = re.search(r'\bstyle="([^"]*)"', tag)
        if not style or not re.search(r'(?:^|;)\s*width:\s*[\d.]+px\s*(?:;|$)', style.group(1)):
            return tag
        css = re.sub(r'(?:^|;)\s*transform:\s*rotate\([-\d.]+deg\)\s*;?', ';', style.group(1))
        return tag[:style.start(1)] + css + tag[style.end(1):]
    return re.sub(r'<p\b[^>]*>', normalize, document, flags=re.IGNORECASE)


class ClipboardPreparationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class _ImageSources(HTMLParser):
    def __init__(self, document: str):
        super().__init__()
        self.sources: list[str] = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.sources.append(dict(attrs).get("src") or "")


def _embedded_clipboard_sources(body, assets, read_asset):
    """Read only referenced frozen assets. No URL fetching or image recompression."""
    sources = _ImageSources(body).sources
    if len(sources) > CLIPBOARD_MAX_IMAGES:
        raise ClipboardPreparationError("clipboard_too_large", "图片数量超过复制上限（100 处）；请减少图片，或选择下方的备用交付方式。")
    by_source = {f'asset://{asset["asset_token"]}': asset for asset in assets}
    urls: dict[str, str] = {}
    projected_bytes = len(body.encode("utf-8"))
    for source in dict.fromkeys(sources):
        asset = by_source.get(source)
        if asset is None:
            raise ClipboardPreparationError("clipboard_image_unresolved", "正文存在未冻结的图片引用，未复制；请返回工作台检查图片并重新确认最终版本。")
        try:
            path, _ = read_asset(asset["id"])
            if path.stat().st_size > CLIPBOARD_IMAGE_MAX_BYTES:
                raise ClipboardPreparationError("clipboard_too_large", "单张图片超过复制大小上限（8 MiB）；请缩小图片后重试，或选择下方的备用交付方式。")
            with path.open("rb") as stream:
                data = stream.read(CLIPBOARD_IMAGE_MAX_BYTES + 1)
        except ClipboardPreparationError:
            raise
        except (OSError, KeyError, ValueError) as exc:
            raise ClipboardPreparationError("clipboard_image_unavailable", "正文图片文件无法读取，未复制；请检查本地文件或返回工作台重新确认图片。") from exc
        if len(data) > CLIPBOARD_IMAGE_MAX_BYTES:
            raise ClipboardPreparationError("clipboard_too_large", "图片超过复制大小上限，未复制；请缩小图片后重试，或选择下方的备用交付方式。")
        if hashlib.sha256(data).hexdigest() != asset.get("output_sha256"):
            raise ClipboardPreparationError("clipboard_image_changed", "正文图片与冻结版本不一致，未复制；请返回工作台重新确认最终版本。")
        try:
            with Image.open(io.BytesIO(data)) as picture:
                mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif"}.get(picture.format)
                if mime is None:
                    raise ValueError("unsupported image")
                picture.verify()
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ClipboardPreparationError("clipboard_image_invalid", "正文图片格式不受支持或文件损坏，未复制；请在工作台替换该图片。") from exc
        # User round-trip evidence: 712/994-byte decorations disappeared while
        # larger PNGs survived. Use standard uncompressed PNG encoding for tiny
        # generated decorations; this is a compatibility candidate, not a claim
        # about a documented WeChat minimum size. Never pad metadata or rasterize text.
        if mime == "image/png" and asset.get("asset_role") == "theme_decoration" and len(data) < CLIPBOARD_TINY_DECORATION_BYTES:
            with Image.open(io.BytesIO(data)) as picture:
                if picture.width * picture.height * 4 > CLIPBOARD_IMAGE_MAX_BYTES:
                    raise ClipboardPreparationError("clipboard_too_large", "装饰图片展开后超过本地复制保护上限，未复制；请下载交付包。")
                output = io.BytesIO()
                picture.save(output, format="PNG", compress_level=0)
                data = output.getvalue()
            if len(data) > CLIPBOARD_IMAGE_MAX_BYTES:
                raise ClipboardPreparationError("clipboard_too_large", "装饰图片超过本地复制保护上限，未复制；请下载交付包。")
        url_size = len(f"data:{mime};base64,") + 4 * ((len(data) + 2) // 3)
        projected_bytes += sources.count(source) * (url_size - len(source.encode("utf-8")))
        if projected_bytes > CLIPBOARD_HTML_MAX_BYTES:
            raise ClipboardPreparationError("clipboard_too_large", "图文超过复制大小上限（24 MiB）；请缩小图片后重试，或选择下方的备用交付方式。")
        urls[asset["id"]] = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    return urls


def _extract_main(document: str) -> str:
    match = re.search(r"<main\b[^>]*>.*?</main>", document, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("冻结版本缺少可发布的 main 内容")
    return match.group(0)


def _responsive_delivery_document(document: str) -> str:
    """Make frozen 390px previews portable without changing component widths."""

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
    text = re.sub(
        r"<(br|/p|/section|/h[1-6]|/li|/blockquote)\b[^>]*>",
        "\n",
        document,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _frontmatter(metadata: dict[str, Any], cover_path: str) -> str:
    values: dict[str, Any] = {"title": metadata["title"], "cover": cover_path}
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
    """Build a portable, provider-neutral delivery bundle."""

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
    files["article.md"] = (_frontmatter(revision["metadata"], cover_relative) + body_html + "\n").encode("utf-8")
    files["article.html"] = portable_html.encode("utf-8")
    files["manifest.json"] = json.dumps(
        {
            "schema_version": "visual_director_delivery.v0.2",
            "revision_id": revision["id"],
            "frozen_html_hash": revision["frozen_html_hash"],
            "asset_manifest_hash": revision["asset_manifest_hash"],
            "title": revision["metadata"]["title"],
            "assets": manifest_items,
            "notes": [
                "article.html is a portable preview and manual-delivery fallback.",
                "article.md preserves metadata and inline HTML for downstream tools.",
                "The built-in publisher uses the frozen revision and official WeChat API directly.",
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
    *,
    hosted_asset_urls: dict[str, str] | None = None,
    read_asset: Callable[[str], tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    document = _clipboard_static_label_geometry(_responsive_delivery_document(revision["frozen_html"]))
    original_body = _extract_main(document)
    if read_asset is not None and hosted_asset_urls is not None:
        raise ValueError("Choose embedded or hosted clipboard images, not both")
    embedded_urls = _embedded_clipboard_sources(original_body, assets, read_asset) if read_asset is not None else None
    cover_url: str | None = None
    for asset in assets:
        used_in_body = f'src="asset://{asset["asset_token"]}"' in original_body
        if hosted_asset_urls is not None and used_in_body and asset["id"] not in hosted_asset_urls:
            raise ValueError("正文图片尚未全部准备完成，未生成带图剪贴板内容")
        target = (embedded_urls or hosted_asset_urls or {}).get(asset["id"]) or absolute_asset_url(asset["id"])
        document = document.replace(f'src="asset://{asset["asset_token"]}"', f'src="{target}"')
        if asset["asset_role"] == "cover":
            cover_url = target
    body_html = _extract_main(document)
    if embedded_urls is not None:
        if any(not source.startswith("data:image/") for source in _ImageSources(body_html).sources):
            raise ClipboardPreparationError("clipboard_image_unresolved", "部分正文图片未能内嵌，未复制；请返回工作台检查图片。")
        if len(body_html.encode("utf-8")) > CLIPBOARD_HTML_MAX_BYTES:
            raise ClipboardPreparationError("clipboard_too_large", "图文超过本地复制保护上限（24 MiB），未复制；请下载交付包。")
    image_count = len(re.findall(r"<img\b", body_html, flags=re.IGNORECASE))
    image_transport = "no_images" if not image_count else "embedded_data" if embedded_urls is not None else "wechat_hosted" if hosted_asset_urls is not None else "local_urls"
    return {
        "schema_version": "clipboard_payload.v0.1",
        "title": revision["metadata"]["title"],
        "html": body_html,
        "text": _plain_text(body_html),
        "cover_url": cover_url,
        "image_count": image_count,
        "image_transport": image_transport,
        "html_bytes": len(body_html.encode("utf-8")),
        "warnings": (["此冻结稿包含旧版定位线稿，保存到微信后可能错乱；请返回工作台重新渲染并确认最终版本。"]
                     if legacy_drawing_present(document) else []) +
                    (["当前复制包含本机图片链接，不能保证导入微信；请下载交付包后手动上传图片。"] if image_transport == "local_urls" else []) +
                    ["粘贴后请保存、重新打开并在手机端检查图片和样式。"],
    }
