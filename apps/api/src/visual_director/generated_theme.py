from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import Any

from .parser import ParsedArticle
from .component_presentation import resolve_component_recipe
from .timeline_recipe import timeline_field
from .heading_numbers import has_explicit_heading_number
from .logic_path_content import LogicPathField, step_field_attributes, step_field_css, step_field_text
from .official_theme_tables import render_official_theme_table
from .ordinary_list_content import ListValue, list_field_reading, ordinary_list_marker, ordinary_list_rows
from .reading_rules import LIST_BODY, apply_reading_css
from .reading_rules import (ARTICLE_TITLE, BODY, LABEL, LEAD, MARKER, QUOTE, SECTION_TITLE, SUBHEADING,
                            TABLE_BODY, TABLE_HEADER, ReadingProfile, authored_emphasis, authored_host_css, render_authored_text)
from .semantic_content import BoundSemanticContent, SemanticField, bind_semantic_content, field_inline
from .theme_extensions import _palette
from .theme_layouts import render_layout, text_style


def _design(config: dict[str, Any]) -> dict[str, Any] | None:
    value = config.get("generated_design_system")
    return value if isinstance(value, dict) else None


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("\n", "<br>")


def _metrics(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    return _design(config) or {}, _palette(config.get("palette", {}))


class _GeneratedTypeScale:
    """Scale legacy decoration CSS before inserting escaped author fields.

    Authored text can literally mention 'font-size:12px;' and an explicit
    reading role uses an absolute size. Neither is a theme decoration token.
    """
    def __init__(self, config: dict[str, Any]):
        typography = config["generated_design_system"]["typography"]
        self.scale = typography["body_scale"]
        self.spacing = {"tight": "-.02em", "normal": "0", "relaxed": ".04em"}[typography["letter_spacing"]]
        self.fields: list[str] = []

    def field(self, markup: str) -> str:
        self.fields.append(markup)
        # Cannot collide with source: author HTML is escaped, and this marker
        # is private to the token layout (not accepted by declarative layouts).
        return f"<!--wvd-type-field:{len(self.fields)-1}-->"

    def scale_css(self, css: str) -> str:
        return re.sub(r"font-size:(\d+(?:\.\d+)?)px;",
                      lambda m: f"font-size:{float(m[1]) * self.scale:g}px;letter-spacing:{self.spacing};", css)

    def finish(self, template: str) -> str:
        scaled = re.sub(r"<[a-zA-Z][^>]*>", lambda tag: self.scale_css(tag[0]), template)
        return re.sub(r"<!--wvd-type-field:(\d+)-->", lambda m: self.fields[int(m[1])], scaled)


def render_generated_paragraph(content: str, config: dict[str, Any], *, lead: bool = False, reading: ReadingProfile | None = None) -> str:
    custom = render_layout("lead", {"body": content}, config, field_roles={"body": LEAD}, reading=reading) if lead else None
    if custom is not None:
        return custom
    design, palette = _metrics(config)
    density = {"airy": 1.2, "balanced": 1, "compact": .85}[design["rhythm"]["density"]]
    margin = round(18 * density)
    inline = _inline(content).replace("<strong>", f'<strong data-content-role="inline-emphasis" style="{generated_inline_emphasis_style(config)}">')
    style = authored_host_css(f"margin:0 0 {margin}px;{text_style(config)}text-align:justify;overflow-wrap:anywhere;", LEAD if lead else BODY, reading)
    return f'<p style="{style}">{authored_emphasis(inline, reading)}</p>'


def _motif(config: dict[str, Any], *, compact: bool = False) -> str:
    design, p = _metrics(config)
    motifs = design.get("motifs", ["none"])
    density = float(design.get("ornament", {}).get("density", 0.4))
    if motifs == ["none"] or density <= 0:
        return ""
    pieces: list[str] = []
    count = 2 if compact or density < 0.55 else 3
    for motif in motifs:
        if motif == "botanical_vine":
            leaves = "".join(
                f'<span style="display:inline-block;width:{13 + index * 2}px;height:{7 + index}px;margin:0 3px;border-radius:90% 0 90% 0;background-color:{p["primary"]};transform:rotate({-28 + index * 24}deg);vertical-align:middle;">&#160;</span>'
                for index in range(count)
            )
            pieces.append(f'<span data-theme-motif="botanical-vine" style="display:inline-block;white-space:nowrap;vertical-align:middle;"><span style="display:inline-block;width:24px;border-top:1px solid {p["secondary"]};vertical-align:middle;">&#160;</span>{leaves}</span>')
        elif motif == "honeycomb":
            cells = "".join(
                f'<span style="display:inline-block;width:9px;height:9px;margin:0 4px;border:1px solid {p["secondary"]};border-radius:2px;background-color:{p["secondary_pale"]};transform:rotate(45deg);vertical-align:middle;">&#160;</span>'
                for _ in range(count + 1)
            )
            pieces.append(f'<span data-theme-motif="honeycomb" style="display:inline-block;white-space:nowrap;vertical-align:middle;">{cells}</span>')
        elif motif == "celestial_orbit":
            pieces.append(f'<span data-theme-motif="celestial-orbit" style="display:inline-block;width:34px;height:17px;border:1px solid {p["sky"]};border-radius:50%;text-align:center;vertical-align:middle;"><span style="display:inline-block;width:7px;height:7px;margin-top:4px;border-radius:50%;background-color:{p["accent"]};">&#160;</span></span>')
        elif motif == "paper_cut":
            pieces.append(f'<span data-theme-motif="paper-cut" style="display:inline-block;white-space:nowrap;vertical-align:middle;"><span style="display:inline-block;width:20px;height:8px;background-color:{p["accent"]};transform:rotate(-7deg);">&#160;</span><span style="display:inline-block;width:28px;height:8px;margin-left:5px;background-color:{p["secondary"]};transform:rotate(4deg);">&#160;</span></span>')
        elif motif == "wave_ripple":
            pieces.append(f'<span data-theme-motif="wave-ripple" style="display:inline-block;width:44px;height:13px;border-top:2px solid {p["sky"]};border-bottom:1px solid {p["secondary"]};border-radius:50%;vertical-align:middle;">&#160;</span>')
        elif motif == "architectural_grid":
            pieces.append(f'<span data-theme-motif="architectural-grid" style="display:inline-block;padding:3px;border:1px solid {p["primary"]};white-space:nowrap;vertical-align:middle;"><span style="display:inline-block;width:7px;height:7px;border-right:1px solid {p["primary"]};">&#160;</span><span style="display:inline-block;width:7px;height:7px;">&#160;</span></span>')
    return '<span style="display:inline-block;white-space:nowrap;vertical-align:middle;">' + '<span style="display:inline-block;width:10px;">&#160;</span>'.join(pieces) + '</span>'


def _frame_style(config: dict[str, Any], *, pad: bool = True) -> str:
    design, p = _metrics(config)
    frame = design.get("frame", "double_rule")
    ornament = design.get("ornament", {})
    border = int(ornament.get("border_width", 1))
    radius = int(ornament.get("corner_radius", 12))
    inset = int(design.get("rhythm", {}).get("inset", 16))
    density = design.get("rhythm", {}).get("density", "balanced")
    inset += 2 if density == "airy" else -2 if density == "compact" else 0
    spacing = {"tight": "-.01em", "normal": "0", "relaxed": ".02em"}.get(
        design.get("typography", {}).get("letter_spacing"),
        "0",
    )
    padding = (f"padding:{inset}px;" if pad else "") + f"letter-spacing:{spacing};"
    if frame == "arched":
        return f'{padding}border:{border}px solid {p["primary"]};border-radius:{max(radius, 18)}px {max(radius, 18)}px 3px 3px;'
    if frame == "double_rule":
        return f'{padding}border:{border}px solid {p["primary"]};border-top:{border + 3}px double {p["primary"]};border-bottom:{border + 3}px double {p["primary"]};'
    if frame == "offset_shadow":
        return f'{padding}border:{border}px solid {p["primary"]};border-radius:{radius}px;background-color:{p["surface"]};box-shadow:7px 7px 0 {p["secondary_pale"]};'
    if frame == "stitched":
        return f'{padding}border:{max(1, border)}px dashed {p["primary"]};border-radius:{radius}px;background-color:{p["surface"]};box-shadow:inset 0 0 0 4px {p["pale"]};'
    if frame == "bracketed":
        return f'{padding}border-left:{border + 3}px solid {p["primary"]};border-right:{border}px solid {p["secondary"]};border-radius:0 {radius}px {radius}px 0;'
    return f'{padding}border-top:{border}px solid {p["primary"]};border-left:{border}px solid {p["primary"]};border-radius:{radius}px 0 0 0;'


def _surface(config: dict[str, Any], index: int = 0) -> str:
    design, p = _metrics(config)
    mode = design.get("surface", "quiet")
    if mode == "tinted":
        return p["pale"] + ";"
    if mode == "layered":
        return p["secondary_pale"] + ";"
    if mode == "alternating":
        return (p["pale"] if index % 2 == 0 else p["surface"]) + ";"
    return p["surface"] + ";"


def _marker(config: dict[str, Any], value: str) -> str:
    design, p = _metrics(config)
    marker = design.get("marker", "medallion")
    if marker == "seed":
        return f'<span style="display:inline-block;width:31px;height:22px;border-radius:90% 8px 90% 8px;background-color:{p["primary"]};color:#FFFFFF;font:700 10px/22px Georgia;text-align:center;transform:rotate(-7deg);vertical-align:top;">{value}</span>'
    if marker == "ticket":
        return f'<span style="display:inline-block;width:34px;padding:4px 0;border-top:2px solid {p["accent"]};border-bottom:2px solid {p["accent"]};color:{p["accent"]};font:800 10px Georgia;text-align:center;vertical-align:top;">{value}</span>'
    if marker == "coordinate":
        return f'<span style="display:inline-block;width:36px;color:{p["primary"]};font:800 9px Georgia;letter-spacing:.06em;vertical-align:top;">{value}</span>'
    if marker == "petal":
        return f'<span style="display:inline-block;width:28px;height:28px;border-radius:70% 15% 70% 15%;background-color:{p["accent_pale"]};color:{p["accent"]};font:800 10px/28px Georgia;text-align:center;transform:rotate(7deg);vertical-align:top;">{value}</span>'
    if marker == "bar":
        return f'<span style="display:inline-block;width:34px;padding-left:7px;border-left:7px solid {p["secondary"]};color:{p["primary"]};font:800 10px/18px Georgia;vertical-align:top;">{value}</span>'
    return f'<span style="display:inline-block;width:29px;height:29px;border:1px solid {p["primary"]};border-radius:50%;background-color:{p["surface"]};color:{p["primary"]};font:800 10px/28px Georgia;text-align:center;vertical-align:top;">{value}</span>'


def generated_inline_emphasis_style(config: dict[str, Any]) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    frame = design["frame"]
    if frame in {"arched", "offset_shadow"}:
        return f'padding:0 4px;border-bottom:6px solid {p["secondary_pale"]};color:{p["primary"]};font-weight:800;'
    if frame in {"stitched", "open_corner"}:
        return f'padding:0 3px;border-bottom:2px dashed {p["secondary"]};color:{p["primary"]};font-weight:800;'
    return f'padding:1px 4px;background-color:{p["secondary_pale"]};color:{p["primary"]};font-weight:800;'


def generated_image_frame_variant(config: dict[str, Any]) -> str | None:
    design = _design(config)
    return f'generated_{design["frame"]}' if design else None


def generated_image_placeholder_style(config: dict[str, Any]) -> str | None:
    design = _design(config)
    if not design:
        return None
    gap = int(design["rhythm"]["component_gap"])
    return f'scroll-margin-top:18px;margin:{gap}px 0;{_frame_style(config)}background-color:{_surface(config)}text-align:center;'


def render_generated_hero(title: str, kicker: str, config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    custom = render_layout("hero", {"title": title, "kicker": kicker}, config, field_roles={"title": ARTICLE_TITLE, "kicker": LABEL}, reading=reading)
    if custom is not None:
        return custom
    composition = design["composition"]
    scale = float(design["typography"]["heading_scale"])
    size = round(29 * scale, 1)
    weight = int(design["typography"]["heading_weight"])
    title_html = render_authored_text(_inline(title), ARTICLE_TITLE, reading)
    motif = _motif(config)
    common = f'data-generated-theme="{html.escape(str(config.get("visual_system", "custom")))}" data-theme-grammar="generated-{composition}"'
    if composition == "arched_editorial":
        return f'<header {common} style="margin:30px 0 38px;{_frame_style(config)}background-color:{_surface(config)}text-align:center;"><p style="margin:-4px 0 18px;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.2em;">{render_authored_text(html.escape(kicker), LABEL, reading)}</p><p style="margin:0 0 15px;">{motif}</p><h1 style="margin:0;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:{size}px;font-weight:{weight};line-height:1.42;">{title_html}</h1><p style="margin:17px 0 -5px;">{_motif(config, compact=True)}</p></header>'
    if composition == "offset_journal":
        return f'<header {common} style="margin:31px 7px 38px;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:-25px 0 17px;text-align:right;"><span style="display:inline-block;padding:5px 11px;background-color:{p["accent"]};color:#FFFFFF;font:800 9px Georgia;letter-spacing:.16em;transform:rotate(2deg);">{render_authored_text(html.escape(kicker), LABEL, reading)}</span></p><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.4;">{title_html}</h1><p style="margin:17px 0 -3px;">{motif}</p></header>'
    if composition == "modular_exhibit":
        return f'<header {common} style="margin:30px 0 38px;border-top:7px solid {p["primary"]};border-bottom:1px solid {p["primary"]};white-space:normal;"><section style="display:inline-block;width:24%;padding:20px 8px 18px 0;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.16em;vertical-align:top;">{render_authored_text(html.escape(kicker), LABEL, reading)}<p style="margin:15px 0 0;">{motif}</p></section><section style="box-sizing:border-box;display:inline-block;width:76%;padding:19px 0 21px 19px;border-left:1px solid {p["secondary"]};vertical-align:top;"><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.4;">{title_html}</h1></section></header>'
    if composition == "ribbon_story":
        return f'<header {common} style="margin:31px 0 38px;padding:0 0 22px;border-bottom:4px solid {p["primary"]};"><p style="margin:0 0 16px;"><span style="display:inline-block;padding:6px 17px;background-color:{p["secondary"]};color:{p["ink"]};font:800 9px Georgia;letter-spacing:.17em;transform:rotate(-2deg);">{render_authored_text(html.escape(kicker), LABEL, reading)}</span></p><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.4;">{title_html}</h1><p style="margin:16px 0 -29px;text-align:right;">{motif}</p></header>'
    if composition == "woven_catalog":
        return f'<header {common} style="margin:31px 0 38px;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:0 0 15px;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.19em;">WOVEN EDITION · {render_authored_text(html.escape(kicker), LABEL, reading)}</p><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.42;">{title_html}</h1><p style="margin:17px 0 0;border-top:1px dashed {p["secondary"]};padding-top:11px;text-align:right;">{motif}</p></header>'
    return f'<header {common} style="margin:31px 0 38px;padding:25px 17px 22px;border-top:1px solid {p["secondary"]};border-bottom:1px solid {p["secondary"]};background-color:{_surface(config)}text-align:center;"><p style="margin:-39px 0 17px;"><span style="display:inline-block;width:62px;height:62px;border:2px solid {p["primary"]};border-radius:50%;background-color:{p["surface"]};color:{p["accent"]};font:800 9px/62px Georgia;letter-spacing:.12em;">{render_authored_text(html.escape(kicker[:8]), LABEL, reading)}</span></p><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.42;">{title_html}</h1><p style="margin:16px 0 0;">{motif}</p></header>'


def render_generated_heading(content: str, level: int, section_index: int, config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    index = "" if has_explicit_heading_number(content) else f"{section_index:02d}"
    custom = render_layout("heading" if level == 2 else "subheading", {"title": content, "index": index}, config, field_roles={"title": SECTION_TITLE if level == 2 else SUBHEADING, "index": MARKER}, reading=reading)
    if custom is not None:
        return f'<section data-heading-level="{level}">{custom}</section>'
    gap = int(design["rhythm"]["section_gap"])
    size = round((22 if level == 2 else 18 if level == 3 else 16) * float(design["typography"]["heading_scale"]), 1)
    weight = int(design["typography"]["heading_weight"])
    text = render_authored_text(_inline(content), SECTION_TITLE if level == 2 else SUBHEADING, reading)
    motif = _motif(config, compact=True)
    grammar = f'generated-{design["composition"]}-{design["frame"]}'
    if level == 2:
        if not index:
            return f'<section data-heading-level="2" data-theme-grammar="{grammar}" style="margin:{gap}px 0 24px;padding-bottom:12px;border-bottom:{design["ornament"]["border_width"]}px solid {p["primary"]};"><strong style="display:block;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.5;">{text}</strong></section>'
        if design["composition"] in {"arched_editorial", "medallion_archive"}:
            return f'<section data-heading-level="2" data-theme-grammar="{grammar}" style="margin:{gap}px 0 24px;text-align:center;"><p style="margin:0 0 10px;">{_marker(config, f"{section_index:02d}")}</p><strong style="display:block;padding:0 12px 13px;border-bottom:{design["ornament"]["border_width"]}px solid {p["primary"]};color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:{size}px;font-weight:{weight};line-height:1.5;">{text}</strong><p style="margin:10px 0 0;">{motif}</p></section>'
        return f'<section data-heading-level="2" data-theme-grammar="{grammar}" style="margin:{gap}px 0 24px;white-space:normal;"><span style="display:inline-block;width:18%;padding-top:3px;vertical-align:top;">{_marker(config, f"{section_index:02d}")}</span><section style="box-sizing:border-box;display:inline-block;width:82%;padding:0 0 12px 15px;border-left:1px solid {p["secondary"]};border-bottom:{design["ornament"]["border_width"]}px solid {p["primary"]};vertical-align:top;"><strong style="display:block;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.5;">{text}</strong><p style="margin:9px 0 0;text-align:right;">{motif}</p></section></section>'
    return f'<section data-heading-level="{level}" data-theme-grammar="{grammar}" style="margin:{round(gap * .64)}px 0 14px;padding:0 0 9px 12px;border-left:{design["ornament"]["border_width"] + 2}px solid {p["accent"]};border-bottom:1px solid {p["secondary_pale"]};"><strong style="color:{p["primary"]};font-size:{size}px;font-weight:{weight};line-height:1.58;">{text}</strong></section>'


def render_generated_break(config: dict[str, Any]) -> str | None:
    custom = render_layout("divider", {}, config)
    if custom is not None:
        return custom
    design, p = _metrics(config)
    if not design:
        return None
    return f'<section data-content-role="thematic-break" data-theme-grammar="generated-{design["composition"]}-divider" style="margin:{design["rhythm"]["component_gap"] + 10}px 0;padding-top:10px;border-top:1px solid {p["secondary"]};text-align:center;">{_motif(config, compact=True)}</section>'


def _has_list_index(node: dict[str, Any]) -> bool:
    return node.get("bind") == "index" or any(_has_list_index(child) for child in node.get("children", []))


# The common theme contract exposes one list layout. Official themes can
# preserve separate bullet artwork and ordered sequence markers.
_WEEKEND_ORDERED_LIST_LAYOUT = {
    "type": "repeat",
    "bind": "items",
    "style": {"padding": [5, 0, 5, 0]},
    "children": [{
        "type": "marker_row",
        "marker_width": 12,
        "gap": 6,
        "children": [
            {
                "type": "field", "bind": "index",
                "style": {
                    "size": "label", "font": "mono", "weight": 750, "line_height": 1.5,
                    "color": "accent", "background": "secondary_pale", "align": "center",
                    "width": 30, "margin": [4, 0, 0, 0], "padding": [2, 2, 2, 2],
                    "radius": [2, 8, 4, 2],
                    "border_bottom": {"width": 1, "color": "secondary", "style": "solid"},
                },
            },
            {"type": "field", "bind": "item", "style": {"line_height": 1.9}},
        ],
    }],
}


_SCREENING_ORDERED_LIST_LAYOUT = {
    "type": "repeat", "bind": "items",
    "style": {"padding": [4, 0, 4, 0]},
    "children": [{
        "type": "marker_row", "marker_width": 10, "gap": 3,
        "children": [
            {
                "type": "field", "bind": "index",
                "style": {
                    "width": 30, "size": "label", "font": "mono", "weight": 800,
                    "line_height": 1.4, "align": "center", "color": "primary", "background": "secondary_pale",
                    "padding": [2, 2, 2, 2], "margin": [4, 0, 0, 0],
                    "radius": [2, 2, 6, 2],
                    "border_left": {"width": 2, "color": "primary", "style": "dotted"},
                    "border_bottom": {"width": 1, "color": "secondary", "style": "solid"},
                },
            },
            {"type": "field", "bind": "item", "style": {"line_height": 1.85}},
        ],
    }],
}
_WINDOW_ORDERED_LIST_LAYOUT = {
    "type": "repeat", "bind": "items",
    "style": {"padding": [2, 3, 2, 2], "border_top": {"width": 1, "color": "primary", "style": "solid"}},
    "children": [{
        "type": "marker_row", "marker_width": 10, "gap": 7,
        "children": [
            {
                "type": "field", "bind": "index",
                "style": {
                    "width": 29, "size": "label", "font": "mono", "weight": 780, "align": "center",
                    "line_height": 1.45, "color": "primary", "background": "pale",
                    "padding": [2, 1, 2, 1], "margin": [3, 0, 0, 0],
                    "border_right": {"width": 1, "color": "primary", "style": "solid"},
                    "border_bottom": {"width": 1, "color": "primary", "style": "solid"},
                },
            },
            {"type": "field", "bind": "item", "style": {"line_height": 1.85, "padding": [0, 0, 5, 0]}},
        ],
        "style": {"padding": [4, 0, 1, 0], "border_bottom": {"width": 1, "color": "secondary", "style": "dotted"}},
    }],
}
def _paper_ordered_list(
    marker_style: dict[str, Any], *, marker_width: int = 10, gap: int = 7,
) -> dict[str, Any]:
    return {
        "type": "repeat", "bind": "items",
        "children": [{
            "type": "marker_row", "marker_width": marker_width, "gap": gap,
            "style": {"padding": [2, 0, 2, 0]},
            "children": [
                {"type": "field", "bind": "index", "style": {
                    "size": "label", "weight": 780, "align": "center",
                    "line_height": 1.45, "padding": [2, 0, 1, 0], "margin": [3, 0, 0, 0],
                    **marker_style,
                }},
                {"type": "field", "bind": "item", "style": {"line_height": 1.82}},
            ],
        }],
    }


_OFFICIAL_ORDERED_LIST_LAYOUTS = {
    "weekend_fieldnotes": _WEEKEND_ORDERED_LIST_LAYOUT,
    "after_screening": _SCREENING_ORDERED_LIST_LAYOUT,
    "retro_window": _WINDOW_ORDERED_LIST_LAYOUT,
    "color_paper_corners": _paper_ordered_list({
        "font": "mono", "color": "primary", "background": "surface",
        "radius": [0, 0, 9, 0], "border_bottom": {"width": 2, "color": "secondary", "style": "solid"},
    }),
    "paper_fold": _paper_ordered_list({
        "font": "serif", "color": "accent", "background": "pale", "radius": [0, 5, 0, 0],
        "border_bottom": {"width": 1, "color": "secondary", "style": "solid"},
    }),
    "candidate_light_blue_watercolor": _paper_ordered_list({
        "font": "serif", "color": "primary", "background": "surface", "radius": [0, 0, 12, 4],
        "border_bottom": {"width": 2, "color": "secondary_pale", "style": "solid"},
    }),
    "toy_storybook": _paper_ordered_list({
        "font": "mono", "color": "primary", "background": "secondary_pale", "radius": [3, 8, 5, 7],
        "border_bottom": {"width": 1, "color": "secondary", "style": "solid"},
    }),
    "indigo_cloth": _paper_ordered_list({
        "font": "mono", "color": "primary", "background": "pale", "radius": [0, 3, 0, 3],
        "border_bottom": {"width": 1, "color": "sky", "style": "dashed"},
    }),
    "night_walk_illustration": _paper_ordered_list({
        "font": "mono", "color": "primary", "background": "secondary_pale", "radius": [8, 8, 1, 1],
        "border_bottom": {"width": 2, "color": "sky", "style": "solid"},
    }, marker_width=8, gap=5),
    "folded_fan_detail": {
        "type": "repeat", "bind": "items",
        "children": [{
            "type": "marker_row", "marker_width": 10, "gap": 7,
            "style": {"padding": [2, 0, 3, 0]},
            "children": [
                {"type": "field", "bind": "index", "style": {
                    "size": "label", "font": "serif", "color": "sky", "weight": 780, "align": "center",
                    "padding": [2, 0, 1, 0], "margin": [3, 0, 0, 0], "background": "sky_pale",
                    "radius": [9, 2, 9, 2], "border_bottom": {"width": 1, "color": "sky", "style": "solid"},
                }},
                {"type": "field", "bind": "item", "style": {"line_height": 1.85}},
            ],
        }],
    },
}


def render_generated_list(items: Sequence[ListValue], ordered: bool, config: dict[str, Any], semantic_role: str) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    ordered_layout = _OFFICIAL_ORDERED_LIST_LAYOUTS.get(config.get("theme_id")) if ordered else None
    if ordered_layout is not None:
        design = {**design, "layouts": {**design.get("layouts", {}), "list": ordered_layout}}
        config = {**config, "generated_design_system": design}
    layout = design.get("layouts", {}).get("list")
    profile = list_field_reading(items)
    if ordered and layout and not _has_list_index(layout):
        # An authored bullet list must not erase the sequence of an ordered
        # Markdown list. Keep its paragraph typography and explicit, copyable
        # numbers without introducing another layout role or a semantic card.
        item_style = apply_reading_css(
            "display:inline-block;width:90%;vertical-align:top;margin:0;overflow-wrap:anywhere;", LIST_BODY, profile,
        )
        rows = "".join(
            '<section style="padding:5px 0;">'
            f'<span data-theme-static="true" data-theme-list-index="true" style="display:inline-block;'
            f'width:10%;vertical-align:top;color:{p["primary"]};font-weight:700;">{index:02d}</span>'
            f'<p data-theme-field="item"{field_attrs} style="{item_style}">'
            f'{item}</p></section>'
            for index, field_attrs, item in ordinary_list_rows(items)
        )
        return f'<section data-theme-list-fallback="numbering" style="margin:{design["rhythm"]["component_gap"]}px 0;{text_style(config)}">{rows}</section>'
    custom = render_layout("list", {"items": items, "ordered": ordered}, config)
    if custom is not None:
        return custom
    rows = []
    item_style = apply_reading_css(
        f'box-sizing:border-box;display:inline-block;width:85%;margin:0;padding:2px 0 2px 11px;color:{p["ink"]};font-size:{round(16 * float(design["typography"]["body_scale"]), 1)}px;line-height:1.75;vertical-align:top;',
        LIST_BODY, profile,
    )
    for index, field_attrs, item in ordinary_list_rows(items):
        value = ordinary_list_marker(index, ordered=ordered, semantic_role=semantic_role, neutral_marker="·")
        index_attr = ' data-theme-list-index="true"' if ordered else ''
        rows.append(f'<section style="padding:11px 0;border-bottom:1px solid {p["secondary_pale"]};white-space:normal;"><span{index_attr} style="display:inline-block;width:15%;vertical-align:top;">{_marker(config, value)}</span><p{field_attrs} style="{item_style}">{item}</p></section>')
    return f'<section data-theme-grammar="generated-{design["marker"]}-list" style="margin:{design["rhythm"]["component_gap"]}px 0;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:-5px 0 9px;text-align:right;">{_motif(config, compact=True)}</p>{"".join(rows)}</section>'


def render_generated_table(rows: list[list[str]], config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str | None:
    design, p = _metrics(config)
    if not design or not rows:
        return None
    scale = _GeneratedTypeScale(config)
    official = render_official_theme_table(config.get("theme_id"), rows, p, design["rhythm"]["component_gap"], _inline, reading=reading, project_text=scale.field)
    if official is not None:
        return scale.finish(official)
    header, *body = rows
    # Give the table a palette accent on the header itself. Do not rely on a
    # paragraph between an outer rule and the table to carry the decoration.
    top_width = design["ornament"]["border_width"] + 2
    ths = "".join(
        f'<th style="padding:10px 8px;border:1px solid {p["primary"]};'
        f'border-top:{top_width}px solid {p["accent"] if i == 0 else p["primary"]};'
        f'background-color:{p["pale"]};color:{p["ink"]};font-size:12px;line-height:1.45;text-align:left;">'
        f'{scale.field(render_authored_text(_inline(cell), TABLE_HEADER, reading))}</th>'
        for i, cell in enumerate(header)
    )
    trs = []
    for row_index, row in enumerate(body):
        cells = "".join(f'<td style="padding:10px 8px;border:1px solid {p["secondary"]};background-color:{_surface(config, row_index)};color:{p["ink"]};font-size:13px;line-height:1.58;vertical-align:top;">{scale.field(render_authored_text(_inline(cell), TABLE_BODY, reading))}</td>' for cell in row)
        trs.append(f'<tr>{cells}</tr>')
    motif = _motif(config, compact=True)
    ornament = (
        f'<section aria-hidden="true" style="margin:0 0 4px;text-align:right;'
        f'font-size:0;line-height:0;">{motif}</section>' if motif else ""
    )
    return scale.finish(
        f'<section data-theme-grammar="generated-{design["frame"]}-table" '
        f'style="margin:{design["rhythm"]["component_gap"]}px 0;overflow-wrap:anywhere;">'
        f'{ornament}<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
        f'<thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></section>',

    )


def render_generated_quote(content: str, config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    custom = render_layout("quote", {"body": content}, config, field_roles={"body": QUOTE}, reading=reading)
    if custom is not None:
        return custom
    scale = _GeneratedTypeScale(config)
    return scale.finish(f'<blockquote data-theme-grammar="generated-{design["composition"]}-quote" style="margin:{design["rhythm"]["component_gap"]}px 0;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:0 0 12px;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.16em;">EVIDENCE · {_motif(config, compact=True)}</p><p style="margin:0;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:650;line-height:1.85;">{scale.field(render_authored_text(_inline(content), QUOTE, reading))}</p></blockquote>')


def render_generated_component(
    slot: dict[str, Any], parsed: ParsedArticle, config: dict[str, Any],
) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    content = bind_semantic_content(slot, parsed)
    return _render_generated_component_payload(content.component, content.layout_payload(), config, design, p)


def render_generated_semantic(
    content: BoundSemanticContent, config: dict[str, Any],
) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    return _render_generated_component_payload(content.component, content.layout_payload(), config, design, p)


def render_generated_logic_path(
    items: list[LogicPathField], config: dict[str, Any],
) -> str | None:
    design, palette = _metrics(config)
    if not design:
        return None
    return _render_generated_component_payload(
        "logic_path", {"kind": "list", "items": items}, config, design, palette,
    )


def _render_generated_component_payload(
    component_type: str, payload: dict[str, Any], config: dict[str, Any],
    design: dict[str, Any], p: dict[str, str],
) -> str:
    layout_payload = payload
    if component_type == "concept_explainer" and payload["kind"] == "title_body":
        layout_payload = {"entries": [{"title": payload["title"], "body": payload["body"]}]}
    custom = render_layout(component_type, layout_payload, config)
    if custom is not None:
        return f'<section data-component-type="{component_type}">{custom}</section>'
    gap = int(design["rhythm"]["component_gap"])
    inset = int(design["rhythm"]["inset"])
    if component_type in {"evidence_callout", "case_card"}:
        frame = f'padding:{inset}px 0 {inset}px {inset}px;border-left:{design["ornament"]["border_width"] + 3}px solid {p["accent"]};border-bottom:1px solid {p["secondary"]};'
        component_surface = p["surface"] + ";"
    elif component_type in {"before_after_timeline", "comparison_card"}:
        frame = f'padding:{inset}px 0;border-top:{design["ornament"]["border_width"] + 2}px solid {p["primary"]};border-bottom:1px solid {p["primary"]};'
        component_surface = p["surface"] + ";"
    elif component_type == "warning_note":
        frame = f'padding:{inset}px;border:{design["ornament"]["border_width"] + 1}px dashed {p["accent"]};border-radius:{design["ornament"]["corner_radius"]}px;'
        component_surface = p["accent_pale"] + ";"
    elif component_type in {"action_checklist", "logic_path"}:
        frame = f'padding:{inset}px;border-top:{design["ornament"]["border_width"] + 4}px solid {p["primary"]};border-bottom:1px solid {p["secondary"]};'
        component_surface = p["pale"] + ";"
    elif component_type == "section_summary":
        frame = f'padding:{inset}px;border:{design["ornament"]["border_width"]}px solid {p["primary"]};border-top:{design["ornament"]["border_width"] + 4}px double {p["primary"]};border-bottom:{design["ornament"]["border_width"] + 4}px double {p["primary"]};'
        component_surface = p["secondary_pale"] + ";"
    else:
        frame = _frame_style(config)
        component_surface = _surface(config)
    grammar = f'generated-{design["composition"]}-{design["marker"]}-component'
    label = {
        "question_hook": "QUESTION", "numbered_insight": "INSIGHT", "evidence_callout": "EVIDENCE",
        "before_after_timeline": "BEFORE / AFTER", "logic_path": "LOGIC PATH", "concept_explainer": "CONCEPT",
        "case_card": "CASE FILE", "warning_note": "NOTICE", "action_checklist": "CHECKLIST",
        "faq_card": "Q / A", "comparison_card": "COMPARISON", "section_summary": "SUMMARY",
    }.get(component_type, component_type.upper())
    recipe = resolve_component_recipe(config, component_type)
    scale = _GeneratedTypeScale(config)

    def render_field(value: str | SemanticField, name: str = "") -> str:
        return scale.field(timeline_field(value, name, recipe, _inline) if name else field_inline(value, _inline))

    head = f'<p style="margin:-5px 0 14px;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.17em;">{label}<span style="float:right;">{_motif(config, compact=True)}</span></p>'
    kind = payload["kind"]
    if kind == "list":
        rows = []
        legacy_style = f'box-sizing:border-box;display:inline-block;width:84%;margin:0;padding-left:8px;color:{p["ink"]};font-size:15px;font-weight:650;line-height:1.75;vertical-align:top;'
        for index, item in enumerate(payload["items"], 1):
            if isinstance(item, LogicPathField):
                # Scale this legacy host first, then apply its absolute role
                # metrics. Its title/detail and original strong are already projected.
                style = step_field_css(scale.scale_css(legacy_style), item)
                cell = scale.field(f'<p{step_field_attributes(item)} style="{style}">{step_field_text(item, _inline)}</p>')
            else:
                cell = f'<p style="{legacy_style}">{render_field(item)}</p>'
            rows.append(f'<section style="padding:10px 0;border-top:1px solid {p["secondary_pale"]};white-space:normal;"><span style="display:inline-block;width:16%;vertical-align:top;">{_marker(config, f"{index:02d}")}</span>{cell}</section>')
        content = "".join(rows)
    elif kind == "pair":
        content = f'<section style="white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:48%;padding:14px;border-top:4px solid {p["accent"]};background-color:{p["accent_pale"]};vertical-align:top;"><p style="margin:0;color:{p["ink"]};font-size:14px;line-height:1.78;">{render_field(payload["left"], "left")}</p></section><section style="box-sizing:border-box;display:inline-block;width:48%;margin:17px 0 0 4%;padding:14px;border-bottom:4px solid {p["primary"]};background-color:{p["pale"]};vertical-align:top;"><p style="margin:0;color:{p["ink"]};font-size:14px;line-height:1.78;">{render_field(payload["right"], "right")}</p></section></section>'
    elif kind == "concept_group":
        entries = []
        for index, entry in enumerate(payload["entries"], 1):
            entries.append(f'<section style="padding:12px 0;border-top:1px solid {p["secondary_pale"]};white-space:normal;"><span style="display:inline-block;width:16%;vertical-align:top;">{_marker(config, f"{index:02d}")}</span><section style="box-sizing:border-box;display:inline-block;width:84%;padding-left:9px;vertical-align:top;"><strong style="display:block;color:{p["primary"]};font-size:17px;line-height:1.58;">{render_field(entry["title"])}</strong><p style="margin:7px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{render_field(entry["body"])}</p></section></section>')
        content = "".join(entries)
    elif kind == "title_body":
        title = render_field(payload["title"])
        body = render_field(payload["body"])
        if component_type == "question_hook":
            content = f'<section style="text-align:center;"><p style="margin:0 0 12px;">{_marker(config, "?")}</p><strong style="display:block;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:20px;line-height:1.65;">{title}</strong></section>'
        else:
            content = f'<strong style="display:block;color:{p["primary"]};font-size:18px;line-height:1.6;">{title}</strong><p style="margin:10px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{body}</p>'
    else:
        content = f'<p style="margin:0;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:16px;font-weight:650;line-height:1.85;">{render_field(payload["body"])}</p>'
    return scale.finish(f'<section data-generated-theme="{html.escape(str(config.get("visual_system", "custom")))}" data-theme-grammar="{grammar}" data-component-type="{component_type}" style="{recipe.margin_css(gap)}{frame}background-color:{component_surface}">{head}{content}</section>')


def generated_rhythm_primitives(config: dict[str, Any]) -> list[dict[str, str]]:
    design, p = _metrics(config)
    if not design:
        return []
    heading = render_generated_heading("先理解问题，再决定行动", 2, 1, config) or ""
    subheading = render_generated_heading("把信息分成三个判断层级", 3, 1, config) or ""
    emphasis = generated_inline_emphasis_style(config) or ""
    divider = render_generated_break(config) or ""
    frame = generated_image_placeholder_style(config) or ""
    image = f'<section style="{frame}"><section style="height:145px;background-color:{p["pale"]};padding-top:35px;box-sizing:border-box;">{_motif(config)}</section><p style="margin:10px 0 0;color:{p["ink"]};font-size:11px;line-height:1.55;">图示 · 图片承接场景，正文负责解释</p></section>'
    closing = f'<section style="margin:34px 0;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:0 0 10px;">{_motif(config)}</p><strong style="display:block;color:{p["primary"]};font-size:17px;line-height:1.65;">把判断带回下一次真实行动</strong><p style="margin:8px 0 0;color:{p["ink"]};font-size:14px;line-height:1.75;">保存文章，并在行动中继续验证。</p></section>'
    image = render_layout("image_caption", {"caption": "图示 · 图片承接场景，正文负责解释", "media": {"specimen": True}}, config) or image
    closing = render_layout("closing_cta", {"body": "把判断带回下一次真实行动。保存文章，并在行动中继续验证。", "media": None}, config) or closing
    return [
        {"role": "section_heading", "label": "章节标题", "html": heading},
        {"role": "subheading", "label": "主题小标题", "html": subheading},
        {"role": "inline_emphasis", "label": "行内重点", "html": f'<p style="margin:22px 0;color:{p["ink"]};font-size:16px;line-height:1.9;">真正需要强调的是 <strong style="{emphasis}">决定读者下一步的关键词</strong>。</p>'},
        {"role": "image_caption", "label": "主题图文位", "html": image},
        {"role": "divider", "label": "章节分割线", "html": divider},
        {"role": "closing_cta", "label": "结尾行动区", "html": closing},
    ]
