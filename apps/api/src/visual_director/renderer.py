from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Any

from .brand import load_brand_profile
from .components import render_component
from .parser import ContentBlock, ParsedArticle
from .plan_schema import validate_plan_for_article
from .theme_extensions import (
    extended_image_frame_variant,
    extended_image_placeholder_style,
    extended_inline_emphasis_style,
    render_extended_break,
    render_extended_heading,
    render_extended_hero,
    render_extended_list,
    render_extended_quote,
    render_extended_table,
)


EXPLICIT_HEADING_NUMBER_RE = re.compile(
    r"^\s*(?:[^\w\u4e00-\u9fff]{0,4}\s*)?"
    r"(?:PART\s*\d+|第[一二三四五六七八九十百0-9]+(?:章|节|部分|步|问)|"
    r"[一二三四五六七八九十百]+[、.．]|\d+[、.．]|"
    r"(?:痛点|问题|步骤|信号|核心功能)[一二三四五六七八九十百0-9]+)",
    flags=re.IGNORECASE,
)
CONCLUSION_CUE_RE = re.compile(r"结论(?:是|：|:)|核心判断|答案是|最重要的是|建议是|这意味着")
GUIDE_CUE_RE = re.compile(r"本文|这篇|今天|接下来|逐个|一次性|直接回答|告诉你|梳理")
CASE_LIST_CONTEXT_RE = re.compile(r"案例|样本|实例|两校|两种学校|同名专业|现实样本|对比|差异")
ACTION_LIST_CONTEXT_RE = re.compile(
    r"行动清单|核验清单|检查清单|操作清单|准备清单|办理清单|"
    r"(?:怎么|如何)(?:做|选|办|核验|检查|准备)|"
    r"(?:提交|申请|填报|办理|操作|执行|核验|检查|准备)(?:前|时|步骤|事项)|"
    r"建议|下一步|注意事项"
)


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("\n", "<br>")


def _body_inline(value: str, config: dict[str, Any]) -> str:
    escaped = html.escape(value)
    palette = config.get("palette", {})
    accent = config["accent"]
    heading_variant = config.get("heading_variant")
    extended_style = extended_inline_emphasis_style(config)
    if extended_style is not None:
        style = extended_style
    elif heading_variant == "botanical_section":
        style = (
            f"padding:0 3px;border-bottom:5px solid {palette.get('accent', accent)};"
            f"color:{palette.get('primary', accent)};font-weight:800;"
        )
    elif heading_variant == "story_chapter":
        style = (
            f"padding:1px 4px;border-bottom:7px solid {palette.get('secondary_pale', '#FBF2D8')};"
            f"color:{palette.get('accent', accent)};font-weight:800;"
        )
    elif heading_variant == "masthead_section":
        style = (
            f"border-bottom:5px solid {palette.get('accent', accent)};"
            f"color:{palette.get('primary', '#202B33')};font-weight:850;"
        )
    elif heading_variant == "indexed_column":
        style = (
            f"padding:1px 3px;border-bottom:2px solid {palette.get('primary', accent)};"
            f"color:{palette.get('primary', accent)};font-weight:800;"
        )
    elif heading_variant == "sticker_section":
        style = (
            f"padding:1px 4px;border-bottom:7px solid {palette.get('secondary_pale', '#FFF6D9')};"
            f"color:{palette.get('primary', accent)};font-weight:850;"
        )
    elif heading_variant == "signal_section":
        style = (
            f"padding:1px 4px;border-bottom:6px solid {palette.get('secondary_pale', '#EAF9F6')};"
            f"color:{palette.get('primary', accent)};font-weight:820;"
        )
    else:
        style = f"color:{accent};font-weight:800;"
    escaped = re.sub(
        r"\*\*(.+?)\*\*",
        lambda match: f'<strong data-content-role="inline-emphasis" style="{style}">{match.group(1)}</strong>',
        escaped,
    )
    return escaped.replace("\n", "<br>")


def _image_frame_variant(config: dict[str, Any]) -> str:
    extended_variant = extended_image_frame_variant(config)
    if extended_variant is not None:
        return extended_variant
    return {
        "botanical_section": "airy_organic",
        "story_chapter": "warm_storybook",
        "masthead_section": "editorial_masthead",
        "indexed_column": "structured_ledger",
        "sticker_section": "campus_sticker",
        "signal_section": "future_signal",
    }.get(str(config.get("heading_variant")), "neutral")


def _reliable_image_caption(alt: str) -> str:
    normalized = alt.strip()
    generic = {"", "图片", "配图", "插图", "原稿图片", "文章配图", "image", "photo"}
    return "" if normalized.lower() in generic else normalized


def _render_thematic_break(config: dict[str, Any]) -> str:
    extended = render_extended_break(config)
    if extended is not None:
        return extended
    palette = config.get("palette", {})
    accent = config["accent"]
    heading_variant = config.get("heading_variant")
    if heading_variant == "botanical_section":
        sky = palette.get("sky", accent)
        secondary = palette.get("secondary", accent)
        return (
            '<p data-content-role="thematic-break" style="margin:34px 0;text-align:center;white-space:nowrap;">'
            f'<span style="display:inline-block;width:29%;height:1px;background-color:{sky};"></span>'
            f'<span style="display:inline-block;width:15px;height:9px;margin:0 10px;border-radius:14px 3px 14px 3px;background-color:{secondary};transform:rotate(-15deg);"></span>'
            f'<span style="display:inline-block;width:29%;height:1px;background-color:{sky};"></span></p>'
        )
    if heading_variant == "story_chapter":
        return (
            '<p data-content-role="thematic-break" style="margin:35px 0;border-top:1px dashed #D7B995;text-align:center;">'
            f'<span style="display:inline-block;width:11px;height:11px;margin-top:-7px;border:1px solid {palette.get("primary", accent)};border-radius:50%;background-color:{palette.get("surface", "#FFFCF7")};"></span>'
            f'<span style="display:inline-block;width:42px;height:9px;margin:-6px 0 0 9px;background-color:{palette.get("secondary", accent)};opacity:.7;transform:rotate(-3deg);"></span></p>'
        )
    if heading_variant == "masthead_section":
        return (
            '<p data-content-role="thematic-break" style="margin:35px 0;border-top:3px solid #202B33;">'
            f'<span style="display:block;width:31%;height:8px;background-color:{palette.get("accent", accent)};"></span></p>'
        )
    if heading_variant == "indexed_column":
        return (
            '<p data-content-role="thematic-break" style="margin:35px 0;border-top:1px solid #AEBBB5;text-align:right;">'
            f'<span style="display:inline-block;width:18%;height:5px;background-color:{palette.get("secondary", accent)};"></span>'
            f'<span style="display:inline-block;width:9px;height:9px;margin-left:8px;border:2px solid {palette.get("primary", accent)};vertical-align:middle;"></span></p>'
        )
    if heading_variant == "sticker_section":
        return (
            '<p data-content-role="thematic-break" style="margin:36px 0;text-align:center;white-space:nowrap;">'
            f'<span style="display:inline-block;width:19%;height:1px;border-top:2px dashed {palette.get("sky", accent)};"></span>'
            f'<span style="display:inline-block;width:30px;height:12px;margin:0 10px;background-color:{palette.get("secondary", accent)};transform:rotate(-4deg);vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:10px;height:10px;margin-right:10px;border-radius:50%;background-color:{palette.get("accent", accent)};vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:19%;height:1px;border-top:2px dashed {palette.get("sky", accent)};"></span></p>'
        )
    if heading_variant == "signal_section":
        return (
            '<p data-content-role="thematic-break" style="margin:38px 0;text-align:center;white-space:nowrap;">'
            f'<span style="display:inline-block;width:20%;height:1px;background-color:{palette.get("sky", accent)};vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:18px;height:7px;margin:0 8px;border-radius:12px 2px 12px 2px;background-color:{palette.get("secondary", accent)};transform:rotate(-12deg);vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:7px;height:7px;margin-right:8px;border-radius:50%;background-color:{palette.get("accent", accent)};vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:20%;height:1px;background-color:{palette.get("primary", accent)};vertical-align:middle;"></span></p>'
        )
    return (
        f'<p data-content-role="thematic-break" style="height:1px;margin:34px 0;background-color:{accent};"></p>'
    )


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
    palette = config.get("palette", {})
    secondary = palette.get("secondary", accent)
    content = str(block.content).strip()
    level = block.level or 2

    extended = render_extended_heading(content, level, section_index, config)
    if extended is not None:
        return extended

    if level == 2 and config["heading_variant"] == "botanical_section":
        section_label = "SECTION" if _has_explicit_heading_number(content) else f"SECTION {section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:43px 0 21px;padding-left:13px;border-left:3px solid {accent};">'
            f'<p style="margin:0 0 6px;color:#76837E;font-family:Georgia,serif;font-size:9px;font-weight:700;letter-spacing:.18em;">{section_label}</p>'
            f'<strong style="display:block;color:#14201F;font-family:Georgia,\'Noto Serif SC\',serif;font-size:22px;line-height:1.5;">{_inline(content)}</strong>'
            f'<p style="height:1px;margin:10px 0 0;background-color:{secondary};"><span style="display:block;width:14px;height:8px;margin-left:-2px;border-radius:12px 2px 12px 2px;background-color:{accent};transform:rotate(-16deg);"></span></p>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "indexed_column":
        section_label = "IDX" if _has_explicit_heading_number(content) else f"{section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:44px 0 22px;border-top:4px solid {accent};white-space:normal;">'
            f'<span style="display:inline-block;width:21%;padding:12px 8px 10px 0;color:{secondary};font-family:Georgia,serif;font-size:28px;font-weight:800;line-height:1;vertical-align:top;">{section_label}</span>'
            f'<strong style="box-sizing:border-box;display:inline-block;width:79%;padding:10px 0 11px 14px;border-left:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;color:#14201F;font-size:21px;line-height:1.48;vertical-align:top;">{_inline(content)}</strong>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "story_chapter":
        section_label = "CHAPTER" if _has_explicit_heading_number(content) else f"CHAPTER {section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:44px 0 22px;padding:3px 0 12px 17px;border-left:5px solid {secondary};border-bottom:1px solid #D7B995;">'
            f'<p style="margin:-9px 0 11px -18px;"><span style="display:inline-block;padding:5px 10px;background-color:{palette.get("accent_pale", "#FBE9E2")};color:{accent};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.12em;transform:rotate(-2deg);">{section_label}</span></p>'
            f'<strong style="display:block;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:22px;line-height:1.52;">{_inline(content)}</strong>'
            f'<p style="margin:9px 0 -17px;text-align:right;"><span style="display:inline-block;width:46px;height:9px;background-color:{secondary};opacity:.72;transform:rotate(-3deg);"></span></p>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "masthead_section":
        section_label = "SECTION" if _has_explicit_heading_number(content) else f"{section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:45px 0 23px;padding:11px 0 13px;border-top:11px solid #202B33;border-bottom:3px solid #202B33;">'
            f'<p style="margin:0 0 8px;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:12px;font-weight:800;letter-spacing:.1em;">{section_label}<span style="display:inline-block;width:46px;height:6px;margin-left:10px;background-color:{accent};"></span></p>'
            f'<strong style="display:block;color:#202B33;font-size:21px;font-weight:850;line-height:1.48;">{_inline(content)}</strong>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "sticker_section":
        section_label = "CAMPUS BULLETIN" if _has_explicit_heading_number(content) else f"COURSE NOTE {section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:45px 0 23px;padding:0 8px 8px 0;">'
            f'<p style="margin:0 0 -8px 17px;"><span style="display:inline-block;padding:5px 12px;background-color:{secondary};color:{palette.get("ink", "#20304A")};font-size:9px;font-weight:800;letter-spacing:.13em;transform:rotate(-2deg);">{section_label}</span></p>'
            f'<section style="padding:19px 17px 16px 26px;border-left:10px dotted {palette.get("sky", accent)};border-bottom:3px solid {accent};background-color:{palette.get("surface", "#FFFEFB")};box-shadow:7px 7px 0 {palette.get("secondary_pale", "#FFF6D9")};">'
            f'<strong style="display:block;color:{palette.get("ink", "#20304A")};font-size:21px;line-height:1.5;">{_inline(content)}</strong>'
            f'</section></section>'
        )

    if level == 2 and config["heading_variant"] == "signal_section":
        section_label = "专题" if _has_explicit_heading_number(content) else f"{section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:48px 0 24px;padding:0 0 10px;white-space:normal;">'
            f'<span style="display:inline-block;width:19%;color:{palette.get("sky_pale", "#EEF1FA")};font-family:Georgia,serif;font-size:46px;font-weight:800;line-height:.92;vertical-align:top;">{section_label}</span>'
            f'<section style="box-sizing:border-box;display:inline-block;width:81%;padding:2px 0 10px 16px;border-left:5px solid {palette.get("secondary", accent)};vertical-align:top;">'
            f'<strong style="display:block;color:{palette.get("ink", "#24304F")};font-size:21px;line-height:1.52;">{_inline(content)}</strong>'
            f'<p style="height:3px;margin:11px 0 0;background:linear-gradient(90deg,{palette.get("accent", accent)} 0%,{palette.get("accent", accent)} 28%,{palette.get("sky_pale", "#EEF1FA")} 28%);"></p></section>'
            "</section>"
        )

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
        if config["heading_variant"] == "botanical_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;white-space:normal;">'
                f'<span style="display:inline-block;width:19px;height:13px;margin:3px 8px 0 0;border-radius:16px 3px 16px 3px;background-color:{accent};transform:rotate(-8deg);vertical-align:top;"></span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:87%;padding-bottom:7px;border-bottom:1px solid {secondary};vertical-align:top;">'
                f'<strong style="color:#263331;font-size:18px;line-height:1.55;font-weight:750;">{_inline(content)}</strong></section>'
                "</section>"
            )
        if config["heading_variant"] == "indexed_column":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;padding:0 0 8px;border-bottom:1px solid #B9C3BE;white-space:normal;">'
                f'<span style="display:inline-block;width:35px;color:{accent};font-family:Georgia,serif;font-size:11px;font-weight:800;vertical-align:top;">SUB</span>'
                f'<strong style="display:inline-block;width:86%;color:#263331;font-size:18px;line-height:1.55;font-weight:750;vertical-align:top;">{_inline(content)}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "story_chapter":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;white-space:normal;">'
                f'<span style="display:inline-block;width:23px;height:23px;margin:0 9px 0 0;border:1px solid {accent};border-radius:50%;color:{accent};font-size:12px;font-weight:800;line-height:23px;text-align:center;transform:rotate(-7deg);vertical-align:top;">✦</span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:86%;padding:0 0 8px;border-bottom:1px dashed #D7B995;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;line-height:1.58;vertical-align:top;">{_inline(content)}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "masthead_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:30px 0 13px;padding:0 0 8px;border-bottom:2px solid #202B33;white-space:normal;">'
                f'<span style="display:block;width:30px;height:7px;margin:0 0 8px;background-color:{palette.get("accent", accent)};"></span>'
                f'<strong style="display:block;color:#202B33;font-size:18px;line-height:1.5;font-weight:850;">{_inline(content)}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "sticker_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;white-space:normal;">'
                f'<span style="display:inline-block;width:32px;height:13px;margin:5px 9px 0 0;background-color:{palette.get("secondary", accent)};transform:rotate(-4deg);vertical-align:top;"></span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:84%;padding:0 0 8px;border-bottom:2px dashed {palette.get("sky", accent)};color:{palette.get("ink", "#20304A")};font-size:18px;line-height:1.55;vertical-align:top;">{_inline(content)}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "_legacy_sticker_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;white-space:normal;">'
                f'<span style="display:inline-block;width:25px;height:25px;margin-right:9px;border-radius:9px 9px 3px 9px;background-color:{palette.get("accent", accent)};color:#FFFFFF;font-size:12px;font-weight:800;line-height:25px;text-align:center;transform:rotate(-5deg);vertical-align:top;">✦</span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:85%;padding:1px 0 8px;border-bottom:2px dashed {palette.get("sky", accent)};color:{palette.get("ink", "#20304A")};font-size:18px;line-height:1.55;vertical-align:top;">{_inline(content)}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "signal_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:30px 0 14px;white-space:normal;">'
                f'<span style="display:inline-block;width:18px;height:8px;margin:6px 10px 0 0;border-radius:12px 2px 12px 2px;background-color:{palette.get("secondary", accent)};transform:rotate(-12deg);vertical-align:top;"></span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:87%;padding:0 0 8px;color:{palette.get("ink", "#24304F")};font-size:18px;line-height:1.55;vertical-align:top;">{_inline(content)}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "_legacy_signal_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;padding-bottom:8px;border-bottom:1px solid #B9D8D2;white-space:normal;">'
                f'<span style="display:inline-block;width:35px;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.1em;vertical-align:top;">NODE</span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:86%;padding-left:12px;border-left:2px solid {palette.get("secondary", accent)};color:{palette.get("ink", "#17313D")};font-size:18px;line-height:1.55;vertical-align:top;">{_inline(content)}</strong>'
                "</section>"
            )
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
    extended = render_extended_table(rows, config)
    if extended is not None:
        return extended
    accent = config["accent"]
    header, *body = rows
    if config.get("table_variant") == "ledger_grid":
        palette = config.get("palette", {})
        secondary = palette.get("secondary", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-top:4px solid {accent};border-bottom:1px solid #AEBBB5;background-color:#FFFFFF;color:{accent};font-size:12px;line-height:1.4;text-align:left;">{_inline(cell)}</th>'
            for cell in header[:4]
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px solid #D1D8D4;background-color:{"#F3F6F1" if cell_index == 0 else "#FFFFFF"};color:#34403E;font-size:13px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>'
                for cell_index, cell in enumerate(row[:4])
            )
            marker = f'<tr><td colspan="{min(len(header), 4)}" style="height:3px;padding:0;background-color:{secondary};"></td></tr>' if row_index == len(body) - 1 else ""
            trs.append(f"<tr>{cells}</tr>{marker}")
        return (
            '<section style="margin:24px 0;overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    if config.get("table_variant") == "soft_ledger":
        palette = config.get("palette", {})
        secondary = palette.get("secondary", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-bottom:2px solid {accent};background-color:#FFF8ED;color:{accent};font-family:Georgia,\'Noto Serif SC\',serif;font-size:12px;line-height:1.45;text-align:left;">{_inline(cell)}</th>'
            for cell in header[:4]
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px dashed #D7B995;background-color:{"#FFFCF7" if cell_index else "#FBF2D8"};color:#342B28;font-size:13px;line-height:1.58;vertical-align:top;">{_inline(cell)}</td>'
                for cell_index, cell in enumerate(row[:4])
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            f'<section style="margin:24px 0;padding-left:7px;border-left:5px solid {secondary};overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    if config.get("table_variant") == "editorial_matrix":
        palette = config.get("palette", {})
        editorial_accent = palette.get("accent", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-top:10px solid #202B33;border-bottom:3px solid #202B33;background-color:#FFFFFF;color:#202B33;font-size:12px;font-weight:850;line-height:1.4;text-align:left;">{_inline(cell)}</th>'
            for cell in header[:4]
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px solid #202B33;border-left:{f"5px solid {editorial_accent}" if cell_index == 0 else "0"};background-color:{"#EEF2F3" if row_index % 2 == 0 else "#FFFFFF"};color:#202B33;font-size:13px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>'
                for cell_index, cell in enumerate(row[:4])
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            '<section style="margin:24px 0;overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    if config.get("table_variant") == "campus_grid":
        palette = config.get("palette", {})
        secondary = palette.get("secondary", accent)
        sky = palette.get("sky", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-bottom:3px solid {accent};background-color:{palette.get("secondary_pale", "#FFF6D9")};color:{palette.get("ink", "#20304A")};font-size:12px;font-weight:800;line-height:1.4;text-align:left;">{_inline(cell)}</th>'
            for cell in header[:4]
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px dashed {sky};background-color:{"#EEF4FF" if row_index % 2 == 0 else "#FFFEFB"};color:{palette.get("ink", "#20304A")};font-size:13px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>'
                for cell in row[:4]
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            f'<section style="margin:24px 0;padding:6px;border:2px solid {accent};border-radius:14px 14px 4px 14px;box-shadow:5px 5px 0 {secondary};overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    if config.get("table_variant") == "signal_matrix":
        palette = config.get("palette", {})
        secondary = palette.get("secondary", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-top:4px solid {accent};border-bottom:1px solid #B9D8D2;background-color:{palette.get("surface", "#FBFEFD")};color:{accent};font-size:12px;font-weight:800;line-height:1.4;text-align:left;">{_inline(cell)}</th>'
            for cell in header[:4]
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px solid #CFE2DE;border-left:{f"3px solid {secondary}" if cell_index == 0 else "0"};background-color:{"#F1F4FF" if row_index % 2 == 0 else "#FBFEFD"};color:{palette.get("ink", "#17313D")};font-size:13px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>'
                for cell_index, cell in enumerate(row[:4])
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            '<section style="margin:24px 0;overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
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


def _list_semantic_role(parsed: ParsedArticle, block_index: int, ordered: bool) -> str:
    if ordered:
        return "numbered_insight"

    context: list[str] = []
    nearest_subheading = ""
    for previous in reversed(parsed.blocks[:block_index]):
        if previous.type == "heading":
            context.append(str(previous.content))
            if (previous.level or 0) >= 3 and not nearest_subheading:
                nearest_subheading = str(previous.content)
            if (previous.level or 0) <= 2:
                break
        elif len(context) < 3 and previous.type in {"paragraph", "quote"}:
            context.append(str(previous.content))

    combined = " ".join(context[:4])
    if nearest_subheading and CASE_LIST_CONTEXT_RE.search(nearest_subheading):
        return "case_points"
    if ACTION_LIST_CONTEXT_RE.search(combined):
        return "action_checklist"
    return "key_points"


def _list_marker(
    index: int,
    *,
    ordered: bool,
    semantic_role: str,
    action_marker: str = "✓",
    neutral_marker: str = "•",
) -> str:
    if ordered:
        return f"{index:02d}"
    if semantic_role == "action_checklist":
        return action_marker
    if semantic_role == "case_points" and index <= 26:
        return chr(64 + index)
    return neutral_marker


def _render_list(
    items: list[str],
    ordered: bool,
    config: dict[str, Any],
    semantic_role: str = "key_points",
) -> str:
    extended = render_extended_list(items, ordered, config, semantic_role)
    if extended is not None:
        return extended
    accent = config["accent"]
    palette = config.get("palette", {})
    secondary = palette.get("secondary", accent)
    sky = palette.get("sky", secondary)
    if config["list_variant"] == "leaf_path":
        rendered = []
        for index, item in enumerate(items, 1):
            marker = str(index) if ordered else _list_marker(index, ordered=False, semantic_role=semantic_role)
            marker_color = (accent, sky, secondary)[(index - 1) % 3]
            rendered.append(
                '<section style="margin:0 0 14px;white-space:normal;">'
                f'<span style="display:inline-block;width:29px;height:20px;border-radius:16px 3px 16px 3px;background-color:{marker_color};color:#fff;font:700 10px/20px Arial;text-align:center;transform:rotate(-6deg);vertical-align:top;">{marker}</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:0 0 10px 13px;border-bottom:1px solid #D7E5E1;color:#34403E;font-size:16px;line-height:1.72;vertical-align:top;">{_body_inline(item, config)}</p></section>'
            )
        return f'<section style="margin:22px 0 25px;padding-left:7px;border-left:1px dotted {sky};">{"".join(rendered)}</section>'
    if config["list_variant"] == "audit_track":
        rendered = []
        for index, item in enumerate(items, 1):
            marker = _list_marker(
                index,
                ordered=ordered,
                semantic_role=semantic_role,
                action_marker="CHK",
                neutral_marker="NOTE",
            )
            if semantic_role == "case_points" and not ordered:
                marker = f"C{index}"
            rendered.append(
                '<section style="border-bottom:1px solid #C7D0CC;white-space:normal;">'
                f'<span style="display:inline-block;width:18%;padding:12px 5px;color:{accent};font-family:Georgia,serif;font-size:11px;font-weight:800;vertical-align:top;">{marker}</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:70%;margin:0;padding:11px 9px;border-left:1px solid #C7D0CC;color:#34403E;font-size:15px;line-height:1.7;vertical-align:top;">{_body_inline(item, config)}</p>'
                f'<span style="display:inline-block;width:12%;padding:12px 0;color:{secondary};font-size:14px;font-weight:800;text-align:right;vertical-align:top;">{"□" if semantic_role == "action_checklist" else "·"}</span></section>'
            )
        return (
            f'<section style="margin:22px 0 25px;border-top:4px solid {accent};">'
            f'<p style="margin:0;padding:7px 0;color:#71807A;font-family:Georgia,serif;font-size:8px;font-weight:800;letter-spacing:.16em;">AUDIT TRACK</p>'
            f'{"".join(rendered)}</section>'
        )
    if config["list_variant"] == "stitched_path":
        rendered = []
        for index, item in enumerate(items, 1):
            marker = _list_marker(index, ordered=ordered, semantic_role=semantic_role)
            rendered.append(
                '<section style="margin:0 0 14px;white-space:normal;">'
                f'<span style="display:inline-block;width:28px;height:28px;margin-left:-16px;border:1px solid {accent};border-radius:50%;background-color:#FFFCF7;color:{accent};font-family:Georgia,serif;font-size:11px;font-weight:800;line-height:28px;text-align:center;vertical-align:top;">{marker}</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:2px 0 11px 13px;border-bottom:1px dashed #D7B995;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:15px;line-height:1.76;vertical-align:top;">{_body_inline(item, config)}</p></section>'
            )
        return (
            f'<section style="margin:22px 0 25px;padding:4px 0 1px 17px;border-left:3px dotted {secondary};">'
            f'{"".join(rendered)}</section>'
        )
    if config["list_variant"] == "proof_list":
        rendered = []
        for index, item in enumerate(items, 1):
            marker = _list_marker(
                index,
                ordered=ordered,
                semantic_role=semantic_role,
                action_marker="■",
                neutral_marker="■",
            )
            rendered.append(
                '<section style="border-top:1px solid #202B33;white-space:normal;">'
                f'<span style="display:inline-block;width:20%;padding:12px 7px 11px 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:18px;font-weight:800;vertical-align:top;">{marker}</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:80%;margin:0;padding:11px 0 12px 14px;border-left:5px solid {accent};color:#202B33;font-size:15px;font-weight:700;line-height:1.7;vertical-align:top;">{_body_inline(item, config)}</p></section>'
            )
        return (
            '<section style="margin:22px 0 25px;border-top:10px solid #202B33;border-bottom:3px solid #202B33;">'
            f'{"".join(rendered)}</section>'
        )
    if config["list_variant"] == "campus_steps":
        rendered = []
        for index, item in enumerate(items, 1):
            marker = _list_marker(index, ordered=ordered, semantic_role=semantic_role)
            marker_color = (
                accent,
                palette.get("accent", accent),
                sky,
                secondary,
            )[(index - 1) % 4]
            rendered.append(
                '<section style="margin:0 0 12px;white-space:normal;">'
                f'<span style="display:inline-block;width:31px;height:31px;border:3px solid #FFFEFB;border-radius:10px 10px 3px 10px;background-color:{marker_color};box-shadow:3px 3px 0 {palette.get("secondary_pale", "#FFF6D9")};color:#FFFFFF;font-family:Georgia,serif;font-size:10px;font-weight:800;line-height:31px;text-align:center;transform:rotate({-4 if index % 2 else 4}deg);vertical-align:top;">{marker}</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:84%;margin:0 0 0 11px;padding:6px 0 11px;border-bottom:2px dashed {sky};color:{palette.get("ink", "#20304A")};font-size:15px;line-height:1.72;vertical-align:top;">{_body_inline(item, config)}</p></section>'
            )
        return f'<section style="margin:22px 0 25px;padding:15px 13px 5px;border:2px solid {accent};border-radius:18px 6px 18px 18px;">{"".join(rendered)}</section>'
    if config["list_variant"] == "signal_track":
        rendered = []
        for index, item in enumerate(items, 1):
            marker = _list_marker(
                index,
                ordered=ordered,
                semantic_role=semantic_role,
                action_marker="•",
            )
            item_background = (
                palette.get("pale", "#F3F5FC"),
                palette.get("secondary_pale", "#EAF9F6"),
                palette.get("accent_pale", "#FFF1EC"),
            )[(index - 1) % 3]
            rendered.append(
                '<section style="margin:0 0 11px;white-space:normal;">'
                f'<span style="display:inline-block;width:17%;padding:10px 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:18px;font-weight:800;vertical-align:top;">{marker}</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:77%;margin:0;padding:11px 14px;border-radius:4px 18px 18px 18px;background-color:{item_background};color:{palette.get("ink", "#24304F")};font-size:15px;line-height:1.72;vertical-align:top;">{_body_inline(item, config)}</p></section>'
            )
        return (
            f'<section style="margin:23px 0 26px;padding:4px 0 1px;">'
            f'{"".join(rendered)}</section>'
        )
    rendered = []
    for index, item in enumerate(items, 1):
        marker = (
            str(index)
            if ordered or config["list_variant"] == "vertical_numbered"
            else _list_marker(index, ordered=False, semantic_role=semantic_role)
        )
        rendered.append(
            '<p style="margin:0 0 12px;color:#34403E;font-size:16px;line-height:1.72;">'
            f'<span style="display:inline-block;width:25px;height:25px;margin-right:9px;border-radius:8px;background-color:{accent};color:#fff;font:700 12px/25px Arial;text-align:center;vertical-align:top;">{marker}</span>'
            f'<span style="display:inline-block;max-width:84%;vertical-align:top;">{_body_inline(item, config)}</span></p>'
        )
    return f'<section style="margin:20px 0 24px;">{"".join(rendered)}</section>'


REFERENCE_LINK_RE = re.compile(r"^\[([^\]]+)]\((https?://[^)]+)\)$", flags=re.IGNORECASE)


def _render_reference_list(items: list[str], config: dict[str, Any]) -> str:
    """Render citations as subdued metadata, never as steps or checklists."""
    palette = config.get("palette", {})
    primary = palette.get("primary", config["accent"])
    rows: list[str] = []
    for item in items:
        match = REFERENCE_LINK_RE.fullmatch(str(item).strip())
        if match:
            label = html.escape(match.group(1).strip())
            url = match.group(2).strip()
            domain_match = re.match(r"https?://([^/]+)", url, flags=re.IGNORECASE)
            domain = html.escape(domain_match.group(1) if domain_match else url)
            content = (
                f'<span style="display:block;color:#4F5B58;font-size:12px;line-height:1.65;">{label}</span>'
                f'<span style="display:block;margin-top:2px;color:#929A97;font:400 9px/1.45 Arial;word-break:break-all;">{domain}</span>'
            )
        else:
            content = f'<span style="color:#4F5B58;font-size:12px;line-height:1.65;">{_inline(str(item))}</span>'
        rows.append(
            '<section data-content-role="reference-item" style="margin:0;padding:9px 0;border-bottom:1px solid #E3E7E4;white-space:normal;">'
            f'<span style="display:inline-block;width:5%;padding-top:7px;color:{primary};font-size:8px;vertical-align:top;">●</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:95%;vertical-align:top;">{content}</span></section>'
        )
    return (
        '<section data-content-role="reference-list" style="margin:18px 0 25px;padding:4px 0 0;">'
        f'{"".join(rows)}</section>'
    )


def _image_placeholder_style(config: dict[str, Any]) -> str:
    extended = extended_image_placeholder_style(config)
    if extended is not None:
        return extended
    palette = config.get("palette", {})
    variant = _image_frame_variant(config)
    if variant == "airy_organic":
        return (
            f"scroll-margin-top:18px;margin:28px 0;padding:18px;border:1px dashed {palette.get('sky', '#8BB9C0')};"
            f"border-radius:18px 18px 5px 18px;background-color:{palette.get('pale', '#EFF8F4')};text-align:center;"
        )
    if variant == "warm_storybook":
        return (
            f"scroll-margin-top:18px;margin:29px 0;padding:20px 16px 24px;border:1px dashed #D7B995;"
            f"background-color:#FFF9EF;box-shadow:7px 7px 0 {palette.get('secondary_pale', '#FBF2D8')};text-align:center;"
        )
    if variant == "editorial_masthead":
        return (
            "scroll-margin-top:18px;margin:29px 0;padding:20px 16px;border-top:11px solid #202B33;"
            "border-right:1px dashed #98A1A4;border-bottom:3px solid #202B33;border-left:1px dashed #98A1A4;"
            "background-color:#F4F6F6;text-align:center;"
        )
    if variant == "structured_ledger":
        return (
            f"scroll-margin-top:18px;margin:28px 0;padding:18px 16px;border-top:4px solid {palette.get('primary', config['accent'])};"
            "border-right:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;border-left:1px solid #AEBBB5;"
            "background-color:#F5F7F5;text-align:center;"
        )
    if variant == "campus_sticker":
        return (
            f"scroll-margin-top:18px;margin:29px 0;padding:20px 16px;border:2px dashed {palette.get('sky', '#62C7BE')};"
            f"border-radius:20px 7px 20px 20px;background-color:{palette.get('surface', '#FFFEFB')};"
            f"box-shadow:6px 6px 0 {palette.get('accent_pale', '#FFF0F5')};text-align:center;"
        )
    if variant == "future_signal":
        return (
            f"scroll-margin-top:18px;margin:30px 0;padding:21px 16px;border-radius:4px 34px 4px 24px;"
            f"background:linear-gradient(135deg,{palette.get('pale', '#F3F5FC')},{palette.get('secondary_pale', '#EAF9F6')});"
            f"box-shadow:6px 6px 0 {palette.get('sky_pale', '#EEF1FA')};text-align:center;"
        )
    return (
        "scroll-margin-top:18px;margin:26px 0;padding:18px;border:1px dashed #AAB8B4;"
        "border-radius:12px;background-color:#F7FAF8;text-align:center;"
    )


def _render_image_placeholder(slot: dict[str, Any], config: dict[str, Any]) -> str:
    accent = config["accent"]
    purpose_label = "结构信息图" if slot["purpose"] == "structured_infographic" else "氛围概念图"
    ratio_label = html.escape(slot["aspect_ratio"])
    reason = _inline(slot["reason"])
    frame_variant = _image_frame_variant(config)
    return (
        f'<section id="{html.escape(slot["image_slot_id"])}" class="image-slot-anchor" '
        f'data-image-frame="{frame_variant}" data-image-caption="" '
        f'style="{_image_placeholder_style(config)}">'
        f'<span style="display:inline-block;margin:0 0 10px;padding:5px 9px;border-radius:999px;'
        f'background-color:{accent};color:#fff;font-size:10px;font-weight:700;letter-spacing:.08em;">'
        f'IMAGE PLAN · {html.escape(purpose_label)}</span>'
        f'<p style="margin:0 0 7px;color:#263331;font-size:15px;font-weight:700;line-height:1.6;">'
        f'计划配图 {ratio_label}</p>'
        f'<p style="margin:0;color:#667370;font-size:13px;line-height:1.65;">{reason}</p>'
        '</section>'
    )


def _render_source_image_placeholder(block: ContentBlock, config: dict[str, Any]) -> str:
    accent = config["accent"]
    content = block.content if isinstance(block.content, dict) else {}
    alt = str(content.get("alt") or "原稿图片").strip()
    caption = _reliable_image_caption(alt)
    frame_variant = _image_frame_variant(config)
    return (
        f'<section id="{html.escape(block.id)}" class="source-image-anchor" '
        f'data-image-frame="{frame_variant}" data-image-caption="{html.escape(caption, quote=True)}" '
        f'style="{_image_placeholder_style(config)}">'
        f'<span style="display:inline-block;margin-bottom:8px;color:{accent};font:700 10px/1.2 Arial;letter-spacing:.14em;">'
        'SOURCE IMAGE · WAITING</span>'
        f'<p style="margin:0;color:#34403E;font-size:14px;font-weight:700;line-height:1.6;">{_inline(alt)}</p>'
        '<p style="margin:5px 0 0;color:#7A8381;font-size:11px;line-height:1.5;">原稿图片未加载，请在预检清单中上传真实资产</p>'
        '</section>'
    )


def _render_fixed_footer(footer: dict[str, Any], config: dict[str, Any]) -> str:
    if not footer.get("enabled", False):
        return ""
    palette = config.get("palette", {})
    accent = config["accent"]
    frame_variant = _image_frame_variant(config)
    footer_text = html.escape(str(footer.get("text") or ""))
    footer_alt = html.escape(str(footer.get("alt_text") or "品牌固定页尾"))
    image = (
        f'<img src="/api/v1/brand-assets/current/content" alt="{footer_alt}" '
        'style="display:block;width:100%;height:auto;margin:0 auto;border:0;" />'
        if footer.get("asset_path")
        else ""
    )
    if frame_variant == "airy_organic":
        style = (
            f"margin:40px 0 0;padding:21px 18px 17px;border-top:1px solid {palette.get('sky', accent)};"
            f"border-radius:22px 22px 6px 22px;background-color:{palette.get('pale', '#EFF8F4')};text-align:center;"
        )
        text_style = f"margin:0 0 14px;color:{palette.get('primary', accent)};font-size:15px;font-weight:800;"
    elif frame_variant == "warm_storybook":
        style = (
            f"margin:40px 0 0;padding:22px 16px 17px;border-left:5px solid {palette.get('accent', accent)};"
            "border-bottom:1px solid #D7B995;background-color:#FFF9EF;text-align:center;"
        )
        text_style = f"margin:0 0 14px;color:{palette.get('primary', accent)};font-family:Georgia,'Noto Serif SC',serif;font-size:15px;font-weight:800;"
    elif frame_variant == "editorial_masthead":
        style = (
            "margin:41px 0 0;padding:20px 0 0;border-top:11px solid #202B33;"
            "border-bottom:3px solid #202B33;text-align:left;"
        )
        text_style = f"margin:0 0 14px;padding-left:13px;border-left:6px solid {palette.get('accent', accent)};color:#202B33;font-size:15px;font-weight:850;"
    elif frame_variant == "structured_ledger":
        style = (
            f"margin:40px 0 0;padding:20px 0 0;border-top:6px solid {palette.get('primary', accent)};"
            "border-bottom:1px solid #AEBBB5;text-align:center;"
        )
        text_style = f"margin:0 0 14px;color:{palette.get('primary', accent)};font-size:15px;font-weight:800;letter-spacing:.02em;"
    elif frame_variant == "campus_sticker":
        style = (
            f"margin:40px 0 0;padding:22px 17px 18px;border:2px dashed {palette.get('sky', accent)};"
            f"border-radius:20px 7px 20px 20px;background-color:{palette.get('surface', '#FFFEFB')};"
            f"box-shadow:6px 6px 0 {palette.get('accent_pale', '#FFF0F5')};text-align:center;"
        )
        text_style = f"margin:0 0 14px;color:{palette.get('primary', accent)};font-size:15px;font-weight:850;"
    elif frame_variant == "future_signal":
        style = (
            f"margin:40px 0 0;padding:21px 17px 18px;border-radius:4px 36px 4px 24px;"
            f"background:linear-gradient(135deg,{palette.get('pale', '#F3F5FC')},{palette.get('secondary_pale', '#EAF9F6')});"
            f"box-shadow:6px 6px 0 {palette.get('sky_pale', '#EEF1FA')};text-align:center;"
        )
        text_style = f"margin:0 0 14px;color:{palette.get('primary', accent)};font-size:15px;font-weight:820;letter-spacing:.02em;"
    else:
        style = "margin:38px 0 0;padding:24px 0 0;border-top:1px solid #D9DED9;text-align:center;"
        text_style = "margin:0 0 14px;color:#263331;font-size:15px;font-weight:700;"
    return (
        f'<footer data-content-role="brand-cta" data-image-frame="{frame_variant}" style="{style}">'
        f'<p style="{text_style}">{footer_text}</p>{image}</footer>'
    )


def render_preview(
    parsed: ParsedArticle,
    plan: dict[str, Any],
    *,
    brand_profile: dict[str, Any] | None = None,
) -> str:
    validated = validate_plan_for_article(plan, parsed)
    configured_root = os.environ.get("VISUAL_DIRECTOR_PROJECT_ROOT")
    project_root = (
        Path(configured_root).expanduser().resolve()
        if configured_root
        else Path(__file__).resolve().parents[4]
    )
    profile = brand_profile if brand_profile is not None else load_brand_profile(project_root)
    config = validated["configuration"]
    accent = config["accent"]
    palette = config.get("palette", {"primary": accent})
    editorial = config["heading_variant"] in {"editorial_left_rule", "masthead_section"}
    warm = config["heading_variant"] == "story_chapter"
    airy = config["heading_variant"] == "botanical_section"
    structured = config["heading_variant"] == "indexed_column"
    campus = config["heading_variant"] == "sticker_section"
    future = config["heading_variant"] == "signal_section"
    slots_by_anchor = {slot["anchor_block_id"]: slot for slot in validated.get("slots", [])}
    image_slots_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for image_slot in validated.get("image_slots", []):
        image_slots_by_anchor.setdefault(image_slot["anchor_block_id"], []).append(image_slot)
    consumed = {block_id for slot in validated.get("slots", []) for block_id in slot["consume_block_ids"]}
    body: list[str] = []
    section_index = 0
    opening_highlight_id, opening_highlight_label = _opening_highlight(parsed)

    for block_index, block in enumerate(parsed.blocks):
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
                if airy:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:24px 0 30px;padding:4px 0 13px 15px;border-left:3px solid {accent};border-bottom:1px solid {palette.get("sky", accent)};">'
                        f'<p style="margin:0 0 7px;color:{accent};font-size:10px;font-weight:700;letter-spacing:.14em;">{html.escape(opening_highlight_label or "本文导读")}</p>'
                        f'<p style="margin:0;color:#17312D;font-size:17px;font-weight:650;line-height:1.78;">{_body_inline(str(block.content), config)}</p>'
                        f'<p style="margin:9px 0 -18px;text-align:right;"><span style="display:inline-block;width:14px;height:8px;border-radius:12px 2px 12px 2px;background-color:{palette.get("secondary", accent)};transform:rotate(-14deg);"></span></p></section>'
                    )
                elif structured:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:24px 0 30px;border-top:4px solid {accent};border-bottom:1px solid #B9C3BE;white-space:normal;">'
                        f'<span style="display:inline-block;width:23%;padding:15px 8px 12px 0;color:{palette.get("secondary", accent)};font-family:Georgia,serif;font-size:9px;font-weight:800;letter-spacing:.12em;vertical-align:top;">LEAD</span>'
                        f'<p style="box-sizing:border-box;display:inline-block;width:77%;margin:0;padding:13px 0 14px 15px;border-left:1px solid #B9C3BE;color:#24302E;font-size:16px;font-weight:650;line-height:1.8;vertical-align:top;">{_body_inline(str(block.content), config)}</p></section>'
                    )
                elif warm:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:25px 0 31px;padding:4px 0 14px 17px;border-left:5px solid {palette.get("secondary", accent)};border-bottom:1px solid #D7B995;">'
                        f'<p style="margin:-9px 0 10px -25px;"><span style="display:inline-block;padding:5px 10px;background-color:{palette.get("accent_pale", "#FBE9E2")};color:{accent};font-size:10px;font-weight:800;letter-spacing:.12em;transform:rotate(-2deg);">{html.escape(opening_highlight_label or "本文导读")}</span></p>'
                        f'<p style="margin:0;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:650;line-height:1.84;">{_body_inline(str(block.content), config)}</p>'
                        f'<p style="margin:9px 0 -20px;text-align:right;"><span style="display:inline-block;width:52px;height:10px;background-color:{palette.get("secondary", accent)};opacity:.72;transform:rotate(-3deg);"></span></p></section>'
                    )
                elif campus:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:26px 0 32px;padding:18px 17px 16px 27px;border-left:10px dotted {palette.get("sky", accent)};background-color:{palette.get("surface", "#FFFEFB")};box-shadow:7px 7px 0 {palette.get("secondary_pale", "#FFF6D9")};">'
                        f'<p style="margin:-25px 0 15px;"><span style="display:inline-block;padding:5px 11px;background-color:{palette.get("secondary", accent)};color:{palette.get("ink", "#20304A")};font-size:9px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">{html.escape(opening_highlight_label or "本文导读")}</span></p>'
                        f'<p style="margin:0;color:{palette.get("ink", "#20304A")};font-size:17px;font-weight:680;line-height:1.82;">{_body_inline(str(block.content), config)}</p></section>'
                    )
                elif False and campus:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:25px 0 31px;padding:6px 0 15px;border-bottom:2px solid {palette.get("sky", accent)};">'
                        f'<p style="width:61px;height:11px;margin:0 0 -5px 15px;background-color:{palette.get("secondary", accent)};transform:rotate(-4deg);"></p>'
                        f'<section style="padding:17px 18px;border:2px solid {accent};border-radius:6px 20px 20px 20px;background-color:{palette.get("surface", "#FFFEFB")};box-shadow:6px 6px 0 {palette.get("accent_pale", "#FFF0F5")};">'
                        f'<p style="margin:0 0 7px;color:{palette.get("accent", accent)};font-size:10px;font-weight:800;letter-spacing:.13em;">{html.escape(opening_highlight_label or "本文导读")}</p>'
                        f'<p style="margin:0;color:{palette.get("ink", "#20304A")};font-size:17px;font-weight:680;line-height:1.82;">{_body_inline(str(block.content), config)}</p></section></section>'
                    )
                elif future:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:28px 0 34px;padding:18px 19px 17px;border-radius:4px 38px 4px 22px;background:linear-gradient(135deg,{palette.get("secondary_pale", "#EAF9F6")},{palette.get("pale", "#F3F5FC")});box-shadow:6px 6px 0 {palette.get("sky_pale", "#EEF1FA")};">'
                        f'<p style="margin:0 0 10px;color:{palette.get("accent", accent)};font-size:10px;font-weight:800;letter-spacing:.1em;">{html.escape(opening_highlight_label or "本文导读")}</p>'
                        f'<p style="margin:0;color:{palette.get("ink", "#24304F")};font-size:17px;font-weight:680;line-height:1.82;">{_body_inline(str(block.content), config)}</p>'
                        f'<p style="margin:10px 0 -22px;text-align:right;"><span style="display:inline-block;width:45px;height:8px;border-radius:14px 3px 14px 3px;background-color:{palette.get("secondary", accent)};transform:rotate(-5deg);"></span></p></section>'
                    )
                elif False and future:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:24px 0 31px;border-top:6px solid {accent};border-bottom:1px solid #B9D8D2;white-space:normal;">'
                        f'<span style="display:inline-block;width:21%;padding:15px 7px 13px 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.11em;vertical-align:top;">LEAD</span>'
                        f'<p style="box-sizing:border-box;display:inline-block;width:79%;margin:0;padding:13px 0 15px 15px;border-left:2px solid {palette.get("secondary", accent)};color:{palette.get("ink", "#17313D")};font-size:17px;font-weight:680;line-height:1.82;vertical-align:top;">{_body_inline(str(block.content), config)}</p></section>'
                    )
                elif editorial:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:24px 0 31px;border-top:10px solid #202B33;border-bottom:3px solid #202B33;white-space:normal;">'
                        f'<span style="display:inline-block;width:22%;padding:15px 7px 13px 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.12em;vertical-align:top;">DECK</span>'
                        f'<p style="box-sizing:border-box;display:inline-block;width:78%;margin:0;padding:13px 0 15px 16px;border-left:6px solid {accent};color:#202B33;font-size:17px;font-weight:750;line-height:1.78;vertical-align:top;">{_body_inline(str(block.content), config)}</p></section>'
                    )
                else:
                    body.append(
                        f'<section data-content-role="lead" data-lead-kind="{html.escape(opening_highlight_label or "本文导读")}" '
                        f'style="margin:22px 0 28px;padding:18px 18px 17px;background-color:#EDF7F4;border-top:3px solid {accent};">'
                        f'<p style="margin:0 0 7px;color:#4E615E;font-size:11px;font-weight:700;letter-spacing:.14em;">{html.escape(opening_highlight_label or "本文导读")}</p>'
                        f'<p style="margin:0;color:#17312D;font-size:17px;font-weight:650;line-height:1.75;">{_body_inline(str(block.content), config)}</p></section>'
                    )
            else:
                body.append(f'<p style="margin:0 0 18px;color:#34403E;font-size:16px;line-height:1.85;text-align:justify;">{_body_inline(str(block.content), config)}</p>')
        elif block.type == "quote":
            extended_quote = render_extended_quote(str(block.content), config)
            if extended_quote is not None:
                body.append(extended_quote)
            elif config.get("quote_variant") == "floating_quote":
                body.append(
                    f'<blockquote style="margin:31px 3px 34px;padding:0 8px 13px 0;border-bottom:1px solid {palette.get("sky", accent)};white-space:normal;">'
                    f'<span style="display:inline-block;width:46px;margin-top:-7px;color:{palette.get("secondary", accent)};font-family:Georgia,serif;font-size:72px;font-weight:700;line-height:.72;vertical-align:top;">“</span>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:82%;padding:4px 0 0 4px;color:#1F2B29;font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;font-weight:650;line-height:1.9;vertical-align:top;">{_body_inline(str(block.content), config)}</span>'
                    f'</blockquote>'
                )
            elif config.get("quote_variant") == "evidence_margin":
                body.append(
                    f'<blockquote style="margin:30px 0;padding:4px 0;border-top:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;white-space:normal;">'
                    f'<span style="display:inline-block;width:23%;padding:17px 8px 13px 0;color:{accent};font-family:Georgia,serif;font-size:9px;font-weight:800;letter-spacing:.14em;vertical-align:top;">QUOTE<br>REF</span>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:77%;padding:15px 0 15px 16px;border-left:4px solid {accent};color:#1F2B29;font-size:17px;font-weight:700;line-height:1.85;vertical-align:top;">{_body_inline(str(block.content), config)}</span></blockquote>'
                )
            elif config.get("quote_variant") == "postcard_quote":
                body.append(
                    f'<blockquote style="margin:33px 4px 32px;padding:0 0 15px;border-bottom:1px solid #D7B995;white-space:normal;">'
                    f'<span style="display:inline-block;width:19%;margin-top:-11px;color:{palette.get("accent_pale", "#FBE9E2")};font-family:Georgia,serif;font-size:76px;font-weight:700;line-height:.75;vertical-align:top;">“</span>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:81%;padding:8px 13px 13px 17px;border-left:3px solid {palette.get("accent", accent)};background-color:#FFF9EF;box-shadow:7px 7px 0 {palette.get("secondary_pale", "#FBF2D8")};color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:650;line-height:1.9;vertical-align:top;">{_body_inline(str(block.content), config)}</span>'
                    f'</blockquote>'
                )
            elif config.get("quote_variant") == "pull_quote":
                body.append(
                    f'<blockquote style="margin:33px 0;padding:8px 0 13px;border-top:11px solid #202B33;border-bottom:3px solid #202B33;white-space:normal;">'
                    f'<span style="display:inline-block;width:23%;padding:7px 8px 0 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:50px;font-weight:800;line-height:.8;vertical-align:top;">“</span>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:77%;padding:9px 0 11px 16px;border-left:6px solid {accent};color:#202B33;font-family:Georgia,\'Noto Serif SC\',serif;font-size:19px;font-weight:800;line-height:1.78;vertical-align:top;">{_body_inline(str(block.content), config)}</span>'
                    f'</blockquote>'
                )
            elif config.get("quote_variant") == "campus_quote":
                body.append(
                    f'<blockquote style="margin:32px 0;padding:7px 0 17px;border-bottom:2px dashed {palette.get("sky", accent)};white-space:normal;">'
                    f'<span style="box-sizing:border-box;display:inline-block;width:65px;margin-left:4px;padding:14px 5px;background-color:{palette.get("accent", accent)};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.12em;text-align:center;transform:rotate(-3deg);vertical-align:top;">CAMPUS<br>RADIO</span>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:79%;margin-left:3%;padding:15px 16px;background-color:{palette.get("secondary_pale", "#FFF6D9")};box-shadow:6px 6px 0 {palette.get("sky_pale", "#EEF4FF")};color:{palette.get("ink", "#20304A")};font-size:17px;font-weight:700;line-height:1.85;vertical-align:top;">{_body_inline(str(block.content), config)}</span></blockquote>'
                )
            elif config.get("quote_variant") == "_legacy_campus_quote":
                body.append(
                    f'<blockquote style="margin:31px 0;padding:6px 0 14px;border-bottom:2px solid {palette.get("sky", accent)};">'
                    f'<p style="width:54px;height:11px;margin:0 0 -5px 13px;background-color:{palette.get("secondary", accent)};transform:rotate(-4deg);"></p>'
                    f'<section style="padding:17px 18px;border:2px solid {accent};border-radius:5px 20px 20px 20px;background-color:{palette.get("surface", "#FFFEFB")};box-shadow:6px 6px 0 {palette.get("accent_pale", "#FFF0F5")};">'
                    f'<span style="display:inline-block;width:34px;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:42px;font-weight:800;line-height:.8;vertical-align:top;">“</span>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:87%;color:{palette.get("ink", "#20304A")};font-size:17px;font-weight:700;line-height:1.85;vertical-align:top;">{_body_inline(str(block.content), config)}</span>'
                    f'</section></blockquote>'
                )
            elif config.get("quote_variant") == "signal_quote":
                body.append(
                    f'<blockquote style="margin:34px 0;padding:2px 0 12px;white-space:normal;">'
                    f'<span style="display:inline-block;width:17%;color:{palette.get("secondary", accent)};font-family:Georgia,serif;font-size:64px;font-weight:800;line-height:.72;vertical-align:top;">“</span>'
                    f'<section style="box-sizing:border-box;display:inline-block;width:83%;padding:4px 0 12px 15px;border-bottom:5px solid {palette.get("accent_pale", "#FFF1EC")};vertical-align:top;">'
                    f'<p style="margin:0 0 8px;color:{palette.get("accent", accent)};font-size:10px;font-weight:800;letter-spacing:.08em;">证据摘录</p>'
                    f'<p style="margin:0;color:{palette.get("ink", "#24304F")};font-size:17px;font-weight:720;line-height:1.86;">{_body_inline(str(block.content), config)}</p></section></blockquote>'
                )
            elif config.get("quote_variant") == "_legacy_signal_quote":
                body.append(
                    f'<blockquote style="margin:31px 0;border-top:6px solid {accent};border-bottom:1px solid #B9D8D2;white-space:normal;">'
                    f'<span style="display:inline-block;width:20%;padding:16px 7px;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.12em;vertical-align:top;">QUOTE</span>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:80%;padding:15px 0 16px 15px;border-left:2px solid {palette.get("secondary", accent)};color:{palette.get("ink", "#17313D")};font-size:17px;font-weight:720;line-height:1.85;vertical-align:top;">{_body_inline(str(block.content), config)}</span></blockquote>'
                )
            elif editorial:
                body.append(
                    f'<blockquote style="margin:30px 6px;padding:24px 12px;border-top:1px solid {accent};border-bottom:1px solid {accent};color:#1F2B29;font-family:Georgia,serif;font-size:20px;line-height:1.75;text-align:center;">{_body_inline(str(block.content), config)}</blockquote>'
                )
            else:
                body.append(
                    f'<blockquote style="margin:24px 0;padding:4px 0 4px 17px;border-left:4px solid {accent};color:#41514E;font-size:17px;line-height:1.75;">{_body_inline(str(block.content), config)}</blockquote>'
                )
        elif block.type in {"ordered_list", "unordered_list"}:
            ordered = block.type == "ordered_list"
            body.append(
                _render_list(
                    list(block.content),
                    ordered,
                    config,
                    _list_semantic_role(parsed, block_index, ordered),
                )
            )
        elif block.type == "reference_list":
            body.append(_render_reference_list(list(block.content), config))
        elif block.type == "table":
            body.append(_render_table(list(block.content), config))
        elif block.type == "source":
            body.append(
                f'<p data-content-role="source" style="margin:24px 0 12px;padding:10px 2px 0;border-top:1px solid #E1E4E1;color:#7A8381;font-size:12px;font-weight:400;line-height:1.65;">{_inline(str(block.content))}</p>'
            )
        elif block.type == "thematic_break":
            body.append(_render_thematic_break(config))
        elif block.type == "image_reference":
            body.append(_render_source_image_placeholder(block, config))
        for image_slot in image_slots_by_anchor.get(block.id, []):
            body.append(_render_image_placeholder(image_slot, config))

    kicker = str(
        profile.get("editorial_kicker" if editorial else "standard_kicker")
        or ("WECHAT · CONTENT BRIEF" if editorial else "公众号 · 阅读指南")
    )
    extended_hero = render_extended_hero(
        parsed.title,
        validated["plan_name"],
        validated["component_library_version"],
        kicker,
        config,
    )
    if extended_hero is not None:
        hero = extended_hero
    elif airy:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:34px 0 23px;border-bottom:1px solid {palette.get("sky", accent)};">'
            f'<p style="margin:0 0 13px;color:{accent};font:700 10px/1.2 Arial;letter-spacing:.16em;">{kicker}</p>'
            f'<h1 style="margin:0;color:#111C1A;font-family:Georgia,\'Noto Serif SC\',serif;font-size:30px;line-height:1.38;font-weight:750;letter-spacing:-.02em;">{_inline(parsed.title)}</h1>'
            f'<p style="margin:15px 0 0;color:#687370;font-size:12px;line-height:1.6;">{html.escape(validated["plan_name"])} · 组件库 {html.escape(validated["component_library_version"])}</p>'
            f'<p style="margin:16px 0 -29px;text-align:right;"><span style="display:inline-block;width:28px;height:14px;border-radius:20px 3px 20px 3px;background-color:{palette.get("secondary", accent)};transform:rotate(-12deg);"></span><span style="display:inline-block;width:7px;height:7px;margin-left:7px;border-radius:50%;background-color:{palette.get("accent", accent)};"></span></p>'
            "</header>"
        )
    elif campus:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:33px 8px 27px 0;">'
            f'<p style="margin:0 0 -8px 19px;"><span style="display:inline-block;padding:5px 12px;background-color:{palette.get("secondary", accent)};color:{palette.get("ink", "#20304A")};font:800 9px/1.2 Georgia,serif;letter-spacing:.14em;transform:rotate(-2deg);">CAMPUS BULLETIN</span></p>'
            f'<section style="padding:22px 18px 19px 28px;border-left:11px dotted {palette.get("sky", accent)};border-bottom:4px solid {accent};background-color:{palette.get("surface", "#FFFEFB")};box-shadow:8px 8px 0 {palette.get("secondary_pale", "#FFF6D9")};">'
            f'<p style="margin:0 0 12px;color:{palette.get("accent", accent)};font:800 9px/1.2 Georgia,serif;letter-spacing:.15em;">{kicker}</p>'
            f'<h1 style="margin:0;color:{palette.get("ink", "#20304A")};font-size:30px;line-height:1.38;font-weight:830;letter-spacing:-.02em;">{_inline(parsed.title)}</h1>'
            f'<p style="margin:16px 0 0;padding-top:11px;border-top:2px dashed {palette.get("sky", accent)};color:#63718A;font-size:11px;line-height:1.6;">{html.escape(validated["plan_name"])} · {html.escape(validated["component_library_version"])}</p></section>'
            "</header>"
        )
    elif False and campus:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:31px 0 24px;border-bottom:2px solid {palette.get("sky", accent)};">'
            f'<p style="width:72px;height:12px;margin:0 0 -4px 17px;background-color:{palette.get("secondary", accent)};transform:rotate(-4deg);"></p>'
            f'<section style="padding:18px 18px 19px;border:2px solid {accent};border-radius:6px 22px 22px 22px;background-color:{palette.get("surface", "#FFFEFB")};box-shadow:7px 7px 0 {palette.get("accent_pale", "#FFF0F5")};">'
            f'<p style="margin:0 0 11px;color:{palette.get("accent", accent)};font:800 10px/1.2 Georgia,serif;letter-spacing:.14em;">{kicker}</p>'
            f'<h1 style="margin:0;color:{palette.get("ink", "#20304A")};font-size:30px;line-height:1.38;font-weight:820;letter-spacing:-.02em;">{_inline(parsed.title)}</h1>'
            f'<p style="margin:15px 0 0;color:#63718A;font-size:12px;line-height:1.6;">{html.escape(validated["plan_name"])} · {html.escape(validated["component_library_version"])}</p></section>'
            "</header>"
        )
    elif future:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="margin:30px 0 29px;padding:24px 20px 20px;border-left:6px solid {palette.get("primary", accent)};border-radius:0 62px 0 24px;background:linear-gradient(135deg,{palette.get("surface", "#FEFEFF")} 0%,{palette.get("pale", "#F3F5FC")} 48%,{palette.get("secondary_pale", "#EAF9F6")} 100%);box-shadow:8px 8px 0 {palette.get("sky_pale", "#EEF1FA")};">'
            f'<p style="margin:0 0 15px;color:{palette.get("primary", accent)};font:800 9px/1.2 Georgia,serif;letter-spacing:.18em;">FUTURE EDITION <span style="color:{palette.get("accent", accent)};">●</span></p>'
            f'<p style="margin:0 0 9px;color:{accent};font-size:10px;font-weight:750;letter-spacing:.1em;">{kicker}</p>'
            f'<h1 style="margin:0;color:{palette.get("ink", "#24304F")};font-size:29px;line-height:1.4;font-weight:830;letter-spacing:-.02em;">{_inline(parsed.title)}</h1>'
            f'<p style="margin:17px 0 0;padding-top:11px;border-top:1px solid {palette.get("sky", accent)};color:#69738F;font-size:10px;line-height:1.5;">{html.escape(validated["plan_name"])} · {html.escape(validated["component_library_version"])}</p>'
            f'<p style="margin:10px 0 -28px;text-align:right;"><span style="display:inline-block;width:58px;height:10px;border-radius:16px 3px 16px 3px;background-color:{palette.get("secondary", accent)};transform:rotate(-6deg);"></span><span style="display:inline-block;width:8px;height:8px;margin-left:8px;border-radius:50%;background-color:{palette.get("accent", accent)};"></span></p>'
            "</header>"
        )
    elif False and future:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:30px 0 23px;border-top:8px solid {accent};border-bottom:1px solid #B9D8D2;">'
            f'<p style="height:5px;margin:-8px 0 15px;background-color:{palette.get("secondary", accent)};width:29%;"></p>'
            f'<section style="white-space:normal;"><span style="display:inline-block;width:21%;color:{palette.get("accent", accent)};font:800 10px/1.2 Georgia,serif;letter-spacing:.13em;vertical-align:top;">SIGNAL</span>'
            f'<section style="box-sizing:border-box;display:inline-block;width:79%;padding-left:15px;border-left:2px solid {palette.get("secondary", accent)};vertical-align:top;">'
            f'<p style="margin:0 0 10px;color:{accent};font:700 10px/1.2 Arial;letter-spacing:.13em;">{kicker}</p>'
            f'<h1 style="margin:0;color:{palette.get("ink", "#17313D")};font-size:29px;line-height:1.4;font-weight:820;letter-spacing:-.02em;">{_inline(parsed.title)}</h1></section></section>'
            f'<p style="margin:16px 0 0;color:#607985;font-size:11px;line-height:1.6;text-align:right;">{html.escape(validated["plan_name"])} · {html.escape(validated["component_library_version"])}</p>'
            "</header>"
        )
    elif warm:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:33px 0 24px;border-left:6px solid {palette.get("secondary", accent)};border-bottom:1px solid #D7B995;">'
            f'<p style="margin:0 0 13px -7px;"><span style="display:inline-block;padding:5px 11px;background-color:{palette.get("accent_pale", "#FBE9E2")};color:{accent};font:800 10px/1.2 Georgia,serif;letter-spacing:.14em;transform:rotate(-2deg);">{kicker}</span></p>'
            f'<section style="padding-left:18px;"><h1 style="margin:0;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:30px;line-height:1.4;font-weight:750;">{_inline(parsed.title)}</h1>'
            f'<p style="margin:15px 0 0;color:#7B6861;font-size:12px;line-height:1.6;">{html.escape(validated["plan_name"])} · {html.escape(validated["component_library_version"])}</p></section>'
            f'<p style="margin:15px 0 -30px;text-align:right;"><span style="display:inline-block;width:56px;height:10px;background-color:{palette.get("secondary", accent)};opacity:.72;transform:rotate(-3deg);"></span><span style="display:inline-block;width:8px;height:8px;margin-left:8px;border-radius:50%;background-color:{palette.get("accent", accent)};"></span></p>'
            "</header>"
        )
    elif editorial:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:29px 0 23px;border-top:13px solid #202B33;border-bottom:4px solid #202B33;">'
            f'<p style="margin:0 0 11px;color:{palette.get("accent", accent)};font:800 10px/1.2 Georgia,serif;letter-spacing:.14em;">FEATURE<span style="display:inline-block;width:52px;height:7px;margin-left:11px;background-color:{accent};"></span></p>'
            f'<p style="margin:0 0 10px;color:{accent};font:800 10px/1.2 Arial;letter-spacing:.14em;">{kicker}</p>'
            f'<h1 style="margin:0;color:#202B33;font-size:31px;line-height:1.34;font-weight:850;letter-spacing:-.03em;">{_inline(parsed.title)}</h1>'
            f'<p style="margin:17px 0 0;padding-top:8px;border-top:1px solid #202B33;color:#687370;font-size:11px;line-height:1.6;text-align:right;">{html.escape(validated["plan_name"])} · {html.escape(validated["component_library_version"])}</p>'
            "</header>"
        )
    elif structured:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:30px 0 23px;border-top:8px solid {accent};border-bottom:1px solid #AEBBB5;">'
            f'<section style="white-space:normal;"><span style="display:inline-block;width:25%;color:{palette.get("secondary", accent)};font:800 10px/1.2 Georgia,serif;letter-spacing:.14em;vertical-align:top;">FEATURE</span>'
            f'<section style="box-sizing:border-box;display:inline-block;width:75%;padding-left:15px;border-left:1px solid #AEBBB5;vertical-align:top;">'
            f'<p style="margin:0 0 10px;color:{accent};font:700 10px/1.2 Arial;letter-spacing:.14em;">{kicker}</p>'
            f'<h1 style="margin:0;color:#111C1A;font-size:29px;line-height:1.38;font-weight:800;letter-spacing:-.02em;">{_inline(parsed.title)}</h1></section></section>'
            f'<p style="margin:16px 0 0;color:#687370;font-size:11px;line-height:1.6;text-align:right;">{html.escape(validated["plan_name"])} · {html.escape(validated["component_library_version"])}</p>'
            "</header>"
        )
    else:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:34px 0 22px;border-bottom:1px solid {accent};">'
            f'<p style="margin:0 0 13px;color:{accent};font:700 11px/1.2 Arial;letter-spacing:.16em;">{kicker}</p>'
            f'<h1 style="margin:0;color:#111C1A;font-family:Georgia,\'Noto Serif SC\',serif;font-size:{32 if editorial else 30}px;line-height:1.35;font-weight:750;letter-spacing:-.02em;">{_inline(parsed.title)}</h1>'
            f'<p style="margin:15px 0 0;color:#687370;font-size:12px;line-height:1.6;">{html.escape(validated["plan_name"])} · 组件库 {html.escape(validated["component_library_version"])}</p>'
            "</header>"
        )
    footer = profile.get("fixed_footer") if isinstance(profile.get("fixed_footer"), dict) else {}
    cta = _render_fixed_footer(footer, config)
    document = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>html{scroll-behavior:smooth}.component-anchor:target,.image-slot-anchor:target,.source-image-anchor:target{outline:2px solid #8FD6CE;outline-offset:7px;border-radius:10px}</style>'
        f'<title>{html.escape(parsed.title)}</title></head>'
        '<body style="box-sizing:border-box;margin:0;padding:0 24px;background-color:#FFFFFF;font-family:\'Noto Sans SC\',\'Microsoft YaHei\',Arial,sans-serif;">'
        f'{hero}<main style="box-sizing:border-box;width:100%;max-width:100%;margin:0 auto;padding:0 0 34px;">'
        f'{"".join(body)}{cta}</main></body></html>'
    )
    lowered = document.lower()
    if "<script" in lowered or re.search(r"\son[a-z]+\s*=", lowered):
        raise ValueError("渲染产物包含禁止脚本或事件属性")
    return document
