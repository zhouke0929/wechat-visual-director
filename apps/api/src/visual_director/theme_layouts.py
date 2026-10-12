"""Bounded, declarative layouts: authors arrange fields, never execute templates.

The same field renderer is used by gallery and article output. Text bindings are
checked independently of appearance so a layout cannot omit or duplicate prose.
"""
from __future__ import annotations

import html
import math
import re
from collections import Counter
from typing import Any

from .theme_drawings import render_drawing, validate_drawing

PALETTE_KEYS = {"primary", "secondary", "accent", "sky", "pale", "secondary_pale", "accent_pale", "sky_pale", "surface", "ink"}
ROLE_FIELDS = {
    "hero": ({"title", "kicker"}, None),
    "heading": ({"title"}, None), "subheading": ({"title"}, None),
    "quote": ({"body"}, None), "lead": ({"body"}, None),
    "list": (set(), "items"),
    "question_hook": ({"title"}, None),
    "numbered_insight": (set(), "items"), "logic_path": (set(), "items"),
    "action_checklist": (set(), "items"), "section_summary": (set(), "items"),
    "evidence_callout": ({"body"}, None), "warning_note": ({"body"}, None),
    "before_after_timeline": ({"left", "right"}, None),
    "comparison_card": ({"left", "right"}, None),
    "concept_explainer": (set(), "entries"),
    "case_card": ({"title", "body"}, None), "faq_card": ({"title", "body"}, None),
    "divider": (set(), None),
    "image_caption": ({"caption"}, None),
    "closing_cta": ({"body"}, None),
}
SIZES = {"body": 16, "display": 56, "title": 29, "heading": 22, "subheading": 18, "caption": 13, "label": 11}
FONTS = {"serif": "Georgia,'Noto Serif SC',serif", "sans": "'Noto Sans SC','Microsoft YaHei',sans-serif", "mono": "Consolas,monospace"}


def _number(value: Any, minimum: float, maximum: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and minimum <= value <= maximum and math.isfinite(value)


def validate_layouts(value: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    def error(path: str, message: str) -> None:
        errors.append({"field": path, "message": message})

    def style(value: Any, path: str) -> None:
        if not isinstance(value, dict):
            error(path, "必须是样式参数对象，不接收 CSS 字符串")
            return
        for key, item in value.items():
            at = f"{path}.{key}"
            if key in {"color", "background"}:
                if not isinstance(item, str) or item not in PALETTE_KEYS:
                    error(at, "必须引用色板角色")
            elif key in {"padding", "margin", "radius"}:
                numbers = item if isinstance(item, list) else [item]
                minimum = -24 if key == "margin" else 0
                if (isinstance(item, list) and len(item) != 4) or not all(_number(n, minimum, 64) for n in numbers):
                    error(at, "间距超出范围；margin 可为 -24–64，其余为 0–64")
            elif key == "rotate":
                if not _number(item, -8, 8):
                    error(at, "旋转必须为 -8–8 度")
            elif key == "width":
                if not _number(item, 16, 160):
                    error(at, "局部宽度必须为 16–160px，始终受容器宽度约束")
            elif key == "fit":
                if item != "content":
                    error(at, "fit 仅支持 content")
            elif key == "shadow":
                if not isinstance(item, dict) or set(item) != {"x", "y", "blur", "color"}:
                    error(at, "阴影须声明 x、y、blur、color")
                elif (not _number(item["x"], -12, 12) or not _number(item["y"], -12, 12)
                      or not _number(item["blur"], 0, 24)
                      or not isinstance(item["color"], str) or item["color"] not in PALETTE_KEYS):
                    error(at, "无效的受控阴影参数")
            elif key in {"align", "font", "size"}:
                options = {"align": {"left", "center", "right", "justify"}, "font": FONTS, "size": SIZES}[key]
                if not isinstance(item, str) or item not in options:
                    error(at, "未知的排版参数")
            elif key == "weight":
                if not _number(item, 400, 900):
                    error(at, "字重必须为 400–900")
            elif key == "line_height":
                if not _number(item, 1.35, 2.2):
                    error(at, "行高必须为 1.35–2.2")
            elif key in {"border", "border_top", "border_right", "border_bottom", "border_left"}:
                if not isinstance(item, dict) or set(item) != {"width", "color", "style"}:
                    error(at, "边框须声明 width、color、style")
                elif (not _number(item["width"], 0, 8)
                      or not isinstance(item["color"], str) or item["color"] not in PALETTE_KEYS
                      or not isinstance(item["style"], str) or item["style"] not in {"solid", "double", "dashed", "dotted"}):
                    error(at, "无效的边框参数")
            else:
                error(at, "不支持的样式参数")

    if not isinstance(value, dict) or not value or set(value) - set(ROLE_FIELDS):
        return [{"field": "design_system.layouts", "message": "必须是非空的角色布局对象，且仅使用支持的角色"}]
    for role, root in value.items():
        required, collection = ROLE_FIELDS[role]
        fields: Counter[str] = Counter()
        repeat_count = 0
        media_count = 0
        node_count = 0

        def visit(node: Any, path: str, depth: int = 0, inside: str | None = None) -> None:
            nonlocal repeat_count, node_count, media_count
            node_count += 1
            if depth > 8 or node_count > 96:
                error(path, "每个布局最多 96 个节点、8 层嵌套")
                return
            if not isinstance(node, dict):
                error(path, "节点必须是对象")
                return
            kind = node.get("type")
            keys = {"stack": {"children"}, "row": {"children", "widths"},
                    "marker_row": {"children", "marker_width", "gap"},
                    "ornament_rule": {"children", "slot_width", "line_color"}, "text": {"text"},
                    "field": {"bind"}, "repeat": {"bind", "children"}, "rule": set(),
                    "shape": {"width", "height"}, "media": set(),
                    "cutout": {"children", "fill", "radius", "pitch", "inset"},
                    "drawing": {"width", "height", "parts", "sizing"}}
            if not isinstance(kind, str) or kind not in keys:
                error(path, "未知节点类型")
                return
            if set(node) - ({"type", "style"} | keys[kind]):
                error(path, "节点包含未知字段")
            style(node.get("style", {}), f"{path}.style")
            if kind == "drawing":
                for message in validate_drawing(node, PALETTE_KEYS):
                    error(path, message)
                if isinstance(node.get("parts"), list):
                    node_count += len(node["parts"])
                    if node_count > 96:
                        error(path, "线描图形计入每角色 96 节点预算")
            elif kind == "cutout":
                if (not isinstance(node.get("fill"), str) or node["fill"] not in PALETTE_KEYS
                        or not _number(node.get("radius"), 2, 8)
                        or not _number(node.get("pitch"), 12, 32)
                        or not _number(node.get("inset"), 10, 32)):
                    error(path, "齿孔需指定色板 fill、radius 2–8、pitch 12–32、inset 10–32")
                elif node["pitch"] < node["radius"] * 2 + 4 or node["inset"] < node["radius"] + 2:
                    error(path, "齿孔间距和内距不足，可能切入内容")
                if isinstance(node.get("style", {}), dict) and set(node.get("style", {})) & {"background", "padding", "radius"}:
                    error(path, "齿孔容器的底色与内距由 fill、inset 管理")
            elif kind == "media":
                media_count += 1
                if role not in {"image_caption", "closing_cta"}:
                    error(path, "图片节点仅用于图文位或页尾，资产由工作台提供")
            elif kind == "text":
                if not isinstance(node.get("text"), str) or not 1 <= len(node["text"]) <= 60:
                    error(path, "固定标签须为 1–60 字符，不放文章正文")
            elif kind == "field":
                bind = node.get("bind")
                allowed = ({"item", "index"} if inside == "items" else {"title", "body", "index"}) if inside else required | ({"index"} if role in {"heading", "subheading"} else set())
                if not isinstance(bind, str) or bind not in allowed:
                    error(path, "字段不属于当前语义角色或重复项")
                else:
                    fields[f"{inside or 'root'}.{bind}"] += 1
            elif kind == "shape":
                if not _number(node.get("width"), 2, 64) or not _number(node.get("height"), 2, 64):
                    error(path, "装饰宽高必须为 2–64px")
                if isinstance(node.get("style", {}), dict) and set(node.get("style", {})) - {"background", "radius", "border", "rotate", "margin", "shadow"}:
                    error(path, "装饰仅支持背景、圆角、边框、旋转、间距和阴影")
            if kind in {"stack", "row", "repeat", "cutout", "marker_row", "ornament_rule"}:
                children = node.get("children")
                if not isinstance(children, list) or not 1 <= len(children) <= 16:
                    error(path, "children 必须包含 1–16 个节点")
                    return
                scope = inside
                if kind == "marker_row":
                    if (len(children) != 2 or not _number(node.get("marker_width"), 6, 18)
                            or not _number(node.get("gap"), 0, 16)):
                        error(path, "标记横排需要两个子节点、6–18% 标记列宽和 0–16px 正文间距")
                    if children and isinstance(children[0], dict):
                        marker = children[0]
                        if marker.get("type") not in {"text", "shape", "field", "drawing"} or (marker.get("type") == "field" and marker.get("bind") != "index"):
                            error(path, "标记只能是短标签、编号、形状或小线描；正文放在第二列")
                if kind == "ornament_rule":
                    if (len(children) != 1 or not _number(node.get("slot_width"), 12, 40)
                            or not isinstance(node.get("line_color"), str) or node["line_color"] not in PALETTE_KEYS):
                        error(path, "装饰线需要一个小线描、12–40% 中央槽宽和色板线色")
                    for child in children:
                        if (not isinstance(child, dict) or child.get("type") != "drawing"
                                or not _number(child.get("height"), 8, 32)
                                or child.get("style")):
                            error(path, "装饰线只接受高 8–32px 的无额外样式 drawing，不包含正文")
                if kind == "repeat":
                    if inside or collection is None or node.get("bind") != collection:
                        error(path, "重复区域必须匹配语义集合，不能嵌套")
                        return
                    repeat_count += 1
                    scope = collection
                if kind == "row":
                    widths = node.get("widths")
                    if (not isinstance(widths, list) or not 2 <= len(widths) <= 3 or len(widths) != len(children)
                            or not all(_number(w, 20, 80) for w in widths) or abs(sum(widths) - 100) > .01):
                        error(path, "横排需要 2–3 列，列宽各为 20–80%，合计 100%")
                for index, child in enumerate(children):
                    visit(child, f"{path}.children[{index}]", depth + 1, scope)

        path = f"design_system.layouts.{role}"
        visit(root, path)
        if media_count != (1 if role in {"image_caption", "closing_cta"} else 0):
            error(path, "图文位和页尾必须且只能包含一个受控 media 节点")
        expected = {f"root.{key}" for key in required}
        if collection:
            expected |= {f"{collection}.{key}" for key in ({"item"} if collection == "items" else {"title", "body"})}
        if any(fields[key] != 1 for key in expected) or any(count > 1 for count in fields.values()) or repeat_count != (1 if collection else 0):
            error(path, "每个正文字段必须且只能出现一次，列表必须完整遍历一次")
    return errors


def text_style(config: dict[str, Any], size: str = "body", *, include_color: bool = True) -> str:
    design = config["generated_design_system"]
    typography = design["typography"]
    heading = size in {"display", "title", "heading", "subheading"}
    px = round(SIZES[size] * typography["heading_scale" if heading else "body_scale"], 2)
    spacing = {"tight": "-.02em", "normal": "0", "relaxed": ".04em"}[typography["letter_spacing"]]
    weight = typography["heading_weight"] if heading else 400
    color = f'color:{config["palette"]["ink"]};' if include_color else ""
    return f'font-size:{px:g}px;font-weight:{weight};letter-spacing:{spacing};line-height:{1.5 if heading else 1.85};{color}'


def _style(values: dict[str, Any], config: dict[str, Any]) -> str:
    result = []
    for key, value in sorted(values.items(), key=lambda item: item[0] != "size"):
        css = key.replace("_", "-")
        if key in {"color", "background"}:
            result.append(f'{"background-color" if key == "background" else key}:{config["palette"][value]}')
        elif key in {"padding", "margin", "radius"}:
            values_px = value if isinstance(value, list) else [value]
            result.append(f'{"border-radius" if key == "radius" else key}:' + " ".join(f"{n:g}px" for n in values_px))
        elif key == "size":
            result.append(text_style(config, value, include_color=False))
        elif key == "font":
            result.append(f"font-family:{FONTS[value]}")
        elif key == "rotate":
            result.append(f"transform:rotate({value:g}deg)")
        elif key == "width":
            result.append(f"width:{value:g}px")
        elif key == "fit":
            result.append("display:inline-block")
        elif key == "shadow":
            result.append(f'box-shadow:{value["x"]:g}px {value["y"]:g}px {value["blur"]:g}px {config["palette"][value["color"]]}')
        elif key.startswith("border"):
            result.append(f'{css}:{value["width"]:g}px {value["style"]} {config["palette"][value["color"]]}')
        else:
            result.append(f'{ {"align": "text-align", "weight": "font-weight"}.get(key, css)}:{value}')
    return ";".join(result) + ";"


def _inline(value: Any) -> str:
    escaped = html.escape(str(value))
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped).replace("\n", "<br>")


def render_layout(role: str, payload: dict[str, Any], config: dict[str, Any]) -> str | None:
    layouts = config.get("generated_design_system", {}).get("layouts", {})
    if role not in layouts:
        return None
    # Plans may contain frozen configuration; validate that path too, not just imports.
    errors = validate_layouts({role: layouts[role]})
    if errors:
        raise ValueError(f"Invalid theme layout: {errors[0]['field']}: {errors[0]['message']}")

    def render(node: dict[str, Any], context: dict[str, Any]) -> str:
        kind = node["type"]
        css = "box-sizing:border-box;max-width:100%;overflow-wrap:anywhere;"
        if kind in {"text", "field"}:
            css += "display:block;margin:0;"
            if kind == "text":
                css += text_style(config, "label", include_color=False)
        styles = node.get("style", {})
        css += _style({k: v for k, v in styles.items() if not (kind == "cutout" and k == "shadow")}, config)
        if kind == "drawing":
            return f'<section aria-hidden="true" style="{css}line-height:0;">{render_drawing(node, config["palette"])}</section>'
        if kind == "cutout":
            # Geometry only: no imported SVG, URL, selector or arbitrary CSS.
            # Independent strips keep both edges aligned at arbitrary widths.
            fill = config["palette"][node["fill"]]
            if "shadow" in styles:
                shadow = styles["shadow"]
                css += (f'filter:drop-shadow({shadow["x"]:g}px {shadow["y"]:g}px '
                        f'{shadow["blur"]:g}px {config["palette"][shadow["color"]]});')
            radius, pitch, inset = node["radius"], node["pitch"], node["inset"]
            gradients = ",".join(f'radial-gradient(circle at {anchor},transparent {radius:g}px,{fill} {radius + .5:g}px)'
                                 for anchor in ("0 50%", "100% 50%", "50% 0", "50% 100%"))
            edge = (f'padding:{inset:g}px;background-image:{gradients};'
                    f'background-size:{inset:g}px {pitch:g}px,{inset:g}px {pitch:g}px,{pitch:g}px {inset:g}px,{pitch:g}px {inset:g}px;'
                    'background-repeat:repeat-y,repeat-y,repeat-x,repeat-x;'
                    'background-position:left top,right top,left top,left bottom;')
            children = "".join(render(child, context) for child in node["children"])
            return (f'<section data-theme-cutout="true" style="{css}{edge}">'
                    f'<section style="background-color:{fill};">{children}</section></section>')
        if kind == "media":
            media = context.get("media")
            if not media:
                return ""
            if media.get("specimen") is True:
                return (f'<section data-theme-media="specimen" style="{css}padding:48px 16px;'
                        f'background-color:{config["palette"]["pale"]};color:{config["palette"]["ink"]};'
                        'text-align:center;">图片展示区</section>')
            # Only core asset references, never a theme-supplied URL or markup.
            source = str(media["src"])
            if not source.startswith(("/api/v1/", "asset://")) or any(c in source for c in "\r\n"):
                raise ValueError("Theme media requires a controlled asset reference")
            return (f'<img data-theme-media="true" src="{html.escape(source, quote=True)}" '
                    f'alt="{html.escape(str(media.get("alt", "")), quote=True)}" '
                    f'style="display:block;width:100%;height:auto;border:0;{css}" />')
        if kind in {"text", "field"}:
            value = node["text"] if kind == "text" else context[node["bind"]]
            if kind == "field" and node["bind"] == "index" and not value:
                return ""
            attr = 'data-theme-static="true"' if kind == "text" or node.get("bind") == "index" else f'data-theme-field="{node["bind"]}"'
            tag = "h1" if role == "hero" and kind == "field" and node["bind"] == "title" else "p"
            return f'<{tag} {attr} style="{css}">{_inline(value)}</{tag}>'
        if kind == "shape":
            return f'<span aria-hidden="true" style="display:inline-block;width:{node["width"]:g}px;height:{node["height"]:g}px;{css}">&#160;</span>'
        if kind == "rule":
            # Empty rich-text blocks may acquire a <br> when saved by an editor.
            # A rule is geometry, not a text line: constrain its line box even
            # if such a placeholder is inserted, while retaining border/margins.
            return (f'<section aria-hidden="true" data-theme-rule="true" '
                    f'style="border-top:1px solid {config["palette"]["primary"]};{css}'
                    'font-size:0;line-height:0;height:0;min-height:0;overflow:hidden;">&#8203;</section>')
        if kind == "repeat":
            rows = []
            for index, item in enumerate(context[node["bind"]], 1):
                child_context = {**(item if isinstance(item, dict) else {"item": item}), "index": f"{index:02d}"}
                rows.append(f'<section style="{css}">' + "".join(render(c, child_context) for c in node["children"]) + "</section>")
            return "".join(rows)
        if kind == "row":
            # No whitespace between column tags: no font-size:0 workaround and
            # no typography/color reset that would break ancestor style tokens.
            children = "".join(f'<section style="box-sizing:border-box;display:inline-block;vertical-align:top;width:{width:g}%;">{render(child, context)}</section>' for width, child in zip(node["widths"], node["children"], strict=True))
            return f'<section style="{css}">{children}</section>'
        if kind == "marker_row":
            width = node["marker_width"]
            marker, body = node["children"]
            if marker.get("type") == "field" and marker.get("bind") == "index" and not context.get("index"):
                # Source numbering stays inside the editable title. Do not
                # leave an empty badge/column beside that already numbered text.
                return f'<section style="{css}">{render(body, context)}</section>'
            # Same percentage inline columns as the established row renderer;
            # no calc(), positioning, flex or table semantics in editable prose.
            return (f'<section data-theme-marker-row="true" style="{css}">'
                    f'<section data-theme-marker="true" style="box-sizing:border-box;display:inline-block;vertical-align:top;width:{width:g}%;">{render(marker, context)}</section>'
                    f'<section data-theme-marker-body="true" style="box-sizing:border-box;display:inline-block;vertical-align:top;width:{100-width:g}%;padding-left:{node["gap"]:g}px;">{render(body, context)}</section></section>')
        if kind == "ornament_rule":
            slot = node["slot_width"]
            line = (f'<section aria-hidden="true" style="box-sizing:border-box;display:inline-block;vertical-align:middle;'
                    f'width:{(100-slot)/2:g}%;border-top:1px solid {config["palette"][node["line_color"]]};'
                    'font-size:0;line-height:0;height:0;overflow:hidden;">&#8203;</section>')
            return (f'<section data-theme-ornament-rule="true" aria-hidden="true" style="{css}font-size:0;line-height:0;">'
                    f'{line}<section style="box-sizing:border-box;display:inline-block;vertical-align:middle;width:{slot:g}%;padding:0 6px;text-align:center;line-height:0;">'
                    f'{render_drawing(node["children"][0], config["palette"])}</section>{line}</section>')
        return f'<section style="{css}">' + "".join(render(c, context) for c in node["children"]) + "</section>"

    rhythm = config["generated_design_system"]["rhythm"]
    gap = rhythm["section_gap" if role == "heading" else "component_gap"]
    gap = round(gap * {"airy": 1.2, "balanced": 1, "compact": .85}[rhythm["density"]])
    return f'<section data-theme-layout="{role}" style="margin:{gap}px 0;{text_style(config)}">{render(layouts[role], payload)}</section>'
