"""Typed, snapshot-local component presentation; not a v1 theme-pack input.

Only register a role/field after a projector can apply it to the actual box
and textual host. This layer knows nothing about Markdown, source selection,
or the IDs of the themes that happen to use the component.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ComponentRecipe:
    layout: str | None = None
    default_variant: str | None = None
    outer_before_px: int | float | None = None
    outer_after_px: int | float | None = None
    field_sizes_px: Mapping[str, int | float] = field(default_factory=lambda: MappingProxyType({}))

    def field_css(self, style: str, field: str) -> str:
        size = self.field_sizes_px.get(field)
        # An absolute local size must not reset the field's weight, leading,
        # tracking, or mark geometry as a typography preset would.
        if size is None:
            return style
        separator = ";" if style and not style.rstrip().endswith(";") else ""
        return f"{style}{separator}font-size:{size:g}px;"

    def margin_css(self, default_gap: int | float) -> str:
        return self.box_css(f"margin:{default_gap:g}px 0;")

    def box_css(self, style: str) -> str:
        # The caller owns this style string: do not search HTML for a presumed
        # "first box", and do not mistake row padding for outside whitespace.
        if self.outer_before_px is None and self.outer_after_px is None:
            return style
        if style and not style.rstrip().endswith(";"):
            style += ";"
        if self.outer_before_px is not None:
            style += f"margin-top:{self.outer_before_px:g}px;"
        if self.outer_after_px is not None:
            style += f"margin-bottom:{self.outer_after_px:g}px;"
        return style


_EMPTY = ComponentRecipe()
_FIELDS = {"before_after_timeline": frozenset({"left", "right"})}


def _number(value: object, lower: int, upper: int, key: str) -> int | float:
    if type(value) not in (int, float) or not lower <= value <= upper or not isfinite(value):
        raise ValueError(f"Invalid component recipe {key}: expected a number in [{lower}, {upper}]")
    return value


def _parse(raw: object) -> dict[str, ComponentRecipe]:
    if (not isinstance(raw, Mapping) or set(raw) != {"version", "roles"}
            or type(raw["version"]) is not int or raw["version"] != 1 or not isinstance(raw["roles"], Mapping)):
        raise ValueError("Invalid component_recipes snapshot: expected version 1 and a roles object")
    recipes: dict[str, ComponentRecipe] = {}
    for role, definition in raw["roles"].items():
        if role == "logic_path":
            # Allow only artwork/layout pairs implemented by a projector.
            if not isinstance(definition, Mapping) or definition not in (
                {"layout": "first_line_ticket", "default_variant": "club_route_map"},
                {"layout": "first_line_marker", "default_variant": "orbit_route"},
                {"layout": "first_line_marker", "default_variant": "business_review__logic_path"},
            ):
                raise ValueError(f"Invalid or unsupported component recipe: {role}")
            recipes[role] = ComponentRecipe(layout=definition["layout"], default_variant=definition["default_variant"])
            continue
        if (role not in _FIELDS or not isinstance(definition, Mapping) or not definition
                or set(definition) - {"layout", "default_variant", "outer_before_px", "outer_after_px", "field_sizes_px"}):
            raise ValueError(f"Invalid or unsupported component recipe: {role}")
        layout = definition.get("layout")
        default_variant = definition.get("default_variant")
        if ("layout" in definition) != ("default_variant" in definition):
            raise ValueError(f"{role} requires layout and default_variant together")
        if "layout" in definition:
            from .component_catalog import allowed_variants
            from .timeline_recipe import TIMELINE_LAYOUTS
            if not isinstance(layout, str) or layout not in TIMELINE_LAYOUTS:
                raise ValueError(f"Unsupported {role} layout: {layout}")
            if not isinstance(default_variant, str) or default_variant not in allowed_variants(role):
                raise ValueError(f"Unsupported {role} default_variant: {default_variant}")
        sizes = definition.get("field_sizes_px", {})
        if (not isinstance(sizes, Mapping) or set(sizes) - _FIELDS[role]
                or ("field_sizes_px" in definition and not sizes)):
            raise ValueError(f"Invalid {role} field_sizes_px: expected named authored fields")
        recipes[role] = ComponentRecipe(
            layout=layout, default_variant=default_variant,
            outer_before_px=_number(definition["outer_before_px"], 0, 64, "outer_before_px") if "outer_before_px" in definition else None,
            outer_after_px=_number(definition["outer_after_px"], 0, 64, "outer_after_px") if "outer_after_px" in definition else None,
            field_sizes_px=MappingProxyType({k: _number(v, 10, 42, k) for k, v in sizes.items()}),
        )
    return recipes


def validate_component_recipes(raw: object) -> None:
    """Validate even unused entries, so unsupported styling never silently ships."""
    _parse(raw)


def resolve_component_recipe(config: Mapping, role: str) -> ComponentRecipe:
    if "component_recipes" not in config:
        return _EMPTY
    return _parse(config["component_recipes"]).get(role, _EMPTY)
