from __future__ import annotations

import html
import re
from typing import Any

from .generated_theme import generated_inline_emphasis_style
from .theme_extensions import extended_inline_emphasis_style


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("\n", "<br>")


def _body_inline(value: str, config: dict[str, Any]) -> str:
    escaped = html.escape(value)
    palette = config.get("palette", {})
    accent = config["accent"]
    heading_variant = config.get("heading_variant")
    generated_style = generated_inline_emphasis_style(config)
    extended_style = extended_inline_emphasis_style(config)
    if generated_style is not None:
        style = generated_style
    elif extended_style is not None:
        style = extended_style
    elif heading_variant == "botanical_section":
        style = (
            f"padding:0 3px;border-bottom:5px solid {palette.get('accent', accent)};"
            f"color:{palette.get('primary', accent)};font-weight:800;"
        )
    elif heading_variant == "story_chapter":
        style = (
            f"padding:1px 4px;border-bottom:7px solid {palette.get('secondary_pale', '#FBF2D8')};"
            f"color:{palette.get('accent', accent)};font-weight:800;"
        )
    elif heading_variant == "masthead_section":
        style = (
            f"border-bottom:5px solid {palette.get('accent', accent)};"
            f"color:{palette.get('primary', '#202B33')};font-weight:850;"
        )
    elif heading_variant == "indexed_column":
        style = (
            f"padding:1px 3px;border-bottom:2px solid {palette.get('primary', accent)};"
            f"color:{palette.get('primary', accent)};font-weight:800;"
        )
    elif heading_variant == "sticker_section":
        style = (
            f"padding:1px 4px;border-bottom:7px solid {palette.get('secondary_pale', '#FFF6D9')};"
            f"color:{palette.get('primary', accent)};font-weight:850;"
        )
    elif heading_variant == "signal_section":
        style = (
            f"padding:1px 4px;border-bottom:6px solid {palette.get('secondary_pale', '#EAF9F6')};"
            f"color:{palette.get('primary', accent)};font-weight:820;"
        )
    else:
        style = f"color:{accent};font-weight:800;"
    escaped = re.sub(
        r"\*\*(.+?)\*\*",
        lambda match: f'<strong data-content-role="inline-emphasis" style="{style}">{match.group(1)}</strong>',
        escaped,
    )
    return escaped.replace("\n", "<br>")
