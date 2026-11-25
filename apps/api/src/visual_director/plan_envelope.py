"""VisualPlan bookkeeping. This module never recommends content or a theme."""

from collections import Counter
from typing import Any

from .component_catalog import COMPONENT_LIBRARY_VERSION, PLAN_SCHEMA_VERSION, RENDERER_VERSION
from .parser import ParsedArticle


def plan_envelope(
    parsed: ParsedArticle, *, article_type: str, history_window: int,
    slots: list[dict[str, Any]], strong_limit: int,
) -> dict[str, Any]:
    """Initialize shared metadata from the original blocks and the slots actually selected."""
    counts = Counter(block.type for block in parsed.blocks)
    usage = {
        "section_heading": sum(1 for b in parsed.blocks if b.type == "heading" and b.level != 1),
        "quote": counts["quote"],
        "data_table": counts["table"],
        "steps": counts["ordered_list"] + counts["unordered_list"],
        "source": counts["source"],
    }
    usage.update(Counter(slot["component_type"] for slot in slots))
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "revision": 1,
        "undo_stack": [],
        "task_id": None,
        "article_type": article_type,
        "component_library_version": COMPONENT_LIBRARY_VERSION,
        "renderer_version": RENDERER_VERSION,
        "history_window": history_window,
        "component_usage": usage,
        "quality_constraints": {
            "max_strong_components_in_a_row": 1,
            "max_strong_components_per_article": strong_limit,
            "avoid_recent_component_sequence": True,
            "facts_locked": True,
        },
    }


def article_strong_limit(parsed: ParsedArticle) -> int:
    return min(6, max(3, 2 + len(parsed.blocks) // 8))


def structural_difference_count(plans: list[dict[str, Any]]) -> int:
    if len(plans) != 2:
        return 0
    keys = ("heading_variant", "key_point_variant", "quote_variant", "list_variant", "table_variant")
    left, right = plans[0]["configuration"], plans[1]["configuration"]
    config_differences = sum(left[key] != right[key] for key in keys)
    left_slots = {(slot["anchor_block_id"], slot["component_type"]) for slot in plans[0].get("slots", [])}
    right_slots = {(slot["anchor_block_id"], slot["component_type"]) for slot in plans[1].get("slots", [])}
    left_images = {(slot["anchor_block_id"], slot["purpose"]) for slot in plans[0].get("image_slots", [])}
    right_images = {(slot["anchor_block_id"], slot["purpose"]) for slot in plans[1].get("image_slots", [])}
    return config_differences + len(left_slots.symmetric_difference(right_slots)) + len(left_images.symmetric_difference(right_images))
