"""Shared interpretation of an ordered step; themes own only its layout."""

from __future__ import annotations

import html
import re
from collections.abc import Callable


STEP_HIERARCHY_FORMAT = "step_hierarchy"
_STEP_TITLE_LINE = re.compile(r"\*\*([^*\r\n]+)\*\*")


def explicit_step_title(line: str) -> str | None:
    """An entirely emphasized line, not the start of a prose sentence."""
    match = _STEP_TITLE_LINE.fullmatch(line)
    return match[1] if match and match[1].strip() else None


def render_step_inline(value: str, inline: Callable[[str], str]) -> str:
    """Render the source's explicit title and detail in one editable field."""
    first_line, boundary, detail = value.partition("\n")
    title = explicit_step_title(first_line)
    if not (boundary and title and detail.strip()):
        return inline(value)
    # The space between the two HTML elements is a literal newline so the
    # editor can round-trip the source boundary without inspecting CSS.
    return (
        f'<strong style="font-weight:750;">{html.escape(title)}</strong>\n'
        f'<span style="display:block;padding-top:2px;font-weight:400;">{inline(detail)}</span>'
    )
