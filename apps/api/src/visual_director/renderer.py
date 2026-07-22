from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from .brand import load_brand_profile
from .components import render_component
from .parser import ContentBlock, ParsedArticle
from .plan_schema import validate_plan_for_article


EXPLICIT_HEADING_NUMBER_RE = re.compile(
    r"^\s*(?:[^\w\u4e00-\u9fff]{0,4}\s*)?"
    r"(?:PART\s*\d+|第[一二三四五六七八九十百0-9]+(?:章|节|部分|步|问)|"
    r"[一二三四五六七八九十百]+[、.．]|\d+[、.．]|"
    r"(?:痛点|问题|步骤|信号|核心功能)[一二三四五六七八九十百0-9]+)",
    flags=re.IGNORECASE,
)
CONCLUSION_CUE_RE = re.compile(r"结论(?:是|：|:)|核心判断|答案是|最重要的是|建议是|这意味着")
GUIDE_CUE_RE = re.compile(r"本文|这篇|今天|接下来|逐个|一次性|直接回答|告诉你|梳理")


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("\n", "<br>")


def _has_explicit_heading_number(value: str) -> bool:
    return bool(EXPLICIT_HEADING_NUMBER_RE.match(value))


def _opening_highlight(parsed: ParsedArticle) -> tuple[str | None, str | None]:
    """Select one substantive pre-section lead instead of styling the first paragraph.

    A short scene setter such as “7月来了。” is not a conclusion. Only
    paragraphs before the first H2 can become a lead, and they need an explicit
    conclusion or guide cue plus enough information to stand on their own.
    """
    candidates: list[ContentBlock] = []
    for block in parsed.blocks:
        if block.type == "heading" and block.level == 2:
            break
        if block.type == "paragraph":
            candidates.append(block)
    for pattern, label in ((CONCLUSION_CUE_RE, "先看结论"), (GUIDE_CUE_RE, "本文导读")):
        for block in reversed(candidates):
            plain = re.sub(r"\*\*", "", str(block.content)).strip()
            if len(plain) >= 28 and pattern.search(plain):
                return block.id, label
    return None, None


def _render_heading(block: ContentBlock, config: dict[str, Any], section_index: int) -> str:
    accent = config["accent"]
    content = str(block.content).strip()
    level = block.level or 2

    if level == 2 and config["heading_variant"] == "numbered_marker":
        if _has_explicit_heading_number(content):
            return (
                '<section data-heading-level="2" data-auto-numbered="false" style="margin:40px 0 20px;padding-top:13px;'
                f'border-top:2px solid {accent};">'
                f'<strong style="display:block;color:#14201F;font-size:22px;line-height:1.48;letter-spacing:.01em;">{_inline(content)}</strong>'
                "</section>"
            )
        return (
            '<section data-heading-level="2" data-auto-numbered="true" style="margin:40px 0 20px;">'
            f'<span class="heading-number" style="display:inline-block;width:32px;height:32px;margin-right:9px;border-radius:50%;background-color:{accent};color:#fff;font:700 14px/32px Arial;text-align:center;vertical-align:top;">{section_index:02d}</span>'
            f'<strong style="display:inline-block;max-width:82%;margin-top:1px;color:#14201F;font-size:22px;line-height:1.45;letter-spacing:.01em;vertical-align:top;">{_inline(content)}</strong>'
            "</section>"
        )

    if level == 2:
        section_label = "SECTION" if _has_explicit_heading_number(content) else f"SECTION {section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:42px 0 20px;padding-left:14px;border-left:3px solid {accent};">'
            f'<p style="margin:0 0 5px;color:#7A7F7C;font:600 10px/1.2 Arial;letter-spacing:.18em;">{section_label}</p>'
            f'<strong style="display:block;color:#14201F;font-family:Georgia,serif;font-size:22px;line-height:1.48;">{_inline(content)}</strong>'
            "</section>"
        )

    if level == 3:
        return (
            '<section data-heading-level="3" data-auto-numbered="false" style="margin:27px 0 12px;">'
            f'<span style="display:inline-block;width:13px;height:3px;margin:0 8px 5px 0;background-color:{accent};vertical-align:middle;"></span>'
            f'<strong style="display:inline;color:#263331;font-size:18px;line-height:1.55;font-weight:750;">{_inline(content)}</strong>'
            "</section>"
        )

    return (
        '<p data-heading-level="4" data-auto-numbered="false" '
        f'style="margin:22px 0 9px;color:{accent};font-size:16px;line-height:1.55;font-weight:750;">{_inline(content)}</p>'
    )


def _render_table(rows: list[list[str]], config: dict[str, Any]) -> str:
    if not rows:
        return ""
    accent = config["accent"]
    header, *body = rows
    ths = "".join(
        f'<th style="padding:10px 8px;background-color:{accent};color:#fff;font-size:13px;line-height:1.4;text-align:left;border:1px solid {accent};">{_inline(cell)}</th>'
        for cell in header[:4]
    )
    trs = []
    for row_index, row in enumerate(body):
        background = "#F7F4EC" if row_index % 2 == 0 else "#FFFFFF"
        cells = "".join(
            f'<td style="padding:10px 8px;background-color:{background};color:#34403E;font-size:13px;line-height:1.5;border:1px solid #D9DED9;vertical-align:top;">{_inline(cell)}</td>'
            for cell in row[:4]
        )
        trs.append(f"<tr>{cells}</tr>")
    return (
        '<section style="margin:22px 0;overflow-x:auto;">'
        f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
        "</section>"
    )


def _render_list(items: list[str], ordered: bool, config: dict[str, Any]) -> str:
    accent = config["accent"]
    rendered = []
    for index, item in enumerate(items, 1):
        marker = str(index) if ordered or config["list_variant"] == "vertical_numbered" else "✓"
        rendered.append(
            '<p style="margin:0 0 12px;color:#34403E;font-size:16px;line-height:1.72;">'
            f'<span style="display:inline-block;width:25px;height:25px;margin-right:9px;border-radius:8px;background-color:{accent};color:#fff;font:700 12px/25px Arial;text-align:center;vertical-align:top;">{marker}</span>'
            f'<span style="display:inline-block;max-width:84%;vertical-align:top;">{_inline(item)}</span></p>'
        )
    return f'<section style="margin:20px 0 24px;">{"".join(rendered)}</section>'


def _render_image_placeholder(slot: dict[str, Any], accent: str) -> str:
    purpose_label = "结构信息图" if slot["purpose"] == "structured_infographic" else "氛围概念图"
    ratio_label = html.escape(slot["aspect_ratio"])
    reason = _inline(slot["reason"])
    return (
        f'<section id="{html.escape(slot["image_slot_id"])}" class="image-slot-anchor" '
        'style="scroll-margin-top:18px;margin:26px 0;padding:18px;border:1px dashed #AAB8B4;'
        'border-radius:16px;background-color:#F7FAF8;text-align:center;">'
        f'<span style="display:inline-block;margin:0 0 10px;padding:5px 9px;border-radius:999px;'
        f'background-color:{accent};color:#fff;font-size:10px;font-weight:700;letter-spacing:.08em;">'
        f'IMAGE PLAN · {html.escape(purpose_label)}</span>'
        f'<p style="margin:0 0 7px;color:#263331;font-size:15px;font-weight:700;line-height:1.6;">'
        f'计划配图 {ratio_label}</p>'
        f'<p style="margin:0;color:#667370;font-size:13px;line-height:1.65;">{reason}</p>'
        '</section>'
    )


def _render_source_image_placeholder(block: ContentBlock, accent: str) -> str:
    content = block.content if isinstance(block.content, dict) else {}
    alt = str(content.get("alt") or "原稿图片").strip()
    return (
        f'<section id="{html.escape(block.id)}" class="source-image-anchor" '
        'style="scroll-margin-top:18px;margin:24px 0;padding:20px 16px;border:1px dashed #B7BDB9;'
        'background-color:#F5F3EC;text-align:center;">'
        f'<span style="display:inline-block;margin-bottom:8px;color:{accent};font:700 10px/1.2 Arial;letter-spacing:.14em;">'
        'SOURCE IMAGE · WAITING</span>'
        f'<p style="margin:0;color:#34403E;font-size:14px;font-weight:700;line-height:1.6;">{_inline(alt)}</p>'
        '<p style="margin:5px 0 0;color:#7A8381;font-size:11px;line-height:1.5;">原稿图片未加载，请在预检清单中上传真实资产</p>'
        '</section>'
    )


def render_preview(
    parsed: ParsedArticle,
    plan: dict[str, Any],
    *,
    brand_profile: dict[str, Any] | None = None,
) -> str:
    validated = validate_plan_for_article(plan, parsed)
    profile = brand_profile if brand_profile is not None else load_brand_profile(Path(__file__).resolve().parents[4])
    config = validated["configuration"]
    accent = config["accent"]
    palette = config.get("palette", {"primary": accent})
    editorial = config["heading_variant"] == "editorial_left_rule"
    slots_by_anchor = {slot["anchor_block_id"]: slot for slot in validated.get("slots", [])}
    image_slots_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for image_slot in validated.get("image_slots", []):
        image_slots_by_anchor.setdefault(image_slot["anchor_block_id"], []).append(image_slot)
    consumed = {block_id for slot in validated.get("slots", []) for block_id in slot["consume_block_ids"]}
    body: list[str] = []
    section_index = 0
    opening_highlight_id, opening_highlight_label = _opening_highlight(parsed)

    for block in parsed.blocks:
        if block.id in slots_by_anchor:
            slot = slots_by_anchor[block.id]
            body.append(
                f'<section id="{html.escape(slot["slot_id"])}" class="component-anchor" style="scroll-margin-top:18px;">'
                f'{render_component(slot, parsed, palette)}</section>'
            )
        elif block.id in consumed:
            pass
        elif block.type == "heading":
            if block.level == 1:
                continue
            if block.level == 2:
                section_index += 1
            body.append(_render_heading(block, config, section_index))
        elif block.type == "paragraph":
            if block.id == opening_highlight_id:
                if editorial:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:22px 0 30px;padding:18px 14px;border-top:1px solid {accent};border-bottom:1px solid {accent};">'
                        f'<p style="margin:0 0 8px;color:#687370;font-size:10px;font-weight:700;letter-spacing:.14em;text-align:center;">{html.escape(opening_highlight_label or "本文导读")}</p>'
                        f'<p style="margin:0;color:#24302E;font-family:Georgia,serif;font-size:17px;line-height:1.8;text-align:center;">{_inline(str(block.content))}</p></section>'
                    )
                else:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:22px 0 28px;padding:18px 18px 17px;background-color:#EDF7F4;border-top:3px solid {accent};">'
                        f'<p style="margin:0 0 7px;color:#4E615E;font-size:11px;font-weight:700;letter-spacing:.14em;">{html.escape(opening_highlight_label or "本文导读")}</p>'
                        f'<p style="margin:0;color:#17312D;font-size:17px;font-weight:650;line-height:1.75;">{_inline(str(block.content))}</p></section>'
                    )
            else:
                body.append(f'<p style="margin:0 0 18px;color:#34403E;font-size:16px;line-height:1.85;text-align:justify;">{_inline(str(block.content))}</p>')
        elif block.type == "quote":
            if editorial:
                body.append(
                    f'<blockquote style="margin:30px 6px;padding:24px 12px;border-top:1px solid {accent};border-bottom:1px solid {accent};color:#1F2B29;font-family:Georgia,serif;font-size:20px;line-height:1.75;text-align:center;">{_inline(str(block.content))}</blockquote>'
                )
            else:
                body.append(
                    f'<blockquote style="margin:24px 0;padding:4px 0 4px 17px;border-left:4px solid {accent};color:#41514E;font-size:17px;line-height:1.75;">{_inline(str(block.content))}</blockquote>'
                )
        elif block.type in {"ordered_list", "unordered_list"}:
            body.append(_render_list(list(block.content), block.type == "ordered_list", config))
        elif block.type == "table":
            body.append(_render_table(list(block.content), config))
        elif block.type == "source":
            body.append(
                f'<p data-content-role="source" style="margin:24px 0 12px;padding:10px 2px 0;border-top:1px solid #E1E4E1;color:#7A8381;font-size:12px;font-weight:400;line-height:1.65;">{_inline(str(block.content))}</p>'
            )
        elif block.type == "image_reference":
            body.append(_render_source_image_placeholder(block, accent))
        for image_slot in image_slots_by_anchor.get(block.id, []):
            body.append(_render_image_placeholder(image_slot, accent))

    kicker = str(
        profile.get("editorial_kicker" if editorial else "standard_kicker")
        or ("WECHAT · CONTENT BRIEF" if editorial else "公众号 · 阅读指南")
    )
    hero = (
        f'<header style="padding:34px 0 22px;border-bottom:1px solid {accent};">'
        f'<p style="margin:0 0 13px;color:{accent};font:700 11px/1.2 Arial;letter-spacing:.16em;">{kicker}</p>'
        f'<h1 style="margin:0;color:#111C1A;font-family:Georgia,\'Noto Serif SC\',serif;font-size:{32 if editorial else 30}px;line-height:1.35;font-weight:750;letter-spacing:-.02em;">{_inline(parsed.title)}</h1>'
        f'<p style="margin:15px 0 0;color:#687370;font-size:12px;line-height:1.6;">{html.escape(validated["plan_name"])} · 组件库 {html.escape(validated["component_library_version"])}</p>'
        "</header>"
    )
    footer = profile.get("fixed_footer") if isinstance(profile.get("fixed_footer"), dict) else {}
    cta = ""
    if footer.get("enabled", False):
        footer_text = html.escape(str(footer.get("text") or ""))
        footer_alt = html.escape(str(footer.get("alt_text") or "品牌固定页尾"))
        image = (
            f'<img src="/api/v1/brand-assets/current/content" alt="{footer_alt}" '
            'style="display:block;width:100%;height:auto;margin:0 auto;border:0;" />'
            if footer.get("asset_path")
            else ""
        )
        cta = (
            '<footer style="margin:38px 0 0;padding:24px 0 0;border-top:1px solid #D9DED9;text-align:center;">'
            f'<p style="margin:0 0 14px;color:#263331;font-size:15px;font-weight:700;">{footer_text}</p>'
            f"{image}</footer>"
        )
    document = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>html{scroll-behavior:smooth}.component-anchor:target,.image-slot-anchor:target,.source-image-anchor:target{outline:2px solid #8FD6CE;outline-offset:7px;border-radius:10px}</style>'
        f'<title>{html.escape(parsed.title)}</title></head>'
        '<body style="margin:0;background-color:#F0EEE7;font-family:\'Noto Sans SC\',\'Microsoft YaHei\',Arial,sans-serif;">'
        '<main style="box-sizing:border-box;width:390px;max-width:100%;margin:0 auto;padding:0 24px 34px;background-color:#FFFEFA;box-shadow:0 12px 40px rgba(27,41,38,.10);">'
        f'{hero}{"".join(body)}{cta}</main></body></html>'
    )
    lowered = document.lower()
    if "<script" in lowered or re.search(r"\son[a-z]+\s*=", lowered):
        raise ValueError("渲染产物包含禁止脚本或事件属性")
    return document
