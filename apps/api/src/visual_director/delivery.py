from __future__ import annotations

import html as html_module
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Callable

import yaml


ROOT_MAIN_PATTERN = re.compile(r'(<main\b[^>]*\bstyle=")([^"]*)(")', flags=re.IGNORECASE)


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
        "warnings": ["粘贴后请保存、重新打开并在手机端检查图片和样式。"],
    }
