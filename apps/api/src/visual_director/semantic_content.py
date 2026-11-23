"""Bind validated plan fields once. A projector receives source fields, not an article.

No schema, CSS names, punctuation, heading text or static decoration is inferred here.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
import re
from types import MappingProxyType
from typing import Any

from .parser import ContentBlock, ParsedArticle
from .logic_path_content import LogicPathField
from .reading_rules import BODY, COMPONENT_TITLE, QUOTE, STEP_BODY, ReadingProfile, render_authored_text
from .step_content import interpret_step

_REFERENCE = re.compile(r"(block-\d{3})(?::item:(\d+))?")


@dataclass(frozen=True, slots=True)
class SemanticField:
    reference: str
    text: str
    role: str
    reading: ReadingProfile | None

    def render(self, inline: Callable[[str], str]) -> str:
        return render_authored_text(inline(self.text), self.role, self.reading)


def field_inline(value: SemanticField | str, inline: Callable[[str], str]) -> str:
    return value.render(inline) if isinstance(value, SemanticField) else inline(value)


def _role(component: str, key: str) -> str:
    if key in ("title", "question", "related_titles"):
        return COMPONENT_TITLE
    if key == "evidence":
        return QUOTE
    if component == "logic_path":
        return STEP_BODY
    return BODY


@dataclass(frozen=True, slots=True)
class BoundSemanticContent:
    component: str
    fields: Mapping[str, SemanticField | tuple[SemanticField, ...]]
    steps: tuple[LogicPathField, ...] = ()

    def one(self, key: str) -> SemanticField:
        value = self.fields[key]
        if not isinstance(value, SemanticField):
            raise ValueError(f"{key} 应为单个内容引用")
        return value

    def many(self, key: str) -> tuple[SemanticField, ...]:
        value = self.fields[key]
        if not isinstance(value, tuple):
            raise ValueError(f"{key} 应为内容引用数组")
        return value

    def concepts(self) -> list[tuple[SemanticField, SemanticField]]:
        titles = [self.one("title")]
        definitions = [self.one("definition")]
        if "related_titles" in self.fields or "related_definitions" in self.fields:
            if not {"related_titles", "related_definitions"} <= self.fields.keys():
                raise ValueError("连续概念词条必须同时提供标题与解释")
            titles.extend(self.many("related_titles"))
            definitions.extend(self.many("related_definitions"))
        if len(titles) != len(definitions) or not 1 <= len(titles) <= 4:
            raise ValueError("连续概念词条必须包含 1–4 组标题与解释")
        return list(zip(titles, definitions, strict=True))

    def step_fields(self, *, editable: bool = False) -> list[LogicPathField]:
        return [replace(step, editable=True) if editable else step for step in self.steps]

    def layout_payload(self) -> dict[str, Any]:
        """Existing kit and declarative layout field names, with source identity retained."""
        if self.component == "logic_path":
            return {"kind": "list", "items": self.step_fields()}
        if self.component in {"numbered_insight", "action_checklist", "section_summary"}:
            return {"kind": "list", "items": self.many("items")}
        if self.component in {"before_after_timeline", "comparison_card"}:
            a, b = ("before", "after") if self.component == "before_after_timeline" else ("left", "right")
            return {"kind": "pair", "left": self.one(a), "right": self.one(b)}
        if self.component == "concept_explainer":
            title, body = self.one("title"), self.one("definition")
            # Saved kit/JSON plans historically group only two present collections:
            # ignore a lone optional collection; do not cap an already paired group.
            # The native recipe's stricter requirements live in concepts().
            if {"related_titles", "related_definitions"} <= self.fields.keys():
                entries = zip((title, *self.many("related_titles")),
                              (body, *self.many("related_definitions")), strict=True)
                return {"kind": "concept_group", "entries": [{"title": a, "body": b} for a, b in entries]}
            return {"kind": "title_body", "title": title, "body": body}
        if self.component == "question_hook":
            return {"kind": "title_body", "title": self.one("title"), "body": ""}
        if self.component in {"case_card", "faq_card"}:
            a, b = ("title", "body") if self.component == "case_card" else ("question", "answer")
            return {"kind": "title_body", "title": self.one(a), "body": self.one(b)}
        if self.component in {"evidence_callout", "warning_note"}:
            return {"kind": "single", "body": self.one("evidence" if self.component == "evidence_callout" else "body")}
        raise ValueError(f"没有组件内容协议：{self.component}")


@dataclass(frozen=True, slots=True)
class SemanticSource:
    """One article index and one selected profile shared by all its semantic slots."""

    blocks: Mapping[str, ContentBlock]
    reading: ReadingProfile | None

    @classmethod
    def from_article(cls, parsed: ParsedArticle, reading: ReadingProfile | None = None) -> SemanticSource:
        return cls(MappingProxyType({block.id: block for block in parsed.blocks}), reading)

    def _field(self, ref: str, role: str) -> SemanticField:
        match = _REFERENCE.fullmatch(ref) if isinstance(ref, str) else None
        if not match:
            raise ValueError(f"无法解析内容绑定：{ref}")
        block_id, index = match.groups()
        if block_id not in self.blocks:
            raise ValueError(f"内容块不存在：{block_id}")
        block = self.blocks[block_id]
        if index is not None:
            if block.type not in {"ordered_list", "unordered_list"} or int(index) >= len(block.content):
                raise ValueError(f"列表项不存在：{ref}")
            return SemanticField(ref, str(block.content[int(index)]), role, self.reading)
        return SemanticField(ref, str(block.content), role, self.reading)

    def bind(self, slot: Mapping[str, Any]) -> BoundSemanticContent:
        component = slot["component_type"]
        fields = {}
        for key, value in slot["content_bindings"].items():
            role = _role(component, key)
            fields[key] = (tuple(self._field(ref, role) for ref in value) if isinstance(value, list)
                           else self._field(value, role))
        steps = ()
        if component == "logic_path":
            items = fields["items"]
            if not isinstance(items, tuple):
                raise ValueError("items 应为内容引用数组")
            steps = tuple(LogicPathField(item.reference, interpret_step(item.text), item.reading) for item in items)
        return BoundSemanticContent(component, MappingProxyType(fields), steps)


def bind_semantic_content(
    slot: Mapping[str, Any], parsed: ParsedArticle, *, reading: ReadingProfile | None = None,
) -> BoundSemanticContent:
    return SemanticSource.from_article(parsed, reading).bind(slot)
