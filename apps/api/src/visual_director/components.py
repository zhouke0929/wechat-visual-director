from __future__ import annotations

import html
import re
from typing import Any

from .parser import ParsedArticle
from .theme_extensions import render_extended_component


REF_RE = re.compile(r"^(block-\d{3})(?::item:(\d+))?$")


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("\n", "<br>")


def _resolve(parsed: ParsedArticle, reference: str) -> str:
    match = REF_RE.fullmatch(reference)
    if not match:
        raise ValueError(f"无法解析内容绑定：{reference}")
    block_id, item_index = match.groups()
    block = next((item for item in parsed.blocks if item.id == block_id), None)
    if block is None:
        raise ValueError(f"内容块不存在：{block_id}")
    if item_index is None:
        return str(block.content)
    return str(block.content[int(item_index)])


def _one(parsed: ParsedArticle, bindings: dict[str, Any], role: str) -> str:
    reference = bindings[role]
    if not isinstance(reference, str):
        raise ValueError(f"{role} 应为单个内容引用")
    return _resolve(parsed, reference)


def _many(parsed: ParsedArticle, bindings: dict[str, Any], role: str) -> list[str]:
    references = bindings[role]
    if not isinstance(references, list):
        raise ValueError(f"{role} 应为内容引用数组")
    return [_resolve(parsed, reference) for reference in references]


DEFAULT_PALETTE = {
    "primary": "#117C73",
    "secondary": "#F4C84A",
    "accent": "#F06A4B",
    "sky": "#58B9E4",
    "pale": "#E9F7F3",
    "secondary_pale": "#FFF7D5",
    "accent_pale": "#FFF0E9",
    "sky_pale": "#EAF7FD",
    "surface": "#FFFEFA",
    "ink": "#20312E",
}


def _plain_list(items: list[str], accent: str) -> str:
    rows = []
    for index, item in enumerate(items, 1):
        rows.append(
            '<p style="margin:0 0 12px;color:#34403E;font-size:16px;line-height:1.75;">'
            f'<strong style="color:{accent};">{index:02d}.</strong> {_inline(item)}</p>'
        )
    return '<section style="margin:24px 0;">' + "".join(rows) + "</section>"


def _concept_entries(
    parsed: ParsedArticle,
    bindings: dict[str, Any],
) -> list[tuple[str, str]]:
    titles = [_one(parsed, bindings, "title")]
    definitions = [_one(parsed, bindings, "definition")]
    if "related_titles" in bindings or "related_definitions" in bindings:
        if "related_titles" not in bindings or "related_definitions" not in bindings:
            raise ValueError("连续概念词条必须同时提供标题与解释")
        titles.extend(_many(parsed, bindings, "related_titles"))
        definitions.extend(_many(parsed, bindings, "related_definitions"))
    if len(titles) != len(definitions) or not 1 <= len(titles) <= 4:
        raise ValueError("连续概念词条必须包含 1–4 组标题与解释")
    return [(_inline(title), _inline(definition)) for title, definition in zip(titles, definitions, strict=True)]


def _render_concept_group(
    entries: list[tuple[str, str]],
    variant: str,
    colors: dict[str, str],
) -> str:
    primary = colors["primary"]
    secondary = colors["secondary"]
    accent = colors["accent"]
    sky = colors["sky"]
    pale = colors["pale"]
    secondary_pale = colors["secondary_pale"]
    accent_pale = colors["accent_pale"]
    sky_pale = colors["sky_pale"]
    surface = colors["surface"]
    ink = colors["ink"]

    if variant == "note_definition":
        rows = []
        for index, (title, definition) in enumerate(entries, 1):
            rows.append(
                f'<section style="padding:16px 0 17px;border-top:1px solid #D7B995;white-space:normal;">'
                f'<span style="display:inline-block;width:17%;padding:2px 8px 0 0;color:{accent};font-family:Georgia,serif;font-size:18px;font-weight:800;vertical-align:top;">{index:02d}<span style="display:block;width:28px;height:7px;margin-top:8px;background-color:{secondary};transform:rotate(-5deg);"></span></span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:83%;padding-left:15px;border-left:2px dashed #D7B995;vertical-align:top;">'
                f'<p style="margin:0 0 7px;color:{primary};font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;font-weight:750;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.86;">{definition}</p></section></section>'
            )
        return (
            f'<section style="margin:32px 0;padding:0 14px 3px;background-color:{surface};box-shadow:6px 7px 0 {secondary_pale};">'
            f'<p style="margin:0 0 2px;padding:8px 12px;background-color:{accent_pale};color:{accent};font-size:11px;font-weight:800;letter-spacing:.12em;">概念手册 · {len(entries)} 个核心词条</p>'
            f'{"".join(rows)}</section>'
        )

    if variant in {"open_definition_note", "airy_definition"}:
        rows = []
        for index, (title, definition) in enumerate(entries, 1):
            dot_color = (primary, sky, accent, secondary)[(index - 1) % 4]
            rows.append(
                f'<section style="margin:0 0 17px;padding:0 0 15px;border-bottom:1px solid {sky};white-space:normal;">'
                f'<span style="display:inline-block;width:10%;color:{dot_color};font-family:Georgia,serif;font-size:12px;font-weight:800;vertical-align:top;">{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:90%;vertical-align:top;">'
                f'<p style="margin:0 0 6px;color:{primary};font-size:17px;font-weight:750;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.84;">{definition}</p></section></section>'
            )
        return (
            f'<section style="margin:29px 0;padding:18px 18px 2px;border-left:3px solid {primary};border-radius:0 20px 6px 0;background-color:{sky_pale};">'
            f'<p style="margin:0 0 16px;color:{primary};font-size:11px;font-weight:800;letter-spacing:.14em;">核心概念</p>'
            f'{"".join(rows)}</section>'
        )

    if variant == "notebook_term":
        rows = []
        for index, (title, definition) in enumerate(entries, 1):
            tab_color = (accent, sky, primary, secondary)[(index - 1) % 4]
            rows.append(
                f'<section style="margin:0 0 14px;padding:13px 13px 14px;background-color:{surface};box-shadow:4px 4px 0 {secondary_pale};white-space:normal;">'
                f'<span style="display:inline-block;width:15%;padding:4px 3px;background-color:{tab_color};color:#FFFFFF;font-family:Georgia,serif;font-size:11px;font-weight:800;text-align:center;vertical-align:top;">{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:85%;padding-left:12px;vertical-align:top;">'
                f'<p style="margin:0 0 7px;color:{primary};font-size:17px;font-weight:800;line-height:1.5;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.82;">{definition}</p></section></section>'
            )
        return (
            f'<section style="margin:31px 0;padding:18px 13px 5px 22px;border-left:9px dotted {sky};background-color:{pale};">'
            f'<p style="margin:-24px 0 17px;"><span style="display:inline-block;padding:5px 11px;background-color:{accent};color:#FFFFFF;font-size:10px;font-weight:800;transform:rotate(-2deg);">课堂词条</span></p>'
            f'{"".join(rows)}</section>'
        )

    if variant == "editorial_definition":
        rows = []
        for index, (title, definition) in enumerate(entries, 1):
            rows.append(
                f'<section style="border-top:1px solid {ink};white-space:normal;">'
                f'<span style="display:inline-block;width:18%;padding:15px 8px 16px 0;color:{accent};font-family:Georgia,serif;font-size:24px;font-weight:800;vertical-align:top;">{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:82%;padding:15px 0 17px 16px;border-left:6px solid {accent};vertical-align:top;">'
                f'<p style="margin:0 0 7px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;font-weight:800;line-height:1.5;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.84;">{definition}</p></section></section>'
            )
        return (
            f'<section style="margin:31px 0;border-top:11px solid {ink};border-bottom:3px solid {ink};">'
            f'<p style="margin:0;padding:8px 0;color:{accent};font-size:10px;font-weight:800;letter-spacing:.16em;">术语索引</p>'
            f'{"".join(rows)}</section>'
        )

    if variant in {"coordinate_definition", "definition_register"}:
        rows = []
        for index, (title, definition) in enumerate(entries, 1):
            rows.append(
                f'<section style="border-top:1px solid #B7C5C0;white-space:normal;">'
                f'<span style="display:inline-block;width:22%;padding:15px 8px;color:{accent};font-family:Georgia,serif;font-size:12px;font-weight:800;vertical-align:top;">TERM-{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:78%;padding:14px 13px 16px;border-left:1px solid #B7C5C0;vertical-align:top;">'
                f'<p style="margin:0 0 6px;color:{primary};font-size:17px;font-weight:750;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.82;">{definition}</p></section></section>'
            )
        return (
            f'<section style="margin:30px 0;border:1px solid {primary};background-color:{surface};">'
            f'<p style="height:8px;margin:0;background-color:{primary};"><span style="display:block;width:27%;height:8px;background-color:{secondary};"></span></p>'
            f'<p style="margin:0;padding:9px 12px;color:{primary};font-size:10px;font-weight:800;letter-spacing:.14em;">概念坐标</p>'
            f'{"".join(rows)}</section>'
        )

    if variant == "hologram_term":
        rows = []
        for index, (title, definition) in enumerate(entries, 1):
            signal = (accent, primary, sky, secondary)[(index - 1) % 4]
            rows.append(
                f'<section style="margin:0 0 12px;padding:14px 15px;border-left:5px solid {signal};border-radius:3px 24px 3px 16px;background-color:{surface};white-space:normal;">'
                f'<span style="display:inline-block;width:13%;color:{signal};font-family:Georgia,serif;font-size:16px;font-weight:800;vertical-align:top;">{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:87%;vertical-align:top;">'
                f'<p style="margin:0 0 6px;color:{ink};font-size:17px;font-weight:800;line-height:1.52;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.82;">{definition}</p></section></section>'
            )
        return (
            f'<section style="margin:32px 0;padding:18px 15px 7px;border-radius:4px 40px 4px 22px;background:linear-gradient(135deg,{sky_pale},{secondary_pale});box-shadow:6px 6px 0 {pale};">'
            f'<p style="margin:0 0 14px;color:{primary};font-size:10px;font-weight:800;letter-spacing:.14em;">概念切片 · {len(entries)} 项</p>'
            f'{"".join(rows)}</section>'
        )

    rows = []
    for index, (title, definition) in enumerate(entries, 1):
        rows.append(
            f'<section style="padding:14px 0;border-top:1px solid {sky};">'
            f'<p style="margin:0 0 7px;color:{primary};font-size:17px;font-weight:750;">{index:02d} · {title}</p>'
            f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.82;">{definition}</p></section>'
        )
    return (
        f'<section style="margin:28px 0;padding:16px;border-left:4px solid {primary};background-color:{pale};">'
        f'<p style="margin:0 0 6px;color:{primary};font-size:11px;font-weight:800;">核心概念</p>{"".join(rows)}</section>'
    )


def render_component(slot: dict[str, Any], parsed: ParsedArticle, palette: dict[str, str] | None = None) -> str:
    component_type = slot["component_type"]
    variant = slot["variant"]
    bindings = slot["content_bindings"]
    colors = {**DEFAULT_PALETTE, **(palette or {})}
    primary = colors["primary"]
    secondary = colors["secondary"]
    accent = colors["accent"]
    sky = colors["sky"]
    pale = colors["pale"]
    secondary_pale = colors["secondary_pale"]
    accent_pale = colors["accent_pale"]
    sky_pale = colors["sky_pale"]
    surface = colors["surface"]
    ink = colors["ink"]

    extended = render_extended_component(slot, parsed, colors)
    if extended is not None:
        return extended

    if component_type == "question_hook":
        title = _inline(_one(parsed, bindings, "title"))
        if variant == "plain_question":
            return f'<p style="margin:28px 0 20px;color:{primary};font-size:20px;font-weight:750;line-height:1.6;text-align:center;">{title}</p>'
        if variant == "warm_letter_prompt":
            return (
                f'<section style="margin:30px 0 26px;padding:18px 16px;border-left:4px solid {accent};border-bottom:1px solid #E7D4BD;background-color:#FFF8ED;">'
                f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:19px;font-weight:750;line-height:1.72;">{title}</p>'
                f'</section>'
            )
        if variant == "campus_notice_prompt":
            return (
                f'<section style="margin:32px 0 28px;padding:0 7px 8px 0;">'
                f'<p style="margin:0 0 -8px 17px;position:relative;"><span style="display:inline-block;padding:5px 13px;background-color:{secondary};color:{ink};font-size:10px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">CAMPUS NOTICE</span></p>'
                f'<section style="padding:20px 18px 18px;border:2px solid {primary};border-radius:3px;background-color:{surface};box-shadow:7px 7px 0 {sky_pale};">'
                f'<span style="display:inline-block;width:18px;height:18px;margin-right:12px;border:5px solid {accent};border-radius:50%;vertical-align:top;"></span>'
                f'<strong style="display:inline-block;width:82%;color:{ink};font-size:19px;line-height:1.62;vertical-align:top;">{title}</strong>'
                f'<p style="height:1px;margin:14px 0 0;background-color:{sky};"><span style="display:block;width:31%;height:4px;background-color:{accent};"></span></p>'
                f'</section></section>'
            )
        if variant == "editorial_deck_question":
            return (
                f'<section style="margin:30px 0 27px;padding:16px 0;border-top:4px solid {ink};border-bottom:1px solid {ink};white-space:normal;">'
                f'<span style="display:inline-block;width:52px;color:{accent};font-family:Georgia,serif;font-size:48px;font-weight:700;line-height:.9;vertical-align:top;">Q.</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:82%;padding-left:15px;border-left:1px solid #C8C4BA;vertical-align:top;">'
                f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:20px;font-weight:750;line-height:1.65;">{title}</p>'
                f'</section></section>'
            )
        if variant == "grid_query_panel":
            return (
                f'<section style="margin:28px 0 26px;border:1px solid {primary};background-color:{surface};">'
                f'<section style="height:7px;background-color:{primary};"><span style="display:inline-block;width:26%;height:7px;background-color:{secondary};"></span></section>'
                f'<section style="padding:17px 15px 16px;">'
                f'<p style="margin:0;color:{ink};font-size:18px;font-weight:750;line-height:1.65;">{title}</p>'
                f'</section></section>'
            )
        if variant == "holo_query":
            return (
                f'<section style="margin:33px 0 31px;padding:19px 19px 18px;border-radius:4px 40px 4px 22px;background:linear-gradient(135deg,{secondary_pale},{pale});box-shadow:6px 6px 0 {sky_pale};">'
                f'<p style="margin:0 0 10px;color:{accent};font-size:10px;font-weight:800;letter-spacing:.1em;">关键问题</p>'
                f'<strong style="display:block;color:{ink};font-size:19px;line-height:1.67;">{title}</strong>'
                f'<p style="margin:12px 0 -23px;text-align:right;"><span style="display:inline-block;width:44px;height:9px;border-radius:14px 3px 14px 3px;background-color:{secondary};transform:rotate(-6deg);"></span></p>'
                f'</section>'
            )
        return (
            '<section style="margin:28px 0 24px;text-align:center;">'
            f'<p style="margin:0 0 8px;"><span style="display:inline-block;width:18px;height:3px;margin-right:8px;background-color:{secondary};"></span>'
            f'<span style="display:inline-block;width:5px;height:5px;border-radius:50%;background-color:{accent};"></span></p>'
            f'<section style="display:inline-block;max-width:86%;padding:15px 20px;border:1px solid {sky};border-radius:20px 20px 5px 20px;background-color:{sky_pale};box-shadow:5px 5px 0 {secondary_pale};color:{ink};font-size:18px;font-weight:750;line-height:1.6;">'
            f'{title}</section></section>'
        )

    if component_type == "numbered_insight":
        items = _many(parsed, bindings, "items")
        if variant == "plain_numbered_list":
            return _plain_list(items, primary)
        if variant == "leaf_index_ribbon":
            rows = []
            for index, item in enumerate(items, 1):
                item_color = (primary, accent, sky, secondary)[(index - 1) % 4]
                rows.append(
                    f'<section style="margin:0 0 17px;white-space:normal;">'
                    f'<span style="display:inline-block;width:32px;color:{item_color};font-family:Georgia,serif;font-size:13px;font-weight:750;line-height:1.4;vertical-align:top;">{index:02d}</span>'
                    f'<section style="box-sizing:border-box;display:inline-block;width:86%;padding:0 0 13px;border-bottom:1px solid {item_color};vertical-align:top;">'
                    f'<p style="margin:0;color:{ink};font-size:15px;font-weight:650;line-height:1.72;">{_inline(item)}</p>'
                    f'</section></section>'
                )
            return (
                f'<section style="margin:28px 0;padding:3px 0 1px 8px;border-left:3px solid {primary};">'
                f'<p style="margin:-9px 0 18px -8px;white-space:nowrap;">'
                f'<span style="display:inline-block;width:16px;height:9px;border-radius:12px 2px 12px 2px;background-color:{primary};transform:rotate(-18deg);"></span>'
                f'<span style="display:inline-block;width:34px;height:1px;margin:0 0 4px 7px;background-color:{secondary};"></span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "data_spine":
            rows = []
            for index, item in enumerate(items, 1):
                offset = 0 if index % 2 else 14
                rows.append(
                    f'<section style="margin:0 0 12px;padding-left:{offset}px;white-space:normal;">'
                    f'<span style="display:inline-block;width:44px;padding:10px 0;border-bottom:4px solid {accent};color:{primary};font-family:Georgia,serif;font-size:15px;font-weight:800;vertical-align:top;">D-{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:78%;margin:0;padding:9px 0 11px 14px;border-left:1px solid #AEBBB5;border-bottom:1px solid #D8DEDA;color:{ink};font-size:14px;font-weight:650;line-height:1.72;vertical-align:top;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:28px 0;padding:4px 0 2px;">'
                f'<p style="height:2px;margin:0 0 16px;background-color:{primary};"><span style="display:block;width:31%;height:7px;background-color:{secondary};"></span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "scrapbook_index":
            rows = []
            for index, item in enumerate(items, 1):
                offset = 13 if index % 2 == 0 else 0
                rows.append(
                    f'<section style="margin:0 0 16px;padding-left:{offset}px;white-space:normal;">'
                    f'<span style="display:inline-block;width:35px;color:{accent if index % 2 else primary};font-family:Georgia,serif;font-size:22px;font-weight:750;line-height:1.25;vertical-align:top;">{index:02d}</span>'
                    f'<section style="box-sizing:border-box;display:inline-block;width:84%;padding:0 0 12px 14px;border-left:1px dashed #D7B995;border-bottom:1px solid #EADCC9;vertical-align:top;">'
                    f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:15px;font-weight:650;line-height:1.78;">{_inline(item)}</p>'
                    f'</section>'
                    f'</section>'
                )
            return (
                f'<section style="margin:29px 0;padding:5px 0 1px 11px;border-left:5px solid {secondary};">'
                f'<p style="margin:-9px 0 18px -16px;"><span style="display:inline-block;width:64px;height:12px;background-color:{accent_pale};transform:rotate(-3deg);"></span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "course_ticket_stack":
            rows = []
            for index, item in enumerate(items, 1):
                item_color = (primary, accent, sky, secondary)[(index - 1) % 4]
                rows.append(
                    f'<section style="margin:0 0 13px;padding:0 0 0 9px;border-left:6px dotted {item_color};white-space:normal;">'
                    f'<span style="display:inline-block;width:54px;padding:13px 4px;background-color:{item_color};color:#FFFFFF;font-family:Georgia,serif;font-size:14px;font-weight:800;text-align:center;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:79%;margin:0;padding:12px 13px;border-top:1px solid {item_color};border-right:1px dashed {item_color};border-bottom:1px solid {item_color};background-color:{surface};color:{ink};font-size:14px;font-weight:650;line-height:1.72;vertical-align:top;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:29px 0;padding:18px 13px 5px;background-color:{sky_pale};">'
                f'<p style="margin:-25px 0 16px 8px;"><span style="display:inline-block;padding:4px 11px;background-color:{secondary};color:{ink};font-size:10px;font-weight:800;letter-spacing:.12em;transform:rotate(-2deg);">COURSE TICKETS</span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "spectrum_nodes":
            rows = []
            for index, item in enumerate(items, 1):
                item_color = (primary, accent, sky, secondary)[(index - 1) % 4]
                item_background = (pale, accent_pale, sky_pale, secondary_pale)[(index - 1) % 4]
                offset = 0 if index % 2 else 6
                rows.append(
                    f'<section style="margin:0 0 14px;padding-left:{offset}%;white-space:normal;">'
                    f'<span style="display:inline-block;width:18%;padding:7px 0;color:{item_color};font-family:Georgia,serif;font-size:25px;font-weight:800;line-height:1.2;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:76%;margin:0;padding:12px 15px;border-radius:{4 if index % 2 else 22}px {22 if index % 2 else 4}px 22px 22px;background-color:{item_background};color:{ink};font-size:14px;font-weight:650;line-height:1.72;vertical-align:top;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:31px 0;padding:5px 0 1px;">'
                f'<p style="margin:0 0 17px;color:{primary};font-size:10px;font-weight:800;letter-spacing:.12em;">关键要点 <span style="color:{accent};">●</span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "coordinate_index":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="border-top:1px solid #B7C5C0;white-space:normal;">'
                    f'<span style="display:inline-block;width:52px;padding:13px 7px;color:{primary};font-family:Georgia,serif;font-size:14px;font-weight:750;vertical-align:top;">R{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:12px 12px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:top;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};">'
                f'<section style="height:8px;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></section>'
                f'{"".join(rows)}'
                f'</section>'
            )
        if variant == "magazine_index":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="margin:0;border-top:1px solid {ink};white-space:normal;">'
                    f'<span style="display:inline-block;width:25%;padding:10px 8px 10px 0;color:{accent};font-family:Georgia,serif;font-size:38px;font-weight:800;line-height:1;letter-spacing:-.08em;vertical-align:top;">{index:02d}</span>'
                    f'<section style="box-sizing:border-box;display:inline-block;width:75%;min-height:64px;padding:11px 0 13px 15px;border-left:5px solid {primary};vertical-align:top;">'
                    f'<p style="margin:0;color:{ink};font-size:15px;font-weight:800;line-height:1.62;">{_inline(item)}</p>'
                    f'</section></section>'
                )
            return (
                f'<section style="margin:28px 0;padding:0;border-top:9px solid {ink};border-bottom:3px solid {ink};">'
                f'<p style="height:7px;margin:0 0 6px;background-color:{accent};width:31%;"></p>'
                f'{"".join(rows)}'
                f'</section>'
            )
        rows = []
        item_palettes = (
            (primary, pale, "#FFFFFF"),
            (secondary, secondary_pale, ink),
            (accent, accent_pale, "#FFFFFF"),
            (sky, sky_pale, "#FFFFFF"),
        )
        for index, item in enumerate(items, 1):
            item_accent, item_pale, number_color = item_palettes[(index - 1) % len(item_palettes)]
            rows.append(
                '<section style="margin:0 0 10px;white-space:normal;">'
                f'<span style="display:inline-block;width:36px;height:36px;border-radius:12px 12px 4px 12px;background-color:{item_accent};color:{number_color};font-size:12px;font-weight:750;line-height:36px;text-align:center;vertical-align:middle;">{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:80%;margin-left:10px;padding:12px 14px;border-left:3px solid {item_accent};border-radius:2px 14px 14px 2px;background-color:{item_pale};vertical-align:middle;">'
                f'<p style="margin:0;color:{ink};font-size:15px;font-weight:650;line-height:1.65;">{_inline(item)}</p></section></section>'
            )
        return (
            '<section style="margin:26px 0;">'
            f'<p style="margin:0 0 9px;">'
            f'<span style="display:inline-block;width:7px;height:7px;margin-right:5px;border-radius:50%;background-color:{accent};"></span>'
            f'<span style="display:inline-block;width:7px;height:7px;margin-right:5px;border-radius:50%;background-color:{secondary};"></span>'
            f'<span style="display:inline-block;width:22px;height:2px;margin:0 12px 2px 0;background-color:{sky};"></span></p>'
            f'{"".join(rows)}</section>'
        )

    if component_type == "evidence_callout":
        evidence = _inline(_one(parsed, bindings, "evidence"))
        if variant == "plain_evidence_note":
            return f'<blockquote style="margin:25px 0;padding:4px 0 4px 16px;border-left:3px solid {primary};color:#3F4A47;font-size:16px;line-height:1.8;">{evidence}</blockquote>'
        if variant == "floating_quote_note":
            return (
                f'<section style="margin:31px 3px 34px;padding:0 8px 13px 0;border-bottom:1px solid {sky};white-space:normal;">'
                f'<span style="display:inline-block;width:46px;margin-top:-7px;color:{secondary};font-family:Georgia,serif;font-size:72px;font-weight:700;line-height:.72;vertical-align:top;">“</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:4px 0 0 4px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:650;line-height:1.9;vertical-align:top;">{evidence}</p>'
                f'<p style="margin:7px 0 -18px;text-align:right;"><span style="display:inline-block;width:34px;height:3px;background-color:{primary};"></span><span style="display:inline-block;width:7px;height:7px;margin-left:7px;border-radius:50%;background-color:{accent};"></span></p>'
                f'</section>'
            )
        if variant == "evidence_margin":
            return (
                f'<section style="margin:29px 0;padding:4px 0;border-top:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;white-space:normal;">'
                f'<span style="display:inline-block;width:23%;padding:17px 10px 13px 0;color:{primary};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.14em;vertical-align:top;">EVIDENCE<br><strong style="display:block;margin-top:8px;color:{accent};font-size:23px;letter-spacing:0;">↳</strong></span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:77%;margin:0;padding:16px 0 15px 16px;border-left:4px solid {primary};color:{ink};font-size:16px;font-weight:700;line-height:1.82;vertical-align:top;">{evidence}</p>'
                f'</section>'
            )
        if variant == "annotated_note":
            return (
                f'<section style="margin:34px 4px 31px;padding:0 0 15px;border-bottom:1px solid #D7B995;white-space:normal;">'
                f'<span style="display:inline-block;width:19%;margin-top:-11px;color:{accent_pale};font-family:Georgia,serif;font-size:76px;font-weight:700;line-height:.75;vertical-align:top;">“</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:81%;padding:6px 13px 13px 17px;border-left:3px solid {accent};background-color:#FFF9EF;box-shadow:7px 7px 0 {secondary_pale};vertical-align:top;">'
                f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:16px;font-weight:650;line-height:1.9;">{evidence}</p></section>'
                f'<p style="margin:8px 0 -21px;text-align:right;"><span style="display:inline-block;width:58px;height:10px;background-color:{secondary};opacity:.72;transform:rotate(-3deg);"></span></p>'
                f'</section>'
            )
        if variant == "megaphone_quote":
            return (
                f'<section style="margin:31px 0;padding:7px 0 17px;border-bottom:2px dashed {sky};white-space:normal;">'
                f'<span style="box-sizing:border-box;display:inline-block;width:66px;margin-left:4px;padding:14px 5px;background-color:{accent};color:#FFFFFF;font-size:10px;font-weight:800;letter-spacing:.12em;text-align:center;transform:rotate(-3deg);vertical-align:top;">CAMPUS<br>RADIO</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:79%;margin-left:3%;padding:15px 16px;background-color:{secondary_pale};box-shadow:6px 6px 0 {sky_pale};vertical-align:top;">'
                f'<p style="margin:0;color:{ink};font-size:16px;font-weight:700;line-height:1.85;">{evidence}</p></section></section>'
            )
        if variant == "pulse_quote":
            return (
                f'<section style="margin:34px 0;padding:3px 0 12px;white-space:normal;">'
                f'<span style="display:inline-block;width:17%;color:{secondary};font-family:Georgia,serif;font-size:64px;font-weight:800;line-height:.72;vertical-align:top;">“</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:83%;padding:4px 0 12px 15px;border-bottom:5px solid {accent_pale};vertical-align:top;">'
                f'<p style="margin:0 0 8px;color:{accent};font-size:10px;font-weight:800;letter-spacing:.08em;">证据摘录</p>'
                f'<p style="margin:0;color:{ink};font-size:16px;font-weight:700;line-height:1.86;">{evidence}</p></section></section>'
            )
        if variant == "editorial_margin_quote":
            return (
                f'<section style="margin:32px 0;padding:8px 0 13px;border-top:10px solid {ink};border-bottom:2px solid {ink};white-space:normal;">'
                f'<span style="display:inline-block;width:24%;padding:8px 8px 0 0;color:{accent};font-family:Georgia,serif;font-size:52px;font-weight:800;line-height:.8;vertical-align:top;">“</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:76%;margin:0;padding:9px 0 11px 16px;border-left:6px solid {accent};color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:19px;font-weight:800;line-height:1.78;vertical-align:top;">{evidence}</p>'
                f'</section>'
            )
        return (
            f'<section style="margin:28px 0;padding:18px 18px 19px;border:1px solid {primary};border-radius:4px 20px 20px 20px;background-color:{surface};box-shadow:5px 5px 0 {sky_pale};">'
            f'<p style="margin:0 0 10px;white-space:nowrap;">'
            f'<span style="display:inline-block;width:8px;height:8px;margin-right:8px;border-radius:50%;background-color:{accent};"></span>'
            f'<span style="display:inline-block;width:26px;height:3px;margin:0 0 2px 0;background-color:{secondary};"></span></p>'
            f'<p style="margin:0;color:{ink};font-size:16px;font-weight:650;line-height:1.8;">{evidence}</p></section>'
        )

    if component_type == "before_after_timeline":
        before = _inline(_one(parsed, bindings, "before"))
        after = _inline(_one(parsed, bindings, "after"))
        if variant == "stacked_before_after":
            return (
                '<section style="margin:25px 0;">'
                f'<p style="margin:0 0 10px;padding:14px;border-left:4px solid {accent};background-color:{accent_pale};line-height:1.7;"><strong>之前：</strong>{before}</p>'
                f'<p style="margin:0;padding:14px;border-left:4px solid {primary};background-color:{pale};line-height:1.7;"><strong>之后：</strong>{after}</p></section>'
            )
        if variant == "paired_current":
            return (
                f'<section style="margin:30px 0;padding:2px 0;white-space:normal;">'
                f'<section style="width:88%;padding:0 0 15px;border-bottom:1px solid {accent};">'
                f'<span style="display:inline-block;width:28px;height:28px;border-radius:50% 50% 50% 5px;background-color:{accent};color:#FFFFFF;font-size:11px;font-weight:800;line-height:28px;text-align:center;vertical-align:top;">前</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:1px 0 0 13px;color:{ink};font-size:14px;line-height:1.78;vertical-align:top;">{before}</p></section>'
                f'<p style="width:12%;height:24px;margin:0 0 0 44%;border-right:2px dotted {sky};"></p>'
                f'<section style="width:88%;margin-left:12%;padding:0 0 15px;border-bottom:1px solid {primary};">'
                f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:1px 13px 0 0;color:{ink};font-size:14px;line-height:1.78;text-align:right;vertical-align:top;">{after}</p>'
                f'<span style="display:inline-block;width:28px;height:28px;border-radius:50% 5px 50% 50%;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:800;line-height:28px;text-align:center;vertical-align:top;">后</span></section>'
                f'</section>'
            )
        if variant == "shift_axis":
            return (
                f'<section style="margin:30px 0;padding-left:19px;border-left:2px solid {primary};">'
                f'<section style="margin:0 0 20px;white-space:normal;">'
                f'<span style="display:inline-block;width:62px;margin-left:-16px;padding:6px 5px;background-color:{accent};color:#FFFFFF;font-size:11px;font-weight:800;text-align:center;vertical-align:top;">基线</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:74%;margin:0;padding:0 0 13px 15px;border-bottom:1px solid #BCC6C1;color:{ink};font-size:14px;line-height:1.76;vertical-align:top;">{before}</p></section>'
                f'<section style="margin:0 0 0 31px;white-space:normal;">'
                f'<span style="display:inline-block;width:62px;margin-left:-16px;padding:6px 5px;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:800;text-align:center;vertical-align:top;">变化</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:70%;margin:0;padding:0 0 13px 15px;border-bottom:4px solid {secondary};color:{ink};font-size:14px;font-weight:650;line-height:1.76;vertical-align:top;">{after}</p></section>'
                f'</section>'
            )
        if variant == "split_page_flip":
            return (
                f'<section style="margin:31px 0;padding:10px 8px 16px;background-color:{sky_pale};white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:15px 13px;border:1px dashed {accent};background-color:{surface};transform:rotate(-1deg);vertical-align:top;">'
                f'<span style="display:block;margin-bottom:10px;color:{accent};font-size:10px;font-weight:800;letter-spacing:.14em;">BEFORE PAGE</span>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.77;">{before}</p></section>'
                f'<span style="display:inline-block;width:6%;padding-top:53px;color:{primary};font-size:18px;text-align:center;vertical-align:top;">›</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:47%;margin-top:15px;padding:15px 13px;border-bottom:5px solid {primary};background-color:{secondary_pale};transform:rotate(1deg);vertical-align:top;">'
                f'<span style="display:block;margin-bottom:10px;color:{primary};font-size:10px;font-weight:800;letter-spacing:.14em;">NEXT PAGE</span>'
                f'<p style="margin:0;color:{ink};font-size:14px;font-weight:650;line-height:1.77;">{after}</p></section></section>'
            )
        if variant == "airy_before_after":
            return (
                f'<section style="margin:28px 0;padding:9px 0;border-top:1px solid {sky};border-bottom:1px solid {sky};white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:15px 14px;border-radius:18px 18px 5px 18px;background-color:{accent_pale};vertical-align:top;">'
                f'<span style="display:inline-block;width:22px;height:4px;margin-bottom:10px;background-color:{accent};"></span>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{before}</p></section>'
                f'<span style="display:inline-block;width:6%;padding-top:42px;color:{primary};font-size:18px;text-align:center;vertical-align:top;">→</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:15px 14px;border-radius:18px 18px 18px 5px;background-color:{pale};vertical-align:top;">'
                f'<span style="display:inline-block;width:22px;height:4px;margin-bottom:10px;background-color:{primary};"></span>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{after}</p></section></section>'
            )
        if variant == "stitched_before_after":
            return (
                f'<section style="margin:31px 0;padding:4px 0 2px 18px;border-left:1px dashed #D7B995;">'
                f'<section style="width:88%;padding:0 0 14px;border-bottom:1px solid #E1CDB2;white-space:normal;">'
                f'<span style="display:inline-block;width:48px;margin-left:-14px;padding:5px 7px;background-color:{accent_pale};color:{accent};font-size:11px;font-weight:800;text-align:center;transform:rotate(-3deg);vertical-align:top;">从前</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:1px 0 0 13px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:14px;line-height:1.82;vertical-align:top;">{before}</p></section>'
                f'<p style="height:27px;margin:0 0 0 47%;border-left:2px dotted {secondary};"></p>'
                f'<section style="width:88%;margin-left:8%;padding:0 0 14px;border-bottom:4px solid {primary};white-space:normal;">'
                f'<span style="display:inline-block;width:48px;margin-left:-14px;padding:5px 7px;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:800;text-align:center;transform:rotate(2deg);vertical-align:top;">后来</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:1px 0 0 13px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:14px;font-weight:650;line-height:1.82;vertical-align:top;">{after}</p></section></section>'
            )
        if variant == "editorial_before_after":
            return (
                f'<section style="margin:31px 0;border-top:10px solid {ink};border-bottom:2px solid {ink};white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:43%;min-height:158px;padding:17px 13px 20px 0;border-right:6px solid {accent};vertical-align:top;">'
                f'<span style="display:block;margin-bottom:15px;color:{accent};font-family:Georgia,serif;font-size:14px;font-weight:800;letter-spacing:.08em;">BEFORE</span>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{before}</p></section>'
                f'<section style="box-sizing:border-box;display:inline-block;width:57%;min-height:158px;margin-top:18px;padding:16px 0 19px 17px;background-color:{pale};vertical-align:top;">'
                f'<span style="display:block;margin-bottom:13px;color:{primary};font-family:Georgia,serif;font-size:27px;font-weight:800;line-height:1;">AFTER</span>'
                f'<p style="margin:0;color:{ink};font-size:15px;font-weight:700;line-height:1.78;">{after}</p></section></section>'
            )
        if variant == "vector_shift":
            return (
                f'<section style="margin:34px 0;padding:4px 0 8px;">'
                f'<section style="width:80%;padding:15px 17px;border-radius:4px 28px 28px 18px;background-color:{accent_pale};"><span style="color:{accent};font-size:10px;font-weight:800;">变化前</span><p style="margin:7px 0 0;color:{ink};font-size:14px;line-height:1.77;">{before}</p></section>'
                f'<p style="height:29px;margin:0 0 0 47%;border-left:2px dotted {secondary};"><span style="display:inline-block;width:8px;height:8px;margin:20px 0 0 -5px;border-radius:50%;background-color:{secondary};"></span></p>'
                f'<section style="width:80%;margin-left:12%;padding:15px 17px;border-radius:28px 4px 18px 28px;background:linear-gradient(135deg,{secondary_pale},{pale});box-shadow:5px 5px 0 {sky_pale};"><span style="color:{primary};font-size:10px;font-weight:800;">变化后</span><p style="margin:7px 0 0;color:{ink};font-size:14px;font-weight:650;line-height:1.77;">{after}</p></section>'
                f'</section>'
            )
        if variant == "change_register":
            return (
                f'<section style="margin:28px 0;border:1px solid {primary};background-color:{surface};">'
                f'<section style="height:8px;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></section>'
                f'<section style="border-bottom:1px solid #B7C5C0;white-space:normal;"><span style="display:inline-block;width:48px;padding:16px 8px;color:{accent};font-size:12px;font-weight:750;vertical-align:top;">之前</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding:15px 13px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;line-height:1.75;vertical-align:top;">{before}</p></section>'
                f'<section style="white-space:normal;"><span style="display:inline-block;width:48px;padding:16px 8px;color:{primary};font-size:12px;font-weight:750;vertical-align:top;">之后</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding:15px 13px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;line-height:1.75;vertical-align:top;">{after}</p></section></section>'
            )
        return (
            f'<section style="margin:28px 0;padding:3px 0 3px 13px;border-left:2px dotted {sky};">'
            '<section style="margin:0 0 20px;padding-left:13px;">'
            f'<span style="display:inline-block;margin:0 0 8px;padding:5px 11px;border-radius:4px 12px 12px 12px;background-color:{accent};color:#FFFFFF;font-size:11px;font-weight:750;">改革前</span>'
            f'<p style="margin:0;padding:12px 14px;border-radius:4px 14px 14px 14px;background-color:{accent_pale};color:{ink};font-size:15px;line-height:1.75;">{before}</p></section>'
            '<section style="padding-left:13px;">'
            f'<span style="display:inline-block;margin:0 0 8px;padding:5px 11px;border-radius:4px 12px 12px 12px;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:750;">改革后</span>'
            f'<p style="margin:0;padding:12px 14px;border-radius:4px 14px 14px 14px;background-color:{pale};color:{ink};font-size:15px;line-height:1.75;">{after}</p></section></section>'
        )

    if component_type == "logic_path":
        items = _many(parsed, bindings, "items")
        if variant == "plain_steps":
            return _plain_list(items, primary)
        if variant == "airy_route":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="margin:0 0 11px;white-space:normal;">'
                    f'<span style="display:inline-block;width:34px;height:34px;border:2px solid {sky};border-radius:50%;background-color:{surface};color:{primary};font-family:Georgia,serif;font-size:11px;font-weight:750;line-height:34px;text-align:center;vertical-align:middle;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0 0 0 10px;padding:10px 13px;border-radius:15px 15px 15px 3px;background-color:{sky_pale};color:{ink};font-size:14px;font-weight:650;line-height:1.68;vertical-align:middle;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:27px 0;padding:16px 13px 8px;border-top:1px solid {sky};border-bottom:1px solid {sky};">'
                f'{"".join(rows)}</section>'
            )
        if variant == "club_route_map":
            rows = []
            for index, item in enumerate(items, 1):
                node_color = (primary, accent, sky, secondary)[(index - 1) % 4]
                rows.append(
                    f'<section style="margin:0 0 11px;white-space:normal;">'
                    f'<span style="display:inline-block;width:20%;padding:10px 5px;background-color:{node_color};color:#FFFFFF;font-size:10px;font-weight:800;letter-spacing:.08em;text-align:center;transform:rotate({-2 if index % 2 else 2}deg);vertical-align:middle;">STOP {index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:76%;margin:0 0 0 4%;padding:10px 12px;border-bottom:2px dashed {node_color};color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:middle;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:29px 0;padding:17px 14px 8px;background-color:{surface};box-shadow:7px 7px 0 {sky_pale};">'
                f'<p style="margin:-25px 0 18px;"><span style="display:inline-block;padding:4px 11px;background-color:{secondary};color:{ink};font-size:9px;font-weight:800;letter-spacing:.14em;">CLUB ROUTE MAP</span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "campus_badge_route":
            rows = []
            for index, item in enumerate(items, 1):
                node_color = (primary, accent, sky, secondary)[(index - 1) % 4]
                text_color = ink if node_color == secondary else "#FFFFFF"
                rows.append(
                    f'<section style="margin:0 0 12px;white-space:normal;">'
                    f'<span style="display:inline-block;width:38px;height:38px;border:3px solid {surface};border-radius:12px 12px 4px 12px;background-color:{node_color};box-shadow:3px 3px 0 {secondary_pale};color:{text_color};font-family:Georgia,serif;font-size:11px;font-weight:800;line-height:38px;text-align:center;transform:rotate({-3 if index % 2 else 3}deg);vertical-align:middle;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:81%;margin:0 0 0 11px;padding:11px 14px;border-bottom:2px solid {node_color};color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:middle;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:28px 0;padding:16px 13px 8px;border:2px dashed {sky};border-radius:19px 6px 19px 19px;background-color:{surface};">'
                f'{"".join(rows)}</section>'
            )
        if variant == "process_register":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="border-top:1px solid #B7C5C0;white-space:normal;">'
                    f'<span style="display:inline-block;width:52px;padding:13px 7px;color:{primary};font-family:Georgia,serif;font-size:13px;font-weight:750;vertical-align:top;">P-{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:69%;margin:0;padding:12px 10px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;font-weight:650;line-height:1.68;vertical-align:top;">{_inline(item)}</p>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:14%;padding:15px 5px;color:{accent};font-size:13px;font-weight:800;text-align:right;vertical-align:top;">→</span>'
                    f'</section>'
                )
            return (
                f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};">'
                f'<p style="height:8px;margin:0;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "orbit_route":
            rows = []
            for index, item in enumerate(items, 1):
                item_color = (primary, secondary, accent, sky)[(index - 1) % 4]
                item_pale = (pale, secondary_pale, accent_pale, sky_pale)[(index - 1) % 4]
                offset = 0 if index % 2 else 7
                radius = "4px 24px 24px 16px" if index % 2 else "24px 4px 16px 24px"
                rows.append(
                    f'<section style="margin:0 0 13px;padding-left:{offset}%;white-space:normal;">'
                    f'<span style="display:inline-block;width:43px;color:{item_color};font-family:Georgia,serif;font-size:28px;font-weight:750;line-height:1.15;opacity:.82;vertical-align:middle;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:78%;margin:0;padding:12px 15px;border-radius:{radius};background:linear-gradient(135deg,{item_pale} 0%,{surface} 100%);box-shadow:4px 5px 0 {sky_pale};color:{ink};font-size:14px;font-weight:650;line-height:1.72;vertical-align:middle;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:31px 0;padding:8px 0 3px;">'
                f'<p style="margin:0 0 16px;color:{primary};font-size:11px;font-weight:800;letter-spacing:.12em;">进程路径'
                f'<span style="display:inline-block;width:48px;height:8px;margin-left:10px;border-radius:14px 3px 14px 3px;background-color:{secondary};transform:rotate(-5deg);vertical-align:middle;"></span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "signal_route":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="border-top:1px solid #B9D8D2;white-space:normal;">'
                    f'<span style="display:inline-block;width:50px;padding:13px 7px;color:{accent};font-family:Georgia,serif;font-size:12px;font-weight:800;vertical-align:top;">S{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:70%;margin:0;padding:12px 10px;border-left:2px solid {secondary};color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:top;">{_inline(item)}</p>'
                    f'<span style="display:inline-block;width:13%;padding:14px 5px;color:{primary};font-size:14px;font-weight:800;text-align:right;vertical-align:top;">●</span>'
                    f'</section>'
                )
            return (
                f'<section style="margin:28px 0;border:1px solid {primary};background-color:{surface};">'
                f'<p style="height:6px;margin:0;background-color:{primary};"><span style="display:block;width:28%;height:6px;background-color:{secondary};"></span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "folded_stair":
            rows = []
            stair_colors = (secondary, "#E98768", "#5FA99E", sky, primary)
            count = max(1, len(items))
            for index, item in enumerate(items, 1):
                progress = 1 if count == 1 else (index - 1) / (count - 1)
                width = round(68 + 32 * progress)
                margin = 100 - width
                background = stair_colors[(index - 1) % len(stair_colors)]
                number_color = ink if index == 1 else "#FFFFFF"
                rows.append(
                    f'<section style="box-sizing:border-box;width:{width}%;min-height:58px;margin:0 0 8px {margin}%;padding:11px 12px;background-color:{background};white-space:normal;">'
                    f'<span style="display:inline-block;width:36px;color:{number_color};font-family:Georgia,serif;font-size:16px;font-weight:750;line-height:1.5;opacity:.76;vertical-align:top;">{index:02d}</span>'
                    f'<strong style="display:inline-block;width:78%;color:{ink};font-size:13px;line-height:1.6;vertical-align:top;">{_inline(item)}</strong>'
                    f'</section>'
                )
            return (
                f'<section style="margin:28px 0;padding:19px 16px 16px;border:1px solid #C9C4B9;background-color:#F7F0E3;">'
                f'{"".join(rows)}</section>'
            )
        route_colors = (
            (accent, accent_pale, "#FFFFFF"),
            (secondary, secondary_pale, ink),
            (primary, pale, "#FFFFFF"),
            (sky, sky_pale, "#FFFFFF"),
        )
        rows = []
        for index, item in enumerate(items, 1):
            node_accent, node_pale, node_text = route_colors[(index - 1) % len(route_colors)]
            rows.append(
                '<section style="margin:0 0 12px;white-space:normal;">'
                f'<span style="display:inline-block;width:40px;height:40px;border:2px solid {surface};border-radius:50%;background-color:{node_accent};box-shadow:0 0 0 2px {node_pale};color:{node_text};font-size:12px;font-weight:750;line-height:40px;text-align:center;vertical-align:middle;">{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:80%;margin-left:10px;padding:13px 15px;border:1px solid {node_accent};border-radius:3px 15px 15px 15px;background-color:{node_pale};vertical-align:middle;">'
                f'<p style="margin:0;color:{ink};font-size:15px;font-weight:700;line-height:1.65;">{_inline(item)}</p></section></section>'
            )
        return (
            '<section style="margin:28px 0;">'
            f'<p style="margin:0 0 13px;"><span style="display:inline-block;width:18px;height:3px;margin:0 7px 2px 0;background-color:{secondary};vertical-align:middle;"></span></p>'
            f'{"".join(rows)}</section>'
        )

    if component_type == "concept_explainer":
        entries = _concept_entries(parsed, bindings)
        if len(entries) > 1:
            return _render_concept_group(entries, variant, colors)
        title, definition = entries[0]
        if variant == "plain_definition":
            return f'<section style="margin:25px 0;padding:16px;border-left:4px solid {primary};background-color:{pale};"><strong style="color:{primary};">{title}</strong><p style="margin:8px 0 0;line-height:1.8;">{definition}</p></section>'
        if variant == "open_definition_note":
            return (
                f'<section style="margin:30px 0;padding:0 0 4px 14px;border-left:3px solid {primary};">'
                f'<p style="margin:0 0 10px;color:{primary};font-family:Georgia,\'Noto Serif SC\',serif;font-size:19px;font-weight:750;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;padding:0 4px 14px 0;border-bottom:1px solid {sky};color:{ink};font-size:15px;line-height:1.86;">{definition}</p>'
                f'<p style="margin:-5px 0 0;text-align:right;"><span style="display:inline-block;width:13px;height:8px;border-radius:10px 2px 10px 2px;background-color:{secondary};transform:rotate(-20deg);"></span><span style="display:inline-block;width:6px;height:6px;margin-left:5px;border-radius:50%;background-color:{accent};"></span></p>'
                f'</section>'
            )
        if variant == "coordinate_definition":
            return (
                f'<section style="margin:30px 0;padding:0;border-top:4px solid {primary};white-space:normal;">'
                f'<span style="display:inline-block;width:25%;padding:14px 9px 12px 0;color:{accent};font-family:Georgia,serif;font-size:20px;font-weight:800;line-height:1;vertical-align:top;">TERM<small style="display:block;margin-top:8px;color:#71807A;font-size:8px;letter-spacing:.16em;">DEFINITION</small></span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:75%;padding:13px 0 14px 16px;border-left:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;vertical-align:top;">'
                f'<strong style="display:block;margin-bottom:7px;color:{primary};font-size:17px;line-height:1.55;">{title}</strong>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.8;">{definition}</p></section>'
                f'</section>'
            )
        if variant == "notebook_term":
            return (
                f'<section style="margin:31px 0;padding:17px 17px 18px 27px;border-left:10px dotted {sky};background-color:{surface};box-shadow:6px 7px 0 {secondary_pale};">'
                f'<p style="margin:-5px 0 11px;"><span style="display:inline-block;padding:4px 10px;background-color:{accent};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.13em;transform:rotate(-2deg);">NOTEBOOK TERM</span></p>'
                f'<p style="margin:0 0 10px;color:{primary};font-size:18px;font-weight:800;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;padding-top:10px;border-top:1px solid {sky};color:{ink};font-size:15px;line-height:1.86;">{definition}</p></section>'
            )
        if variant == "airy_definition":
            return (
                f'<section style="margin:28px 0;padding:19px 18px;border:1px solid {sky};border-radius:20px 20px 6px 20px;background-color:{sky_pale};box-shadow:5px 5px 0 {secondary_pale};">'
                f'<span style="display:inline-block;width:28px;height:4px;margin-bottom:12px;background-color:{secondary};"></span>'
                f'<p style="margin:0 0 9px;color:{primary};font-size:17px;font-weight:750;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:15px;line-height:1.85;">{definition}</p></section>'
            )
        if variant == "note_definition":
            return (
                f'<section style="margin:32px 0;padding:0 10px 14px 0;border-bottom:1px solid #D7B995;white-space:normal;">'
                f'<span style="display:inline-block;width:24%;padding:13px 10px 28px;background-color:{accent_pale};color:{accent};font-family:Georgia,serif;font-size:13px;font-weight:800;line-height:1.45;text-align:center;transform:rotate(-2deg);vertical-align:top;">词条<span style="display:block;width:0;height:0;margin:12px auto -22px;border-left:16px solid transparent;border-top:13px solid {secondary};"></span></span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:76%;padding:5px 0 5px 18px;border-left:2px dashed #D7B995;vertical-align:top;">'
                f'<p style="margin:0 0 9px;color:{primary};font-family:Georgia,\'Noto Serif SC\',serif;font-size:19px;font-weight:750;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:15px;line-height:1.88;">{definition}</p></section></section>'
            )
        if variant == "editorial_definition":
            return (
                f'<section style="margin:31px 0;border-top:10px solid {ink};border-bottom:2px solid {ink};white-space:normal;">'
                f'<p style="box-sizing:border-box;display:inline-block;width:39%;margin:0;padding:15px 12px 18px 0;color:{accent};font-family:Georgia,\'Noto Serif SC\',serif;font-size:23px;font-weight:800;line-height:1.42;vertical-align:top;">{title}</p>'
                f'<p style="box-sizing:border-box;display:inline-block;width:61%;margin:0;padding:15px 0 18px 17px;border-left:6px solid {accent};color:{ink};font-size:15px;line-height:1.84;vertical-align:top;">{definition}</p></section>'
            )
        if variant == "hologram_term":
            return (
                f'<section style="margin:33px 0;padding:19px 18px 18px;border-radius:4px 44px 4px 22px;background:linear-gradient(135deg,{surface},{secondary_pale});box-shadow:6px 6px 0 {sky_pale};">'
                f'<p style="margin:0 0 11px;"><span style="display:inline-block;padding:4px 10px;border-radius:12px 3px 12px 3px;background-color:{primary};color:#FFFFFF;font-size:10px;font-weight:800;">概念</span></p>'
                f'<p style="margin:0 0 9px;color:{ink};font-size:18px;font-weight:800;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;padding-top:11px;border-top:1px solid {secondary};color:{ink};font-size:15px;line-height:1.85;">{definition}</p>'
                f'<p style="margin:9px 0 -23px;text-align:right;"><span style="display:inline-block;width:38px;height:8px;border-radius:14px 3px 14px 3px;background-color:{accent};transform:rotate(-6deg);"></span></p></section>'
            )
        if variant == "definition_register":
            return (
                f'<section style="margin:28px 0;border:1px solid {primary};background-color:{surface};">'
                f'<section style="height:8px;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></section>'
                f'<p style="margin:0;padding:14px 15px;border-bottom:1px solid #B7C5C0;color:{primary};font-size:17px;font-weight:750;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;padding:15px;border-left:7px solid {secondary};color:{ink};font-size:15px;line-height:1.85;">{definition}</p></section>'
            )
        return (
            '<section style="margin:28px 0;">'
            f'<p style="margin:0 0 -1px 14px;"><span style="display:inline-block;width:52px;height:8px;border-radius:8px 8px 0 0;background-color:{primary};"></span></p>'
            f'<section style="padding:18px 18px 19px;border:1px solid {primary};border-radius:4px 16px 16px 16px;background-color:{pale};box-shadow:5px 5px 0 {secondary_pale};">'
            f'<p style="margin:0 0 9px;color:{primary};font-size:17px;font-weight:750;line-height:1.55;">{title}</p>'
            f'<p style="margin:0;color:#3D4845;font-size:16px;line-height:1.85;">{definition}</p></section></section>'
        )

    if component_type == "case_card":
        title = _inline(_one(parsed, bindings, "title"))
        body = _inline(_one(parsed, bindings, "body"))
        if variant == "plain_case":
            return f'<section style="margin:25px 0;padding:16px;border-left:4px solid {primary};background-color:{surface};"><strong style="color:{primary};">案例｜{title}</strong><p style="margin:8px 0 0;color:{ink};font-size:15px;line-height:1.8;">{body}</p></section>'
        if variant == "polaroid_story":
            return (
                f'<section style="margin:33px 8px 32px;padding:15px 15px 21px;background-color:{surface};box-shadow:8px 9px 0 {sky_pale};transform:rotate(-1deg);">'
                f'<p style="width:72px;height:12px;margin:-22px auto 15px;background-color:{secondary};opacity:.85;"></p>'
                f'<p style="margin:0 0 12px;padding-bottom:11px;border-bottom:2px dashed {sky};color:{primary};font-size:18px;font-weight:800;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;color:{ink};font-size:15px;line-height:1.86;">{body}</p>'
                f'<p style="margin:14px 0 -13px;text-align:right;"><span style="color:{accent};font-size:9px;font-weight:800;letter-spacing:.15em;">CAMPUS STORY</span></p></section>'
            )
        if variant == "campus_story_card":
            return (
                f'<section style="margin:31px 0;padding:7px 0 16px;border-bottom:2px solid {sky};">'
                f'<p style="width:68px;height:12px;margin:0 0 -5px 17px;background-color:{secondary};transform:rotate(-4deg);"></p>'
                f'<section style="padding:18px 17px;border:2px solid {primary};border-radius:5px 20px 20px 20px;background-color:{surface};box-shadow:6px 6px 0 {accent_pale};">'
                f'<p style="margin:0 0 10px;color:{primary};font-size:18px;font-weight:800;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;padding-top:11px;border-top:2px dashed {sky};color:{ink};font-size:15px;line-height:1.85;">{body}</p></section></section>'
            )
        if variant == "prototype_file":
            return (
                f'<section style="margin:33px 0 31px;padding:18px 18px 19px;border-radius:4px 36px 4px 24px;background:linear-gradient(140deg,{pale},{secondary_pale});box-shadow:7px 7px 0 {sky_pale};">'
                f'<p style="margin:-24px 0 14px;"><span style="display:inline-block;padding:5px 11px;border-radius:13px 3px 13px 3px;background-color:{accent};color:#FFFFFF;font-size:10px;font-weight:800;transform:rotate(-2deg);">案例观察</span></p>'
                f'<p style="margin:0 0 10px;color:{ink};font-size:18px;font-weight:800;line-height:1.55;">{title}</p>'
                f'<p style="margin:0;padding-top:11px;border-top:1px solid {sky};color:{ink};font-size:15px;line-height:1.85;">{body}</p></section>'
            )
        if variant == "signal_case_file":
            return (
                f'<section style="margin:29px 0;border:1px solid {primary};background-color:{surface};">'
                f'<p style="height:6px;margin:0;background-color:{secondary};"><span style="display:block;width:27%;height:6px;background-color:{accent};"></span></p>'
                f'<section style="padding:15px 16px;border-bottom:1px solid #B9D8D2;"><strong style="color:{primary};font-size:17px;line-height:1.55;">{title}</strong></section>'
                f'<p style="margin:0;padding:15px 16px 17px;border-left:7px solid {secondary};color:{ink};font-size:15px;line-height:1.84;">{body}</p></section>'
            )
        return (
            f'<section style="margin:30px 0;padding:18px;border:1px solid {primary};border-radius:3px 18px 18px 18px;background-color:{surface};box-shadow:6px 6px 0 {secondary_pale};">'
            f'<p style="margin:0 0 9px;color:{primary};font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;font-weight:750;line-height:1.55;">{title}</p>'
            f'<p style="margin:0;padding-top:11px;border-top:1px dashed {secondary};color:{ink};font-size:15px;line-height:1.85;">{body}</p></section>'
        )

    if component_type == "warning_note":
        body = _inline(_one(parsed, bindings, "body"))
        if variant == "plain_warning":
            return f'<p style="margin:24px 0;padding:13px 15px;border-left:4px solid {accent};background-color:{accent_pale};color:{ink};font-size:15px;line-height:1.75;"><strong>注意：</strong>{body}</p>'
        if variant == "corner_flag":
            return (
                f'<section style="margin:30px 0;padding:2px 0 0 14px;border-left:1px solid {accent};">'
                f'<p style="margin:0;color:{ink};font-size:15px;font-weight:650;line-height:1.82;">{body}</p>'
                f'<p style="margin:12px 0 0;white-space:nowrap;"><span style="display:inline-block;width:42px;height:3px;background-color:{accent};"></span><span style="display:inline-block;width:10px;height:10px;margin-left:8px;background-color:{secondary};transform:rotate(45deg);"></span></p>'
                f'</section>'
            )
        if variant == "risk_flag":
            return (
                f'<section style="margin:30px 0;border-top:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;white-space:normal;">'
                f'<span style="display:inline-block;width:21%;padding:16px 6px;background-color:{accent};color:#FFFFFF;font-family:Georgia,serif;font-size:11px;font-weight:800;letter-spacing:.1em;text-align:center;vertical-align:top;">RISK<br><strong style="font-size:24px;line-height:1.15;">!</strong></span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:79%;margin:0;padding:15px 0 15px 17px;color:{ink};font-size:15px;line-height:1.82;vertical-align:top;">{body}</p>'
                f'</section>'
            )
        if variant == "sticky_alert":
            return (
                f'<section style="margin:32px 5px;padding:19px 17px 17px;background-color:{secondary_pale};box-shadow:7px 7px 0 {accent_pale};transform:rotate(-1deg);">'
                f'<p style="margin:-27px 0 13px;"><span style="display:inline-block;padding:4px 10px;background-color:{accent};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.13em;">PINNED</span></p>'
                f'<p style="margin:0;color:{ink};font-size:15px;font-weight:650;line-height:1.82;">{body}</p></section>'
            )
        if variant == "soft_caution":
            return (
                f'<section style="margin:27px 0;padding:15px 17px;border:1px solid {sky};border-radius:18px 18px 5px 18px;background-color:{sky_pale};">'
                f'<span style="display:inline-block;width:9px;height:9px;margin-right:10px;border-radius:50%;background-color:{accent};vertical-align:top;"></span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:90%;margin:0;color:{ink};font-size:15px;line-height:1.8;vertical-align:top;">{body}</p></section>'
            )
        if variant == "taped_caution":
            return (
                f'<section style="margin:31px 0;padding:3px 0 13px 17px;border-left:6px solid {accent};border-bottom:1px solid #D7B995;white-space:normal;">'
                f'<span style="display:inline-block;width:20%;margin-left:-17px;padding:10px 6px 19px;background-color:{secondary};color:{primary};font-family:Georgia,serif;font-size:20px;font-weight:800;line-height:1;text-align:center;transform:rotate(-4deg);vertical-align:top;">!</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:80%;margin:0;padding:5px 0 8px 15px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:15px;font-weight:650;line-height:1.84;vertical-align:top;">{body}</p></section>'
            )
        if variant == "margin_caution":
            return (
                f'<section style="margin:31px 0;padding:0;border-top:2px solid {ink};border-bottom:9px solid {ink};white-space:normal;">'
                f'<span style="display:inline-block;width:21%;padding:18px 6px;background-color:{accent};color:#FFFFFF;font-family:Georgia,serif;font-size:38px;font-weight:800;line-height:1;text-align:center;vertical-align:top;">!</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:79%;margin:0;padding:16px 0 18px 17px;color:{ink};font-size:15px;font-weight:750;line-height:1.82;vertical-align:top;">{body}</p></section>'
            )
        if variant == "anomaly_alert":
            return (
                f'<section style="margin:33px 0;padding:16px 17px;border-left:6px solid {accent};border-radius:3px 24px 24px 3px;background-color:{accent_pale};white-space:normal;">'
                f'<span style="display:inline-block;width:18%;color:{accent};font-family:Georgia,serif;font-size:28px;font-weight:800;line-height:1;vertical-align:top;">!</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:82%;vertical-align:top;"><p style="margin:0 0 6px;color:{accent};font-size:10px;font-weight:800;">需要注意</p>'
                f'<p style="margin:0;color:{ink};font-size:15px;line-height:1.82;">{body}</p></section></section>'
            )
        if variant == "risk_register":
            return (
                f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};">'
                f'<section style="height:8px;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{accent};"></span></section>'
                f'<section style="white-space:normal;"><span style="display:inline-block;width:48px;padding:17px 8px;color:{accent};font-family:Georgia,serif;font-size:20px;font-weight:750;text-align:center;vertical-align:top;">!</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding:15px 14px;border-left:1px solid #B7C5C0;color:{ink};font-size:15px;line-height:1.8;vertical-align:top;">{body}</p></section></section>'
            )
        return (
            f'<section style="margin:28px 0;padding:16px 17px;border:1px solid {accent};border-radius:14px 3px 14px 3px;background-color:{accent_pale};">'
            f'<p style="margin:-22px 0 12px;"><span style="display:inline-block;width:54px;height:10px;background-color:{secondary};transform:rotate(-2deg);"></span></p>'
            f'<p style="margin:0;color:{ink};font-size:15px;font-weight:650;line-height:1.8;">{body}</p></section>'
        )

    if component_type == "action_checklist":
        items = _many(parsed, bindings, "items")
        if variant == "plain_checklist":
            rows = [f'<p style="margin:0 0 10px;color:{ink};font-size:15px;line-height:1.75;">□ {_inline(item)}</p>' for item in items]
            return f'<section style="margin:24px 0;padding:15px;border-left:3px solid {primary};background-color:{pale};">{"".join(rows)}</section>'
        if variant == "leaf_check_path":
            rows = []
            for index, item in enumerate(items, 1):
                item_color = (primary, sky, secondary)[(index - 1) % 3]
                rows.append(
                    f'<section style="margin:0 0 15px;white-space:normal;">'
                    f'<span style="display:inline-block;width:29px;height:20px;border-radius:16px 3px 16px 3px;background-color:{item_color};color:#FFFFFF;font-size:10px;font-weight:800;line-height:20px;text-align:center;transform:rotate(-6deg);vertical-align:top;">✓</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:0 0 11px 13px;border-bottom:1px solid #D6E5E1;color:{ink};font-size:14px;line-height:1.72;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:28px 0;padding:2px 0 1px 7px;border-left:1px dotted {sky};">'
                f'{"".join(rows)}</section>'
            )
        if variant == "audit_track":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="margin:0;border-bottom:1px solid #C7D0CC;white-space:normal;">'
                    f'<span style="display:inline-block;width:18%;padding:12px 7px;color:{primary};font-family:Georgia,serif;font-size:12px;font-weight:800;vertical-align:top;">CHK-{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:70%;margin:0;padding:11px 10px;border-left:1px solid #C7D0CC;color:{ink};font-size:14px;line-height:1.7;vertical-align:top;">{_inline(item)}</p>'
                    f'<span style="display:inline-block;width:12%;padding:12px 0;color:{accent};font-size:15px;font-weight:800;text-align:right;vertical-align:top;">□</span></section>'
                )
            return (
                f'<section style="margin:28px 0;border-top:4px solid {primary};">'
                f'<p style="margin:0;padding:7px 0;color:#71807A;font-family:Georgia,serif;font-size:8px;font-weight:800;letter-spacing:.16em;">AUDIT TRACK / HUMAN CHECK</p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "punch_card_list":
            rows = []
            for index, item in enumerate(items, 1):
                item_color = (primary, accent, sky, secondary)[(index - 1) % 4]
                rows.append(
                    f'<section style="margin:0 0 10px;padding:0 0 0 8px;border-left:5px dotted {item_color};white-space:normal;">'
                    f'<span style="display:inline-block;width:44px;padding:11px 4px;background-color:{item_color};color:#FFFFFF;font-family:Georgia,serif;font-size:11px;font-weight:800;text-align:center;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:81%;margin:0;padding:10px 12px;border-top:1px dashed {item_color};border-bottom:1px dashed {item_color};color:{ink};font-size:14px;line-height:1.72;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:29px 0;padding:16px 12px 6px;background-color:{secondary_pale};">'
                f'<p style="margin:-23px 0 16px 9px;"><span style="display:inline-block;padding:4px 10px;background-color:{primary};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">PUNCH LIST</span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "soft_tick_list":
            rows = []
            for item in items:
                rows.append(
                    f'<section style="margin:0 0 9px;padding:11px 13px;border-radius:15px 15px 15px 4px;background-color:{pale};white-space:normal;">'
                    f'<span style="display:inline-block;width:23px;height:23px;border-radius:50%;background-color:{primary};color:#FFFFFF;font-size:12px;font-weight:800;line-height:23px;text-align:center;vertical-align:top;">✓</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding-left:10px;color:{ink};font-size:14px;line-height:1.7;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return f'<section style="margin:27px 0;">{"".join(rows)}</section>'
        if variant == "field_checklist":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="margin:0 0 14px;white-space:normal;">'
                    f'<span style="display:inline-block;width:28px;height:28px;margin-left:-16px;border:1px solid {accent};border-radius:50%;background-color:{surface};color:{accent};font-family:Georgia,serif;font-size:11px;font-weight:800;line-height:28px;text-align:center;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:2px 0 12px 13px;border-bottom:1px dashed #D7B995;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:14px;line-height:1.78;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:29px 0;padding:6px 0 1px 17px;border-left:3px dotted {secondary};">'
                f'<p style="width:68px;height:11px;margin:-12px 0 18px -15px;background-color:{accent_pale};transform:rotate(-3deg);"></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "proofing_checklist":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="padding:0;border-top:1px solid {ink};white-space:normal;">'
                    f'<span style="display:inline-block;width:19%;padding:13px 6px 12px 0;color:{accent};font-family:Georgia,serif;font-size:20px;font-weight:800;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:69%;margin:0;padding:12px 9px 13px 13px;border-left:5px solid {primary};color:{ink};font-size:14px;font-weight:700;line-height:1.72;vertical-align:top;">{_inline(item)}</p>'
                    f'<span style="display:inline-block;width:12%;padding:13px 0;color:{accent};font-size:18px;font-weight:800;text-align:right;vertical-align:top;">□</span></section>'
                )
            return (
                f'<section style="margin:29px 0;padding:0;border-top:10px solid {ink};border-bottom:3px solid {ink};">'
                f'<p style="width:35%;height:7px;margin:0 0 5px;background-color:{accent};"></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "mission_nodes":
            rows = []
            for index, item in enumerate(items, 1):
                item_color = (primary, secondary, accent, sky)[(index - 1) % 4]
                item_background = (pale, secondary_pale, accent_pale, sky_pale)[(index - 1) % 4]
                rows.append(
                    f'<section style="margin:0 0 11px;white-space:normal;">'
                    f'<span style="display:inline-block;width:17%;padding:11px 0;color:{item_color};font-family:Georgia,serif;font-size:16px;font-weight:800;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:76%;margin:0;padding:11px 14px;border-radius:4px 18px 18px 18px;background-color:{item_background};color:{ink};font-size:14px;line-height:1.72;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:31px 0;padding:5px 0 1px;">'
                f'<p style="margin:0 0 16px;color:{primary};font-size:10px;font-weight:800;letter-spacing:.1em;">行动清单 <span style="color:{secondary};">→</span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "audit_matrix":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="border-top:1px solid #B7C5C0;white-space:normal;">'
                    f'<span style="display:inline-block;width:46px;padding:12px 7px;color:{primary};font-family:Georgia,serif;font-size:12px;font-weight:750;vertical-align:top;">A{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:68%;margin:0;padding:11px 10px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;line-height:1.7;vertical-align:top;">{_inline(item)}</p>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:17%;padding:13px 5px;color:{accent};font-size:13px;font-weight:800;text-align:right;vertical-align:top;">□</span></section>'
                )
            return f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};"><p style="height:8px;margin:0;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></p>{"".join(rows)}</section>'
        rows = []
        for index, item in enumerate(items, 1):
            rows.append(
                f'<section style="margin:0;padding:11px 0;border-bottom:1px dashed #D8D2C6;white-space:normal;">'
                f'<span style="display:inline-block;width:24px;height:24px;border:1px solid {primary};border-radius:4px;color:{primary};font-size:10px;font-weight:750;line-height:24px;text-align:center;vertical-align:top;">{index:02d}</span>'
                f'<p style="display:inline-block;width:84%;margin:0 0 0 11px;color:{ink};font-size:15px;line-height:1.7;vertical-align:top;">{_inline(item)}</p></section>'
            )
        return f'<section style="margin:28px 0;padding:17px 17px 7px;border:1px solid {primary};background-color:{surface};">{"".join(rows)}</section>'

    if component_type == "faq_card":
        question = _inline(_one(parsed, bindings, "question"))
        answer = _inline(_one(parsed, bindings, "answer"))
        if variant == "plain_qa":
            return f'<section style="margin:25px 0;"><p style="margin:0 0 8px;color:{primary};font-size:17px;font-weight:750;">Q：{question}</p><p style="margin:0;color:{ink};font-size:15px;line-height:1.8;">A：{answer}</p></section>'
        if variant == "conversation_bubble":
            return (
                f'<section style="margin:27px 0;">'
                f'<section style="width:84%;margin:0 0 10px;padding:12px 15px;border-radius:18px 18px 18px 4px;background-color:{sky_pale};">'
                f'<p style="margin:0;color:{primary};font-size:15px;font-weight:750;line-height:1.7;"><span style="margin-right:7px;color:{sky};font-family:Georgia,serif;">Q</span>{question}</p></section>'
                f'<section style="width:84%;margin-left:8%;padding:13px 15px;border-radius:18px 4px 18px 18px;background-color:{pale};box-shadow:4px 4px 0 {secondary_pale};">'
                f'<p style="margin:0;color:{ink};font-size:15px;line-height:1.8;"><strong style="margin-right:7px;color:{accent};font-family:Georgia,serif;">A</strong>{answer}</p></section></section>'
            )
        if variant == "advice_letter":
            return (
                f'<section style="margin:29px 0;padding:18px 17px;border:1px solid #E2CEB1;border-radius:3px 18px 4px 18px;background-color:#FFF8EC;box-shadow:5px 5px 0 {accent_pale};">'
                f'<p style="margin:0 0 12px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:750;line-height:1.68;">来信：{question}</p>'
                f'<p style="margin:0;padding-top:12px;border-top:1px dashed #D7C3A6;color:#4A514D;font-size:15px;line-height:1.84;">回信：{answer}</p></section>'
            )
        if variant == "campus_dialogue":
            return (
                f'<section style="margin:31px 0;padding:16px 13px 10px;background-color:{sky_pale};">'
                f'<p style="margin:-24px 0 15px 8px;"><span style="display:inline-block;padding:4px 10px;background-color:{secondary};color:{ink};font-size:9px;font-weight:800;letter-spacing:.13em;transform:rotate(-2deg);">CAMPUS TALK</span></p>'
                f'<section style="width:84%;padding:13px 15px;border-left:5px solid {accent};background-color:{surface};box-shadow:5px 5px 0 {secondary_pale};"><p style="margin:0;color:{ink};font-size:15px;font-weight:750;line-height:1.72;">{question}</p></section>'
                f'<section style="width:84%;margin:13px 0 0 8%;padding:13px 15px;border-bottom:4px solid {primary};background-color:{surface};"><p style="margin:0;color:{ink};font-size:14px;line-height:1.82;">{answer}</p></section></section>'
            )
        if variant == "campus_qa_cards":
            return (
                f'<section style="margin:29px 0;padding:5px 0 7px;">'
                f'<section style="width:86%;padding:14px 16px;border:2px solid {primary};border-radius:18px 18px 18px 5px;background-color:{surface};box-shadow:5px 5px 0 {secondary_pale};">'
                f'<p style="margin:0;color:{primary};font-size:16px;font-weight:800;line-height:1.7;"><span style="margin-right:8px;color:{accent};font-family:Georgia,serif;">Q</span>{question}</p></section>'
                f'<section style="width:84%;margin:12px 0 0 8%;padding:14px 16px;border-radius:18px 5px 18px 18px;background-color:{sky_pale};">'
                f'<p style="margin:0;color:{ink};font-size:15px;line-height:1.82;"><strong style="margin-right:8px;color:{sky};font-family:Georgia,serif;">A</strong>{answer}</p></section></section>'
            )
        if variant == "qa_register":
            return (
                f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};">'
                f'<p style="height:8px;margin:0;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></p>'
                f'<section style="padding:13px 14px;border-bottom:1px solid #B7C5C0;white-space:normal;"><span style="display:inline-block;width:35px;color:{accent};font-family:Georgia,serif;font-size:18px;font-weight:750;vertical-align:top;">Q</span><p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;color:{ink};font-size:15px;font-weight:750;line-height:1.68;vertical-align:top;">{question}</p></section>'
                f'<section style="padding:13px 14px 15px;white-space:normal;"><span style="display:inline-block;width:35px;color:{primary};font-family:Georgia,serif;font-size:18px;font-weight:750;vertical-align:top;">A</span><p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;color:{ink};font-size:14px;line-height:1.82;vertical-align:top;">{answer}</p></section></section>'
            )
        if variant == "console_dialogue":
            return (
                f'<section style="margin:32px 0;padding:18px 17px;border-radius:4px 34px 4px 24px;background:linear-gradient(135deg,{pale},{secondary_pale});">'
                f'<p style="margin:0 0 13px;color:{accent};font-size:10px;font-weight:800;">问答</p>'
                f'<p style="margin:0 0 13px;padding:0 0 11px;border-bottom:1px solid {sky};color:{ink};font-size:15px;font-weight:750;line-height:1.72;"><span style="margin-right:9px;color:{accent};font-family:Georgia,serif;font-size:20px;">Q</span>{question}</p>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.82;"><span style="margin-right:9px;color:{primary};font-family:Georgia,serif;font-size:17px;font-weight:800;">A</span>{answer}</p></section>'
            )
        if variant == "signal_qa":
            return (
                f'<section style="margin:28px 0;border:1px solid {primary};background-color:{surface};">'
                f'<p style="height:6px;margin:0;background-color:{primary};"><span style="display:block;width:29%;height:6px;background-color:{accent};"></span></p>'
                f'<section style="padding:13px 15px;border-bottom:1px solid #B9D8D2;white-space:normal;"><span style="display:inline-block;width:42px;color:{accent};font-family:Georgia,serif;font-size:12px;font-weight:800;vertical-align:top;">ASK</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;color:{ink};font-size:15px;font-weight:750;line-height:1.7;vertical-align:top;">{question}</p></section>'
                f'<section style="padding:14px 15px 16px;white-space:normal;"><span style="display:inline-block;width:42px;color:{primary};font-family:Georgia,serif;font-size:12px;font-weight:800;vertical-align:top;">RSP</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding-left:12px;border-left:2px solid {secondary};color:{ink};font-size:14px;line-height:1.82;vertical-align:top;">{answer}</p></section></section>'
            )
        return (
            f'<section style="margin:28px 0;padding:17px 0 15px;border-top:4px solid {ink};border-bottom:1px solid {ink};background-color:#FBF6EC;">'
            f'<section style="padding:0 15px 15px;white-space:normal;">'
            f'<span style="display:inline-block;width:50px;color:{accent};font-family:Georgia,serif;font-size:28px;font-weight:750;line-height:1;vertical-align:top;">Q/</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:750;line-height:1.68;vertical-align:top;">{question}</p></section>'
            f'<section style="padding:14px 15px 0;border-top:1px solid #CFCAC0;white-space:normal;">'
            f'<span style="display:inline-block;width:50px;color:{primary};font-family:Georgia,serif;font-size:20px;font-weight:750;line-height:1.2;vertical-align:top;">A/</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;color:{ink};font-size:14px;line-height:1.84;vertical-align:top;">{answer}</p></section></section>'
        )

    if component_type == "comparison_card":
        left = _inline(_one(parsed, bindings, "left"))
        right = _inline(_one(parsed, bindings, "right"))
        if variant == "plain_comparison":
            return f'<section style="margin:25px 0;"><p style="margin:0 0 9px;padding:12px;background-color:{accent_pale};line-height:1.75;"><strong>一：</strong>{left}</p><p style="margin:0;padding:12px;background-color:{pale};line-height:1.75;"><strong>二：</strong>{right}</p></section>'
        if variant == "orbit_comparison":
            return (
                f'<section style="margin:30px 0;padding:8px 0;white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:0 13px 15px 0;border-bottom:2px solid {sky};vertical-align:top;">'
                f'<span style="display:block;width:18px;height:18px;margin-bottom:10px;border:4px solid {accent};border-radius:50%;"></span>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{left}</p></section>'
                f'<span style="display:inline-block;width:6%;padding-top:42px;color:{primary};font-size:20px;text-align:center;vertical-align:top;">↗</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:15px 0 0 13px;border-top:2px solid {primary};vertical-align:top;">'
                f'<p style="margin:0 0 10px;color:{ink};font-size:14px;line-height:1.78;">{right}</p>'
                f'<span style="display:block;width:24px;height:12px;margin-left:auto;border-radius:18px 3px 18px 3px;background-color:{secondary};transform:rotate(-12deg);"></span></section>'
                f'</section>'
            )
        if variant == "split_ledger":
            return (
                f'<section style="margin:30px 0;border-top:4px solid {primary};border-bottom:1px solid #AEBBB5;white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:38%;padding:17px 13px 19px 0;vertical-align:top;">'
                f'<span style="display:block;margin-bottom:11px;color:{accent};font-family:Georgia,serif;font-size:28px;font-weight:800;">A</span>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{left}</p></section>'
                f'<section style="box-sizing:border-box;display:inline-block;width:62%;margin-top:14px;padding:15px 0 17px 17px;border-left:1px solid #AEBBB5;background-color:{pale};vertical-align:top;">'
                f'<span style="display:block;margin-bottom:9px;color:{primary};font-family:Georgia,serif;font-size:18px;font-weight:800;">B / CONTRAST</span>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{right}</p></section>'
                f'</section>'
            )
        if variant == "debate_cards":
            return (
                f'<section style="margin:31px 0;padding:15px 10px;background-color:{secondary_pale};white-space:normal;">'
                f'<p style="margin:-23px 0 15px;text-align:center;"><span style="display:inline-block;padding:4px 12px;background-color:{primary};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.14em;">CAMPUS DEBATE</span></p>'
                f'<section style="box-sizing:border-box;display:inline-block;width:46%;padding:15px 13px;border-top:5px solid {accent};background-color:{surface};transform:rotate(-1deg);vertical-align:top;"><p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{left}</p></section>'
                f'<span style="display:inline-block;width:8%;padding-top:45px;color:{sky};font-family:Georgia,serif;font-size:14px;font-weight:800;text-align:center;vertical-align:top;">VS</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:46%;margin-top:17px;padding:15px 13px;border-bottom:5px solid {primary};background-color:{surface};transform:rotate(1deg);vertical-align:top;"><p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{right}</p></section></section>'
            )
        if variant == "soft_split":
            return (
                f'<section style="margin:28px 0;white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:48%;padding:16px 14px;border:1px solid {sky};border-radius:18px 18px 5px 18px;background-color:{sky_pale};vertical-align:top;"><span style="display:block;width:24px;height:4px;margin-bottom:11px;background-color:{accent};"></span><p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{left}</p></section>'
                f'<section style="box-sizing:border-box;display:inline-block;width:48%;margin-left:4%;padding:16px 14px;border:1px solid {primary};border-radius:18px 18px 18px 5px;background-color:{pale};vertical-align:top;"><span style="display:block;width:24px;height:4px;margin-bottom:11px;background-color:{primary};"></span><p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{right}</p></section></section>'
            )
        if variant == "postcard_split":
            return (
                f'<section style="margin:31px 0;padding:6px 0 18px;border-bottom:1px solid #D7B995;white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:46%;min-height:156px;padding:11px 13px 17px 0;border-right:1px dashed #D7B995;vertical-align:top;">'
                f'<span style="display:block;width:42px;height:10px;margin:0 0 15px;background-color:{accent_pale};transform:rotate(-4deg);"></span>'
                f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:14px;line-height:1.82;">{left}</p></section>'
                f'<section style="box-sizing:border-box;display:inline-block;width:54%;min-height:156px;margin-top:19px;padding:15px 0 11px 18px;background-color:#FFF8ED;box-shadow:7px 7px 0 {secondary_pale};vertical-align:top;">'
                f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:14px;font-weight:650;line-height:1.82;">{right}</p>'
                f'<span style="display:block;width:13px;height:13px;margin:14px 0 0 auto;border-radius:50%;background-color:{primary};"></span></section></section>'
            )
        if variant == "editorial_split":
            return (
                f'<section style="margin:31px 0;border-top:11px solid {ink};border-bottom:3px solid {ink};white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:42%;min-height:164px;padding:16px 13px 19px 0;border-right:6px solid {accent};vertical-align:top;">'
                f'<span style="display:block;margin-bottom:14px;color:{accent};font-family:Georgia,serif;font-size:35px;font-weight:800;line-height:1;">A</span>'
                f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.8;">{left}</p></section>'
                f'<section style="box-sizing:border-box;display:inline-block;width:58%;min-height:164px;margin-top:18px;padding:15px 0 18px 17px;background-color:{pale};vertical-align:top;">'
                f'<span style="display:block;margin-bottom:12px;color:{primary};font-family:Georgia,serif;font-size:22px;font-weight:800;line-height:1;">B / COUNTERPOINT</span>'
                f'<p style="margin:0;color:{ink};font-size:14px;font-weight:700;line-height:1.8;">{right}</p></section></section>'
            )
        if variant == "dual_channel":
            return (
                f'<section style="margin:33px 0;padding:6px 0 12px;white-space:normal;">'
                f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:16px 14px;border-radius:4px 28px 4px 20px;background-color:{pale};vertical-align:top;"><span style="display:block;margin-bottom:9px;color:{primary};font-size:10px;font-weight:800;">A</span><p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{left}</p></section>'
                f'<span style="display:inline-block;width:6%;padding-top:55px;color:{secondary};font-size:18px;font-weight:800;text-align:center;vertical-align:top;">×</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:47%;margin-top:22px;padding:16px 14px;border-radius:28px 4px 20px 4px;background-color:{accent_pale};vertical-align:top;"><span style="display:block;margin-bottom:9px;color:{accent};font-size:10px;font-weight:800;">B</span><p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{right}</p></section></section>'
            )
        if variant == "comparison_register":
            return (
                f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};">'
                f'<section style="height:8px;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></section>'
                f'<section style="white-space:normal;"><span style="box-sizing:border-box;display:inline-block;width:50%;padding:15px;border-right:1px solid #B7C5C0;color:{ink};font-size:14px;line-height:1.76;vertical-align:top;">{left}</span><span style="box-sizing:border-box;display:inline-block;width:50%;padding:15px;color:{ink};font-size:14px;line-height:1.76;vertical-align:top;">{right}</span></section></section>'
            )
        return (
            f'<section style="margin:28px 0;padding:16px;border:1px solid #D8D3C8;background-color:{surface};white-space:normal;">'
            f'<section style="box-sizing:border-box;display:inline-block;width:48%;padding:14px;border-top:4px solid {accent};background-color:{accent_pale};vertical-align:top;"><p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{left}</p></section>'
            f'<section style="box-sizing:border-box;display:inline-block;width:48%;margin-left:4%;padding:14px;border-top:4px solid {primary};background-color:{pale};vertical-align:top;"><p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{right}</p></section></section>'
        )

    if component_type == "section_summary":
        items = _many(parsed, bindings, "items")
        if variant == "plain_summary":
            return _plain_list(items, primary)
        rows = []
        for item in items:
            rows.append(f'<p style="margin:0 0 9px;color:{ink};font-size:15px;line-height:1.7;"><span style="color:{accent};font-weight:800;">—</span> {_inline(item)}</p>')
        if variant == "mint_closing_field":
            return (
                f'<section style="margin:32px 0;padding:20px 2px 10px;border-top:1px solid {primary};border-bottom:1px solid {sky};">'
                f'<p style="margin:-27px 0 17px;text-align:center;"><span style="display:inline-block;padding:0 12px;background-color:{surface};color:{primary};font-family:Georgia,serif;font-size:22px;">✦</span></p>'
                f'{"".join(rows)}'
                f'<p style="margin:15px 0 0;text-align:right;"><span style="display:inline-block;width:48px;height:8px;border-radius:12px 2px 12px 2px;background-color:{secondary};transform:rotate(-5deg);"></span></p>'
                f'</section>'
            )
        if variant == "executive_strip":
            register_rows = []
            for index, item in enumerate(items, 1):
                register_rows.append(
                    f'<section style="padding:10px 0;border-top:1px solid #C7D0CC;white-space:normal;">'
                    f'<span style="display:inline-block;width:18%;color:{accent};font-family:Georgia,serif;font-size:12px;font-weight:800;vertical-align:top;">OUT-{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:32px 0;padding:0 0 2px;border-top:7px solid {primary};">'
                f'<section style="padding:9px 0 5px;white-space:normal;"><span style="display:inline-block;width:30%;color:{primary};font-family:Georgia,serif;font-size:20px;font-weight:800;vertical-align:top;">SUM</span><span style="display:inline-block;width:70%;padding-top:7px;color:#71807A;font-family:Georgia,serif;font-size:9px;font-weight:800;letter-spacing:.16em;text-align:right;vertical-align:top;">EXECUTIVE SUMMARY</span></section>'
                f'{"".join(register_rows)}</section>'
            )
        if variant == "noticeboard_takeaway":
            return (
                f'<section style="margin:32px 0;padding:20px 18px 16px;border:2px dashed {primary};background-color:{secondary_pale};box-shadow:7px 7px 0 {sky_pale};">'
                f'<p style="margin:-29px 0 17px;"><span style="display:inline-block;padding:5px 12px;background-color:{accent};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">NOTICEBOARD</span></p>'
                f'{"".join(rows)}'
                f'<p style="margin:14px 0 0;text-align:right;"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background-color:{primary};"></span><span style="display:inline-block;width:36px;height:2px;margin:0 0 4px 8px;background-color:{sky};"></span></p></section>'
            )
        if variant == "airy_takeaway":
            return (
                f'<section style="margin:30px 0;padding:18px 19px;border:1px solid {sky};border-radius:18px 18px 5px 18px;background-color:{sky_pale};box-shadow:5px 5px 0 {secondary_pale};">'
                f'<span style="display:block;width:28px;height:4px;margin-bottom:13px;background-color:{secondary};"></span>{"".join(rows)}</section>'
            )
        if variant == "letter_takeaway":
            return (
                f'<section style="margin:33px 0;padding:3px 3px 14px 19px;border-left:5px solid {accent};border-bottom:1px solid #D7B995;">'
                f'<p style="margin:-10px 0 17px -18px;"><span style="display:inline-block;width:72px;height:12px;background-color:{secondary};opacity:.72;transform:rotate(-3deg);"></span></p>'
                f'{"".join(rows)}'
                f'<p style="margin:15px 0 0;text-align:right;"><span style="display:inline-block;width:54px;height:1px;background-color:{primary};"></span><span style="display:inline-block;width:8px;height:8px;margin-left:8px;border-radius:50%;background-color:{accent};"></span></p></section>'
            )
        if variant == "editorial_takeaway":
            editorial_rows = []
            for index, item in enumerate(items, 1):
                editorial_rows.append(
                    f'<section style="padding:11px 0;border-top:1px solid {ink};white-space:normal;">'
                    f'<span style="display:inline-block;width:20%;color:{accent};font-family:Georgia,serif;font-size:22px;font-weight:800;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:80%;margin:0;padding-left:14px;border-left:5px solid {primary};color:{ink};font-size:14px;font-weight:700;line-height:1.72;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:33px 0;padding:0;border-top:11px solid {ink};border-bottom:3px solid {ink};">'
                f'<p style="width:32%;height:7px;margin:0 0 5px;background-color:{accent};"></p>'
                f'{"".join(editorial_rows)}</section>'
            )
        if variant == "signal_core":
            core_rows = []
            for index, item in enumerate(items, 1):
                core_rows.append(
                    f'<section style="padding:9px 0;white-space:normal;"><span style="display:inline-block;width:14%;color:{accent if index % 2 else primary};font-family:Georgia,serif;font-size:15px;font-weight:800;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;color:{ink};font-size:14px;font-weight:650;line-height:1.72;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:34px 0;padding:19px 18px 14px;border-radius:4px 42px 4px 26px;background:linear-gradient(135deg,{secondary_pale},{pale});box-shadow:7px 7px 0 {sky_pale};">'
                f'<p style="margin:0 0 10px;color:{primary};font-size:10px;font-weight:800;letter-spacing:.08em;">要点回收</p>'
                f'{"".join(core_rows)}'
                f'<p style="margin:8px 0 -20px;text-align:right;"><span style="display:inline-block;width:52px;height:9px;border-radius:14px 3px 14px 3px;background-color:{secondary};transform:rotate(-5deg);"></span><span style="display:inline-block;width:8px;height:8px;margin-left:8px;border-radius:50%;background-color:{accent};"></span></p></section>'
            )
        if variant == "summary_register":
            register_rows = []
            for index, item in enumerate(items, 1):
                register_rows.append(
                    f'<section style="border-top:1px solid #B7C5C0;white-space:normal;"><span style="display:inline-block;width:46px;padding:12px 7px;color:{primary};font-family:Georgia,serif;font-size:12px;font-weight:750;vertical-align:top;">{index:02d}</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding:11px 10px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;line-height:1.7;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return (
                f'<section style="margin:30px 0;border:1px solid {primary};background-color:{surface};">'
                f'<section style="height:8px;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></section>'
                f'{"".join(register_rows)}</section>'
            )
        return (
            f'<section style="margin:30px 0;padding:18px 19px;border-top:4px solid {primary};background-color:{pale};">'
            f'{"".join(rows)}</section>'
        )

    raise ValueError(f"没有组件渲染器：{component_type}.{variant}")
