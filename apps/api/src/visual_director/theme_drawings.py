"""Bounded text-free geometry compiled to the same PNG in preview and delivery."""
from __future__ import annotations

import math
import base64
import hashlib
import io
import json
import re
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw

DRAWING_COMPILER_VERSION = "drawing_png.v1"
DRAWING_SCALE = 4


@lru_cache(maxsize=256)
def _compile_png(serialized: str) -> bytes:
    node, palette = json.loads(serialized)
    scale = DRAWING_SCALE
    image = Image.new("RGBA", (math.ceil(node["width"] * scale), math.ceil(node["height"] * scale)))
    draw = ImageDraw.Draw(image)
    for part in node["parts"]:
        color = palette[part["stroke"]]
        thickness = max(1, round(part["stroke_width"] * scale))
        if part["kind"] == "polyline":
            draw.line([(x * scale, y * scale) for x, y in part["points"]], fill=color, width=thickness, joint="curve")
        else:
            box = (part["x"] * scale, part["y"] * scale,
                   (part["x"] + part["w"]) * scale, (part["y"] + part["h"]) * scale)
            draw.ellipse(box, outline=color, width=thickness, fill=palette.get(part.get("fill")))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def drawing_png(node: dict[str, Any], palette: dict[str, str]) -> bytes:
    errors = validate_drawing(node, set(palette))
    if errors or any(not isinstance(v, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", v) for v in palette.values()):
        raise ValueError("Invalid drawing geometry or palette")
    # Cache only the drawing and colors, not unrelated layout or article content.
    geometry = {key: node[key] for key in ("width", "height", "parts")}
    return _compile_png(json.dumps([geometry, palette], sort_keys=True, separators=(",", ":")))


def validate_drawing(node: dict[str, Any], palette_keys: set[str]) -> list[str]:
    def number(v, lo, hi):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi

    width, height = node.get("width"), node.get("height")
    if not number(width, 16, 160) or not number(height, 8, 160):
        return ["线描画布宽 16–160、高 8–160"]
    parts = node.get("parts")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 32:
        return ["线描需包含 1–32 个图形"]
    errors = []
    for part in parts:
        if not isinstance(part, dict):
            errors.append("线描图形必须是对象")
            continue
        kind = part.get("kind")
        keys = {"polyline": {"points"}, "ellipse": {"x", "y", "w", "h", "fill"}}
        if not isinstance(kind, str) or kind not in keys or set(part) - (keys[kind] | {"kind", "stroke", "stroke_width"}):
            errors.append("线描仅接收折线、椭圆与受控颜色；不接收文字、URL 或代码")
            continue
        if not isinstance(part.get("stroke"), str) or part["stroke"] not in palette_keys or not number(part.get("stroke_width"), .5, 4):
            errors.append("线描需使用色板描边及 0.5–4px 线宽")
        if kind == "polyline":
            points = part.get("points")
            if not isinstance(points, list) or not 2 <= len(points) <= 32 or any(
                not isinstance(p, list) or len(p) != 2 or not number(p[0], 0, width) or not number(p[1], 0, height) for p in points
            ):
                errors.append("折线需包含 2–32 个画布内坐标")
        else:
            if not (number(part.get("x"), 0, width) and number(part.get("y"), 0, height)
                    and number(part.get("w"), 1, width) and number(part.get("h"), 1, height)):
                errors.append("椭圆范围无效")
            elif part["x"] + part["w"] > width or part["y"] + part["h"] > height:
                errors.append("椭圆不能超出画布")
            if "fill" in part and (not isinstance(part["fill"], str) or part["fill"] not in palette_keys):
                errors.append("填充需引用色板")
    return errors


def render_drawing(node: dict[str, Any], palette: dict[str, str]) -> str:
    width, height = node["width"], node["height"]
    content = drawing_png(node, palette)
    digest = hashlib.sha256(content).hexdigest()
    source = "data:image/png;base64," + base64.b64encode(content).decode("ascii")
    # Inline core-generated PNG works in standalone samples as well as the app.
    # Freeze materializes it into controlled assets before clipboard/API delivery.
    return (f'<section data-theme-drawing="true" aria-hidden="true" style="display:inline-block;'
            f'vertical-align:middle;width:{width:g}px;max-width:100%;pointer-events:none;line-height:0;font-size:0;">'
            f'<img data-theme-decoration="{digest}" data-decoration-compiler="{DRAWING_COMPILER_VERSION}" '
            f'src="{source}" alt="" width="{width:g}" '
            f'style="display:block;width:{width:g}px;max-width:100%;height:auto;border:0;" /></section>')
