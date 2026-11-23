"""Native logic-path drawing recipes: layout only, without content binding."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .logic_path_content import LogicPathField, step_field_attributes, step_field_css, step_field_text


def render_native_logic_path(
    items: Sequence[str | LogicPathField], variant: str, colors: dict[str, str],
    *, theme_kit: str | None, item_inline: Callable[[str], str],
) -> str:
    primary, secondary, accent, sky = (colors[name] for name in ("primary", "secondary", "accent", "sky"))
    pale, secondary_pale, accent_pale, sky_pale = (colors[name] for name in ("pale", "secondary_pale", "accent_pale", "sky_pale"))
    surface, ink = colors["surface"], colors["ink"]

    def text_field(item: str | LogicPathField, style: str, *, tag: str = "p", prefix: str = "") -> str:
        style = step_field_css(style, item)
        return f'<{tag}{step_field_attributes(item)} style="{style}">{prefix}{step_field_text(item, item_inline)}</{tag}>'

    if variant == "plain_steps":
        rows = []
        for index, item in enumerate(items, 1):
            prefix_attr = ' data-editor-step-prefix="true"' if isinstance(item, LogicPathField) and item.editable else ""
            prefix = f'<strong{prefix_attr} style="color:{primary};">{index:02d}.</strong> '
            rows.append(text_field(item, "margin:0 0 12px;color:#34403E;font-size:16px;line-height:1.75;", prefix=prefix))
        return '<section style="margin:24px 0;">' + "".join(rows) + "</section>"
    if variant == "warm_route_nodes" and theme_kit == "warm_storybook_v1":
        rows = []
        for index, item in enumerate(items, 1):
            last = index == len(items)
            tab_color = secondary_pale if last else accent_pale
            tab_edge = secondary if last else accent
            seam = "0" if last else "1px dotted #D7B995"
            rows.append(
                f'<section style="box-sizing:border-box;padding:8px 9px 8px 8px;border-bottom:{seam};white-space:normal;">'
                f'<span data-theme-static="true" style="box-sizing:border-box;display:inline-block;width:31px;margin:1px 8px 0 -39px;padding:3px 0 2px;border-left:2px solid {tab_edge};border-radius:1px 8px 8px 1px;background-color:{tab_color};color:{primary};font:700 12px/20px Georgia,serif;text-align:center;vertical-align:top;">{index:02d}</span>'
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:100%;margin:0;color:{ink};font-size:15px;font-weight:550;line-height:1.76;vertical-align:top;overflow-wrap:anywhere;")}</section>'
            )
        return (
            f'<section data-theme-grammar="warm-stitched-notebook" style="margin:28px 0;padding:0 3px 3px 26px;border-bottom:1px solid #D7B995;">'
            f'<section data-theme-decoration="warm-route-tape" aria-hidden="true" style="box-sizing:border-box;height:8px;margin:0 8px -3px 0;text-align:right;font-size:1px;line-height:1px;">'
            f'<span style="display:inline-block;width:39px;height:7px;background-color:{secondary};opacity:.7;vertical-align:top;transform:rotate(-4deg);">&#160;</span></section>'
            f'<section data-theme-route-steps="true" style="padding:4px 0 2px 7px;border-top:1px solid #D7B995;border-left:1px dashed #D7B995;border-radius:0 13px 0 0;background-color:{surface};">{"".join(rows)}</section></section>'
        )
    if variant == "airy_route" and theme_kit == "airy_organic_v1":
        rows = []
        for index, item in enumerate(items, 1):
            last = index == len(items)
            # Let the stem grow with wrapped text; keep the leaf shapes in the gutter.
            leaf_end = last and index > 1
            rail_color = "transparent" if last else sky
            node_border = secondary if leaf_end else sky
            node_shape = "20px 4px 20px 5px" if leaf_end else "50%"
            node_background = secondary_pale if leaf_end else surface
            rows.append(
                f'<section style="padding:0 0 {0 if last else 13}px 26px;border-left:1px solid {rail_color};white-space:normal;">'
                f'<span data-theme-static="true" style="box-sizing:border-box;display:inline-block;width:32px;height:30px;margin:0 10px 0 -42px;border:1px solid {node_border};border-radius:{node_shape};background-color:{node_background};color:{primary};font-family:Georgia,serif;font-size:12px;font-weight:700;line-height:28px;text-align:center;vertical-align:top;">{index:02d}</span>'
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:100%;margin:0;padding:2px 0 0;color:{ink};font-size:15px;font-weight:500;line-height:1.75;vertical-align:top;overflow-wrap:anywhere;")}'
                '</section>'
            )
        sprout = (
            f'<section data-theme-decoration="airy-route-sprout" aria-hidden="true" style="box-sizing:border-box;height:17px;border-left:1px solid {sky};">'
            f'<span style="box-sizing:border-box;display:inline-block;width:17px;height:9px;margin:0 0 0 -1px;border-radius:14px 2px 14px 3px;background-color:{primary};font-size:1px;line-height:1px;vertical-align:top;transform:rotate(-19deg);">&#160;</span>'
            f'<span style="display:inline-block;width:4px;height:4px;margin:1px 0 0 6px;border-radius:50%;background-color:{accent};font-size:1px;line-height:1px;vertical-align:top;">&#160;</span>'
            '</section>'
        )
        return f'<section data-theme-grammar="airy-connected-route" style="margin:27px 0;padding:2px 0 2px 16px;">{sprout}<section data-theme-route-steps="true">{"".join(rows)}</section></section>'
    if variant == "airy_route":
        rows = []
        for index, item in enumerate(items, 1):
            rows.append(
                f'<section style="margin:0 0 11px;white-space:normal;">'
                f'<span style="display:inline-block;width:34px;height:34px;border:2px solid {sky};border-radius:50%;background-color:{surface};color:{primary};font-family:Georgia,serif;font-size:11px;font-weight:750;line-height:34px;text-align:center;vertical-align:middle;">{index:02d}</span>'
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:82%;margin:0 0 0 10px;padding:10px 13px;border-radius:15px 15px 15px 3px;background-color:{sky_pale};color:{ink};font-size:14px;font-weight:650;line-height:1.68;vertical-align:middle;")}'
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
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:76%;margin:0 0 0 4%;padding:10px 12px;border-bottom:2px dashed {node_color};color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:middle;")}</section>'
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
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:81%;margin:0 0 0 11px;padding:11px 14px;border-bottom:2px solid {node_color};color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:middle;")}'
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
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:69%;margin:0;padding:12px 10px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;font-weight:650;line-height:1.68;vertical-align:top;")}'
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
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:78%;margin:0;padding:12px 15px;border-radius:{radius};background:linear-gradient(135deg,{item_pale} 0%,{surface} 100%);box-shadow:4px 5px 0 {sky_pale};color:{ink};font-size:14px;font-weight:650;line-height:1.72;vertical-align:middle;")}</section>'
            )
        caption = "" if theme_kit == "future_science_editorial_v1" else f'<p style="margin:0 0 16px;color:{primary};font-size:11px;font-weight:800;letter-spacing:.12em;">进程路径' f'<span style="display:inline-block;width:48px;height:8px;margin-left:10px;border-radius:14px 3px 14px 3px;background-color:{secondary};transform:rotate(-5deg);vertical-align:middle;"></span></p>'
        return (
            f'<section style="margin:31px 0;padding:8px 0 3px;">'
            f'{caption}'
            f'{"".join(rows)}</section>'
        )
    if variant == "signal_route":
        rows = []
        for index, item in enumerate(items, 1):
            rows.append(
                f'<section style="border-top:1px solid #B9D8D2;white-space:normal;">'
                f'<span style="display:inline-block;width:50px;padding:13px 7px;color:{accent};font-family:Georgia,serif;font-size:12px;font-weight:800;vertical-align:top;">S{index:02d}</span>'
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:70%;margin:0;padding:12px 10px;border-left:2px solid {secondary};color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:top;")}'
                f'<span style="display:inline-block;width:13%;padding:14px 5px;color:{primary};font-size:14px;font-weight:800;text-align:right;vertical-align:top;">●</span>'
                f'</section>'
            )
        return (
            f'<section style="margin:28px 0;border:1px solid {primary};background-color:{surface};">'
            f'<p style="height:6px;margin:0;background-color:{primary};"><span style="display:block;width:28%;height:6px;background-color:{secondary};"></span></p>'
            f'{"".join(rows)}</section>'
        )
    if variant == "folded_stair" and theme_kit == "independent_magazine_v1":
        rows = []
        for index, item in enumerate(items, 1):
            inset = round(24 * (len(items) - index) / max(1, len(items) - 1))
            tab_color = (accent, secondary, primary)[(index - 1) % 3]
            tab_ink = ink if (index - 1) % 3 == 1 else "#FFFFFF"
            rows.append(
                f'<section style="margin:0 0 7px {inset}px;padding:9px 10px 9px 49px;border-top:1px solid {primary};border-bottom:1px solid #DFDDD3;background-color:{surface};white-space:normal;">'
                f'<span data-theme-static="true" style="box-sizing:border-box;display:inline-block;width:37px;margin:0 12px 0 -49px;padding:2px 0 4px;background-color:{tab_color};border-radius:0 0 10px 0;color:{tab_ink};font:750 16px/20px Georgia,serif;text-align:center;vertical-align:top;">{index:02d}</span>'
                f'{text_field(item, f"box-sizing:border-box;display:inline-block;width:100%;margin:0;color:{ink};font-size:15px;font-weight:650;line-height:1.73;vertical-align:top;overflow-wrap:anywhere;")}</section>'
            )
        return (
            f'<section data-theme-grammar="editorial-step-folio" style="margin:28px 0;padding:4px 0 1px;border-bottom:3px solid {ink};">'
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
                f'{text_field(item, f"display:inline-block;width:78%;color:{ink};font-size:13px;line-height:1.6;vertical-align:top;", tag="strong")}'
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
            f'{text_field(item, f"margin:0;color:{ink};font-size:15px;font-weight:700;line-height:1.65;")}</section></section>'
        )
    return (
        '<section style="margin:28px 0;">'
        f'<p style="margin:0 0 13px;"><span style="display:inline-block;width:18px;height:3px;margin:0 7px 2px 0;background-color:{secondary};vertical-align:middle;"></span></p>'
        f'{"".join(rows)}</section>'
    )
