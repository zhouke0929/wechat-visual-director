"""Source identity and text for one logic-path field, before choosing a layout."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass

from .parser import ParsedArticle
from .reading_rules import STEP_BODY, ReadingProfile, apply_reading_css


_STEP_REF = re.compile(r"(block-\d{3})(?::item:(\d+))?")


@dataclass(frozen=True)
class LogicPathField:
    reference: str
    text: str
    reading: ReadingProfile | None = None


def bind_logic_path_fields(
    parsed: ParsedArticle, references: list[str], *, reading: ReadingProfile | None = None,
) -> list[LogicPathField]:
    blocks = {block.id: block for block in parsed.blocks}
    fields = []
    for reference in references:
        match = _STEP_REF.fullmatch(reference)
        if not match:
            raise ValueError(f"无法解析内容绑定：{reference}")
        block_id, raw_index = match.groups()
        if block_id not in blocks:
            raise ValueError(f"内容块不存在：{block_id}")
        block = blocks[block_id]
        if raw_index is None:
            fields.append(LogicPathField(block_id, str(block.content), reading))
        else:
            index = int(raw_index)
            fields.append(LogicPathField(f"{block_id}:item:{index}", str(block.content[index]), reading))
    return fields


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
