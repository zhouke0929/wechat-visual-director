"""Source fields and compatibility policies for ordinary Markdown lists."""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass

from .reading_rules import ReadingProfile, apply_reading_emphasis


@dataclass(frozen=True, slots=True)
class OrdinaryListField:
    reference: str
    ordinal: int
    text: str
    reading: ReadingProfile | None = None


ListValue = str | OrdinaryListField


def bind_ordinary_list(
    block_id: str, items: Iterable[str], *, reading: ReadingProfile | None = None,
) -> list[OrdinaryListField]:
    # The editable identity is a source position, not the visible text, number
    # or CSS path. Duplicate items and authored marker shapes are independent.
    return [OrdinaryListField(f"{block_id}:item:{i}", i + 1, text, reading) for i, text in enumerate(items)]


def list_field_reading(items: Sequence[object]) -> ReadingProfile | None:
    # All fields are bound from one original list and share its reading profile.
    first = items[0] if items else None
    return first.reading if isinstance(first, OrdinaryListField) else None


def ordinary_list_ordinal(value: object, legacy_ordinal: int) -> int:
    return value.ordinal if isinstance(value, OrdinaryListField) else legacy_ordinal


def ordinary_list_attributes(value: ListValue) -> str:
    if not isinstance(value, OrdinaryListField):
        return ""
    return f' data-editor-list-ref="{html.escape(value.reference, quote=True)}"'


def ordinary_list_inline(text: str) -> str:
    """The existing plain inline treatment in kit and declarative list layouts."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text)).replace("\n", "<br>")


def ordinary_list_text(value: ListValue, inline: Callable[[str], str] = ordinary_list_inline) -> str:
    if isinstance(value, OrdinaryListField):
        return apply_reading_emphasis(inline(value.text), value.reading)
    return inline(value)


def ordinary_list_row(
    value: ListValue, index: int, inline: Callable[[str], str] = ordinary_list_inline,
) -> tuple[int, str, str]:
    return ordinary_list_ordinal(value, index), ordinary_list_attributes(value), ordinary_list_text(value, inline)


def ordinary_list_rows(values: Iterable[ListValue], inline: Callable[[str], str] = ordinary_list_inline) -> Iterator[tuple[int, str, str]]:
    for index, value in enumerate(values, 1):
        yield ordinary_list_row(value, index, inline)


def ordinary_list_marker(
    index: int, *, ordered: bool, semantic_role: str, action_marker: str = "✓", neutral_marker: str = "•",
) -> str:
    if ordered:
        return f"{index:02d}"
    if semantic_role == "action_checklist":
        return action_marker
    if semantic_role == "case_points" and index <= 26:
        return chr(64 + index)
    return neutral_marker
