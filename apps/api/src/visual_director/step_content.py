"""Shared interpretation of an ordered step; themes own only its layout."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass

from .reading_rules import STEP_DETAIL, STEP_TITLE, ReadingProfile, apply_reading_css, apply_reading_emphasis, reading_gap


STEP_HIERARCHY_FORMAT = "step_hierarchy"
_STEP_TITLE_LINE = re.compile(r"\*\*([^*\r\n]+)\*\*")


def explicit_step_title(line: str) -> str | None:
    """An entirely emphasized line, not the start of a prose sentence."""
    match = _STEP_TITLE_LINE.fullmatch(line)
    return match[1] if match and match[1].strip() else None


@dataclass(frozen=True, slots=True)
class StepContent:
    """The literal source and its optional explicit title/detail; no presentation here."""

    source: str
    title: str | None = None
    detail: str | None = None


def interpret_step(value: str) -> StepContent:
    first_line, boundary, detail = value.partition("\n")
    title = explicit_step_title(first_line) if boundary and detail.strip() else None
    return StepContent(value, title, detail if title is not None else None)


def render_step_text(
    step: StepContent, inline: Callable[[str], str], *, hierarchy: bool, reading: ReadingProfile | None = None,
) -> str:
    """Project previously interpreted source; even an opt-in cannot invent a title."""
    title, detail = step.title, step.detail
    if not hierarchy or title is None:
        return apply_reading_emphasis(inline(step.source), reading)
    title_box = "font-weight:750;"
    if reading is not None:
        title_rule = reading.rules[STEP_TITLE]
        if any(metric is not None for metric in (title_rule.before_px, title_rule.inset_before_px, title_rule.inset_after_px)):
            # Inline <strong> has no effective vertical margins. Make the
            # explicit title line a box only when an override asks for them.
            title_box += "display:inline-block;box-sizing:border-box;max-width:100%;"
    title_style = apply_reading_css(title_box, STEP_TITLE, reading)
    gap = reading_gap(STEP_TITLE, reading, 2)
    detail_style = apply_reading_css(
        f"display:block;padding-top:{gap:g}px;font-weight:400;", STEP_DETAIL, reading,
        inset_before_offset=gap,
    )
    detail_text = apply_reading_emphasis(inline(detail or ""), reading)
    # Preserve the authored newline for editing as well as presentation.
    return (
        f'<strong style="{title_style}">{html.escape(title)}</strong>\n'
        f'<span style="{detail_style}">{detail_text}</span>'
    )
