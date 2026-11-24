"""Reviewed internal typography choices for official themes only.

An omitted property keeps the published theme's own CSS. This is not an
extension-pack format and does not accept editor- or user-supplied CSS.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType


THEME_READING_OVERRIDES: Mapping[str, Mapping[str, Mapping[str, int | float | str]]] = MappingProxyType({
    # Only the text host changes: keep source emphasis, authored breaks and
    # every marker/rail exactly as drawn by the individual step recipe.
    "structured_grid": {"step_body": {"weight": 400}},
    "future_tech": {"step_body": {"weight": 400}},
    "business_review": {"step_body": {"weight": 400}},
    "editorial_contrast": {"step_body": {"weight": 500}},
    "youth_campus": {"step_body": {"weight": 500}},
    "pop_poster": {
        "step_title": {"size_px": 16, "weight": 750, "line_height": 1.45, "after_px": 4},
        "step_body": {"size_px": 14, "weight": 400, "line_height": 1.72},
        "step_detail": {"size_px": 14, "weight": 400, "line_height": 1.72},
    },
})
