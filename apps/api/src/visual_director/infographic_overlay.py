from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .parser import ParsedArticle


FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)


class InfographicOverlayError(RuntimeError):
    pass


def _font_path() -> str:
    configured = os.environ.get("VISUAL_DIRECTOR_CJK_FONT")
    candidates = (configured, *FONT_CANDIDATES) if configured else FONT_CANDIDATES
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise InfographicOverlayError("未找到可用于确定性信息图叠字的中文字体")


def resolve_overlay_copy(parsed: ParsedArticle, fact_bindings: dict[str, Any]) -> tuple[str, list[str]]:
    blocks = {block.id: block for block in parsed.blocks}
    title_ref = fact_bindings.get("title_ref")
    title = str(blocks[title_ref].content) if title_ref in blocks else ""
    items: list[str] = []
    for reference in fact_bindings.get("item_refs", []):
        block_id, _, item_part = reference.partition(":item:")
        block = blocks.get(block_id)
        if block is None or not item_part.isdigit() or not isinstance(block.content, list):
            continue
        index = int(item_part)
        if index < len(block.content):
            items.append(str(block.content[index]))
    if not title and fact_bindings.get("item_refs"):
        item_block_id = str(fact_bindings["item_refs"][0]).partition(":item:")[0]
        item_position = next(
            (index for index, block in enumerate(parsed.blocks) if block.id == item_block_id),
            -1,
        )
        for block in reversed(parsed.blocks[:item_position]):
            if block.type == "heading" and block.level != 1:
                title = str(block.content)
                break
    title = title or "关键步骤"
    if not 2 <= len(items) <= 4:
        raise InfographicOverlayError("结构信息图必须绑定 2–4 个原文节点")
    return title, items


def _fit_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int) -> list[str]:
    normalized = " ".join(text.replace("**", "").split())
    lines: list[str] = []
    current = ""
    for character in normalized:
        candidate = current + character
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > width:
            lines.append(current)
            current = character
            if len(lines) == max_lines:
                break
        else:
            current = candidate
    if len(lines) < max_lines and current:
        lines.append(current)
    consumed = "".join(lines)
    if len(consumed) < len(normalized) and lines:
        lines[-1] = lines[-1][:-1] + "…" if len(lines[-1]) > 1 else "…"
    return lines


def _fit_text_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font_path: str,
    max_size: int,
    min_size: int,
    width: int,
    height: int,
    max_lines: int,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    for size in range(max_size, min_size - 1, -2):
        font = ImageFont.truetype(font_path, size, index=0)
        line_height = int(size * 1.35)
        lines = _fit_lines(draw, text, font, width, max_lines)
        if lines and len(lines) * line_height <= height:
            return font, lines, line_height
    font = ImageFont.truetype(font_path, min_size, index=0)
    return font, _fit_lines(draw, text, font, width, max_lines), int(min_size * 1.35)


def compose_structured_infographic(content: bytes, *, title: str, items: list[str]) -> bytes:
    with Image.open(BytesIO(content)) as source:
        base = source.convert("RGB")
    width, height = base.size
    softened = base.filter(ImageFilter.GaussianBlur(radius=max(2, width // 420))).convert("RGBA")
    veil = Image.new("RGBA", (width, height), (255, 252, 244, 178))
    canvas = Image.alpha_composite(softened, veil)
    draw = ImageDraw.Draw(canvas)
    font_path = _font_path()
    number_font = ImageFont.truetype(font_path, max(22, width // 48), index=0)

    margin_x = int(width * 0.06)
    title_y = int(height * 0.07)
    ink = "#213532"
    primary = "#176E5E"
    accents = ("#176E5E", "#C15C3D", "#AA7A18", "#315E68")
    title_bottom = int(height * 0.235)
    draw.rounded_rectangle(
        (margin_x, title_y, width - margin_x, title_bottom),
        radius=max(20, width // 90),
        fill=(255, 253, 247, 246),
    )
    draw.rounded_rectangle(
        (margin_x, title_y, margin_x + max(9, width // 140), title_bottom),
        radius=max(4, width // 300),
        fill=primary,
    )
    title_font, title_lines, line_height = _fit_text_box(
        draw,
        title,
        font_path=font_path,
        max_size=max(42, width // 27),
        min_size=max(28, width // 50),
        width=width - 2 * margin_x - int(width * 0.075),
        height=title_bottom - title_y - int(height * 0.045),
        max_lines=2,
    )
    title_text_y = title_y + max(16, (title_bottom - title_y - len(title_lines) * line_height) // 2)
    for index, line in enumerate(title_lines):
        draw.text(
            (margin_x + int(width * 0.035), title_text_y + index * line_height),
            line,
            font=title_font,
            fill=ink,
        )

    grid_top = int(height * 0.30)
    grid_bottom = int(height * 0.92)
    gap = int(width * 0.025)
    columns = len(items) if len(items) in {2, 3} else 2
    rows = 1 if len(items) in {2, 3} else 2
    card_width = (width - 2 * margin_x - gap) // columns
    if columns == 3:
        card_width = (width - 2 * margin_x - gap * 2) // 3
    card_height = (grid_bottom - grid_top - gap * (rows - 1)) // rows
    for index, item in enumerate(items):
        row, column = divmod(index, columns)
        x1 = margin_x + column * (card_width + gap)
        y1 = grid_top + row * (card_height + gap)
        x2, y2 = x1 + card_width, y1 + card_height
        shadow = max(7, width // 150)
        radius = max(20, width // 95)
        draw.rounded_rectangle(
            (x1 + shadow, y1 + shadow, x2 + shadow, y2 + shadow),
            radius=radius,
            fill=(31, 58, 52, 24),
        )
        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=radius,
            fill=(255, 254, 250, 248),
            outline=accents[index],
            width=max(3, width // 500),
        )
        badge_radius = max(22, width // 48)
        badge_x, badge_y = x1 + int(width * 0.025) + badge_radius, y1 + int(height * 0.04) + badge_radius
        draw.ellipse(
            (badge_x - badge_radius, badge_y - badge_radius, badge_x + badge_radius, badge_y + badge_radius),
            fill=accents[index],
        )
        number = f"{index + 1:02d}"
        bbox = draw.textbbox((0, 0), number, font=number_font)
        draw.text(
            (badge_x - (bbox[2] - bbox[0]) / 2, badge_y - (bbox[3] - bbox[1]) / 2 - 3),
            number,
            font=number_font,
            fill="white",
        )
        text_x = x1 + int(width * 0.025)
        text_y = badge_y + badge_radius + int(height * 0.035)
        text_bottom = y2 - int(height * 0.04)
        body_font, lines, body_line_height = _fit_text_box(
            draw,
            item,
            font_path=font_path,
            max_size=max(30, width // 38),
            min_size=max(21, width // 62),
            width=card_width - int(width * 0.05),
            height=max(1, text_bottom - text_y),
            max_lines=4,
        )
        for line_index, line in enumerate(lines):
            draw.text(
                (text_x, text_y + line_index * body_line_height),
                line,
                font=body_font,
                fill=ink,
            )

    output = BytesIO()
    canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
