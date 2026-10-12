from __future__ import annotations

import html
import re
from typing import Any

from .parser import ParsedArticle
from .heading_numbers import has_explicit_heading_number
from .theme_extensions import _palette, _payload
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


def _body_metrics(document: str, config: dict[str, Any]) -> str:
    """Apply typography to legacy token layouts as well as declarative layouts."""
    scale = config["generated_design_system"]["typography"]["body_scale"]
    spacing = {"tight": "-.02em", "normal": "0", "relaxed": ".04em"}[config["generated_design_system"]["typography"]["letter_spacing"]]
    return re.sub(r"font-size:(\d+(?:\.\d+)?)px;", lambda match: f"font-size:{float(match[1]) * scale:g}px;letter-spacing:{spacing};", document)


def render_generated_paragraph(content: str, config: dict[str, Any], *, lead: bool = False) -> str:
    custom = render_layout("lead", {"body": content}, config) if lead else None
    if custom is not None:
        return custom
    design, palette = _metrics(config)
    density = {"airy": 1.2, "balanced": 1, "compact": .85}[design["rhythm"]["density"]]
    margin = round(18 * density)
    inline = _inline(content).replace("<strong>", f'<strong style="{generated_inline_emphasis_style(config)}">')
    return f'<p style="margin:0 0 {margin}px;{text_style(config)}text-align:justify;overflow-wrap:anywhere;">{inline}</p>'


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


def render_generated_hero(title: str, kicker: str, config: dict[str, Any]) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    custom = render_layout("hero", {"title": title, "kicker": kicker}, config)
    if custom is not None:
        return custom
    composition = design["composition"]
    scale = float(design["typography"]["heading_scale"])
    size = round(29 * scale, 1)
    weight = int(design["typography"]["heading_weight"])
    title_html = _inline(title)
    motif = _motif(config)
    common = f'data-generated-theme="{html.escape(str(config.get("visual_system", "custom")))}" data-theme-grammar="generated-{composition}"'
    if composition == "arched_editorial":
        return f'<header {common} style="margin:30px 0 38px;{_frame_style(config)}background-color:{_surface(config)}text-align:center;"><p style="margin:-4px 0 18px;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.2em;">{html.escape(kicker)}</p><p style="margin:0 0 15px;">{motif}</p><h1 style="margin:0;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:{size}px;font-weight:{weight};line-height:1.42;">{title_html}</h1><p style="margin:17px 0 -5px;">{_motif(config, compact=True)}</p></header>'
    if composition == "offset_journal":
        return f'<header {common} style="margin:31px 7px 38px;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:-25px 0 17px;text-align:right;"><span style="display:inline-block;padding:5px 11px;background-color:{p["accent"]};color:#FFFFFF;font:800 9px Georgia;letter-spacing:.16em;transform:rotate(2deg);">{html.escape(kicker)}</span></p><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.4;">{title_html}</h1><p style="margin:17px 0 -3px;">{motif}</p></header>'
    if composition == "modular_exhibit":
        return f'<header {common} style="margin:30px 0 38px;border-top:7px solid {p["primary"]};border-bottom:1px solid {p["primary"]};white-space:normal;"><section style="display:inline-block;width:24%;padding:20px 8px 18px 0;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.16em;vertical-align:top;">{html.escape(kicker)}<p style="margin:15px 0 0;">{motif}</p></section><section style="box-sizing:border-box;display:inline-block;width:76%;padding:19px 0 21px 19px;border-left:1px solid {p["secondary"]};vertical-align:top;"><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.4;">{title_html}</h1></section></header>'
    if composition == "ribbon_story":
        return f'<header {common} style="margin:31px 0 38px;padding:0 0 22px;border-bottom:4px solid {p["primary"]};"><p style="margin:0 0 16px;"><span style="display:inline-block;padding:6px 17px;background-color:{p["secondary"]};color:{p["ink"]};font:800 9px Georgia;letter-spacing:.17em;transform:rotate(-2deg);">{html.escape(kicker)}</span></p><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.4;">{title_html}</h1><p style="margin:16px 0 -29px;text-align:right;">{motif}</p></header>'
    if composition == "woven_catalog":
        return f'<header {common} style="margin:31px 0 38px;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:0 0 15px;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.19em;">WOVEN EDITION · {html.escape(kicker)}</p><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.42;">{title_html}</h1><p style="margin:17px 0 0;border-top:1px dashed {p["secondary"]};padding-top:11px;text-align:right;">{motif}</p></header>'
    return f'<header {common} style="margin:31px 0 38px;padding:25px 17px 22px;border-top:1px solid {p["secondary"]};border-bottom:1px solid {p["secondary"]};background-color:{_surface(config)}text-align:center;"><p style="margin:-39px 0 17px;"><span style="display:inline-block;width:62px;height:62px;border:2px solid {p["primary"]};border-radius:50%;background-color:{p["surface"]};color:{p["accent"]};font:800 9px/62px Georgia;letter-spacing:.12em;">{html.escape(kicker[:8])}</span></p><h1 style="margin:0;color:{p["ink"]};font-size:{size}px;font-weight:{weight};line-height:1.42;">{title_html}</h1><p style="margin:16px 0 0;">{motif}</p></header>'


def render_generated_heading(content: str, level: int, section_index: int, config: dict[str, Any]) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    index = "" if has_explicit_heading_number(content) else f"{section_index:02d}"
    custom = render_layout("heading" if level == 2 else "subheading", {"title": content, "index": index}, config)
    if custom is not None:
        return f'<section data-heading-level="{level}">{custom}</section>'
    gap = int(design["rhythm"]["section_gap"])
    size = round((22 if level == 2 else 18 if level == 3 else 16) * float(design["typography"]["heading_scale"]), 1)
    weight = int(design["typography"]["heading_weight"])
    text = _inline(content)
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


def render_generated_list(items: list[str], ordered: bool, config: dict[str, Any], semantic_role: str) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    custom = render_layout("list", {"items": items}, config)
    if custom is not None:
        return custom
    rows = []
    for index, item in enumerate(items, 1):
        value = f"{index:02d}" if ordered else ("✓" if semantic_role == "action_checklist" else chr(64 + index) if semantic_role == "case_points" and index <= 26 else "·")
        rows.append(f'<section style="padding:11px 0;border-bottom:1px solid {p["secondary_pale"]};white-space:normal;"><span style="display:inline-block;width:15%;vertical-align:top;">{_marker(config, value)}</span><p style="box-sizing:border-box;display:inline-block;width:85%;margin:0;padding:2px 0 2px 11px;color:{p["ink"]};font-size:{round(16 * float(design["typography"]["body_scale"]), 1)}px;line-height:1.75;vertical-align:top;">{_inline(item)}</p></section>')
    return f'<section data-theme-grammar="generated-{design["marker"]}-list" style="margin:{design["rhythm"]["component_gap"]}px 0;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:-5px 0 9px;text-align:right;">{_motif(config, compact=True)}</p>{"".join(rows)}</section>'


def render_generated_table(rows: list[list[str]], config: dict[str, Any]) -> str | None:
    design, p = _metrics(config)
    if not design or not rows:
        return None
    header, *body = rows
    ths = "".join(f'<th style="padding:10px 8px;border:1px solid {p["primary"]};background-color:{p["pale"]};color:{p["ink"]};font-size:12px;line-height:1.45;text-align:left;">{_inline(cell)}</th>' for cell in header)
    trs = []
    for row_index, row in enumerate(body):
        cells = "".join(f'<td style="padding:10px 8px;border:1px solid {p["secondary"]};background-color:{_surface(config, row_index)};color:{p["ink"]};font-size:13px;line-height:1.58;vertical-align:top;">{_inline(cell)}</td>' for cell in row)
        trs.append(f'<tr>{cells}</tr>')
    return _body_metrics(f'<section data-theme-grammar="generated-{design["frame"]}-table" style="margin:{design["rhythm"]["component_gap"]}px 0;padding-top:9px;border-top:{design["ornament"]["border_width"] + 2}px solid {p["accent"]};overflow-wrap:anywhere;"><p style="margin:-1px 0 9px;text-align:right;">{_motif(config, compact=True)}</p><table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></section>', config)


def render_generated_quote(content: str, config: dict[str, Any]) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    custom = render_layout("quote", {"body": content}, config)
    if custom is not None:
        return custom
    return _body_metrics(f'<blockquote data-theme-grammar="generated-{design["composition"]}-quote" style="margin:{design["rhythm"]["component_gap"]}px 0;{_frame_style(config)}background-color:{_surface(config)}"><p style="margin:0 0 12px;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.16em;">EVIDENCE · {_motif(config, compact=True)}</p><p style="margin:0;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:650;line-height:1.85;">{_inline(content)}</p></blockquote>', config)


def render_generated_component(slot: dict[str, Any], parsed: ParsedArticle, config: dict[str, Any]) -> str | None:
    design, p = _metrics(config)
    if not design:
        return None
    component_type = str(slot["component_type"])
    payload = _payload(slot, parsed)
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
    head = f'<p style="margin:-5px 0 14px;color:{p["accent"]};font:800 9px Georgia;letter-spacing:.17em;">{label}<span style="float:right;">{_motif(config, compact=True)}</span></p>'
    kind = payload["kind"]
    if kind == "list":
        rows = []
        for index, item in enumerate(payload["items"], 1):
            rows.append(f'<section style="padding:10px 0;border-top:1px solid {p["secondary_pale"]};white-space:normal;"><span style="display:inline-block;width:16%;vertical-align:top;">{_marker(config, f"{index:02d}")}</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding-left:8px;color:{p["ink"]};font-size:15px;font-weight:650;line-height:1.75;vertical-align:top;">{_inline(item)}</p></section>')
        content = "".join(rows)
    elif kind == "pair":
        content = f'<section style="white-space:normal;"><section style="box-sizing:border-box;display:inline-block;width:48%;padding:14px;border-top:4px solid {p["accent"]};background-color:{p["accent_pale"]};vertical-align:top;"><p style="margin:0;color:{p["ink"]};font-size:14px;line-height:1.78;">{_inline(payload["left"])}</p></section><section style="box-sizing:border-box;display:inline-block;width:48%;margin:17px 0 0 4%;padding:14px;border-bottom:4px solid {p["primary"]};background-color:{p["pale"]};vertical-align:top;"><p style="margin:0;color:{p["ink"]};font-size:14px;line-height:1.78;">{_inline(payload["right"])}</p></section></section>'
    elif kind == "concept_group":
        entries = []
        for index, entry in enumerate(payload["entries"], 1):
            entries.append(f'<section style="padding:12px 0;border-top:1px solid {p["secondary_pale"]};white-space:normal;"><span style="display:inline-block;width:16%;vertical-align:top;">{_marker(config, f"{index:02d}")}</span><section style="box-sizing:border-box;display:inline-block;width:84%;padding-left:9px;vertical-align:top;"><strong style="display:block;color:{p["primary"]};font-size:17px;line-height:1.58;">{_inline(entry["title"])}</strong><p style="margin:7px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{_inline(entry["body"])}</p></section></section>')
        content = "".join(entries)
    elif kind == "title_body":
        title = _inline(payload["title"])
        body = _inline(payload["body"])
        if component_type == "question_hook":
            content = f'<section style="text-align:center;"><p style="margin:0 0 12px;">{_marker(config, "?")}</p><strong style="display:block;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:20px;line-height:1.65;">{title}</strong></section>'
        else:
            content = f'<strong style="display:block;color:{p["primary"]};font-size:18px;line-height:1.6;">{title}</strong><p style="margin:10px 0 0;color:{p["ink"]};font-size:14px;line-height:1.82;">{body}</p>'
    else:
        content = f'<p style="margin:0;color:{p["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:16px;font-weight:650;line-height:1.85;">{_inline(payload["body"])}</p>'
    return _body_metrics(f'<section data-generated-theme="{html.escape(str(config.get("visual_system", "custom")))}" data-theme-grammar="{grammar}" data-component-type="{component_type}" style="margin:{gap}px 0;{frame}background-color:{component_surface}">{head}{content}</section>', config)


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
