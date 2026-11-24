"""Explicit editorial fixtures for theme rendering: no planner or user content."""
from __future__ import annotations

from typing import Any

from .component_catalog import COMPONENT_CATALOG
from .parser import ParsedArticle
from .plan_envelope import article_strong_limit, plan_envelope


def fixture_plan(parsed: ParsedArticle, slots: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    slots = [] if slots is None else slots
    return {
        **plan_envelope(parsed, article_type="tutorial_steps", history_window=5, slots=slots,
                        strong_limit=article_strong_limit(parsed)),
        "plan_name": "主题样本", "slots": slots, "image_slots": [], "configuration": {},
    }


def sample_article_plan(parsed: ParsedArticle) -> dict[str, Any]:
    """The three authored components in theme_specimens.ARTICLE (shared by all themes)."""
    slots = []
    for role, sources, bindings in (
        ("faq_card", ["block-005", "block-006"], {"question": "block-005", "answer": "block-006"}),
        ("numbered_insight", ["block-009"], {"items": [f"block-009:item:{i}" for i in range(3)]}),
        ("action_checklist", ["block-013"], {"items": [f"block-013:item:{i}" for i in range(3)]}),
    ):
        component = COMPONENT_CATALOG[role]
        slots.append({
            "slot_id": f"slot-{len(slots) + 1:03d}", "anchor_block_id": sources[0],
            "consume_block_ids": sources, "semantic_role": role, "component_type": role,
            "variant": component["primary_variant"], "fallback_variant": component["fallback_variant"],
            "emphasis": "secondary", "content_bindings": bindings, "selection_reason": "样本册固定编排",
            "facts_locked": True,
        })
    return fixture_plan(parsed, slots)
