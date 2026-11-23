"""Foundation projectors: render bound sources, never select semantic components."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .foundation_content import FoundationBlock
from .foundation_lists import _render_list
from .foundation_media import _render_fixed_footer, _render_source_image_placeholder
from .foundation_prose import (
    _render_reference_list, native_family, render_hero, render_lead, render_paragraph,
    render_quote, render_source,
)
from .foundation_structure import _render_heading, _render_table, _render_thematic_break
from .ordinary_list_content import bind_ordinary_list
from .reading_rules import ReadingProfile


@dataclass(frozen=True, slots=True)
class FoundationRenderer:
    config: dict[str, Any]
    family: str
    reading: ReadingProfile | None
    indexed_lists: bool

    @classmethod
    def for_theme(cls, config: dict[str, Any], reading: ReadingProfile | None, indexed_lists: bool) -> FoundationRenderer:
        return cls(config, native_family(config), reading, indexed_lists)

    def block(self, source: FoundationBlock) -> str:
        return BLOCK_PROJECTORS[source.role](source, self)

    # These two sources belong to the document/brand, not a Markdown block.
    def hero(self, title: str, profile: dict[str, Any], plan: dict[str, Any]) -> str:
        editorial = self.family == "editorial"
        kicker = str(profile.get("editorial_kicker" if editorial else "standard_kicker")
                     or ("WECHAT · CONTENT BRIEF" if editorial else "公众号 · 阅读指南"))
        return render_hero(title, kicker, plan["plan_name"], plan["component_library_version"],
                           self.config, self.family, self.reading)

    def closing_cta(self, profile: dict[str, Any]) -> str:
        footer = profile.get("fixed_footer")
        return _render_fixed_footer(footer if isinstance(footer, dict) else {}, self.config, reading=self.reading)


def _list(field: FoundationBlock, theme: FoundationRenderer) -> str:
    block = field.block
    items = (bind_ordinary_list(block.id, block.content, reading=theme.reading)
             if theme.indexed_lists else list(block.content))
    return _render_list(items, field.role == "ordered_list", theme.config, field.list_context)


def _heading(field: FoundationBlock, theme: FoundationRenderer) -> str:
    return _render_heading(field.block, theme.config, field.section_index, reading=theme.reading)


BlockProjector = Callable[[FoundationBlock, FoundationRenderer], str]
BLOCK_PROJECTORS: Mapping[str, BlockProjector] = MappingProxyType({
    "lead": lambda f, t: render_lead(str(f.block.content), f.lead_label, t.config, t.family, t.reading),
    "paragraph": lambda f, t: render_paragraph(str(f.block.content), t.config, t.family, t.reading),
    "section_heading": _heading,
    "subheading": _heading,
    "quote": lambda f, t: render_quote(str(f.block.content), t.config, t.family, t.reading),
    "ordered_list": _list,
    "unordered_list": _list,
    "reference_list": lambda f, t: _render_reference_list(list(f.block.content), t.config, reading=t.reading),
    "table": lambda f, t: _render_table(list(f.block.content), t.config, reading=t.reading),
    "source": lambda f, t: render_source(str(f.block.content), t.reading),
    "divider": lambda f, t: _render_thematic_break(t.config),
    "image_caption": lambda f, t: _render_source_image_placeholder(f.block, t.config, reading=t.reading),
})
