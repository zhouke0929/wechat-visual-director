"""Source identity and text for one logic-path field, before choosing a layout."""

from __future__ import annotations

import html
from collections.abc import Callable
from dataclasses import dataclass

from .reading_rules import STEP_BODY, ReadingProfile, apply_reading_css


@dataclass(frozen=True)
class LogicPathField:
    reference: str
    text: str
    reading: ReadingProfile | None = None


def step_field_attributes(value: str | LogicPathField) -> str:
    if not isinstance(value, LogicPathField):
        return ""
    return f' data-editor-step-ref="{html.escape(value.reference, quote=True)}"'


def step_field_text(value: str | LogicPathField, inline: Callable[[str], str]) -> str:
    return inline(value.text if isinstance(value, LogicPathField) else value)


def step_field_reading(value: object) -> ReadingProfile | None:
    return value.reading if isinstance(value, LogicPathField) else None


def step_field_css(style: str, value: str | LogicPathField) -> str:
    return apply_reading_css(style, STEP_BODY, step_field_reading(value))
