"""Reviewed internal typography choices for official themes only.

An omitted property inherits the shared role default. This is not an
extension-pack format and does not accept editor- or user-supplied CSS.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType


THEME_READING_OVERRIDES: Mapping[str, Mapping[str, Mapping[str, int | float | str]]] = MappingProxyType({
    "pop_poster": MappingProxyType({
        # Pop already puts visual emphasis in the label and numbered badge.
        # Keep its colored list rows compact, without restoring all-bold prose
        # or also shrinking the text of the separate logic-path component.
        "list_body": MappingProxyType({"size_px": 15, "line_height": 1.75}),
    }),
})
