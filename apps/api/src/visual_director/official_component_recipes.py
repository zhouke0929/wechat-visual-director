"""Capture opt-in official artwork settings when a theme is selected, never on render."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any

from .component_presentation import validate_component_recipes


# theme ID -> component ID -> presentation options. Nothing in v1.0.0 opts in.
# These are maintainer declarations, separate from the v1 extension-pack schema.
OFFICIAL_COMPONENT_RECIPES: Mapping[str, dict[str, dict[str, Any]]] = MappingProxyType({
    "youth_campus": {"logic_path": {"layout": "first_line_ticket"}},
    "future_tech": {"logic_path": {"layout": "first_line_marker"}},
    "business_review": {"logic_path": {"layout": "first_line_marker"}},
})


def capture_component_recipes(theme: str, default_variant: Callable[[str, str], str]) -> dict | None:
    declarations = OFFICIAL_COMPONENT_RECIPES.get(theme)
    if not declarations:
        return None
    roles = deepcopy(declarations)
    for role, options in roles.items():
        if not isinstance(options, dict) or "default_variant" in options:
            raise ValueError(f"Invalid official component recipe: {theme}.{role}")
        if "layout" in options:
            # Preserve manual variations and replay this plan without re-querying
            # a newer version of the theme catalogue.
            try:
                options["default_variant"] = default_variant(role, theme)
            except KeyError as exc:
                raise ValueError(f"Unknown official component: {theme}.{role}") from exc
    snapshot = {"version": 1, "roles": roles}
    validate_component_recipes(snapshot)
    return snapshot
