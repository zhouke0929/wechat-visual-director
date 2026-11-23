"""Reviewed internal typography choices for official themes only.

An omitted property keeps the published theme's own CSS. This is not an
extension-pack format and does not accept editor- or user-supplied CSS.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType


THEME_READING_OVERRIDES: Mapping[str, Mapping[str, Mapping[str, int | float | str]]] = MappingProxyType({})
