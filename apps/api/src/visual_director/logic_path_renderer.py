"""Bind the logic path once, then project it through the selected layout."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .generated_theme import render_generated_logic_path
from .component_presentation import resolve_component_recipe
from .render_pilot import renderer_pilot_enabled
from .logic_path_content import LogicPathField
from .logic_path_styles import render_native_logic_path
from .theme_extensions import render_extended_logic_path


def render_logic_path(
    fields: list[LogicPathField], variant: str,
    config: dict[str, Any], palette: dict[str, str], *,
    quiet_folio: bool, inline: Callable[[str], str],
) -> str:
    # The sources (including each original item index) are resolved before
    # choosing the visual layout. No projector needs the article or plan.
    generated = render_generated_logic_path(fields, config)
    if generated is not None:
        return generated
    recipe = resolve_component_recipe(config, "logic_path") if renderer_pilot_enabled() else None
    active = recipe if recipe and recipe.default_variant == variant else None
    extended = render_extended_logic_path(
        variant, fields, palette, quiet_folio=quiet_folio, recipe=active,
    )
    if extended is not None:
        return extended
    return render_native_logic_path(
        fields, variant, palette, theme_kit=config.get("theme_kit"), item_inline=inline,
        layout=active.layout if active else None,
    )
