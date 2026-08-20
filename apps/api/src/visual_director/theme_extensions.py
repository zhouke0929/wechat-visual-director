from __future__ import annotations

import html
import re
from typing import Any

from .parser import ParsedArticle


EXTENDED_THEME_KITS: dict[str, dict[str, Any]] = {
    "oriental_archive": {
        "label": "新中式雅集",
        "english": "ORIENTAL ARCHIVE",
        "description": "以题签、印记、册页边框和克制留白组织文化叙事，不复制传统公文模板。",
        "ideal_for": ["文化故事", "节日风物", "历史人物", "品牌叙事"],
        "personality": ["东方", "雅致", "含蓄"],
        "palette": ["#7A2E2E", "#B58A4A", "#68705C", "#FFFDF7"],
        "grammar": "oriental",
        "component_prefix": "雅集",
        "configuration": {
            "heading_variant": "oriental_folio",
            "key_point_variant": "seal_highlight",
            "quote_variant": "scroll_quote",
            "list_variant": "folio_index",
            "table_variant": "archive_ledger",
            "theme_kit": "oriental_archive_v1",
            "accent": "#7A2E2E",
            "palette": {
                "primary": "#7A2E2E",
                "secondary": "#B58A4A",
                "accent": "#A54838",
                "sky": "#87937A",
                "pale": "#F4F1E7",
                "secondary_pale": "#F7EFDC",
                "accent_pale": "#F5E9E4",
                "sky_pale": "#EEF0E8",
                "surface": "#FFFDF7",
                "ink": "#302C27",
            },
        },
        "visual_dna": {
            "dna": {"warmth": .72, "saturation": .32, "contrast": .58, "geometry": .30, "tactility": .82, "dimensionality": .12, "energy": .34, "information_density": .52, "brand_formality": .78},
            "material_tags": ["rice_paper", "ink_rule", "seal_mark", "folio_page"],
            "palette_family": "oriental_earth",
            "palette_variants": {"cinnabar_ink": ["warm_ivory", "cinnabar", "aged_gold", "sage_ink"]},
            "surface_variants": ["rice_paper_folio", "bound_archive_page"],
            "tone": ["东方", "雅致", "克制"],
        },
    },
    "vintage_press": {
        "label": "复古报刊",
        "english": "VINTAGE PRESS",
        "description": "以粗细版线、剪报栏、日期戳和新闻索引建立事件感与材料感。",
        "ideal_for": ["事件追踪", "人物采访", "行业观察", "城市故事"],
        "personality": ["纪实", "锐利", "有年代感"],
        "palette": ["#1F2523", "#B64032", "#C49A52", "#FBF5E8"],
        "grammar": "press",
        "component_prefix": "报刊",
        "configuration": {
            "heading_variant": "press_masthead",
            "key_point_variant": "news_highlight",
            "quote_variant": "press_quote",
            "list_variant": "news_register",
            "table_variant": "press_matrix",
            "theme_kit": "vintage_press_v1",
            "accent": "#1F2523",
            "palette": {
                "primary": "#1F2523",
                "secondary": "#C49A52",
                "accent": "#B64032",
                "sky": "#76827E",
                "pale": "#F1EBDD",
                "secondary_pale": "#F5E8C9",
                "accent_pale": "#F4E3DE",
                "sky_pale": "#E9ECE7",
                "surface": "#FBF5E8",
                "ink": "#202422",
            },
        },
        "visual_dna": {
            "dna": {"warmth": .58, "saturation": .26, "contrast": .90, "geometry": .54, "tactility": .76, "dimensionality": .08, "energy": .68, "information_density": .78, "brand_formality": .74},
            "material_tags": ["newsprint", "ink_rule", "date_stamp", "paper_clipping"],
            "palette_family": "newsprint_red",
            "palette_variants": {"black_red": ["newsprint", "carbon_ink", "editorial_red", "aged_gold"]},
            "surface_variants": ["aged_newsprint", "clipped_press_page"],
            "tone": ["纪实", "鲜明", "材料感"],
        },
    },
    "pop_poster": {
        "label": "波普海报",
        "english": "POP POSTER",
        "description": "以超大标签、撞色切块、错位贴纸和强节奏编号制造高辨识度的传播画面。",
        "ideal_for": ["活动宣传", "新品发布", "热点话题", "营销内容"],
        "personality": ["醒目", "有趣", "高能量"],
        "palette": ["#14213D", "#FFB703", "#F2385A", "#F7F7F2"],
        "grammar": "pop",
        "component_prefix": "波普",
        "configuration": {
            "heading_variant": "pop_billboard",
            "key_point_variant": "poster_highlight",
            "quote_variant": "pop_quote",
            "list_variant": "poster_stack",
            "table_variant": "poster_matrix",
            "theme_kit": "pop_poster_v1",
            "accent": "#14213D",
            "palette": {
                "primary": "#14213D",
                "secondary": "#FFB703",
                "accent": "#F2385A",
                "sky": "#34A0A4",
                "pale": "#EEF1F7",
                "secondary_pale": "#FFF2BF",
                "accent_pale": "#FFE7EC",
                "sky_pale": "#E2F3F1",
                "surface": "#FDFDF8",
                "ink": "#18213A",
            },
        },
        "visual_dna": {
            "dna": {"warmth": .48, "saturation": .88, "contrast": .92, "geometry": .70, "tactility": .48, "dimensionality": .18, "energy": .96, "information_density": .62, "brand_formality": .28},
            "material_tags": ["poster_paper", "sticker_cut", "marker_ink", "offset_print"],
            "palette_family": "pop_primary",
            "palette_variants": {"navy_yellow": ["paper_white", "deep_navy", "signal_yellow", "hot_pink"]},
            "surface_variants": ["offset_poster", "layered_sticker_wall"],
            "tone": ["醒目", "活力", "传播感"],
        },
    },
    "natural_atlas": {
        "label": "自然图鉴",
        "english": "NATURAL ATLAS",
        "description": "以标本标签、有机曲线、观察编号和自然纸色组织温和而清晰的知识内容。",
        "ideal_for": ["生活方式", "健康科普", "旅行观察", "可持续议题"],
        "personality": ["自然", "平静", "有观察感"],
        "palette": ["#3F6B57", "#C7924F", "#A8674E", "#FBFAF3"],
        "grammar": "atlas",
        "component_prefix": "图鉴",
        "configuration": {
            "heading_variant": "atlas_specimen",
            "key_point_variant": "specimen_highlight",
            "quote_variant": "field_note_quote",
            "list_variant": "specimen_path",
            "table_variant": "atlas_matrix",
            "theme_kit": "natural_atlas_v1",
            "accent": "#3F6B57",
            "palette": {
                "primary": "#3F6B57",
                "secondary": "#C7924F",
                "accent": "#A8674E",
                "sky": "#83A59A",
                "pale": "#EDF2E9",
                "secondary_pale": "#F5EBD7",
                "accent_pale": "#F3E6DF",
                "sky_pale": "#E8F0ED",
                "surface": "#FBFAF3",
                "ink": "#2E3A33",
            },
        },
        "visual_dna": {
            "dna": {"warmth": .66, "saturation": .30, "contrast": .42, "geometry": .20, "tactility": .72, "dimensionality": .14, "energy": .30, "information_density": .48, "brand_formality": .54},
            "material_tags": ["botanical_paper", "specimen_label", "pencil_line", "organic_curve"],
            "palette_family": "botanical_earth",
            "palette_variants": {"fern_ochre": ["paper_white", "fern_green", "ochre", "clay"]},
            "surface_variants": ["field_notebook", "botanical_specimen_page"],
            "tone": ["自然", "安静", "观察"],
        },
    },
    "business_review": {
        "label": "商业画报",
        "english": "BUSINESS REVIEW",
        "description": "以执行摘要、指标栏、深色页眉和金属色细线呈现克制的商业判断。",
        "ideal_for": ["商业分析", "职场方法", "产品案例", "品牌洞察"],
        "personality": ["专业", "高级", "有决策感"],
        "palette": ["#17324D", "#C2E25B", "#ED6A5A", "#F7F4EB"],
        "grammar": "business",
        "component_prefix": "商业",
        "configuration": {
            "heading_variant": "business_review",
            "key_point_variant": "executive_highlight",
            "quote_variant": "executive_quote",
            "list_variant": "executive_register",
            "table_variant": "business_matrix",
            "theme_kit": "business_review_v1",
            "accent": "#1E2930",
            "palette": {
                "primary": "#17324D",
                "secondary": "#C2E25B",
                "accent": "#ED6A5A",
                "sky": "#6A8FA3",
                "pale": "#EFF2E8",
                "secondary_pale": "#EEF6C8",
                "accent_pale": "#F9E1DA",
                "sky_pale": "#E5EDF0",
                "surface": "#F7F4EB",
                "ink": "#203243",
            },
        },
        "visual_dna": {
            "dna": {"warmth": .42, "saturation": .55, "contrast": .82, "geometry": .70, "tactility": .32, "dimensionality": .24, "energy": .72, "information_density": .80, "brand_formality": .88},
            "material_tags": ["editorial_print", "signal_diagram", "orbit_mark", "index_disc", "data_surface"],
            "palette_family": "executive_signal",
            "palette_variants": {"signal_lime_coral": ["paper_white", "deep_navy", "lime_signal", "coral_accent"]},
            "surface_variants": ["clean_editorial_stock", "signal_map_page"],
            "tone": ["专业", "鲜明", "行动感"],
        },
    },
    "cinematic_story": {
        "label": "电影叙事",
        "english": "CINEMATIC STORY",
        "description": "以分镜、字幕条、场次标记和宽银幕留白推动人物、案例与品牌故事。",
        "ideal_for": ["人物故事", "案例复盘", "品牌纪录", "访谈评论"],
        "personality": ["叙事", "沉浸", "有画面感"],
        "palette": ["#553B5D", "#F2A65A", "#D35A54", "#FAF4E8"],
        "grammar": "cinema",
        "component_prefix": "电影",
        "configuration": {
            "heading_variant": "cinema_scene",
            "key_point_variant": "subtitle_highlight",
            "quote_variant": "subtitle_quote",
            "list_variant": "scene_sequence",
            "table_variant": "cinema_matrix",
            "theme_kit": "cinematic_story_v1",
            "accent": "#191919",
            "palette": {
                "primary": "#553B5D",
                "secondary": "#F2A65A",
                "accent": "#D35A54",
                "sky": "#62969D",
                "pale": "#F2E9DD",
                "secondary_pale": "#FCE8C8",
                "accent_pale": "#F8DEDA",
                "sky_pale": "#DDEBED",
                "surface": "#FAF4E8",
                "ink": "#332B36",
            },
        },
        "visual_dna": {
            "dna": {"warmth": .60, "saturation": .46, "contrast": .66, "geometry": .44, "tactility": .72, "dimensionality": .16, "energy": .58, "information_density": .56, "brand_formality": .68},
            "material_tags": ["festival_program", "film_frame", "storyboard_strip", "paper_ticket", "matte_paper"],
            "palette_family": "festival_warm",
            "palette_variants": {"plum_apricot": ["paper_white", "muted_plum", "apricot", "brick_red"]},
            "surface_variants": ["film_festival_program", "light_storyboard_page"],
            "tone": ["叙事", "温暖", "镜头感"],
        },
    },
}


EXTENDED_THEME_IDS = tuple(EXTENDED_THEME_KITS)
EXTENDED_THEME_VISUAL_DNA = {
    theme_id: kit["visual_dna"] for theme_id, kit in EXTENDED_THEME_KITS.items()
}

COMPONENT_LABELS = {
    "question_hook": "开篇提问",
    "numbered_insight": "观点索引",
    "evidence_callout": "证据摘录",
    "before_after_timeline": "前后转折",
    "logic_path": "逻辑路径",
    "concept_explainer": "概念解释",
    "case_card": "案例切片",
    "warning_note": "风险提示",
    "action_checklist": "行动清单",
    "case_points": "案例差异",
    "key_points": "要点拆解",
    "faq_card": "问答片段",
    "comparison_card": "对照观点",
    "section_summary": "阶段小结",
}


def _list_heading(grammar: str, component_type: str, label: str) -> str:
    """Return a theme-flavoured heading without changing the list's meaning."""
    if grammar == "press":
        return f"CLIPPING · {label}"
    if grammar == "atlas":
        return f"OBSERVATION LOG / {label}"
    if grammar == "business":
        return f"SIGNAL MAP / {label}"
    if grammar == "cinema":
        prefix = {
            "action_checklist": "SHOT LIST",
            "case_points": "CASE NOTES",
            "key_points": "SCENE NOTES",
        }.get(component_type, "SCENE NOTES")
        return f"{prefix} / {label}"
    return label


def extended_variant_name(theme_id: str, component_type: str) -> str:
    return f"{theme_id}__{component_type}"


def extended_variant_theme(variant: str) -> str | None:
    theme_id, separator, _ = variant.partition("__")
    return theme_id if separator and theme_id in EXTENDED_THEME_KITS else None


def extended_component_label(theme_id: str, component_type: str) -> str:
    return f"{EXTENDED_THEME_KITS[theme_id]['component_prefix']}·{COMPONENT_LABELS.get(component_type, component_type)}"


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("\n", "<br>")


def _resolve(parsed: ParsedArticle, reference: str) -> str:
    block_id, _, item_index = reference.partition(":item:")
    block = next(block for block in parsed.blocks if block.id == block_id)
    if item_index:
        return str(block.content[int(item_index)])
    return str(block.content)


def _one(parsed: ParsedArticle, bindings: dict[str, Any], role: str) -> str:
    value = bindings[role]
    if isinstance(value, list):
        value = value[0]
    return _resolve(parsed, str(value))


def _many(parsed: ParsedArticle, bindings: dict[str, Any], role: str) -> list[str]:
    value = bindings[role]
    values = value if isinstance(value, list) else [value]
    return [_resolve(parsed, str(item)) for item in values]


def _payload(slot: dict[str, Any], parsed: ParsedArticle) -> dict[str, Any]:
    component_type = str(slot["component_type"])
    bindings = slot["content_bindings"]
    if component_type in {"numbered_insight", "logic_path", "action_checklist", "section_summary"}:
        return {"kind": "list", "items": _many(parsed, bindings, "items")}
    if component_type in {"before_after_timeline", "comparison_card"}:
        left_role, right_role = ("before", "after") if component_type == "before_after_timeline" else ("left", "right")
        return {"kind": "pair", "left": _one(parsed, bindings, left_role), "right": _one(parsed, bindings, right_role)}
    if component_type == "concept_explainer":
        if "related_titles" in bindings and "related_definitions" in bindings:
            titles = [_one(parsed, bindings, "title"), *_many(parsed, bindings, "related_titles")]
            definitions = [_one(parsed, bindings, "definition"), *_many(parsed, bindings, "related_definitions")]
            return {
                "kind": "concept_group",
                "entries": [
                    {"title": title, "body": definition}
                    for title, definition in zip(titles, definitions, strict=True)
                ],
            }
        return {"kind": "title_body", "title": _one(parsed, bindings, "title"), "body": _one(parsed, bindings, "definition")}
    if component_type == "case_card":
        return {"kind": "title_body", "title": _one(parsed, bindings, "title"), "body": _one(parsed, bindings, "body")}
    if component_type == "faq_card":
        return {"kind": "title_body", "title": _one(parsed, bindings, "question"), "body": _one(parsed, bindings, "answer")}
    if component_type == "question_hook":
        return {"kind": "title_body", "title": _one(parsed, bindings, "title"), "body": ""}
    role = "evidence" if component_type == "evidence_callout" else "body"
    return {"kind": "single", "body": _one(parsed, bindings, role)}


def _palette(palette: dict[str, str]) -> dict[str, str]:
    primary = palette.get("primary", "#263331")
    return {
        "primary": primary,
        "secondary": palette.get("secondary", primary),
        "accent": palette.get("accent", primary),
        "sky": palette.get("sky", primary),
        "pale": palette.get("pale", "#F4F4F0"),
        "secondary_pale": palette.get("secondary_pale", "#F7F1DE"),
        "accent_pale": palette.get("accent_pale", "#F6E9E4"),
        "sky_pale": palette.get("sky_pale", "#EDF1F0"),
        "surface": palette.get("surface", "#FFFEFA"),
        "ink": palette.get("ink", "#263331"),
    }


def _sticker(name: str, style: str, alt: str = "") -> str:
    return (
        f'<img src="/api/v1/theme-assets/{html.escape(name)}" alt="{html.escape(alt)}" '
        f'style="display:block;max-width:100%;height:auto;{style}" />'
    )


def _sticker_overlay(
    name: str,
    width: str,
    *,
    align: str = "right",
    translate_y: str = "-42%",
    opacity: str = ".84",
    rotate: str = "0deg",
) -> str:
    """Overlay a decoration without letting its transparent canvas add whitespace."""
    return (
        '<section data-decoration-layer="overlay" '
        f'style="height:0;line-height:0;overflow:visible;text-align:{align};">'
        f'{_sticker(name, f"display:inline-block;width:{width};margin:0 2%;opacity:{opacity};transform:translateY({translate_y}) rotate({rotate});vertical-align:top;")}'
        '</section>'
    )


REDESIGNED_GRAMMARS = {"oriental", "press", "atlas", "business", "cinema"}


def _decorate_payload(
    grammar: str,
    component_type: str,
    markup: str,
    p: dict[str, str],
) -> str:
    if grammar == "oriental":
        if component_type not in {"numbered_insight", "concept_explainer", "logic_path"}:
            return markup
        asset = "oriental-branch.png" if component_type in {"numbered_insight", "logic_path"} else "oriental-seal.png"
        width = "42%" if asset == "oriental-branch.png" else "12%"
        return f'<section data-theme-decoration="oriental-sticker">{_sticker_overlay(asset, width)}{markup}</section>'
    if grammar == "press":
        if component_type not in {"action_checklist", "evidence_callout", "logic_path"}:
            return markup
        asset = "press-tape.png" if component_type in {"action_checklist", "logic_path"} else "press-burst.png"
        width = "54%" if asset == "press-tape.png" else "13%"
        return f'<section data-theme-decoration="press-sticker">{_sticker_overlay(asset, width, align="center", opacity=".9", rotate="-2deg")}{markup}</section>'
    if grammar == "atlas":
        if component_type not in {"numbered_insight", "concept_explainer", "action_checklist"}:
            return markup
        asset = "atlas-leaf.png" if component_type in {"numbered_insight", "action_checklist"} else "atlas-flower.png"
        width = "19%" if asset == "atlas-leaf.png" else "13%"
        return f'<section data-theme-decoration="atlas-sticker">{_sticker_overlay(asset, width, opacity=".78")}{markup}</section>'
    if grammar == "business":
        if component_type == "numbered_insight":
            return markup
        if component_type == "concept_explainer":
            return f'<section data-theme-decoration="business-orbit-overlay">{_sticker_overlay("business-orbit.png", "13%", align="right", translate_y="-18%", opacity=".78")}{markup}</section>'
        if component_type == "evidence_callout":
            return f'<section data-theme-decoration="business-signal-overlay">{_sticker_overlay("business-signal.png", "22%", align="left", translate_y="-28%", opacity=".82")}{markup}</section>'
        return markup
    # Film-festival editorial: keep the rhythm of scenes without turning the
    # whole article into a black contact sheet.
    light_markup = markup.replace(
        f"background-color:{p['primary']}",
        f"background-color:{p['surface']}",
    ).replace("color:#FFFFFF", f"color:{p['primary']}")
    if component_type not in {"numbered_insight", "concept_explainer", "logic_path"}:
        return light_markup
    asset = "cinema-clapper.png" if component_type in {"numbered_insight", "logic_path"} else "cinema-reel.png"
    width = "27%" if asset == "cinema-clapper.png" else "18%"
    return f'<section data-theme-decoration="film-festival-sticker">{_sticker_overlay(asset, width, opacity=".88")}{light_markup}</section>'


def _distinct_payload_html(grammar: str, component_type: str, payload: dict[str, Any], p: dict[str, str]) -> str:
    """Render five materially different reading grammars without theme recolors."""
    kind = payload["kind"]
    label = COMPONENT_LABELS.get(component_type, component_type)
    if kind == "concept_group":
        if grammar == "cinema":
            entries = "".join(
                f'<section style="margin:0 0 17px;white-space:normal;"><span style="display:inline-block;width:24%;padding:7px 10px 0 0;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.18em;vertical-align:top;">CAST {index:02d}</span><section style="box-sizing:border-box;display:inline-block;width:76%;padding:5px 0 13px 17px;border-left:1px dashed {p["primary"]};border-bottom:2px solid {p["secondary"]};vertical-align:top;"><strong style="display:block;color:{p["primary"]};font-family:Georgia,Noto Serif SC,serif;font-size:18px;line-height:1.55;">{_inline(entry["title"])}</strong><p style="margin:9px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{_inline(entry["body"])}</p></section></section>'
                for index, entry in enumerate(payload["entries"], 1)
            )
            return f'<section data-content-role="concept-glossary" data-theme-grammar="cast-dossier" style="margin:32px 0;padding:15px 0 2px;border-top:1px dashed {p["primary"]};border-bottom:1px dashed {p["primary"]};"><p style="margin:-24px 0 18px;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.24em;">CAST DOSSIER / 概念角色表</p>{entries}</section>'
        entries = "".join(
            _distinct_payload_html(
                grammar,
                component_type,
                {"kind": "title_body", "title": entry["title"], "body": entry["body"]},
                p,
            )
            for entry in payload["entries"]
        )
        wrappers = {
            "oriental": f"margin:31px 0;padding:5px 0 3px 22px;border-left:1px solid {p['secondary']};",
            "press": f"margin:31px 0;padding:15px 12px 5px;background-color:{p['pale']};border:1px dashed {p['secondary']};",
            "atlas": f"margin:31px 0;padding:16px 12px 5px 30px;border-left:2px dotted {p['sky']};background-color:{p['surface']};",
            "business": f"margin:31px 0;border-top:1px solid {p['primary']};",
            "cinema": f"margin:31px 0;padding:13px 0;border-top:1px dashed {p['primary']};border-bottom:1px dashed {p['primary']};",
        }
        return f'<section data-content-role="concept-glossary" style="{wrappers[grammar]}">{entries}</section>'

    if kind == "list":
        items = [_inline(item) for item in payload["items"]]
        list_heading = _list_heading(grammar, component_type, label)
        if grammar == "oriental":
            rows = "".join(
                f'<section style="margin:0 0 16px;white-space:normal;"><span style="display:inline-block;width:17%;padding-top:2px;color:{p["accent"]};font-family:Georgia,serif;font-size:12px;letter-spacing:.12em;vertical-align:top;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:83%;margin:0;padding:0 0 13px 16px;border-left:1px solid {p["secondary"]};border-bottom:1px solid #E5DCCB;color:{p["ink"]};font-size:14px;line-height:1.82;vertical-align:top;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-theme-grammar="bound-folio" data-list-role="{component_type}" style="margin:31px 0;padding:19px 0 3px 24px;background-color:{p["surface"]};"><p style="margin:0 0 18px -24px;color:{p["primary"]};font-size:9px;letter-spacing:.28em;">— {list_heading}</p>{rows}</section>'
        if grammar == "press":
            rows = "".join(
                f'<section style="margin:0 0 10px;padding:11px 12px;background-color:{p["surface"]};border:1px solid #C9BAA0;box-shadow:3px 3px 0 {p["secondary_pale"]};white-space:normal;transform:rotate({-0.35 if index % 2 else 0.35}deg);"><span style="display:inline-block;width:13%;color:{p["accent"]};font-family:Georgia,serif;font-size:19px;font-weight:900;vertical-align:top;">{index}</span><p style="box-sizing:border-box;display:inline-block;width:87%;margin:0;padding-left:12px;border-left:1px dashed #978B78;color:{p["ink"]};font-family:Georgia,Noto Serif SC,serif;font-size:14px;line-height:1.72;vertical-align:top;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-theme-grammar="clipping-stack" data-list-role="{component_type}" style="margin:31px 0;padding:18px 13px 8px;background-color:{p["pale"]};border-top:1px dashed {p["accent"]};border-bottom:1px dashed {p["accent"]};"><p style="margin:-29px 0 15px;text-align:center;"><span style="display:inline-block;padding:4px 13px;background-color:{p["accent"]};color:#FFFFFF;font-size:8px;letter-spacing:.18em;transform:rotate(-2deg);">{list_heading}</span></p>{rows}</section>'
        if grammar == "atlas":
            rows = "".join(
                f'<section style="margin:0 0 13px;white-space:normal;"><span style="display:inline-block;width:34px;height:34px;margin-left:-24px;border:1px solid {p["primary"]};border-radius:50%;background-color:{p["surface"]};color:{p["primary"]};font:700 10px/34px Georgia;text-align:center;vertical-align:top;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:87%;margin:0;padding:3px 0 12px 15px;border-bottom:1px solid #D8E0D4;color:{p["ink"]};font-size:14px;line-height:1.8;vertical-align:top;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-theme-grammar="field-log" data-list-role="{component_type}" style="margin:31px 0;padding:18px 12px 5px 32px;border-left:2px dotted {p["sky"]};background:repeating-linear-gradient(0deg,{p["surface"]}, {p["surface"]} 31px, {p["sky_pale"]} 32px);"><p style="margin:-28px 0 18px;color:{p["primary"]};font:700 9px/1.2 Georgia;letter-spacing:.22em;">{list_heading}</p>{rows}</section>'
        if grammar == "business":
            rows = "".join(
                f'<section style="margin:0 0 13px;white-space:normal;transform:translateX({0 if index % 2 else 12}px);"><span style="display:inline-block;width:38px;height:38px;border-radius:50%;background-color:{p["secondary"] if index % 2 else p["accent"]};color:{p["primary"]};font:800 13px/38px Georgia;text-align:center;vertical-align:middle;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:78%;margin:0 0 0 10px;padding:10px 14px 11px;border-bottom:2px solid {p["primary"]};color:{p["ink"]};font-size:14px;font-weight:650;line-height:1.72;vertical-align:middle;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-theme-grammar="signal-orbit" data-list-role="{component_type}" style="margin:31px 0;padding:9px 12px 2px 0;"><p style="margin:0 0 17px;color:{p["accent"]};font-size:8px;font-weight:800;letter-spacing:.22em;text-align:right;">{list_heading}</p>{rows}</section>'
        rows = "".join(
            f'<section style="margin:0 0 11px;padding-left:{0 if index % 2 else 8}%;white-space:normal;"><span style="display:inline-block;width:20%;padding:11px 5px;color:{p["accent"]};font:700 9px/1.3 Georgia;letter-spacing:.12em;vertical-align:top;">{index:02d}:00</span><p style="box-sizing:border-box;display:inline-block;width:{80 if index % 2 else 72}%;margin:0;padding:10px 13px 11px;border-left:2px solid {p["accent"]};border-bottom:1px dashed {p["primary"]};color:{p["ink"]};font-size:14px;line-height:1.75;vertical-align:top;">{item}</p></section>'
            for index, item in enumerate(items, 1)
        )
        return f'<section data-theme-grammar="storyboard-track" data-list-role="{component_type}" style="margin:32px 0;padding:13px 0 3px;border-top:4px solid {p["primary"]};"><p style="margin:0 0 16px;color:{p["secondary"]};font:700 8px/1.2 Georgia;letter-spacing:.24em;">{list_heading}</p>{rows}</section>'

    if kind == "pair":
        left, right = _inline(payload["left"]), _inline(payload["right"])
        if grammar == "oriental":
            return f'<section data-theme-grammar="folding-page" style="margin:32px 0;padding:12px 0;border-top:1px solid {p["secondary"]};border-bottom:1px solid {p["secondary"]};white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:49%;padding:8px 22px 18px 6px;vertical-align:top;"><span style="color:{p["accent"]};font-size:9px;letter-spacing:.2em;">其一</span><p style="margin:15px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{left}</p></section><section style="box-sizing:border-box;display:inline-block;width:49%;margin-top:28px;padding:8px 7px 18px 22px;border-left:1px solid #D9CCB5;background-color:{p["pale"]};vertical-align:top;"><span style="color:{p["primary"]};font-size:9px;letter-spacing:.2em;">其二</span><p style="margin:15px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{right}</p></section></section>'
        if grammar == "press":
            return f'<section data-theme-grammar="two-column-clipping" style="margin:32px 0;padding:14px;background-color:{p["pale"]};border:1px dashed #A99A81;white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:48%;padding:13px;background-color:{p["surface"]};border:1px solid #C9BAA0;transform:rotate(-1deg);vertical-align:top;"><b style="color:{p["accent"]};font:900 20px Georgia;">A</b><p style="margin:9px 0 0;color:{p["ink"]};font-family:Georgia,Noto Serif SC,serif;font-size:14px;line-height:1.75;">{left}</p></section><section style="box-sizing:border-box;display:inline-block;width:48%;margin:22px 0 0 4%;padding:13px;background-color:{p["secondary_pale"]};border:1px solid #C9BAA0;transform:rotate(1deg);vertical-align:top;"><b style="color:{p["primary"]};font:900 20px Georgia;">B</b><p style="margin:9px 0 0;color:{p["ink"]};font-family:Georgia,Noto Serif SC,serif;font-size:14px;line-height:1.75;">{right}</p></section></section>'
        if grammar == "atlas":
            return f'<section data-theme-grammar="specimen-comparison" style="margin:32px 0;padding:16px 11px 12px 27px;border-left:2px dotted {p["sky"]};background-color:{p["surface"]};white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:46%;padding:15px 12px;border-bottom:2px solid {p["primary"]};vertical-align:top;"><span style="display:block;width:18px;height:18px;margin-bottom:12px;border:1px solid {p["primary"]};border-radius:50%;"></span><p style="margin:0;color:{p["ink"]};font-size:14px;line-height:1.78;">{left}</p></section><section style="box-sizing:border-box;display:inline-block;width:46%;margin:26px 0 0 8%;padding:15px 12px;border-top:2px solid {p["accent"]};background-color:{p["pale"]};vertical-align:top;"><p style="margin:0 0 12px;color:{p["ink"]};font-size:14px;line-height:1.78;">{right}</p><span style="display:block;width:26px;height:13px;margin-left:auto;border-radius:80% 0 80% 0;background-color:{p["accent"]};transform:rotate(-14deg);"></span></section></section>'
        if grammar == "business":
            return f'<section data-theme-grammar="decision-spread" style="margin:34px 0;padding:7px 0 16px;white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:45%;padding:15px 17px 19px;border-radius:42px 42px 8px 42px;background-color:{p["secondary_pale"]};vertical-align:top;transform:rotate(-1deg);"><span style="display:block;color:{p["secondary"]};font:800 24px Georgia;">A</span><p style="margin:8px 0 0;color:{p["ink"]};font-size:13px;line-height:1.75;">{left}</p></section><section style="box-sizing:border-box;display:inline-block;width:51%;margin:34px 0 0 4%;padding:17px 17px 16px;border-radius:8px 42px 42px 42px;background-color:{p["sky_pale"]};vertical-align:top;transform:rotate(1deg);"><span style="color:{p["accent"]};font-size:8px;letter-spacing:.2em;">ALTERNATIVE B</span><p style="margin:10px 0 0;color:{p["ink"]};font-size:15px;font-weight:650;line-height:1.78;">{right}</p></section></section>'
        return f'<section data-theme-grammar="shot-reverse-shot" style="margin:34px 0;padding:8px 0 15px;white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:58%;padding:16px 15px 18px;border:1px solid {p["primary"]};border-radius:3px 24px 3px 24px;background-color:{p["surface"]};box-shadow:6px 6px 0 {p["secondary_pale"]};vertical-align:top;transform:rotate(-.7deg);"><span style="color:{p["accent"]};font:700 8px Georgia;letter-spacing:.18em;">SHOT A / WIDE</span><p style="margin:12px 0 0;color:{p["ink"]};font-size:14px;line-height:1.78;">{left}</p></section><section style="box-sizing:border-box;display:inline-block;width:38%;margin:43px 0 0 4%;padding:15px 13px;border-radius:22px 3px 22px 3px;background-color:{p["accent_pale"]};color:{p["primary"]};vertical-align:top;transform:rotate(1deg);"><span style="font:700 8px Georgia;letter-spacing:.18em;">REVERSE / CLOSE</span><p style="margin:12px 0 0;font-size:13px;line-height:1.75;">{right}</p></section></section>'

    if kind == "title_body":
        title, body = _inline(payload["title"]), _inline(payload["body"])
        body_html = f'<p style="margin:12px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{body}</p>' if body else ""
        if grammar == "oriental":
            return f'<section data-theme-grammar="title-slip" style="margin:31px 0;padding:4px 0 17px 26px;border-left:1px solid {p["secondary"]};"><p style="margin:0 0 17px -26px;"><span style="display:inline-block;padding:4px 12px;background-color:{p["accent_pale"]};color:{p["accent"]};font-size:9px;letter-spacing:.22em;">{label}</span></p><strong style="display:block;color:{p["primary"]};font-family:Georgia,Noto Serif SC,serif;font-size:19px;line-height:1.55;">{title}</strong>{body_html}<p style="width:42%;height:1px;margin:16px 0 0;background-color:{p["secondary"]};"></p></section>'
        if grammar == "press":
            return f'<section data-theme-grammar="news-clipping" style="margin:31px 5px;padding:16px 15px;background-color:{p["surface"]};border:1px solid #C9BAA0;box-shadow:5px 5px 0 {p["secondary_pale"]};transform:rotate(-.35deg);"><p style="margin:-25px 0 13px;text-align:right;"><span style="display:inline-block;padding:4px 10px;background-color:{p["accent"]};color:#FFFFFF;font-size:8px;letter-spacing:.16em;">{label}</span></p><strong style="display:block;padding-bottom:9px;border-bottom:3px double {p["ink"]};color:{p["ink"]};font-family:Georgia,Noto Serif SC,serif;font-size:20px;line-height:1.48;">{title}</strong>{body_html}</section>'
        if grammar == "atlas":
            return f'<section data-theme-grammar="specimen-entry" style="margin:31px 0;padding:17px 14px 16px 30px;border-left:2px dotted {p["sky"]};background-color:{p["surface"]};"><p style="margin:-25px 0 15px -18px;"><span style="display:inline-block;padding:4px 11px;border:1px solid {p["primary"]};border-radius:50% 50% 4px 50%;background-color:{p["surface"]};color:{p["primary"]};font-size:8px;letter-spacing:.16em;">SPECIMEN</span></p><strong style="display:block;color:{p["primary"]};font-family:Georgia,Noto Serif SC,serif;font-size:19px;line-height:1.55;">{title}</strong>{body_html}<span style="display:block;width:31px;height:15px;margin:15px 0 0 auto;border-radius:80% 0 80% 0;background-color:{p["accent"]};transform:rotate(-16deg);"></span></section>'
        if grammar == "business":
            return f'<section data-theme-grammar="executive-brief" style="margin:33px 0;padding:4px 0 9px;white-space:normal;"><span style="display:inline-block;width:72px;height:72px;margin:0 -18px 0 0;border:12px solid {p["secondary_pale"]};border-radius:50%;color:{p["accent"]};font-size:8px;font-weight:800;letter-spacing:.12em;line-height:48px;text-align:center;vertical-align:top;">{label}</span><section style="box-sizing:border-box;display:inline-block;width:78%;padding:13px 0 16px 22px;border-bottom:3px solid {p["primary"]};vertical-align:top;"><strong style="display:block;color:{p["primary"]};font-size:19px;line-height:1.52;">{title}</strong>{body_html}</section></section>'
        return f'<section data-theme-grammar="screenplay-cue" style="margin:33px 0;padding:4px 0 12px 24%;border-bottom:1px dashed {p["primary"]};"><p style="margin:0 0 11px -31%;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.22em;text-align:center;">SCENE / {label}</p><strong style="display:block;color:{p["primary"]};font-family:Georgia,Noto Serif SC,serif;font-size:19px;line-height:1.52;">{title}</strong>{body_html}<p style="margin:13px 0 -5px;color:{p["secondary"]};font:700 8px Georgia;letter-spacing:.18em;text-align:right;">CUT TO →</p></section>'

    body = _inline(payload["body"])
    if grammar == "oriental":
        return f'<blockquote data-theme-grammar="margin-annotation" style="margin:32px 0 32px 16%;padding:5px 0 12px 18px;border-left:1px solid {p["accent"]};color:{p["ink"]};font-family:Georgia,"Noto Serif SC",serif;font-size:17px;line-height:1.9;"><span style="display:block;margin:0 0 9px -19px;color:{p["accent"]};font-size:8px;letter-spacing:.22em;">◈ {label}</span>{body}</blockquote>'
    if grammar == "press":
        return f'<blockquote data-theme-grammar="pull-quote-clipping" style="margin:33px 4px;padding:16px 15px;background-color:{p["secondary_pale"]};border:1px solid #C9BAA0;box-shadow:4px 4px 0 {p["accent_pale"]};color:{p["ink"]};font-family:Georgia,"Noto Serif SC",serif;font-size:18px;font-weight:750;line-height:1.82;transform:rotate(.4deg);"><span style="display:block;margin-bottom:10px;padding-bottom:6px;border-bottom:3px double {p["ink"]};color:{p["accent"]};font-size:8px;letter-spacing:.2em;">PULL QUOTE / {label}</span>{body}</blockquote>'
    if grammar == "atlas":
        return f'<blockquote data-theme-grammar="field-annotation" style="margin:32px 0;padding:18px 17px 18px 31px;border-left:2px dotted {p["sky"]};background-color:{p["pale"]};color:{p["ink"]};font-size:16px;line-height:1.88;"><span style="display:block;margin:0 0 10px -18px;color:{p["primary"]};font:700 8px Georgia;letter-spacing:.22em;">FIELD NOTE / {label}</span>{body}</blockquote>'
    if grammar == "business":
        return f'<blockquote data-theme-grammar="key-signal" style="margin:34px 0;padding:15px 18px 17px 68px;border-radius:8px 38px 38px 38px;background-color:{p["sky_pale"]};color:{p["ink"]};font-size:17px;font-weight:720;line-height:1.85;position:relative;"><span style="display:block;margin:0 0 9px -50px;color:{p["accent"]};font:900 31px/1 Georgia;">↗</span><span style="display:block;margin:-30px 0 10px;color:{p["primary"]};font-size:8px;letter-spacing:.2em;">KEY SIGNAL</span>{body}</blockquote>'
    return f'<blockquote data-theme-grammar="subtitle-cue" style="margin:36px 6% 34px;padding:4px 0 12px;color:{p["primary"]};font-size:17px;font-weight:700;line-height:1.88;text-align:center;"><span style="display:block;margin-bottom:12px;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.22em;text-align:left;">SUBTITLE / {label}</span><span style="display:block;color:{p["secondary"]};font:900 34px/1 Georgia;text-align:left;">“</span>{body}<span style="display:block;width:44%;height:2px;margin:15px auto 0;background-color:{p["accent"]};"></span></blockquote>'


def _payload_html(grammar: str, component_type: str, payload: dict[str, Any], p: dict[str, str]) -> str:
    kind = payload["kind"]
    label = COMPONENT_LABELS.get(component_type, component_type)
    if grammar in REDESIGNED_GRAMMARS:
        return _decorate_payload(
            grammar,
            component_type,
            _distinct_payload_html(grammar, component_type, payload, p),
            p,
        )
    if kind == "concept_group":
        entries = "".join(
            _payload_html(
                grammar,
                component_type,
                {"kind": "title_body", "title": entry["title"], "body": entry["body"]},
                p,
            )
            for entry in payload["entries"]
        )
        return f'<section data-content-role="concept-glossary" style="margin:30px 0;">{entries}</section>'
    if kind == "list":
        items = [_inline(item) for item in payload["items"]]
        list_heading = _list_heading(grammar, component_type, label)
        if grammar == "oriental":
            rows = "".join(
                f'<section style="padding:12px 0;border-top:1px solid #D9CCB5;white-space:normal;"><span style="display:inline-block;width:16%;color:{p["accent"]};font-family:Georgia,serif;font-size:13px;font-weight:800;vertical-align:top;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding-left:13px;border-left:2px solid {p["secondary"]};color:{p["ink"]};font-size:14px;line-height:1.78;vertical-align:top;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-list-role="{component_type}" style="margin:29px 0;padding:7px 18px 13px;border-left:5px solid {p["primary"]};border-bottom:1px solid {p["secondary"]};background-color:{p["surface"]};"><p style="margin:0 0 8px;color:{p["primary"]};font-size:10px;font-weight:800;letter-spacing:.2em;">{list_heading}</p>{rows}</section>'
        if grammar == "press":
            rows = "".join(
                f'<section style="border-top:1px solid {p["ink"]};white-space:normal;"><span style="display:inline-block;width:18%;padding:12px 0;color:{p["accent"]};font-family:Georgia,serif;font-size:22px;font-weight:900;vertical-align:top;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:12px 0 13px 14px;border-left:5px solid {p["primary"]};color:{p["ink"]};font-size:14px;font-weight:650;line-height:1.72;vertical-align:top;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-list-role="{component_type}" style="margin:29px 0;border-top:12px solid {p["primary"]};border-bottom:3px solid {p["primary"]};"><p style="margin:0;padding:7px 0;color:{p["accent"]};font-size:9px;font-weight:900;letter-spacing:.18em;">{list_heading}</p>{rows}</section>'
        if grammar == "pop":
            colors = (p["secondary_pale"], p["accent_pale"], p["sky_pale"])
            rows = "".join(
                f'<section style="margin:0 0 11px;white-space:normal;transform:translateX({5 if index % 2 else 0}px);"><span style="display:inline-block;width:36px;height:29px;background-color:{p["accent"] if index % 2 else p["primary"]};color:#FFFFFF;font-family:Georgia,serif;font-size:12px;font-weight:900;line-height:29px;text-align:center;transform:rotate({-3 if index % 2 else 3}deg);vertical-align:top;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0 0 0 8px;padding:8px 12px 10px;border-bottom:5px solid {p["secondary"]};background-color:{colors[(index-1)%3]};color:{p["ink"]};font-size:14px;font-weight:700;line-height:1.68;vertical-align:top;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-list-role="{component_type}" style="margin:30px 0;padding:18px 13px 7px;border:3px solid {p["primary"]};box-shadow:7px 7px 0 {p["secondary"]};"><p style="margin:-31px 0 16px;"><span style="display:inline-block;padding:5px 12px;background-color:{p["accent"]};color:#FFFFFF;font-size:9px;font-weight:900;letter-spacing:.14em;transform:rotate(-2deg);">{list_heading}</span></p>{rows}</section>'
        if grammar == "atlas":
            rows = "".join(
                f'<section style="margin:0 0 13px;white-space:normal;"><span style="display:inline-block;width:30px;height:30px;margin-left:-17px;border:1px solid {p["primary"]};border-radius:50% 50% 8px 50%;background-color:{p["surface"]};color:{p["primary"]};font-family:Georgia,serif;font-size:10px;font-weight:800;line-height:30px;text-align:center;transform:rotate(-8deg);vertical-align:top;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:87%;margin:0;padding:4px 0 11px 13px;border-bottom:1px dotted {p["sky"]};color:{p["ink"]};font-size:14px;line-height:1.76;vertical-align:top;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-list-role="{component_type}" style="margin:29px 0;padding:16px 13px 6px 21px;border-left:3px dotted {p["sky"]};background-color:{p["pale"]};border-radius:3px 24px 3px 24px;"><p style="margin:-25px 0 15px;color:{p["primary"]};font-size:9px;font-weight:800;letter-spacing:.18em;">{list_heading}</p>{rows}</section>'
        if grammar == "business":
            rows = "".join(
                f'<section style="border-top:1px solid #B8C0C1;white-space:normal;"><span style="display:inline-block;width:20%;padding:12px 7px 11px 0;color:{p["secondary"]};font-family:Georgia,serif;font-size:17px;font-weight:800;vertical-align:top;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:80%;margin:0;padding:11px 0 12px 14px;border-left:1px solid #B8C0C1;color:{p["ink"]};font-size:14px;font-weight:650;line-height:1.72;vertical-align:top;">{item}</p></section>'
                for index, item in enumerate(items, 1)
            )
            return f'<section data-list-role="{component_type}" style="margin:29px 0;border-top:8px solid {p["primary"]};border-bottom:2px solid {p["primary"]};"><p style="margin:0;padding:8px 0;color:{p["accent"]};font-size:9px;font-weight:800;letter-spacing:.18em;text-align:right;">{list_heading}</p>{rows}</section>'
        rows = "".join(
            f'<section style="padding:11px 0;border-top:1px solid #C9C5BC;white-space:normal;"><span style="display:inline-block;width:24%;color:{p["secondary"]};font-family:Georgia,serif;font-size:11px;font-weight:800;letter-spacing:.08em;vertical-align:top;">SCENE {index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:76%;margin:0;padding-left:14px;border-left:5px solid {p["accent"]};color:{p["ink"]};font-size:14px;line-height:1.75;vertical-align:top;">{item}</p></section>'
            for index, item in enumerate(items, 1)
        )
        return f'<section data-list-role="{component_type}" style="margin:30px 0;padding:8px 16px 13px;border-top:12px solid {p["primary"]};border-bottom:12px solid {p["primary"]};background-color:{p["surface"]};"><p style="margin:0 0 7px;color:{p["accent"]};font-size:9px;font-weight:800;letter-spacing:.2em;">{list_heading}</p>{rows}</section>'

    if kind == "pair":
        left, right = _inline(payload["left"]), _inline(payload["right"])
        if grammar == "oriental":
            return f'<section style="margin:30px 0;padding:16px 0;border-top:1px solid {p["secondary"]};border-bottom:1px solid {p["secondary"]};white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:46%;padding:12px 13px;border-right:1px solid #D9CCB5;vertical-align:top;"><span style="color:{p["accent"]};font-family:Georgia,serif;font-size:22px;">壹</span><p style="margin:9px 0 0;color:{p["ink"]};font-size:14px;line-height:1.78;">{left}</p></section><span style="display:inline-block;width:8%;padding-top:55px;color:{p["secondary"]};text-align:center;vertical-align:top;">◆</span><section style="box-sizing:border-box;display:inline-block;width:46%;margin-top:17px;padding:12px 13px;background-color:{p["pale"]};vertical-align:top;"><span style="color:{p["primary"]};font-family:Georgia,serif;font-size:22px;">贰</span><p style="margin:9px 0 0;color:{p["ink"]};font-size:14px;line-height:1.78;">{right}</p></section></section>'
        if grammar in {"press", "business"}:
            top = 11 if grammar == "press" else 7
            return f'<section style="margin:30px 0;border-top:{top}px solid {p["primary"]};border-bottom:2px solid {p["primary"]};white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:44%;min-height:145px;padding:15px 13px;border-right:5px solid {p["accent"]};vertical-align:top;"><span style="color:{p["secondary"]};font-family:Georgia,serif;font-size:20px;font-weight:900;">A</span><p style="margin:10px 0 0;color:{p["ink"]};font-size:14px;line-height:1.76;">{left}</p></section><section style="box-sizing:border-box;display:inline-block;width:56%;min-height:145px;margin-top:17px;padding:15px;background-color:{p["pale"]};vertical-align:top;"><span style="color:{p["primary"]};font-family:Georgia,serif;font-size:14px;font-weight:900;">B / COUNTERPOINT</span><p style="margin:10px 0 0;color:{p["ink"]};font-size:14px;font-weight:650;line-height:1.76;">{right}</p></section></section>'
        if grammar == "pop":
            return f'<section style="margin:31px 0;padding:13px;border:3px solid {p["primary"]};background-color:{p["secondary_pale"]};white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:47%;padding:15px 13px;border-top:8px solid {p["accent"]};background-color:{p["surface"]};transform:rotate(-1deg);vertical-align:top;"><p style="margin:0;color:{p["ink"]};font-size:14px;font-weight:700;line-height:1.75;">{left}</p></section><span style="display:inline-block;width:6%;padding-top:48px;color:{p["primary"]};font-weight:900;text-align:center;vertical-align:top;">×</span><section style="box-sizing:border-box;display:inline-block;width:47%;margin-top:19px;padding:15px 13px;border-bottom:8px solid {p["primary"]};background-color:{p["sky_pale"]};transform:rotate(1deg);vertical-align:top;"><p style="margin:0;color:{p["ink"]};font-size:14px;font-weight:700;line-height:1.75;">{right}</p></section></section>'
        if grammar == "atlas":
            return f'<section style="margin:30px 0;white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:48%;padding:17px 14px;border:1px solid {p["sky"]};border-radius:25px 4px 25px 4px;background-color:{p["sky_pale"]};vertical-align:top;"><span style="display:block;width:25px;height:15px;margin-bottom:10px;border-radius:18px 3px 18px 3px;background-color:{p["primary"]};transform:rotate(-10deg);"></span><p style="margin:0;color:{p["ink"]};font-size:14px;line-height:1.78;">{left}</p></section><section style="box-sizing:border-box;display:inline-block;width:48%;margin:20px 0 0 4%;padding:17px 14px;border:1px solid {p["secondary"]};border-radius:4px 25px 4px 25px;background-color:{p["secondary_pale"]};vertical-align:top;"><p style="margin:0 0 10px;color:{p["ink"]};font-size:14px;line-height:1.78;">{right}</p><span style="display:block;width:25px;height:15px;margin-left:auto;border-radius:18px 3px 18px 3px;background-color:{p["accent"]};transform:rotate(9deg);"></span></section></section>'
        return f'<section style="margin:31px 0;border-top:12px solid {p["primary"]};border-bottom:12px solid {p["primary"]};white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:50%;padding:16px 14px;border-right:2px solid {p["accent"]};vertical-align:top;"><span style="color:{p["secondary"]};font-size:10px;font-weight:800;letter-spacing:.15em;">SHOT A</span><p style="margin:11px 0 0;color:{p["ink"]};font-size:14px;line-height:1.76;">{left}</p></section><section style="box-sizing:border-box;display:inline-block;width:50%;padding:16px 14px;background-color:{p["pale"]};vertical-align:top;"><span style="color:{p["accent"]};font-size:10px;font-weight:800;letter-spacing:.15em;">SHOT B</span><p style="margin:11px 0 0;color:{p["ink"]};font-size:14px;line-height:1.76;">{right}</p></section></section>'

    if kind == "title_body":
        title, body = _inline(payload["title"]), _inline(payload["body"])
        if grammar == "oriental":
            body_html = f'<p style="margin:11px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{body}</p>' if body else ""
            return f'<section style="margin:30px 0;padding:18px 18px 17px;border-left:5px solid {p["primary"]};border-bottom:1px solid {p["secondary"]};background-color:{p["surface"]};"><p style="margin:-27px 0 15px;"><span style="display:inline-block;padding:5px 12px;background-color:{p["accent_pale"]};color:{p["primary"]};font-size:10px;font-weight:800;letter-spacing:.16em;">{label}</span></p><strong style="display:block;color:{p["primary"]};font-family:Georgia,serif;font-size:18px;line-height:1.58;">{title}</strong>{body_html}<p style="margin:13px 0 -20px;text-align:right;"><span style="display:inline-block;width:16px;height:16px;border:2px solid {p["accent"]};color:{p["accent"]};font-size:8px;line-height:13px;text-align:center;">印</span></p></section>'
        if grammar == "press":
            body_html = f'<p style="margin:0;padding-left:14px;border-left:5px solid {p["accent"]};color:{p["ink"]};font-size:14px;line-height:1.8;">{body}</p>' if body else ""
            return f'<section style="margin:30px 0;padding:0 0 15px;border-top:13px solid {p["primary"]};border-bottom:3px solid {p["primary"]};"><p style="margin:0;padding:7px 0;border-bottom:1px solid {p["primary"]};color:{p["accent"]};font-size:9px;font-weight:900;letter-spacing:.18em;">NEWS DESK / {label}</p><strong style="display:block;padding:13px 0 8px;color:{p["ink"]};font-family:Georgia,serif;font-size:20px;line-height:1.52;">{title}</strong>{body_html}</section>'
        if grammar == "pop":
            body_html = f'<p style="margin:12px 0 0;padding:12px;background-color:{p["surface"]};color:{p["ink"]};font-size:14px;line-height:1.78;">{body}</p>' if body else ""
            return f'<section style="margin:31px 0;padding:20px 17px 16px;border:3px solid {p["primary"]};background-color:{p["secondary_pale"]};box-shadow:8px 8px 0 {p["accent"]};"><p style="margin:-31px 0 15px;"><span style="display:inline-block;padding:5px 12px;background-color:{p["primary"]};color:#FFFFFF;font-size:9px;font-weight:900;letter-spacing:.14em;transform:rotate(-2deg);">{label}</span></p><strong style="display:block;color:{p["primary"]};font-size:19px;font-weight:900;line-height:1.5;">{title}</strong>{body_html}</section>'
        if grammar == "atlas":
            body_html = f'<p style="margin:11px 0 0;padding-top:10px;border-top:1px dotted {p["sky"]};color:{p["ink"]};font-size:14px;line-height:1.82;">{body}</p>' if body else ""
            return f'<section style="margin:31px 0;padding:18px;border:1px solid {p["sky"]};border-radius:4px 28px 4px 28px;background-color:{p["surface"]};box-shadow:6px 6px 0 {p["pale"]};"><p style="margin:-27px 0 15px;"><span style="display:inline-block;padding:5px 12px;border-radius:15px 3px 15px 3px;background-color:{p["primary"]};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.16em;">SPECIMEN / {label}</span></p><strong style="display:block;color:{p["primary"]};font-family:Georgia,serif;font-size:18px;line-height:1.58;">{title}</strong>{body_html}</section>'
        if grammar == "business":
            body_html = f'<p style="margin:0;padding:15px 0 15px 30%;border-left:1px solid #B8C0C1;color:{p["ink"]};font-size:14px;line-height:1.8;">{body}</p>' if body else ""
            return f'<section style="margin:31px 0;border-top:8px solid {p["primary"]};border-bottom:2px solid {p["primary"]};"><section style="padding:10px 0;border-bottom:1px solid #B8C0C1;white-space:normal;"><span style="display:inline-block;width:30%;color:{p["secondary"]};font-size:9px;font-weight:800;letter-spacing:.15em;vertical-align:top;">{label}</span><strong style="display:inline-block;width:70%;color:{p["primary"]};font-size:18px;line-height:1.5;vertical-align:top;">{title}</strong></section>{body_html}</section>'
        body_html = f'<p style="margin:12px 0 0;padding-top:11px;border-top:1px solid #C9C5BC;color:{p["ink"]};font-size:14px;line-height:1.82;">{body}</p>' if body else ""
        return f'<section style="margin:31px 0;padding:0 15px 17px;border-top:13px solid {p["primary"]};border-bottom:13px solid {p["primary"]};background-color:{p["surface"]};"><p style="margin:0 -15px 15px;padding:6px 12px;background-color:{p["accent"]};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.18em;">SCENE CARD / {label}</p><strong style="display:block;color:{p["ink"]};font-family:Georgia,serif;font-size:19px;line-height:1.55;">{title}</strong>{body_html}</section>'

    body = _inline(payload["body"])
    if grammar == "oriental":
        return f'<blockquote style="margin:31px 0;padding:14px 17px;border-left:5px solid {p["accent"]};border-bottom:1px solid {p["secondary"]};background-color:{p["secondary_pale"]};color:{p["ink"]};font-family:Georgia,serif;font-size:17px;line-height:1.85;"><span style="display:block;margin-bottom:7px;color:{p["primary"]};font-size:9px;font-weight:800;letter-spacing:.18em;">{label}</span>{body}</blockquote>'
    if grammar == "press":
        return f'<blockquote style="margin:31px 0;padding:9px 0 14px;border-top:12px solid {p["primary"]};border-bottom:3px solid {p["primary"]};white-space:normal;"><span style="display:inline-block;width:22%;color:{p["accent"]};font-family:Georgia,serif;font-size:45px;font-weight:900;line-height:.9;vertical-align:top;">“</span><span style="box-sizing:border-box;display:inline-block;width:78%;padding:7px 0 7px 15px;border-left:5px solid {p["accent"]};color:{p["ink"]};font-family:Georgia,serif;font-size:18px;font-weight:750;line-height:1.8;vertical-align:top;">{body}</span></blockquote>'
    if grammar == "pop":
        return f'<blockquote style="margin:32px 0;padding:18px 17px;border:3px solid {p["primary"]};background-color:{p["accent"]};box-shadow:8px 8px 0 {p["secondary"]};color:#FFFFFF;font-size:17px;font-weight:800;line-height:1.8;"><span style="display:block;margin-bottom:8px;color:{p["secondary"]};font-size:9px;font-weight:900;letter-spacing:.18em;">LOUD / {label}</span>{body}</blockquote>'
    if grammar == "atlas":
        return f'<blockquote style="margin:31px 0;padding:17px 18px;border-left:3px dotted {p["sky"]};border-radius:3px 25px 3px 25px;background-color:{p["pale"]};color:{p["ink"]};font-size:16px;line-height:1.85;"><span style="display:block;margin-bottom:9px;color:{p["primary"]};font-size:9px;font-weight:800;letter-spacing:.18em;">FIELD NOTE / {label}</span>{body}</blockquote>'
    if grammar == "business":
        return f'<blockquote style="margin:31px 0;border-top:8px solid {p["primary"]};border-bottom:2px solid {p["primary"]};white-space:normal;"><span style="display:inline-block;width:26%;padding:15px 8px 0 0;color:{p["secondary"]};font-size:9px;font-weight:800;letter-spacing:.14em;vertical-align:top;">KEY SIGNAL</span><span style="box-sizing:border-box;display:inline-block;width:74%;padding:15px 0 15px 16px;border-left:1px solid #B8C0C1;color:{p["ink"]};font-size:17px;font-weight:700;line-height:1.82;vertical-align:top;">{body}</span></blockquote>'
    return f'<blockquote style="margin:31px 0;padding:18px 16px;border-top:13px solid {p["primary"]};border-bottom:13px solid {p["primary"]};background-color:{p["surface"]};color:{p["ink"]};font-size:17px;font-weight:700;line-height:1.85;text-align:center;"><span style="display:block;margin-bottom:10px;color:{p["accent"]};font-size:9px;font-weight:800;letter-spacing:.2em;text-align:left;">SUBTITLE / {label}</span>{body}</blockquote>'


def render_extended_component(
    slot: dict[str, Any],
    parsed: ParsedArticle,
    palette: dict[str, str],
) -> str | None:
    theme_id = extended_variant_theme(str(slot.get("variant", "")))
    if theme_id is None:
        return None
    component_type = str(slot["component_type"])
    grammar = EXTENDED_THEME_KITS[theme_id]["grammar"]
    component_markup = _payload_html(
        grammar,
        component_type,
        _payload(slot, parsed),
        _palette(palette),
    )
    if grammar == "pop":
        asset = "pop-arrow.png" if component_type in {"numbered_insight", "action_checklist", "logic_path"} else "pop-star.png"
        width = "31%" if asset == "pop-arrow.png" else "13%"
        component_markup = (
            f'<section data-theme-decoration="pop-sticker">'
            f'{_sticker_overlay(asset, width, rotate="2deg")}'
            f'{component_markup}</section>'
        )
    return (
        f'<section data-extended-theme="{theme_id}" data-component-type="{component_type}">'
        f'{component_markup}'
        "</section>"
    )


def _theme_id(config: dict[str, Any]) -> str | None:
    value = str(config.get("visual_system") or config.get("theme_id") or "")
    return value if value in EXTENDED_THEME_KITS else None


def extended_inline_emphasis_style(config: dict[str, Any]) -> str | None:
    theme_id = _theme_id(config)
    if theme_id is None:
        return None
    p = _palette(config["palette"])
    grammar = EXTENDED_THEME_KITS[theme_id]["grammar"]
    styles = {
        "oriental": f"padding:0 3px;border-bottom:5px solid {p['secondary_pale']};color:{p['primary']};font-weight:800;",
        "press": f"border-bottom:4px solid {p['accent']};color:{p['primary']};font-weight:900;",
        "pop": f"padding:1px 5px;background-color:{p['secondary']};color:{p['primary']};font-weight:900;",
        "atlas": f"padding:0 3px;border-bottom:6px solid {p['sky_pale']};color:{p['primary']};font-weight:800;",
        "business": f"padding:0 3px;border-bottom:2px solid {p['secondary']};color:{p['primary']};font-weight:800;",
        "cinema": f"padding:1px 4px;background-color:{p['primary']};color:{p['surface']};font-weight:800;",
    }
    return styles[grammar]


def _distinct_heading(content: str, level: int, section_index: int, grammar: str, p: dict[str, str]) -> str | None:
    if grammar not in REDESIGNED_GRAMMARS:
        return None
    text = _inline(content)
    if level == 2:
        if grammar == "oriental":
            return f'<section data-heading-level="2" data-theme-grammar="folio-heading" style="margin:48px 0 24px;white-space:normal;"><span style="display:inline-block;width:18%;padding:5px 0;color:{p["accent"]};font:700 9px Georgia;letter-spacing:.22em;vertical-align:top;">卷 {section_index:02d}</span><section style="box-sizing:border-box;display:inline-block;width:82%;padding:0 0 15px 19px;border-left:1px solid {p["secondary"]};border-bottom:1px solid #DDD1BA;vertical-align:top;"><strong style="display:block;color:{p["ink"]};font-family:Georgia,Noto Serif SC,serif;font-size:22px;font-weight:650;line-height:1.55;">{text}</strong><span style="display:block;width:28px;height:5px;margin:12px 0 0 auto;background-color:{p["accent"]};"></span></section></section>'
        if grammar == "press":
            return f'<section data-heading-level="2" data-theme-grammar="edition-heading" style="margin:47px 0 24px;padding:7px 0 12px;border-top:4px double {p["ink"]};border-bottom:1px solid {p["ink"]};"><p style="margin:0 0 9px;color:{p["accent"]};font:800 8px Georgia;letter-spacing:.23em;text-align:center;">SECTION {section_index:02d} · SPECIAL EDITION</p><strong style="display:block;color:{p["ink"]};font-family:Georgia,Noto Serif SC,serif;font-size:23px;font-weight:900;line-height:1.42;text-align:center;">{text}</strong></section>'
        if grammar == "atlas":
            return f'<section data-heading-level="2" data-theme-grammar="notebook-heading" style="margin:47px 0 24px;padding:4px 0 0 8px;border-left:2px dotted {p["sky"]};white-space:normal;"><span style="display:inline-block;width:42px;height:42px;border:1px solid {p["primary"]};border-radius:50%;background-color:{p["surface"]};color:{p["primary"]};font:700 9px/42px Georgia;text-align:center;vertical-align:middle;">{section_index:02d}</span><strong style="box-sizing:border-box;display:inline-block;width:82%;margin-left:10px;padding:8px 0 11px;border-bottom:2px solid {p["primary"]};color:{p["ink"]};font-family:Georgia,Noto Serif SC,serif;font-size:22px;line-height:1.5;vertical-align:middle;">{text}</strong><p style="margin:8px 0 0 54px;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.2em;">FIELD OBSERVATION</p></section>'
        if grammar == "business":
            return f'<section data-heading-level="2" data-theme-grammar="report-heading" style="margin:48px 0 24px;border-top:3px solid {p["accent"]};white-space:normal;"><span style="display:inline-block;width:27%;padding:14px 0;color:{p["secondary"]};font:800 34px/1 Georgia;vertical-align:top;">{section_index:02d}</span><section style="box-sizing:border-box;display:inline-block;width:73%;padding:14px 0 15px 18px;border-left:1px solid #CAD2D5;vertical-align:top;"><p style="margin:0 0 8px;color:{p["accent"]};font-size:8px;letter-spacing:.2em;">ANALYSIS CHAPTER</p><strong style="display:block;color:{p["primary"]};font-size:22px;line-height:1.5;">{text}</strong></section></section>'
        return f'<section data-heading-level="2" data-theme-grammar="opening-credit" style="margin:48px 0 25px;white-space:normal;"><span style="display:inline-block;width:22%;padding:8px 10px 0 0;color:{p["accent"]};font:700 9px Georgia;letter-spacing:.18em;vertical-align:top;">SCENE<br><b style="font-size:25px;line-height:1.4;">{section_index:02d}</b></span><section style="box-sizing:border-box;display:inline-block;width:78%;padding:4px 0 14px 18px;border-left:1px dashed {p["primary"]};border-bottom:4px solid {p["secondary"]};vertical-align:top;"><p style="margin:0 0 9px;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.24em;">OPENING SHOT / EXT. DAY</p><strong style="display:block;color:{p["primary"]};font-family:Georgia,Noto Serif SC,serif;font-size:22px;font-weight:700;line-height:1.52;">{text}</strong></section></section>'
    if level == 3:
        if grammar == "oriental":
            return f'<section data-heading-level="3" style="margin:30px 0 14px;padding-left:18%;white-space:normal;"><strong style="display:block;padding:0 0 8px 15px;border-left:1px solid {p["accent"]};color:{p["primary"]};font-family:Georgia,"Noto Serif SC",serif;font-size:18px;line-height:1.58;">{text}</strong></section>'
        if grammar == "press":
            return f'<section data-heading-level="3" style="margin:30px 4px 14px;padding:9px 12px;background-color:{p["secondary_pale"]};border-left:1px dashed #A99A81;transform:rotate(-.3deg);"><strong style="color:{p["ink"]};font-family:Georgia,"Noto Serif SC",serif;font-size:18px;line-height:1.55;">{text}</strong></section>'
        if grammar == "atlas":
            return f'<section data-heading-level="3" style="margin:30px 0 14px;padding:0 0 9px 31px;border-bottom:1px solid #D8E0D4;white-space:normal;"><span style="display:inline-block;width:24px;height:13px;margin:4px 8px 0 -25px;border-radius:80% 0 80% 0;background-color:{p["accent"]};transform:rotate(-13deg);vertical-align:top;"></span><strong style="color:{p["primary"]};font-size:18px;line-height:1.55;">{text}</strong></section>'
        if grammar == "business":
            return f'<section data-heading-level="3" style="margin:30px 0 14px;border-bottom:1px solid #CAD2D5;white-space:normal;"><span style="display:inline-block;width:24%;padding:8px 0;color:{p["secondary"]};font-size:8px;letter-spacing:.2em;vertical-align:top;">INSIGHT</span><strong style="box-sizing:border-box;display:inline-block;width:76%;padding:6px 0 10px 16px;border-left:4px solid {p["accent"]};color:{p["primary"]};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong></section>'
        return f'<section data-heading-level="3" data-theme-grammar="stage-direction" style="margin:30px 0 14px;padding:4px 0 9px 18%;border-bottom:1px dashed {p["primary"]};"><span style="display:block;margin:0 0 6px;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.2em;">( STAGE DIRECTION )</span><strong style="color:{p["primary"]};font-size:17px;line-height:1.55;">{text}</strong></section>'
    return f'<p data-heading-level="4" style="margin:23px 0 10px;color:{p["primary"]};font-size:16px;font-weight:800;line-height:1.58;">{text}</p>'


def render_extended_heading(content: str, level: int, section_index: int, config: dict[str, Any]) -> str | None:
    theme_id = _theme_id(config)
    if theme_id is None:
        return None
    p = _palette(config["palette"])
    grammar = EXTENDED_THEME_KITS[theme_id]["grammar"]
    distinct = _distinct_heading(content, level, section_index, grammar, p)
    if distinct is not None:
        if grammar == "cinema":
            distinct = distinct.replace(
                f"background-color:{p['primary']}",
                f"background-color:{p['surface']}",
            ).replace("color:#FFFFFF", f"color:{p['primary']}")
        if level == 2:
            heading_assets = {
                "oriental": ("oriental-branch.png", "35%"),
                "press": ("press-burst.png", "11%"),
                "atlas": ("atlas-leaf.png", "17%"),
                "business": ("business-signal.png", "27%"),
                "cinema": ("cinema-clapper.png", "24%"),
            }
            asset, width = heading_assets[grammar]
            distinct = (
                f'<section data-theme-decoration="heading-sticker">'
                f'{_sticker_overlay(asset, width, opacity=".82")}'
                f'{distinct}</section>'
            )
        return distinct
    text = _inline(content)
    explicit = bool(re.match(r"^(?:第[一二三四五六七八九十百0-9]+[章节部分篇]|(?:PART|SECTION|CHAPTER)\s*[0-9IVX]+)", content, re.I))
    if level == 2:
        if grammar == "oriental":
            label = "卷" if explicit else f"卷 {section_index:02d}"
            return f'<section data-heading-level="2" data-auto-numbered="{str(not explicit).lower()}" style="margin:44px 0 22px;padding:3px 0 13px 17px;border-left:5px solid {p["primary"]};border-bottom:1px solid {p["secondary"]};"><p style="margin:-9px 0 11px -25px;"><span style="display:inline-block;padding:5px 11px;background-color:{p["accent_pale"]};color:{p["primary"]};font-size:10px;font-weight:800;letter-spacing:.18em;">{label}</span></p><strong style="display:block;color:{p["ink"]};font-family:Georgia,serif;font-size:22px;line-height:1.52;">{text}</strong><p style="margin:9px 0 -18px;text-align:right;"><span style="display:inline-block;width:18px;height:18px;border:2px solid {p["accent"]};color:{p["accent"]};font-size:8px;line-height:15px;text-align:center;">印</span></p></section>'
        if grammar == "press":
            label = "EXTRA" if explicit else f"NEWS / {section_index:02d}"
            return f'<section data-heading-level="2" data-auto-numbered="{str(not explicit).lower()}" style="margin:45px 0 23px;padding:9px 0 12px;border-top:13px solid {p["primary"]};border-bottom:3px solid {p["primary"]};"><p style="margin:0 0 8px;color:{p["accent"]};font-size:10px;font-weight:900;letter-spacing:.18em;">{label}<span style="display:inline-block;width:48px;height:6px;margin-left:10px;background-color:{p["secondary"]};"></span></p><strong style="display:block;color:{p["ink"]};font-family:Georgia,serif;font-size:22px;font-weight:850;line-height:1.48;">{text}</strong></section>'
        if grammar == "pop":
            label = "TOPIC" if explicit else f"TOPIC {section_index:02d}"
            return f'<section data-heading-level="2" data-auto-numbered="{str(not explicit).lower()}" style="margin:46px 6px 25px;padding:18px 16px 16px;border:3px solid {p["primary"]};background-color:{p["secondary_pale"]};box-shadow:8px 8px 0 {p["accent"]};"><p style="margin:-29px 0 14px;"><span style="display:inline-block;padding:5px 12px;background-color:{p["primary"]};color:#FFFFFF;font-size:9px;font-weight:900;letter-spacing:.16em;transform:rotate(-2deg);">{label}</span></p><strong style="display:block;color:{p["primary"]};font-size:22px;font-weight:900;line-height:1.48;">{text}</strong></section>'
        if grammar == "atlas":
            label = "SPECIMEN" if explicit else f"SPECIMEN {section_index:02d}"
            return f'<section data-heading-level="2" data-auto-numbered="{str(not explicit).lower()}" style="margin:45px 0 23px;padding:18px 17px;border:1px solid {p["sky"]};border-radius:4px 29px 4px 29px;background-color:{p["surface"]};box-shadow:7px 7px 0 {p["pale"]};"><p style="margin:-27px 0 14px;"><span style="display:inline-block;padding:5px 12px;border-radius:15px 3px 15px 3px;background-color:{p["primary"]};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.16em;">{label}</span></p><strong style="display:block;color:{p["ink"]};font-family:Georgia,serif;font-size:22px;line-height:1.52;">{text}</strong></section>'
        if grammar == "business":
            label = "BRIEF" if explicit else f"BRIEF {section_index:02d}"
            return f'<section data-heading-level="2" data-auto-numbered="{str(not explicit).lower()}" style="margin:46px 0 23px;border-top:9px solid {p["primary"]};border-bottom:2px solid {p["primary"]};white-space:normal;"><span style="display:inline-block;width:23%;padding:13px 8px 10px 0;color:{p["secondary"]};font-family:Georgia,serif;font-size:12px;font-weight:800;letter-spacing:.12em;vertical-align:top;">{label}</span><strong style="box-sizing:border-box;display:inline-block;width:77%;padding:12px 0 12px 15px;border-left:1px solid #B8C0C1;color:{p["ink"]};font-size:21px;line-height:1.5;vertical-align:top;">{text}</strong></section>'
        label = "SCENE" if explicit else f"SCENE {section_index:02d}"
        return f'<section data-heading-level="2" data-auto-numbered="{str(not explicit).lower()}" style="margin:46px 0 24px;padding:0 15px 14px;border-top:14px solid {p["primary"]};border-bottom:14px solid {p["primary"]};background-color:{p["surface"]};"><p style="margin:0 -15px 14px;padding:6px 12px;background-color:{p["accent"]};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.2em;">{label}</p><strong style="display:block;color:{p["ink"]};font-family:Georgia,serif;font-size:22px;line-height:1.5;">{text}</strong></section>'
    if level == 3:
        if grammar == "oriental":
            return f'<section data-heading-level="3" style="margin:29px 0 13px;white-space:normal;"><span style="display:inline-block;width:24px;height:24px;margin-right:9px;border:1px solid {p["primary"]};color:{p["primary"]};font-size:11px;line-height:22px;text-align:center;vertical-align:top;">笺</span><strong style="box-sizing:border-box;display:inline-block;width:86%;padding-bottom:7px;border-bottom:1px solid {p["secondary"]};color:{p["ink"]};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong></section>'
        if grammar == "press":
            return f'<section data-heading-level="3" style="margin:29px 0 13px;padding:8px 0;border-top:4px solid {p["primary"]};border-bottom:1px solid {p["primary"]};"><span style="display:inline-block;width:20%;color:{p["accent"]};font-size:9px;font-weight:900;letter-spacing:.14em;vertical-align:top;">SUBJECT</span><strong style="display:inline-block;width:80%;color:{p["ink"]};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong></section>'
        if grammar == "pop":
            return f'<section data-heading-level="3" style="margin:29px 0 13px;white-space:normal;"><span style="display:inline-block;width:28px;height:13px;margin:5px 9px 0 0;background-color:{p["accent"]};transform:rotate(-5deg);vertical-align:top;"></span><strong style="box-sizing:border-box;display:inline-block;width:84%;padding-bottom:7px;border-bottom:5px solid {p["secondary"]};color:{p["primary"]};font-size:18px;font-weight:900;line-height:1.55;vertical-align:top;">{text}</strong></section>'
        if grammar == "atlas":
            return f'<section data-heading-level="3" style="margin:29px 0 13px;white-space:normal;"><span style="display:inline-block;width:22px;height:14px;margin:4px 9px 0 0;border-radius:18px 3px 18px 3px;background-color:{p["primary"]};transform:rotate(-9deg);vertical-align:top;"></span><strong style="box-sizing:border-box;display:inline-block;width:86%;padding-bottom:7px;border-bottom:1px dotted {p["sky"]};color:{p["ink"]};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong></section>'
        if grammar == "business":
            return f'<section data-heading-level="3" style="margin:29px 0 13px;padding:8px 0;border-bottom:1px solid #B8C0C1;white-space:normal;"><span style="display:inline-block;width:20%;color:{p["secondary"]};font-size:9px;font-weight:800;letter-spacing:.14em;vertical-align:top;">INSIGHT</span><strong style="display:inline-block;width:80%;color:{p["ink"]};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong></section>'
        return f'<section data-heading-level="3" style="margin:29px 0 13px;padding:8px 12px;border-left:6px solid {p["accent"]};background-color:{p["primary"]};"><strong style="color:{p["surface"]};font-size:18px;line-height:1.55;">{text}</strong></section>'
    return f'<p data-heading-level="4" style="margin:22px 0 9px;color:{p["primary"]};font-size:16px;font-weight:800;line-height:1.55;">{text}</p>'


def _distinct_break(grammar: str, p: dict[str, str]) -> str | None:
    if grammar == "oriental":
        return f'<section data-content-role="thematic-break" data-theme-grammar="folio-turn" style="margin:40px 2px;text-align:right;white-space:nowrap;"><span style="display:inline-block;width:56%;border-top:1px solid #D9C9AC;vertical-align:middle;"></span><span style="display:inline-block;margin:0 10px;color:{p["accent"]};font:700 9px Georgia;letter-spacing:.22em;vertical-align:middle;">卷 · 页</span><span style="display:inline-block;width:12px;height:12px;border:1px solid {p["accent"]};background-color:{p["accent_pale"]};transform:rotate(45deg);vertical-align:middle;"></span></section>'
    if grammar == "press":
        return f'<section data-content-role="thematic-break" data-theme-grammar="edition-rule" style="margin:39px 0 37px;border-top:3px double {p["ink"]};border-bottom:1px solid {p["ink"]};text-align:center;"><span style="display:inline-block;margin:-12px auto -9px;padding:2px 12px;background-color:{p["surface"]};color:{p["accent"]};font:800 8px Georgia;letter-spacing:.24em;vertical-align:middle;">CONTINUED ON NEXT COLUMN</span></section>'
    if grammar == "atlas":
        return f'<section data-content-role="thematic-break" data-theme-grammar="field-coordinate" style="margin:39px 0;text-align:center;white-space:nowrap;"><span style="display:inline-block;width:8px;height:8px;border:1px solid {p["primary"]};border-radius:50%;vertical-align:middle;"></span><span style="display:inline-block;width:22%;margin:0 7px;border-top:1px dotted {p["sky"]};vertical-align:middle;"></span><span style="display:inline-block;padding:2px 8px;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.19em;vertical-align:middle;">FIELD NOTE</span><span style="display:inline-block;width:22%;margin:0 7px;border-top:1px dotted {p["sky"]};vertical-align:middle;"></span><span style="display:inline-block;width:16px;height:9px;border-radius:80% 0 80% 0;background-color:{p["primary"]};transform:rotate(-18deg);vertical-align:middle;"></span></section>'
    if grammar == "business":
        return f'<section data-content-role="thematic-break" data-theme-grammar="metric-ruler" style="margin:39px 0;white-space:nowrap;"><span style="display:inline-block;width:18%;height:7px;background-color:{p["secondary"]};vertical-align:middle;"></span><span style="display:inline-block;width:64%;border-top:1px solid #B9C2C4;vertical-align:middle;"></span><span style="display:inline-block;width:18%;padding-left:9px;color:{p["accent"]};font:800 8px Georgia;letter-spacing:.12em;vertical-align:middle;">NEXT</span></section>'
    if grammar == "cinema":
        holes = ''.join(f'<span style="display:inline-block;width:7px;height:7px;margin:0 5px;border-radius:50%;background-color:{p["secondary"]};vertical-align:middle;"></span>' for _ in range(7))
        return f'<section data-content-role="thematic-break" data-theme-grammar="ticket-perforation" style="margin:40px 0;text-align:center;white-space:nowrap;"><span style="display:inline-block;width:21%;border-top:1px dashed {p["primary"]};vertical-align:middle;"></span>{holes}<span style="display:inline-block;width:21%;border-top:1px dashed {p["primary"]};vertical-align:middle;"></span><span style="display:block;margin:8px 0 0;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.28em;">CUT TO</span></section>'
    return None


def render_extended_break(config: dict[str, Any]) -> str | None:
    theme_id = _theme_id(config)
    if theme_id is None:
        return None
    p = _palette(config["palette"])
    grammar = EXTENDED_THEME_KITS[theme_id]["grammar"]
    distinct = _distinct_break(grammar, p)
    if distinct is not None:
        return distinct
    if grammar == "oriental":
        return f'<p data-content-role="thematic-break" style="margin:36px 0;border-top:1px solid {p["secondary"]};text-align:center;"><span style="display:inline-block;width:17px;height:17px;margin-top:-10px;border:2px solid {p["accent"]};background-color:{p["surface"]};color:{p["accent"]};font-size:8px;line-height:14px;">印</span></p>'
    if grammar == "press":
        return f'<p data-content-role="thematic-break" style="margin:36px 0;border-top:7px solid {p["primary"]};"><span style="display:block;width:28%;height:7px;background-color:{p["accent"]};"></span></p>'
    if grammar == "pop":
        return f'<p data-content-role="thematic-break" style="margin:37px 0;text-align:center;white-space:nowrap;"><span style="display:inline-block;width:22%;height:4px;background-color:{p["primary"]};"></span><span style="display:inline-block;width:30px;height:13px;margin:0 9px;background-color:{p["secondary"]};transform:rotate(-5deg);vertical-align:middle;"></span><span style="display:inline-block;width:11px;height:11px;margin-right:9px;background-color:{p["accent"]};transform:rotate(15deg);vertical-align:middle;"></span><span style="display:inline-block;width:22%;height:4px;background-color:{p["primary"]};"></span></p>'
    if grammar == "atlas":
        return f'<p data-content-role="thematic-break" style="margin:36px 0;text-align:center;white-space:nowrap;"><span style="display:inline-block;width:27%;height:1px;border-top:2px dotted {p["sky"]};"></span><span style="display:inline-block;width:19px;height:12px;margin:0 11px;border-radius:18px 3px 18px 3px;background-color:{p["primary"]};transform:rotate(-12deg);"></span><span style="display:inline-block;width:27%;height:1px;border-top:2px dotted {p["sky"]};"></span></p>'
    if grammar == "business":
        return f'<p data-content-role="thematic-break" style="margin:36px 0;border-top:2px solid {p["primary"]};text-align:right;"><span style="display:inline-block;width:19%;height:6px;background-color:{p["secondary"]};"></span></p>'
    return f'<p data-content-role="thematic-break" style="margin:37px 0;border-top:11px solid {p["primary"]};border-bottom:3px solid {p["accent"]};height:5px;"></p>'


def render_extended_list(
    items: list[str],
    ordered: bool,
    config: dict[str, Any],
    semantic_role: str = "key_points",
) -> str | None:
    theme_id = _theme_id(config)
    if theme_id is None:
        return None
    payload = {"kind": "list", "items": items}
    component_type = "numbered_insight" if ordered else semantic_role
    return _payload_html(EXTENDED_THEME_KITS[theme_id]["grammar"], component_type, payload, _palette(config["palette"]))


def _distinct_table(rows: list[list[str]], grammar: str, p: dict[str, str]) -> str | None:
    if grammar not in REDESIGNED_GRAMMARS or not rows:
        return None
    header, *body = rows
    if grammar == "oriental":
        ths = ''.join(f'<th style="padding:9px 7px;border-bottom:1px solid {p["accent"]};color:{p["primary"]};font-family:Georgia,serif;font-size:12px;text-align:left;">{_inline(cell)}</th>' for cell in header[:4])
        trs = []
        for row in body:
            cells = ''.join(f'<td style="padding:11px 7px;border-bottom:1px solid #DDD1BA;color:{p["ink"]};font-size:13px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>' for cell in row[:4])
            trs.append(f'<tr>{cells}</tr>')
        return f'<section data-theme-grammar="archive-ledger" style="margin:27px 0;padding:8px 16px 13px;border-left:5px solid {p["accent"]};background-color:{p["surface"]};"><p style="margin:0 0 7px;color:{p["secondary"]};font:700 8px Georgia;letter-spacing:.22em;">ARCHIVE LEDGER</p><table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></section>'
    if grammar == "press":
        ths = ''.join(f'<th style="padding:8px 6px;border-right:1px solid {p["ink"]};border-bottom:3px double {p["ink"]};color:{p["ink"]};font-family:Georgia,serif;font-size:12px;text-align:left;">{_inline(cell)}</th>' for cell in header[:4])
        trs = []
        for row in body:
            cells = ''.join(f'<td style="padding:9px 6px;border-right:1px solid #A69A84;border-bottom:1px dotted #A69A84;color:{p["ink"]};font-size:12px;line-height:1.5;vertical-align:top;">{_inline(cell)}</td>' for cell in row[:4])
            trs.append(f'<tr>{cells}</tr>')
        return f'<section data-theme-grammar="newspaper-columns" style="margin:27px 0;padding:8px 0;border-top:7px solid {p["ink"]};border-bottom:3px double {p["ink"]};"><p style="margin:0 0 8px;color:{p["accent"]};font:900 8px Georgia;letter-spacing:.22em;text-align:right;">DATA DESK / SPECIAL EDITION</p><table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></section>'
    if grammar == "atlas":
        ths = ''.join(f'<th style="padding:8px 7px;border-bottom:1px solid {p["primary"]};color:{p["primary"]};font-size:11px;text-align:left;">{_inline(cell)}</th>' for cell in header[:4])
        trs = []
        for index, row in enumerate(body, start=1):
            cells = ''.join(f'<td style="padding:10px 7px;border-bottom:1px dotted {p["sky"]};color:{p["ink"]};font-size:12px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>' for cell in row[:4])
            trs.append(f'<tr data-specimen="{index:02d}">{cells}</tr>')
        return f'<section data-theme-grammar="specimen-register" style="margin:27px 0;padding:14px 13px 12px;border:1px solid {p["sky"]};border-radius:3px 24px 3px 24px;background-color:{p["surface"]};"><p style="margin:-24px 0 10px;"><span style="display:inline-block;padding:4px 10px;border-radius:12px 2px 12px 2px;background-color:{p["primary"]};color:#FFF;font:700 8px Georgia;letter-spacing:.2em;">SPECIMEN REGISTER</span></p><table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></section>'
    if grammar == "business":
        ths = ''.join(f'<th style="padding:9px 8px;border-left:1px solid #B9C2C4;background-color:{p["primary"]};color:#FFF;font-size:11px;text-align:left;">{_inline(cell)}</th>' for cell in header[:4])
        trs = []
        for index, row in enumerate(body):
            bg = p["surface"] if index % 2 else p["sky_pale"]
            cells = ''.join(f'<td style="padding:10px 8px;border-left:1px solid #C8D0D2;border-bottom:1px solid #C8D0D2;background-color:{bg};color:{p["ink"]};font-size:12px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>' for cell in row[:4])
            trs.append(f'<tr>{cells}</tr>')
        return f'<section data-theme-grammar="executive-dashboard" style="margin:27px 0;border-top:8px solid {p["secondary"]};"><p style="margin:0;padding:7px 0;color:{p["accent"]};font:800 8px Georgia;letter-spacing:.2em;text-align:right;">DECISION MATRIX</p><table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></section>'
    ths = ''.join(f'<th style="padding:9px 7px;border-bottom:2px solid {p["accent"]};background-color:{p["secondary_pale"]};color:{p["primary"]};font-size:11px;text-align:left;">{_inline(cell)}</th>' for cell in header[:4])
    trs = []
    for row in body:
        cells = ''.join(f'<td style="padding:10px 7px;border-bottom:1px dashed #C9B9B8;background-color:{p["surface"]};color:{p["ink"]};font-size:12px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>' for cell in row[:4])
        trs.append(f'<tr>{cells}</tr>')
    return f'<section data-theme-grammar="festival-program-table" style="margin:27px 0;padding:14px 12px 15px;border:1px dashed {p["primary"]};border-radius:3px 24px 3px 24px;background-color:{p["surface"]};box-shadow:7px 7px 0 {p["accent_pale"]};"><p style="margin:0 0 10px;color:{p["accent"]};font:700 8px Georgia;letter-spacing:.23em;">FESTIVAL PROGRAM / DATA TAKE</p><table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></section>'


def render_extended_table(rows: list[list[str]], config: dict[str, Any]) -> str | None:
    theme_id = _theme_id(config)
    if theme_id is None or not rows:
        return None
    p = _palette(config["palette"])
    grammar = EXTENDED_THEME_KITS[theme_id]["grammar"]
    distinct = _distinct_table(rows, grammar, p)
    if distinct is not None:
        return distinct
    header, *body = rows
    strong = grammar in {"press", "business", "cinema"}
    border = p["primary"] if strong else p["sky"]
    header_bg = p["primary"] if strong else p["pale"]
    header_color = "#FFFFFF" if strong else p["primary"]
    ths = "".join(f'<th style="padding:10px 8px;border:1px solid {border};background-color:{header_bg};color:{header_color};font-size:12px;line-height:1.4;text-align:left;">{_inline(cell)}</th>' for cell in header[:4])
    trs = []
    for row_index, row in enumerate(body):
        background = p["surface"] if row_index % 2 else p["secondary_pale"]
        cells = "".join(f'<td style="padding:10px 8px;border:1px solid {border};background-color:{background};color:{p["ink"]};font-size:13px;line-height:1.55;vertical-align:top;">{_inline(cell)}</td>' for cell in row[:4])
        trs.append(f"<tr>{cells}</tr>")
    top = "10px" if grammar in {"press", "cinema"} else "4px"
    return f'<section style="margin:24px 0;border-top:{top} solid {p["primary"]};overflow-x:auto;"><table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></section>'


def render_extended_quote(content: str, config: dict[str, Any]) -> str | None:
    theme_id = _theme_id(config)
    if theme_id is None:
        return None
    return _payload_html(EXTENDED_THEME_KITS[theme_id]["grammar"], "evidence_callout", {"kind": "single", "body": content}, _palette(config["palette"]))


def extended_image_frame_variant(config: dict[str, Any]) -> str | None:
    theme_id = _theme_id(config)
    return f"extended_{EXTENDED_THEME_KITS[theme_id]['grammar']}" if theme_id else None


def _distinct_image_placeholder_style(grammar: str, p: dict[str, str]) -> str | None:
    if grammar == "oriental":
        return f"scroll-margin-top:18px;margin:32px 0;padding:9px 18px 15px 25px;border-left:6px solid {p['accent']};border-top:1px solid #D9C9AC;border-bottom:1px solid #D9C9AC;background-color:{p['surface']};box-shadow:8px 8px 0 {p['secondary_pale']};"
    if grammar == "press":
        return f"scroll-margin-top:18px;margin:32px 7px;padding:8px;border:2px solid {p['ink']};background-color:{p['surface']};box-shadow:-7px 7px 0 {p['secondary_pale']};transform:rotate(-.25deg);"
    if grammar == "atlas":
        return f"scroll-margin-top:18px;margin:32px 0;padding:16px 13px 13px 29px;border-left:2px dotted {p['sky']};border-bottom:1px solid #D8E0D4;background-color:{p['surface']};"
    if grammar == "business":
        return f"scroll-margin-top:18px;margin:32px 0;padding:0 0 12px;border-top:10px solid {p['secondary']};border-bottom:1px solid #B9C2C4;background-color:{p['surface']};"
    if grammar == "cinema":
        return f"scroll-margin-top:18px;margin:33px 0;padding:17px 14px 15px 24px;border-left:8px solid {p['secondary']};border-radius:3px 28px 3px 28px;background-color:{p['surface']};box-shadow:8px 8px 0 {p['accent_pale']};"
    return None


def extended_image_placeholder_style(config: dict[str, Any]) -> str | None:
    theme_id = _theme_id(config)
    if theme_id is None:
        return None
    p = _palette(config["palette"])
    grammar = EXTENDED_THEME_KITS[theme_id]["grammar"]
    distinct = _distinct_image_placeholder_style(grammar, p)
    if distinct is not None:
        return distinct
    if grammar == "press":
        return f"scroll-margin-top:18px;margin:30px 0;padding:12px;border-top:11px solid {p['primary']};border-bottom:3px solid {p['primary']};background-color:{p['surface']};"
    if grammar == "pop":
        return f"scroll-margin-top:18px;margin:31px 6px;padding:13px;border:3px solid {p['primary']};background-color:{p['surface']};box-shadow:8px 8px 0 {p['secondary']};"
    if grammar == "atlas":
        return f"scroll-margin-top:18px;margin:30px 0;padding:14px;border:1px solid {p['sky']};border-radius:4px 28px 4px 28px;background-color:{p['surface']};"
    if grammar == "business":
        return f"scroll-margin-top:18px;margin:30px 0;padding:13px;border-top:8px solid {p['primary']};border-bottom:2px solid {p['primary']};background-color:{p['surface']};"
    if grammar == "cinema":
        return f"scroll-margin-top:18px;margin:31px 0;padding:13px;border-top:13px solid {p['primary']};border-bottom:13px solid {p['primary']};background-color:{p['surface']};"
    return f"scroll-margin-top:18px;margin:30px 0;padding:14px 17px;border-left:5px solid {p['primary']};border-bottom:1px solid {p['secondary']};background-color:{p['surface']};"


def _distinct_hero(title_html: str, kicker: str, grammar: str, p: dict[str, str]) -> str | None:
    escaped_kicker = html.escape(kicker)
    if grammar == "oriental":
        return f'<header data-content-role="article-metadata-preview" data-theme-grammar="bound-folio-cover" style="margin:30px 0 32px;padding:0;border-top:1px solid #D9C9AC;border-bottom:1px solid #D9C9AC;white-space:normal;"><section style="display:inline-block;width:17%;padding:26px 0 22px;color:{p["accent"]};font:700 10px Georgia;letter-spacing:.18em;vertical-align:top;writing-mode:vertical-rl;">卷首 · {escaped_kicker}</section><section style="box-sizing:border-box;display:inline-block;width:83%;padding:25px 18px 25px 22px;border-left:1px solid {p["secondary"]};vertical-align:top;"><p style="margin:0 0 16px;color:{p["secondary"]};font:700 8px Georgia;letter-spacing:.24em;">ORIENTAL FOLIO / 典藏页</p><h1 style="margin:0;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:30px;font-weight:650;line-height:1.45;">{title_html}</h1><span style="display:block;width:22px;height:22px;margin:17px 0 0 auto;border:2px solid {p["accent"]};background-color:{p["accent_pale"]};"></span></section></header>'
    if grammar == "press":
        return f'<header data-content-role="article-metadata-preview" data-theme-grammar="front-page" style="margin:28px 0 33px;padding:9px 0 16px;border-top:5px double {p["ink"]};border-bottom:5px double {p["ink"]};"><section style="padding:7px 0;border-bottom:1px solid {p["ink"]};white-space:normal;"><span style="display:inline-block;width:30%;color:{p["accent"]};font:900 9px Georgia;letter-spacing:.18em;vertical-align:middle;">VOL. 01 / EXTRA</span><strong style="display:inline-block;width:40%;color:{p["ink"]};font:900 19px Georgia;text-align:center;vertical-align:middle;">THE DAILY BRIEF</strong><span style="display:inline-block;width:30%;color:#6E675B;font:700 8px Georgia;text-align:right;vertical-align:middle;">{escaped_kicker}</span></section><h1 style="margin:15px 0 12px;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:32px;font-weight:900;line-height:1.3;text-align:center;">{title_html}</h1><p style="margin:0;padding-top:9px;border-top:1px solid {p["ink"]};color:{p["accent"]};font:800 8px Georgia;letter-spacing:.14em;text-align:right;">SPECIAL REPORT</p></header>'
    if grammar == "atlas":
        return f'<header data-content-role="article-metadata-preview" data-theme-grammar="field-notebook-cover" style="margin:30px 0 33px;padding:22px 18px 23px 34px;border-left:2px dotted {p["sky"]};border-bottom:1px solid #D8E0D4;background-color:{p["surface"]};"><section style="white-space:normal;"><span style="display:inline-block;width:68%;color:{p["primary"]};font:700 9px Georgia;letter-spacing:.2em;vertical-align:top;">FIELD NOTE / {escaped_kicker}</span><span style="display:inline-block;width:32%;color:{p["accent"]};font:700 8px Georgia;text-align:right;vertical-align:top;">OBS. 01</span></section><h1 style="margin:19px 0 14px;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:30px;font-weight:680;line-height:1.43;">{title_html}</h1><p style="margin:0;padding-top:11px;border-top:1px dotted {p["sky"]};text-align:right;"><span style="display:inline-block;width:29px;height:15px;border-radius:80% 0 80% 0;background-color:{p["primary"]};transform:rotate(-17deg);"></span><span style="display:inline-block;width:19px;height:11px;margin-left:4px;border-radius:80% 0 80% 0;background-color:{p["accent"]};transform:rotate(17deg);"></span></p></header>'
    if grammar == "business":
        return f'<header data-content-role="article-metadata-preview" data-theme-grammar="market-pictorial-cover" style="margin:31px 0 36px;padding:22px 20px 20px;border-radius:4px 48px 4px 48px;background-color:{p["surface"]};box-shadow:10px 10px 0 {p["sky_pale"]};"><section style="white-space:normal;"><span style="display:inline-block;width:70%;color:{p["accent"]};font:800 8px Georgia;letter-spacing:.22em;vertical-align:middle;">BUSINESS PICTORIAL / {escaped_kicker}</span><span style="display:inline-block;width:30%;text-align:right;vertical-align:middle;"><span style="display:inline-block;width:13px;height:13px;border-radius:50%;background-color:{p["secondary"]};"></span><span style="display:inline-block;width:13px;height:13px;margin-left:5px;border-radius:50%;background-color:{p["accent"]};"></span></span></section><h1 style="margin:24px 0 17px;color:{p["ink"]};font-size:30px;font-weight:820;line-height:1.42;">{title_html}</h1><p style="margin:0;padding-top:10px;border-top:1px solid {p["sky"]};"><span style="display:inline-block;width:18%;height:9px;border-radius:9px;background-color:{p["secondary"]};vertical-align:middle;"></span><span style="display:inline-block;width:13%;height:9px;margin-left:5px;border-radius:9px;background-color:{p["accent"]};vertical-align:middle;"></span></p></header>'
    if grammar == "cinema":
        holes = ''.join(f'<span style="display:inline-block;width:8px;height:8px;margin:0 6px;border-radius:50%;background-color:{p["secondary"]};"></span>' for _ in range(7))
        return f'<header data-content-role="article-metadata-preview" data-theme-grammar="festival-program-cover" style="margin:31px 0 36px;padding:17px 18px 20px;border:1px dashed {p["primary"]};border-radius:3px 34px 3px 34px;background-color:{p["surface"]};box-shadow:9px 9px 0 {p["accent_pale"]};"><p style="margin:-25px 0 16px;text-align:right;white-space:nowrap;">{holes}</p><p style="margin:0 0 17px;color:{p["accent"]};font:800 8px Georgia;letter-spacing:.23em;">OPENING SHOT / {escaped_kicker}</p><h1 style="margin:0;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:30px;font-weight:760;line-height:1.4;">{title_html}</h1><p style="height:2px;margin:18px 0 0;background-color:{p["secondary"]};"></p><p style="margin:16px -7px -27px;text-align:right;"><span style="display:inline-block;padding:5px 13px;border-radius:15px 2px 15px 2px;background-color:{p["accent"]};color:#FFF;font:700 8px Georgia;letter-spacing:.2em;transform:rotate(-2deg);">FADE IN</span></p></header>'
    if grammar == "pop":
        return f'<header data-content-role="article-metadata-preview" data-theme-grammar="poster-wall" style="margin:30px 5px 35px;padding:21px 17px 18px;border:3px solid {p["primary"]};background-color:{p["secondary_pale"]};box-shadow:9px 9px 0 {p["accent"]};transform:rotate(-.35deg);"><p style="margin:-31px 0 15px;"><span style="display:inline-block;padding:5px 12px;background-color:{p["primary"]};color:#FFF;font-size:9px;font-weight:900;letter-spacing:.18em;transform:rotate(-2deg);">POP EDITION / {escaped_kicker}</span></p><h1 style="margin:0;color:{p["primary"]};font-size:30px;font-weight:900;line-height:1.35;">{title_html}</h1><p style="height:5px;margin:16px 0 0;background-color:{p["secondary"]};"></p></header>'
    return None


def render_extended_hero(title: str, plan_name: str, component_version: str, kicker: str, config: dict[str, Any]) -> str | None:
    theme_id = _theme_id(config)
    if theme_id is None:
        return None
    p = _palette(config["palette"])
    grammar = EXTENDED_THEME_KITS[theme_id]["grammar"]
    title_html = _inline(title)
    # plan_name and component_version remain part of the structured plan for
    # diagnostics, but must never leak into reader-facing article HTML.
    _ = (plan_name, component_version)
    distinct = _distinct_hero(title_html, kicker, grammar, p)
    if distinct is not None:
        hero_assets = {
            "oriental": ("oriental-branch.png", "47%"),
            "press": ("press-tape.png", "52%"),
            "atlas": ("atlas-leaf.png", "22%"),
            "business": ("business-orbit.png", "24%"),
            "cinema": ("cinema-reel.png", "20%"),
            "pop": ("pop-star.png", "18%"),
        }
        if grammar == "cinema":
            distinct = distinct.replace(
                f"background-color:{p['primary']}",
                f"background-color:{p['surface']}",
            ).replace("color:#FFF", f"color:{p['primary']}")
        asset, width = hero_assets[grammar]
        return (
            f'<section data-theme-decoration="hero-sticker">'
            f'{_sticker_overlay(asset, width, translate_y="-28%", opacity=".82")}'
            f'{distinct}</section>'
        )
    if grammar == "oriental":
        return f'<header data-content-role="article-metadata-preview" style="padding:35px 0 25px;border-left:6px solid {p["primary"]};border-bottom:1px solid {p["secondary"]};"><p style="margin:0 0 13px -7px;"><span style="display:inline-block;padding:5px 12px;background-color:{p["accent_pale"]};color:{p["primary"]};font-size:9px;font-weight:800;letter-spacing:.18em;">雅集 · {html.escape(kicker)}</span></p><section style="padding-left:18px;"><h1 style="margin:0;color:{p["ink"]};font-family:Georgia,serif;font-size:30px;line-height:1.4;font-weight:750;">{title_html}</h1></section><p style="margin:13px 0 -32px;text-align:right;"><span style="display:inline-block;width:20px;height:20px;border:2px solid {p["accent"]};color:{p["accent"]};font-size:8px;line-height:17px;text-align:center;">印</span></p></header>'
    if grammar == "press":
        return f'<header data-content-role="article-metadata-preview" style="padding:12px 0 21px;border-top:16px solid {p["primary"]};border-bottom:5px solid {p["primary"]};"><p style="margin:0 0 8px;padding-bottom:7px;border-bottom:1px solid {p["primary"]};color:{p["accent"]};font-size:9px;font-weight:900;letter-spacing:.2em;">SPECIAL EDITION　·　{html.escape(kicker)}</p><h1 style="margin:0;color:{p["ink"]};font-family:Georgia,serif;font-size:31px;line-height:1.34;font-weight:900;letter-spacing:-.02em;">{title_html}</h1></header>'
    if grammar == "pop":
        return f'<header data-content-role="article-metadata-preview" style="margin:33px 6px 29px;padding:22px 18px 19px;border:4px solid {p["primary"]};background-color:{p["secondary_pale"]};box-shadow:10px 10px 0 {p["accent"]};"><p style="margin:-34px 0 16px;"><span style="display:inline-block;padding:6px 13px;background-color:{p["primary"]};color:#FFFFFF;font-size:9px;font-weight:900;letter-spacing:.18em;transform:rotate(-2deg);">POP EDITION</span></p><p style="margin:0 0 10px;color:{p["accent"]};font-size:10px;font-weight:900;letter-spacing:.12em;">{html.escape(kicker)}</p><h1 style="margin:0;color:{p["primary"]};font-size:30px;line-height:1.36;font-weight:900;letter-spacing:-.03em;">{title_html}</h1><p style="height:5px;margin:16px 0 0;background-color:{p["secondary"]};"></p></header>'
    if grammar == "atlas":
        return f'<header data-content-role="article-metadata-preview" style="margin:32px 0 28px;padding:24px 19px 21px;border:1px solid {p["sky"]};border-radius:4px 35px 4px 35px;background-color:{p["surface"]};box-shadow:8px 8px 0 {p["pale"]};"><p style="margin:-33px 0 16px;"><span style="display:inline-block;padding:5px 13px;border-radius:16px 3px 16px 3px;background-color:{p["primary"]};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.18em;">NATURAL ATLAS</span></p><p style="margin:0 0 10px;color:{p["accent"]};font-size:9px;font-weight:800;letter-spacing:.14em;">{html.escape(kicker)}</p><h1 style="margin:0;color:{p["ink"]};font-family:Georgia,serif;font-size:30px;line-height:1.4;font-weight:750;">{title_html}</h1><p style="height:1px;margin:16px 0 0;background-color:{p["sky"]};"></p></header>'
    if grammar == "business":
        return f'<header data-content-role="article-metadata-preview" style="padding:18px 0 22px;border-top:13px solid {p["primary"]};border-bottom:3px solid {p["primary"]};"><section style="white-space:normal;"><span style="display:inline-block;width:25%;color:{p["secondary"]};font-size:9px;font-weight:800;letter-spacing:.16em;vertical-align:top;">BUSINESS<br>REVIEW</span><section style="box-sizing:border-box;display:inline-block;width:75%;padding-left:16px;border-left:1px solid #B8C0C1;vertical-align:top;"><p style="margin:0 0 10px;color:{p["accent"]};font-size:9px;font-weight:800;letter-spacing:.13em;">{html.escape(kicker)}</p><h1 style="margin:0;color:{p["ink"]};font-size:29px;line-height:1.4;font-weight:820;">{title_html}</h1></section></section></header>'
    return f'<header data-content-role="article-metadata-preview" style="margin:31px 0 29px;padding:0 18px 18px;border-top:17px solid {p["primary"]};border-bottom:17px solid {p["primary"]};background-color:{p["surface"]};"><p style="margin:0 -18px 16px;padding:7px 13px;background-color:{p["accent"]};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.2em;">OPENING SHOT　·　{html.escape(kicker)}</p><h1 style="margin:0;color:{p["ink"]};font-family:Georgia,serif;font-size:30px;line-height:1.38;font-weight:780;">{title_html}</h1></header>'


def extended_rhythm_primitives(theme_id: str, palette: dict[str, str]) -> list[dict[str, str]]:
    kit = EXTENDED_THEME_KITS[theme_id]
    config = {**kit["configuration"], "visual_system": theme_id, "theme_id": theme_id, "palette": palette}
    p = _palette(palette)
    heading = render_extended_heading("先理解问题，再决定行动", 2, 1, config) or ""
    subheading = render_extended_heading("把信息分成三个判断层级", 3, 1, config) or ""
    emphasis = extended_inline_emphasis_style(config) or ""
    divider = render_extended_break(config) or ""
    grammar = kit["grammar"]
    frame = extended_image_placeholder_style(config) or ""
    image = (
        f'<section style="{frame}"><section style="height:145px;background-color:{p["pale"]};">'
        f'<span style="display:block;width:61%;height:11px;margin:0 0 17px;background-color:{p["secondary"]};"></span>'
        f'<span style="display:block;width:43%;height:11px;margin-left:35%;background-color:{p["accent"]};"></span></section>'
        f'<p style="margin:10px 0 0;color:#6D756F;font-size:11px;line-height:1.55;text-align:center;">图示 · 图片承接场景，正文负责解释</p></section>'
    )
    cta = _payload_html(grammar, "section_summary", {"kind": "title_body", "title": "把判断带回下一次真实行动", "body": "保存文章，并在行动中继续验证。"}, p)
    return [
        {"role": "section_heading", "label": "章节标题", "html": heading},
        {"role": "subheading", "label": "主题小标题", "html": subheading},
        {"role": "inline_emphasis", "label": "行内重点", "html": f'<p style="margin:22px 0;color:{p["ink"]};font-size:16px;line-height:1.9;">真正需要强调的是 <strong style="{emphasis}">决定读者下一步的关键词</strong>。</p>'},
        {"role": "image_caption", "label": "主题图文位", "html": image},
        {"role": "divider", "label": "章节分割线", "html": divider},
        {"role": "closing_cta", "label": "结尾行动区", "html": cta},
    ]
