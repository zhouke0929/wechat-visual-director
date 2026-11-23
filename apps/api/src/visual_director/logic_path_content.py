"""Source identity and text for one logic-path field, before choosing a layout."""

from __future__ import annotations

import html
from collections.abc import Callable
from dataclasses import dataclass

from .reading_rules import STEP_BODY, STEP_DETAIL, STEP_TITLE, ReadingProfile, apply_reading_css, authored_metrics
from .step_content import StepContent, interpret_step, render_step_text


@dataclass(frozen=True, slots=True)
class LogicPathField:
    reference: str
    content: StepContent
    reading: ReadingProfile | None = None
    editable: bool = False


def step_field_attributes(value: str | LogicPathField) -> str:
    if not isinstance(value, LogicPathField) or not value.editable:
        return ""
    return f' data-editor-step-ref="{html.escape(value.reference, quote=True)}"'


def step_field_text(value: str | LogicPathField, inline: Callable[[str], str], *, hierarchy: bool = False) -> str:
    if not isinstance(value, LogicPathField):
        # Standalone theme-layout samples may still supply raw strings. Real
        # articles always arrive through BoundSemanticContent.step_fields().
        return render_step_text(interpret_step(value), inline, hierarchy=True) if hierarchy else inline(value)
    reading = value.reading
    hierarchy = hierarchy or bool(authored_metrics(STEP_TITLE, reading) or authored_metrics(STEP_DETAIL, reading))
    return render_step_text(value.content, inline, hierarchy=hierarchy, reading=reading)


def step_field_reading(value: object) -> ReadingProfile | None:
    return value.reading if isinstance(value, LogicPathField) else None


def step_field_css(style: str, value: str | LogicPathField) -> str:
    return apply_reading_css(style, STEP_BODY, step_field_reading(value))
