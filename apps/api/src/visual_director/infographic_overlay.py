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


def compose_structured_infographic(content: bytes, *, title: str, items: list[str]) -> bytes:
    with Image.open(BytesIO(content)) as source:
        base = source.convert("RGB")
    width, height = base.size
    softened = base.filter(ImageFilter.GaussianBlur(radius=max(2, width // 420))).convert("RGBA")
    veil = Image.new("RGBA", (width, height), (255, 252, 244, 178))
    canvas = Image.alpha_composite(softened, veil)
    draw = ImageDraw.Draw(canvas)
    font_path = _font_path()
    title_font = ImageFont.truetype(font_path, max(34, width // 23), index=0)
    body_font = ImageFont.truetype(font_path, max(24, width // 34), index=0)
    number_font = ImageFont.truetype(font_path, max(24, width // 34), index=0)

    margin_x = int(width * 0.075)
    title_y = int(height * 0.075)
    ink = "#213532"
    primary = "#176E5E"
    accents = ("#176E5E", "#C15C3D", "#AA7A18", "#315E68")
    draw.rounded_rectangle(
        (margin_x, title_y, width - margin_x, int(height * 0.23)),
        radius=24,
        fill=(255, 253, 247, 242),
        outline=primary,
        width=max(3, width // 380),
    )
    title_lines = _fit_lines(draw, title, title_font, width - 2 * margin_x - 70, 2)
    line_height = int(title_font.size * 1.25)
    for index, line in enumerate(title_lines):
        draw.text((margin_x + 34, title_y + 22 + index * line_height), line, font=title_font, fill=ink)

    grid_top = int(height * 0.29)
    grid_bottom = int(height * 0.91)
    gap = int(width * 0.035)
    columns = 2
    rows = 1 if len(items) == 2 else 2
    card_width = (width - 2 * margin_x - gap) // columns
    card_height = (grid_bottom - grid_top - gap * (rows - 1)) // rows
    for index, item in enumerate(items):
        row, column = divmod(index, columns)
        x1 = margin_x + column * (card_width + gap)
        y1 = grid_top + row * (card_height + gap)
        x2, y2 = x1 + card_width, y1 + card_height
        if len(items) == 3 and index == 2:
            x2 = width - margin_x
        shadow = max(8, width // 100)
        draw.rounded_rectangle((x1 + shadow, y1 + shadow, x2 + shadow, y2 + shadow), radius=28, fill=(31, 58, 52, 30))
        draw.rounded_rectangle((x1, y1, x2, y2), radius=28, fill=(255, 254, 250, 246), outline=accents[index], width=4)
        badge_radius = max(25, width // 34)
        badge_x, badge_y = x1 + 36 + badge_radius, y1 + 30 + badge_radius
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
        text_x = x1 + 36
        text_y = badge_y + badge_radius + 24
        lines = _fit_lines(draw, item, body_font, card_width - 72, 3)
        for line_index, line in enumerate(lines):
            draw.text((text_x, text_y + line_index * int(body_font.size * 1.45)), line, font=body_font, fill=ink)

    output = BytesIO()
    canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
