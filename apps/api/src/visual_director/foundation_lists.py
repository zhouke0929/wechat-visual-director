from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .foundation_inline import _body_inline
from .generated_theme import render_generated_list
from .theme_extensions import render_extended_list
from .ordinary_list_content import ListValue, list_field_reading, ordinary_list_marker, ordinary_list_rows
from .reading_rules import LIST_BODY, apply_reading_css


def _render_list(
    items: Sequence[ListValue],
    ordered: bool,
    config: dict[str, Any],
    semantic_role: str = "key_points",
) -> str:
    generated = render_generated_list(items, ordered, config, semantic_role)
    if generated is not None:
        return generated
    extended = render_extended_list(items, ordered, config, semantic_role)
    if extended is not None:
        return extended
    accent = config["accent"]
    palette = config.get("palette", {})
    secondary = palette.get("secondary", accent)
    sky = palette.get("sky", secondary)
    rows = ordinary_list_rows(items, lambda text: _body_inline(text, config))
    reading = list_field_reading(items)
    if config["list_variant"] == "leaf_path":
        rendered = []
        item_style = apply_reading_css("box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:0 0 10px 13px;border-bottom:1px solid #D7E5E1;color:#34403E;font-size:16px;line-height:1.72;vertical-align:top;", LIST_BODY, reading)
        for index, field_attrs, item in rows:
            marker = str(index) if ordered else ordinary_list_marker(index, ordered=False, semantic_role=semantic_role)
            marker_color = (accent, sky, secondary)[(index - 1) % 3]
            rendered.append(
                '<section style="margin:0 0 14px;white-space:normal;">'
                f'<span style="display:inline-block;width:29px;height:20px;border-radius:16px 3px 16px 3px;background-color:{marker_color};color:#fff;font:700 10px/20px Arial;text-align:center;transform:rotate(-6deg);vertical-align:top;">{marker}</span>'
                f'<p{field_attrs} style="{item_style}">{item}</p></section>'
            )
        return f'<section style="margin:22px 0 25px;padding-left:7px;border-left:1px dotted {sky};">{"".join(rendered)}</section>'
    if config["list_variant"] == "audit_track":
        rendered = []
        item_style = apply_reading_css("box-sizing:border-box;display:inline-block;width:70%;margin:0;padding:11px 9px;border-left:1px solid #C7D0CC;color:#34403E;font-size:15px;line-height:1.7;vertical-align:top;", LIST_BODY, reading)
        for index, field_attrs, item in rows:
            marker = ordinary_list_marker(
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
                f'<p{field_attrs} style="{item_style}">{item}</p>'
                f'<span style="display:inline-block;width:12%;padding:12px 0;color:{secondary};font-size:14px;font-weight:800;text-align:right;vertical-align:top;">{"□" if semantic_role == "action_checklist" else "·"}</span></section>'
            )
        return (
            f'<section style="margin:22px 0 25px;border-top:4px solid {accent};">'
            f'<p style="margin:0;padding:7px 0;color:#71807A;font-family:Georgia,serif;font-size:8px;font-weight:800;letter-spacing:.16em;">AUDIT TRACK</p>'
            f'{"".join(rendered)}</section>'
        )
    if config["list_variant"] == "stitched_path":
        rendered = []
        item_style = apply_reading_css("box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:2px 0 11px 13px;border-bottom:1px dashed #D7B995;color:#342B28;font-family:Georgia,'Noto Serif SC',serif;font-size:15px;line-height:1.76;vertical-align:top;", LIST_BODY, reading)
        for index, field_attrs, item in rows:
            marker = ordinary_list_marker(index, ordered=ordered, semantic_role=semantic_role)
            rendered.append(
                '<section style="margin:0 0 14px;white-space:normal;">'
                f'<span style="display:inline-block;width:28px;height:28px;margin-left:-16px;border:1px solid {accent};border-radius:50%;background-color:#FFFCF7;color:{accent};font-family:Georgia,serif;font-size:11px;font-weight:800;line-height:28px;text-align:center;vertical-align:top;">{marker}</span>'
                f'<p{field_attrs} style="{item_style}">{item}</p></section>'
            )
        return (
            f'<section style="margin:22px 0 25px;padding:4px 0 1px 17px;border-left:3px dotted {secondary};">'
            f'{"".join(rendered)}</section>'
        )
    if config["list_variant"] == "proof_list":
        rendered = []
        item_style = apply_reading_css(f"box-sizing:border-box;display:inline-block;width:80%;margin:0;padding:11px 0 12px 14px;border-left:5px solid {accent};color:#202B33;font-size:15px;font-weight:700;line-height:1.7;vertical-align:top;", LIST_BODY, reading)
        for index, field_attrs, item in rows:
            marker = ordinary_list_marker(
                index,
                ordered=ordered,
                semantic_role=semantic_role,
                action_marker="■",
                neutral_marker="■",
            )
            rendered.append(
                '<section style="border-top:1px solid #202B33;white-space:normal;">'
                f'<span style="display:inline-block;width:20%;padding:12px 7px 11px 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:18px;font-weight:800;vertical-align:top;">{marker}</span>'
                f'<p{field_attrs} style="{item_style}">{item}</p></section>'
            )
        return (
            '<section style="margin:22px 0 25px;border-top:10px solid #202B33;border-bottom:3px solid #202B33;">'
            f'{"".join(rendered)}</section>'
        )
    if config["list_variant"] == "campus_steps":
        rendered = []
        item_style = apply_reading_css(f"box-sizing:border-box;display:inline-block;width:84%;margin:0 0 0 11px;padding:6px 0 11px;border-bottom:2px dashed {sky};color:{palette.get('ink', '#20304A')};font-size:15px;line-height:1.72;vertical-align:top;", LIST_BODY, reading)
        for index, field_attrs, item in rows:
            marker = ordinary_list_marker(index, ordered=ordered, semantic_role=semantic_role)
            marker_color = (
                accent,
                palette.get("accent", accent),
                sky,
                secondary,
            )[(index - 1) % 4]
            rendered.append(
                '<section style="margin:0 0 12px;white-space:normal;">'
                f'<span style="display:inline-block;width:31px;height:31px;border:3px solid #FFFEFB;border-radius:10px 10px 3px 10px;background-color:{marker_color};box-shadow:3px 3px 0 {palette.get("secondary_pale", "#FFF6D9")};color:#FFFFFF;font-family:Georgia,serif;font-size:10px;font-weight:800;line-height:31px;text-align:center;transform:rotate({-4 if index % 2 else 4}deg);vertical-align:top;">{marker}</span>'
                f'<p{field_attrs} style="{item_style}">{item}</p></section>'
            )
        return f'<section style="margin:22px 0 25px;padding:15px 13px 5px;border:2px solid {accent};border-radius:18px 6px 18px 18px;">{"".join(rendered)}</section>'
    if config["list_variant"] == "signal_track":
        rendered = []
        for index, field_attrs, item in rows:
            marker = ordinary_list_marker(
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
            item_style = apply_reading_css(f"box-sizing:border-box;display:inline-block;width:77%;margin:0;padding:11px 14px;border-radius:4px 18px 18px 18px;background-color:{item_background};color:{palette.get('ink', '#24304F')};font-size:15px;line-height:1.72;vertical-align:top;", LIST_BODY, reading)
            rendered.append(
                '<section style="margin:0 0 11px;white-space:normal;">'
                f'<span style="display:inline-block;width:17%;padding:10px 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:18px;font-weight:800;vertical-align:top;">{marker}</span>'
                f'<p{field_attrs} style="{item_style}">{item}</p></section>'
            )
        return (
            f'<section style="margin:23px 0 26px;padding:4px 0 1px;">'
            f'{"".join(rendered)}</section>'
        )
    rendered = []
    item_style = apply_reading_css("display:inline-block;max-width:84%;vertical-align:top;", LIST_BODY, reading)
    for index, field_attrs, item in rows:
        marker = (
            str(index)
            if ordered or config["list_variant"] == "vertical_numbered"
            else ordinary_list_marker(index, ordered=False, semantic_role=semantic_role)
        )
        rendered.append(
            '<p style="margin:0 0 12px;color:#34403E;font-size:16px;line-height:1.72;">'
            f'<span style="display:inline-block;width:25px;height:25px;margin-right:9px;border-radius:8px;background-color:{accent};color:#fff;font:700 12px/25px Arial;text-align:center;vertical-align:top;">{marker}</span>'
            f'<span{field_attrs} style="{item_style}">{item}</span></p>'
        )
    return f'<section style="margin:20px 0 24px;">{"".join(rendered)}</section>'
