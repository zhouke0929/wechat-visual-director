"""Bind the logic path once, then project it through the selected layout."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .generated_theme import render_generated_logic_path
from .logic_path_content import bind_logic_path_fields
from .logic_path_styles import render_native_logic_path
from .parser import ParsedArticle
from .reading_rules import ReadingProfile
from .step_content import render_step_inline
from .theme_extensions import render_extended_logic_path


def render_logic_path(
    parsed: ParsedArticle, references: list[str], variant: str,
    config: dict[str, Any], palette: dict[str, str], *,
    theme_id: str | None, quiet_folio: bool, inline: Callable[[str], str],
    step_inline: Callable[[str], str] | None,
    reading: ReadingProfile | None = None,
) -> str:
    # The sources (including each original item index) are resolved before
    # choosing the visual layout. No projector needs the article or plan.
    fields = bind_logic_path_fields(parsed, references, reading=reading)
    if reading is not None and step_inline is not None:
        step_inline = lambda text: render_step_inline(text, inline, reading=reading)
    generated = render_generated_logic_path(fields, config, step_inline=step_inline)
    if generated is not None:
        return generated
    extended = render_extended_logic_path(
        variant, fields, palette, quiet_folio=quiet_folio,
        step_inline=step_inline, visual_system=theme_id,
    )
    if extended is not None:
        return extended
    return render_native_logic_path(
        fields, variant, palette, theme_kit=config.get("theme_kit"), item_inline=step_inline or inline,
    )
