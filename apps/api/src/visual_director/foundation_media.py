from __future__ import annotations

import html
import json
from typing import Any

from .parser import ContentBlock
from .foundation_inline import _inline
from .generated_theme import generated_image_frame_variant, generated_image_placeholder_style
from .theme_extensions import extended_image_frame_variant, extended_image_placeholder_style
from .image_caption_render import caption_metrics_attribute
from .reading_rules import BRAND_FOOTER, ReadingProfile, render_authored_text


def _image_frame_variant(config: dict[str, Any]) -> str:
    generated_variant = generated_image_frame_variant(config)
    if generated_variant is not None:
        return generated_variant
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


def _image_placeholder_style(config: dict[str, Any]) -> str:
    generated = generated_image_placeholder_style(config)
    if generated is not None:
        return generated
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


def _custom_image_metadata(config: dict[str, Any]) -> str:
    design = config.get("generated_design_system", {})
    layout = design.get("layouts", {}).get("image_caption")
    if layout is None:
        return ""
    snapshot = {"palette": config["palette"], "generated_design_system": {
        "layouts": {"image_caption": layout}, "typography": design["typography"], "rhythm": design["rhythm"],
    }}
    return f'data-theme-image-config="{html.escape(json.dumps(snapshot, ensure_ascii=False), quote=True)}"'


def _render_image_placeholder(slot: dict[str, Any], config: dict[str, Any]) -> str:
    accent = config["accent"]
    purpose_label = "结构信息图" if slot["purpose"] == "structured_infographic" else "氛围概念图"
    ratio_label = html.escape(slot["aspect_ratio"])
    reason = _inline(slot["reason"])
    frame_variant = _image_frame_variant(config)
    return (
        f'<section id="{html.escape(slot["image_slot_id"])}" class="image-slot-anchor" '
        f'data-image-frame="{frame_variant}" data-image-caption="" {_custom_image_metadata(config)} '
        f'style="{_image_placeholder_style(config)}">'
        f'<span style="display:inline-block;margin:0 0 10px;padding:5px 9px;border-radius:999px;'
        f'background-color:{accent};color:#fff;font-size:10px;font-weight:700;letter-spacing:.08em;">'
        f'IMAGE PLAN · {html.escape(purpose_label)}</span>'
        f'<p style="margin:0 0 7px;color:#263331;font-size:15px;font-weight:700;line-height:1.6;">'
        f'计划配图 {ratio_label}</p>'
        f'<p style="margin:0;color:#667370;font-size:13px;line-height:1.65;">{reason}</p>'
        '</section>'
    )


def _render_source_image_placeholder(block: ContentBlock, config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str:
    accent = config["accent"]
    content = block.content if isinstance(block.content, dict) else {}
    alt = str(content.get("alt") or "原稿图片").strip()
    caption = _reliable_image_caption(alt)
    frame_variant = _image_frame_variant(config)
    return (
        f'<section id="{html.escape(block.id)}" class="source-image-anchor"{caption_metrics_attribute(reading)} '
        f'data-image-frame="{frame_variant}" data-image-caption="{html.escape(caption, quote=True)}" {_custom_image_metadata(config)} '
        f'style="{_image_placeholder_style(config)}">'
        f'<span style="display:inline-block;margin-bottom:8px;color:{accent};font:700 10px/1.2 Arial;letter-spacing:.14em;">'
        'SOURCE IMAGE · WAITING</span>'
        f'<p style="margin:0;color:#34403E;font-size:14px;font-weight:700;line-height:1.6;">{_inline(alt)}</p>'
        '<p style="margin:5px 0 0;color:#7A8381;font-size:11px;line-height:1.5;">原稿图片未加载，请在预检清单中上传真实资产</p>'
        '</section>'
    )


def _render_fixed_footer(footer: dict[str, Any], config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str:
    if not footer.get("enabled", False):
        return ""
    from .theme_layouts import render_layout

    custom = render_layout("closing_cta", {
        "body": str(footer.get("text") or ""),
        "media": {"src": "/api/v1/brand-assets/current/content", "alt": footer.get("alt_text", "品牌固定页尾")} if footer.get("asset_path") else None,
    }, config, field_roles={"body": BRAND_FOOTER}, reading=reading)
    if custom is not None:
        return f'<footer data-content-role="brand-cta">{custom}</footer>'
    palette = config.get("palette", {})
    accent = config["accent"]
    frame_variant = _image_frame_variant(config)
    footer_text = render_authored_text(html.escape(str(footer.get("text") or "")), BRAND_FOOTER, reading)
    footer_alt = html.escape(str(footer.get("alt_text") or "品牌固定页尾"))
    image = (
        f'<img src="/api/v1/brand-assets/current/content" alt="{footer_alt}" '
        'style="display:block;width:100%;height:auto;margin:0 auto;border:0;" />'
        if footer.get("asset_path")
        else ""
    )
    if frame_variant == "warm_storybook" and config.get("theme_kit") == "warm_storybook_v1":
        paper = palette.get("secondary_pale", "#FBF2D8")
        rust = palette.get("primary", accent)
        line = '<span style="display:inline-block;width:22%;margin-top:9px;border-top:1px solid #D7B995;vertical-align:top;">&#160;</span>'
        seal = (
            f'<span style="box-sizing:border-box;display:inline-block;width:26px;height:19px;margin:0 10px;border:1px solid {rust};'
            f'border-radius:3px 1px 3px 1px;background-color:{paper};text-align:center;vertical-align:top;">'
            f'<span style="box-sizing:border-box;display:inline-block;width:11px;height:11px;margin-top:0;border-left:1px solid {rust};border-bottom:1px solid {rust};vertical-align:top;transform:rotate(-45deg);">&#160;</span></span>'
        )
        text = (
            f'<p style="margin:0 0 {12 if image else 0}px;padding:0 7px;color:{rust};font-family:Georgia,\'Noto Serif SC\',serif;font-size:16px;font-weight:650;line-height:1.85;overflow-wrap:anywhere;">{footer_text}</p>'
            if footer_text else ""
        )
        return (
            f'<footer data-content-role="brand-cta" data-image-frame="{frame_variant}" data-theme-grammar="warm-letter-signoff" style="margin:36px 0 0;padding:0 4px;text-align:center;">'
            f'<section data-theme-decoration="warm-letter-seal" aria-hidden="true" style="margin:0 0 10px;text-align:center;line-height:19px;font-size:1px;">{line}{seal}{line}</section>'
            f'{text}{image}</footer>'
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
