from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any

from .component_catalog import (
    COMPONENT_CATALOG,
    VISUAL_SYSTEM_CATALOG,
    VISUAL_SYSTEM_ORDER,
    automatic_variants,
)
from .editorial_brief import (
    EditorialBrief,
    SectionBrief,
    adjacent_concept_pairs,
    adjacent_comparison_pair,
    validate_editorial_brief_for_article,
)
from .parser import ContentBlock, ParsedArticle
from .plan_schema import validate_plan_for_article
from .planner import (
    component_diversity_target,
    component_opportunity_diagnostics,
    generate_plans,
    supplement_component_coverage,
)


class EditorialBriefCompileError(ValueError):
    pass


ART_DIRECTION_PALETTES: dict[str, dict[str, str]] = {
    "ink_navy_editorial": {
        "primary": "#243B53",
        "secondary": "#D6A84B",
        "accent": "#B85C47",
        "sky": "#7897A8",
        "pale": "#EEF2F3",
        "secondary_pale": "#FBF3DC",
        "accent_pale": "#F8EAE5",
        "sky_pale": "#EDF3F5",
        "surface": "#FFFDF8",
        "ink": "#202B33",
    },
    "warm_coral_editorial": {
        "primary": "#8E4B3B",
        "secondary": "#D7A83E",
        "accent": "#D66B4D",
        "sky": "#6D9C96",
        "pale": "#F8EEE9",
        "secondary_pale": "#FBF2D8",
        "accent_pale": "#FBE9E2",
        "sky_pale": "#EAF3F1",
        "surface": "#FFFCF7",
        "ink": "#342B28",
    },
    "sage_sunlit_editorial": {
        "primary": "#526A43",
        "secondary": "#D7A83F",
        "accent": "#C66A51",
        "sky": "#779B91",
        "pale": "#F0F2E7",
        "secondary_pale": "#FBF1D8",
        "accent_pale": "#F7E9E4",
        "sky_pale": "#EAF0ED",
        "surface": "#FFFDF8",
        "ink": "#26332F",
    },
    "campus_pop_editorial": {
        "primary": "#2D6CDF",
        "secondary": "#FFC857",
        "accent": "#F06F8F",
        "sky": "#72C9C1",
        "pale": "#EEF4FF",
        "secondary_pale": "#FFF6D9",
        "accent_pale": "#FFF0F5",
        "sky_pale": "#EAF9F6",
        "surface": "#FFFEFB",
        "ink": "#20304A",
    },
    "future_signal_editorial": {
        "primary": "#304B8E",
        "secondary": "#5CCBC1",
        "accent": "#FF826E",
        "sky": "#98A7E8",
        "pale": "#F3F5FC",
        "secondary_pale": "#EAF9F6",
        "accent_pale": "#FFF1EC",
        "sky_pale": "#EEF1FA",
        "surface": "#FEFEFF",
        "ink": "#24304F",
    },
}

LIGHT_READING_PALETTE: dict[str, str] = {
    "primary": "#52766F",
    "secondary": "#DDBD61",
    "accent": "#D98268",
    "sky": "#8BB9C0",
    "pale": "#F1F7F5",
    "secondary_pale": "#FBF6E5",
    "accent_pale": "#FAEFEB",
    "sky_pale": "#EFF6F7",
    "surface": "#FFFDF9",
    "ink": "#283532",
}


def _art_direction_profile(brief: EditorialBrief) -> tuple[str, dict[str, Any]]:
    """Map model semantics to a frozen, WeChat-safe visual configuration."""
    roles = set(brief.art_direction.palette_roles)
    if {"deep_navy", "warm_ivory"}.issubset(roles):
        profile = "ink_navy_editorial"
    elif {"coral_accent", "warm_ivory"}.issubset(roles):
        profile = "warm_coral_editorial"
    else:
        profile = "sage_sunlit_editorial"

    if brief.art_direction.style_family == "editorial_paper_cut":
        layout = {
            "heading_variant": "editorial_left_rule",
            "key_point_variant": "concise_rule",
            "quote_variant": "centered_sentence",
            "list_variant": "compact_checklist",
            "table_variant": "highlighted_column",
        }
    elif brief.art_direction.style_family == "clean_3d_geometry":
        layout = {
            "heading_variant": "numbered_marker",
            "key_point_variant": "concise_rule",
            "quote_variant": "side_quote",
            "list_variant": "vertical_numbered",
            "table_variant": "compact_grid",
        }
    else:
        layout = {
            "heading_variant": "numbered_marker",
            "key_point_variant": "warm_note",
            "quote_variant": "side_quote",
            "list_variant": "vertical_numbered",
            "table_variant": "highlighted_column",
        }
    palette = ART_DIRECTION_PALETTES[profile]
    return profile, {**layout, "accent": palette["primary"], "palette": palette}


def _ordered_blocks(parsed: ParsedArticle, block_ids: list[str]) -> list[ContentBlock]:
    requested = set(block_ids)
    return [block for block in parsed.blocks if block.id in requested]


def _item_refs(block: ContentBlock, limit: int | None = None) -> list[str]:
    size = len(block.content) if limit is None else min(len(block.content), limit)
    return [f"{block.id}:item:{index}" for index in range(size)]


def _recent_counts(
    recent_summaries: list[dict[str, Any]],
) -> tuple[Counter[str], Counter[tuple[str, str]]]:
    component_counts: Counter[str] = Counter()
    variant_counts: Counter[tuple[str, str]] = Counter()
    for summary in recent_summaries:
        for item in summary.get("components", []):
            if not isinstance(item, dict) or not item.get("component_type"):
                continue
            component_type = str(item["component_type"])
            component_counts[component_type] += 1
            if item.get("variant"):
                variant_counts[(component_type, str(item["variant"]))] += 1
    return component_counts, variant_counts


def _compile_bindings(
    section: SectionBrief,
    blocks: list[ContentBlock],
    parsed: ParsedArticle,
) -> dict[str, str | list[str]]:
    component = section.component_intent
    headings = [block for block in blocks if block.type == "heading" and (block.level or 0) >= 3]
    lists = [block for block in blocks if block.type in {"ordered_list", "unordered_list"}]
    evidence = [block for block in blocks if block.type in {"quote", "paragraph"}]

    if component == "question_hook" and headings:
        return {"title": headings[0].id}
    if component in {"numbered_insight", "logic_path"} and lists:
        return {"items": _item_refs(lists[0], 5)}
    if component == "evidence_callout" and evidence:
        return {"evidence": evidence[0].id}
    if component == "before_after_timeline" and lists and len(lists[0].content) >= 2:
        refs = _item_refs(lists[0], 2)
        return {"before": refs[0], "after": refs[1]}
    if component == "concept_explainer":
        pairs = adjacent_concept_pairs(
            section.source_block_ids,
            {block.id: block for block in parsed.blocks},
            require_concept_semantics=True,
        )
        if pairs:
            bindings: dict[str, str | list[str]] = {
                "title": pairs[0][0].id,
                "definition": pairs[0][1].id,
            }
            if len(pairs) > 1:
                bindings["related_titles"] = [pair[0].id for pair in pairs[1:]]
                bindings["related_definitions"] = [pair[1].id for pair in pairs[1:]]
            return bindings
    if component in {"case_card", "faq_card"}:
        requested = {block.id for block in blocks}
        for index, block in enumerate(parsed.blocks[:-1]):
            following = parsed.blocks[index + 1]
            if (
                block.id in requested
                and following.id in requested
                and block.type == "heading"
                and (block.level or 0) >= 3
                and following.type == "paragraph"
            ):
                if component == "case_card":
                    return {"title": block.id, "body": following.id}
                return {"question": block.id, "answer": following.id}
    if component == "warning_note" and evidence:
        return {"body": evidence[0].id}
    if component == "action_checklist" and lists:
        # The normalizer only accepts up to ten source items. Bind every one:
        # consuming the list while rendering only six would silently delete
        # the remaining checklist facts from the final article.
        return {"items": _item_refs(lists[0])}
    if component == "section_summary" and lists:
        return {"items": _item_refs(lists[0], 6)}
    if component == "comparison_card" and lists and len(lists[0].content) >= 2:
        refs = _item_refs(lists[0], 2)
        return {"left": refs[0], "right": refs[1]}
    if component == "comparison_card":
        pair = adjacent_comparison_pair(
            section.source_block_ids,
            {block.id: block for block in parsed.blocks},
        )
        if pair:
            return {"left": pair[0].id, "right": pair[1].id}
    raise EditorialBriefCompileError(f"原文块与组件意图不兼容：{component} -> {section.source_block_ids}")


def _consumed_block_ids(
    parsed: ParsedArticle,
    bindings: dict[str, str | list[str]],
) -> list[str]:
    referenced: set[str] = set()
    for value in bindings.values():
        values = value if isinstance(value, list) else [value]
        for reference in values:
            referenced.add(reference.split(":item:", 1)[0])
    return [block.id for block in parsed.blocks if block.id in referenced]


def _compile_slots(
    brief: EditorialBrief,
    parsed: ParsedArticle,
    recent_summaries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    component_counts, variant_counts = _recent_counts(recent_summaries)
    slots: list[dict[str, Any]] = []
    adjustments: list[dict[str, str]] = []
    consumed: set[str] = set()
    positions = {block.id: index for index, block in enumerate(parsed.blocks)}
    consumed_positions: set[int] = set()
    selected_type_counts: Counter[str] = Counter()
    selected_family_counts: Counter[str] = Counter()
    semantic_family = {
        "question_hook": "question",
        "faq_card": "question",
        "before_after_timeline": "comparison",
        "comparison_card": "comparison",
    }
    for section in brief.sections:
        if section.component_intent == "plain":
            continue
        blocks = _ordered_blocks(parsed, section.source_block_ids)
        if not blocks:
            raise EditorialBriefCompileError("组件建议出现空引用")
        try:
            bindings = _compile_bindings(section, blocks, parsed)
        except EditorialBriefCompileError:
            if section.component_intent != "concept_explainer":
                raise
            adjustments.append(
                {
                    "code": "concept_explainer_lowered_to_plain",
                    "component": section.component_intent,
                    "source_block_ids": ",".join(section.source_block_ids),
                    "reason": "未找到可安全绑定的 H3+ 标题与紧随定义段落，保留原文普通排版",
                }
            )
            continue
        consume_block_ids = _consumed_block_ids(parsed, bindings)
        if not consume_block_ids:
            raise EditorialBriefCompileError("组件没有生成可消费的原文绑定")
        if consumed.intersection(consume_block_ids):
            raise EditorialBriefCompileError("多个组件的实际内容绑定发生重复")
        candidate_positions = {positions[block_id] for block_id in consume_block_ids}
        if any(
            abs(candidate - existing) <= 1
            for candidate in candidate_positions
            for existing in consumed_positions
        ):
            adjustments.append(
                {
                    "code": "adjacent_component_lowered_to_plain",
                    "component": section.component_intent,
                    "source_block_ids": ",".join(section.source_block_ids),
                    "reason": "相邻强组件之间没有普通正文缓冲，已保留为普通排版。",
                }
            )
            continue
        family = semantic_family.get(section.component_intent, section.component_intent)
        if selected_type_counts[section.component_intent] >= 2 or selected_family_counts[family] >= 2:
            adjustments.append(
                {
                    "code": "repeated_component_lowered_to_plain",
                    "component": section.component_intent,
                    "source_block_ids": ",".join(section.source_block_ids),
                    "reason": "同类强组件单篇最多出现两次，已保留为普通排版。",
                }
            )
            continue
        definition = COMPONENT_CATALOG[section.component_intent]
        variants = automatic_variants(section.component_intent)
        # Editorial paper-cut deliberately prefers the approved magazine-like
        # alternate. Other style families keep the least-recently-used rule.
        # This turns the model's art direction into visible, deterministic
        # component treatment without allowing free-form HTML/CSS generation.
        if brief.art_direction.style_family == "editorial_paper_cut" and len(variants) > 1:
            variant = variants[1]
        else:
            variant = min(
                variants,
                key=lambda value: (variant_counts[(section.component_intent, value)], variants.index(value)),
            )
        avoided = variants[0] if variant != variants[0] else None
        slots.append(
            {
                "slot_id": f"slot-{len(slots) + 1:03d}",
                "anchor_block_id": consume_block_ids[0],
                "consume_block_ids": consume_block_ids,
                "semantic_role": section.component_intent,
                "component_type": section.component_intent,
                "variant": variant,
                "fallback_variant": definition["fallback_variant"],
                "emphasis": "primary" if section.visual_priority == "high" else "secondary",
                "content_bindings": bindings,
                "selection_reason": section.reasoning,
                "history_evidence": {
                    "recent_use_count": variant_counts[(section.component_intent, variant)],
                    "component_use_count": component_counts[section.component_intent],
                    "selected_variant": variant,
                    "avoided_variant": avoided,
                    "penalty_applied": avoided is not None,
                },
                "facts_locked": True,
            }
        )
        consumed.update(consume_block_ids)
        consumed_positions.update(candidate_positions)
        selected_type_counts[section.component_intent] += 1
        selected_family_counts[family] += 1
    return slots, adjustments


def _compile_images(brief: EditorialBrief, parsed: ParsedArticle) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for intent in brief.image_intents:
        blocks = _ordered_blocks(parsed, intent.source_block_ids)
        fact_bindings: dict[str, Any] = {"title_ref": None, "item_refs": [], "facts_locked": True}
        if intent.purpose == "structured_infographic":
            list_block = next(
                (block for block in blocks if block.type in {"ordered_list", "unordered_list"} and len(block.content) >= 2),
                None,
            )
            if list_block is None:
                raise EditorialBriefCompileError("结构信息图必须引用至少包含两个条目的原文列表")
            heading = next((block for block in blocks if block.type == "heading"), None)
            fact_bindings = {
                "title_ref": heading.id if heading else None,
                "item_refs": _item_refs(list_block, 4),
                "facts_locked": True,
            }
        result.append(
            {
                "image_slot_id": f"image-slot-{len(result) + 1:03d}",
                "anchor_block_id": intent.anchor_block_id,
                "source_block_ids": [block.id for block in blocks],
                "placement": "after_anchor",
                "purpose": intent.purpose,
                "required": False,
                "reason": f"{intent.necessity}：{intent.visual_metaphor}",
                "aspect_ratio": intent.aspect_ratio,
                "visual_intent": {
                    "subject": intent.visual_metaphor,
                    "composition": "branching" if intent.purpose == "structured_infographic" else "wide_scene",
                    "style_family": brief.art_direction.style_family,
                    "palette_role": "plan_palette",
                    "palette_roles": list(brief.art_direction.palette_roles),
                    "tone": list(brief.art_direction.tone),
                    "negative_space": "lower_right" if intent.aspect_ratio == "4:3" else "lower_third",
                },
                "fact_bindings": fact_bindings,
                "history_evidence": {
                    "recent_use_count": 0,
                    "avoided_style_family": None,
                    "penalty_applied": bool(brief.art_direction.avoid_recent_patterns),
                },
            }
        )
    return result


def compile_editorial_brief(
    parsed: ParsedArticle,
    brief: EditorialBrief | dict[str, Any],
    history_window: int,
    recent_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    recent = recent_summaries or []
    contract = validate_editorial_brief_for_article(brief, parsed)
    baseline = generate_plans(parsed, contract.article.article_type, history_window, recent)[0]
    palette_profile, art_configuration = _art_direction_profile(contract)
    slots, compiler_adjustments = _compile_slots(contract, parsed, recent)
    slots, coverage_adjustments, coverage_target = supplement_component_coverage(
        parsed,
        slots,
        recent,
    )
    compiler_adjustments.extend(coverage_adjustments)
    opportunity_diagnostics = component_opportunity_diagnostics(parsed, recent)
    selected_component_types = [slot["component_type"] for slot in slots]
    selected_type_counts = Counter(selected_component_types)
    block_positions = {block.id: index for index, block in enumerate(parsed.blocks)}
    occupied_article_thirds = sorted(
        {
            min(
                2,
                (block_positions[slot["anchor_block_id"]] * 3)
                // max(1, len(parsed.blocks)),
            )
            for slot in slots
        }
    )
    diversity_target = component_diversity_target(parsed, coverage_target)
    compiled = {
        **baseline,
        "plan_name": "智能规划 · Editorial Brief",
        "recommendation": "experimental",
        "style_mode": palette_profile,
        "summary": contract.article.narrative,
        "configuration": art_configuration,
        "slots": slots,
        "image_slots": _compile_images(contract, parsed),
        "editorial_brief_metadata": {
            "schema_version": contract.schema_version,
            "article_type": contract.article.article_type,
            "audience": contract.article.audience,
            "reader_task": contract.article.reader_task,
            "tone": contract.art_direction.tone,
            "palette_roles": contract.art_direction.palette_roles,
            "palette_profile": palette_profile,
            "style_family": contract.art_direction.style_family,
            "avoid_recent_patterns": contract.art_direction.avoid_recent_patterns,
            "compiler_adjustments": compiler_adjustments,
        },
        "component_diagnostics": {
            **opportunity_diagnostics,
            "requested_component_count": sum(
                1
                for section in contract.sections
                if section.component_intent != "plain"
            ),
            "selected_component_count": len(slots),
            "selected_component_types": selected_component_types,
            "selected_distinct_component_type_count": len(selected_type_counts),
            "repeated_component_types": sorted(
                component_type
                for component_type, count in selected_type_counts.items()
                if count > 1
            ),
            "occupied_article_thirds": occupied_article_thirds,
            "rhythm_target_distinct_types": diversity_target,
            "rhythm_status": (
                "pass"
                if len(selected_type_counts) >= diversity_target
                else "limited_by_source_candidates"
            ),
            "coverage_target": coverage_target,
            "coverage_added_count": len(coverage_adjustments),
            "compiler_adjustments": compiler_adjustments,
        },
    }
    strong_limit = min(6, max(3, 2 + len(parsed.blocks) // 8))
    compiled["quality_constraints"] = {
        **compiled["quality_constraints"],
        "max_strong_components_per_article": strong_limit,
        "facts_locked": True,
    }
    return validate_plan_for_article(compiled, parsed)


def _structure_fingerprint(plan: dict[str, Any]) -> str:
    payload = {
        "slots": [
            {
                "anchor_block_id": slot["anchor_block_id"],
                "consume_block_ids": slot["consume_block_ids"],
                "component_type": slot["component_type"],
                "content_bindings": slot["content_bindings"],
            }
            for slot in plan.get("slots", [])
        ],
        "image_slots": [
            {
                "anchor_block_id": slot["anchor_block_id"],
                "source_block_ids": slot["source_block_ids"],
                "purpose": slot["purpose"],
                "fact_bindings": slot["fact_bindings"],
            }
            for slot in plan.get("image_slots", [])
        ],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def structure_fingerprint(plan: dict[str, Any]) -> str:
    """Public helper used by deterministic migrations and acceptance checks."""
    return _structure_fingerprint(plan)


def visual_system_variant(component_type: str, visual_system: str) -> str:
    """Choose the deterministic component morphology assigned to a visual system."""
    definition = COMPONENT_CATALOG[component_type]
    system_variants = definition.get("system_variants", {})
    if visual_system in system_variants:
        return str(system_variants[visual_system]["value"])
    if visual_system in {"light_reading", "warm_humanist"}:
        return definition["primary_variant"]
    if definition.get("alternate_variant"):
        return definition["alternate_variant"]
    return definition["fallback_variant"]


def visual_system_configuration(visual_system: str) -> dict[str, Any]:
    if visual_system == "light_reading":
        return {
            "heading_variant": "botanical_section",
            "key_point_variant": "open_highlight",
            "quote_variant": "floating_quote",
            "list_variant": "leaf_path",
            "table_variant": "compact_grid",
            "theme_kit": "airy_organic_v1",
            "accent": LIGHT_READING_PALETTE["primary"],
            "palette": copy.deepcopy(LIGHT_READING_PALETTE),
        }
    if visual_system == "warm_humanist":
        warm_palette = ART_DIRECTION_PALETTES["warm_coral_editorial"]
        return {
            "heading_variant": "story_chapter",
            "key_point_variant": "margin_highlight",
            "quote_variant": "postcard_quote",
            "list_variant": "stitched_path",
            "table_variant": "soft_ledger",
            "theme_kit": "warm_storybook_v1",
            "accent": warm_palette["primary"],
            "palette": copy.deepcopy(warm_palette),
        }
    if visual_system == "youth_campus":
        campus_palette = ART_DIRECTION_PALETTES["campus_pop_editorial"]
        return {
            "heading_variant": "sticker_section",
            "key_point_variant": "marker_highlight",
            "quote_variant": "campus_quote",
            "list_variant": "campus_steps",
            "table_variant": "campus_grid",
            "theme_kit": "campus_bulletin_v2",
            "accent": campus_palette["primary"],
            "palette": copy.deepcopy(campus_palette),
        }
    if visual_system == "structured_grid":
        grid_palette = ART_DIRECTION_PALETTES["sage_sunlit_editorial"]
        return {
            "heading_variant": "indexed_column",
            "key_point_variant": "margin_register",
            "quote_variant": "evidence_margin",
            "list_variant": "audit_track",
            "table_variant": "ledger_grid",
            "theme_kit": "structured_editorial_v1",
            "accent": grid_palette["primary"],
            "palette": copy.deepcopy(grid_palette),
        }
    if visual_system == "future_tech":
        future_palette = ART_DIRECTION_PALETTES["future_signal_editorial"]
        return {
            "heading_variant": "signal_section",
            "key_point_variant": "signal_highlight",
            "quote_variant": "signal_quote",
            "list_variant": "signal_track",
            "table_variant": "signal_matrix",
            "theme_kit": "future_science_editorial_v1",
            "accent": future_palette["primary"],
            "palette": copy.deepcopy(future_palette),
        }
    editorial_palette = ART_DIRECTION_PALETTES["ink_navy_editorial"]
    return {
        "heading_variant": "masthead_section",
        "key_point_variant": "headline_rule",
        "quote_variant": "pull_quote",
        "list_variant": "proof_list",
        "table_variant": "editorial_matrix",
        "theme_kit": "independent_magazine_v1",
        "accent": editorial_palette["primary"],
        "palette": copy.deepcopy(editorial_palette),
    }


def _visual_system_counts(recent_summaries: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    editorial_modes = {
        "editorial_contrast",
        "ink_navy_editorial",
        "warm_coral_editorial",
        "sage_sunlit_editorial",
    }
    for summary in recent_summaries:
        value = summary.get("visual_system") or summary.get("style_mode")
        if value == "light_reading":
            counts["light_reading"] += 1
        elif value in {
            "warm_humanist",
            "youth_campus",
            "structured_grid",
            "future_tech",
        }:
            counts[str(value)] += 1
        elif value in editorial_modes:
            counts["editorial_contrast"] += 1
    return counts


ARTICLE_TYPE_THEME_AFFINITY: dict[str, tuple[str, ...]] = {
    "data_policy": (
        "structured_grid",
        "editorial_contrast",
        "future_tech",
        "light_reading",
        "youth_campus",
        "warm_humanist",
    ),
    "tutorial_steps": (
        "structured_grid",
        "youth_campus",
        "light_reading",
        "editorial_contrast",
        "warm_humanist",
        "future_tech",
    ),
    "viewpoint_trend": (
        "editorial_contrast",
        "future_tech",
        "light_reading",
        "warm_humanist",
        "structured_grid",
        "youth_campus",
    ),
    "lively_growth": (
        "youth_campus",
        "warm_humanist",
        "light_reading",
        "future_tech",
        "editorial_contrast",
        "structured_grid",
    ),
}


def _normalized_visual_system(summary: dict[str, Any]) -> str | None:
    value = summary.get("visual_system") or summary.get("style_mode")
    if value in VISUAL_SYSTEM_ORDER:
        return str(value)
    if value in {
        "ink_navy_editorial",
        "warm_coral_editorial",
        "sage_sunlit_editorial",
    }:
        return "editorial_contrast"
    return None


def recommend_visual_system(
    article_type: str,
    recent_summaries: list[dict[str, Any]],
    history_window: int,
) -> tuple[str, Counter[str], str | None]:
    """Pick one theme without repeating the immediately previous frozen article.

    Recent usage is the primary signal. Article type only breaks ties, so a model
    classification can never lock the operator into one visual system.
    """
    recent = recent_summaries[:history_window]
    counts = _visual_system_counts(recent)
    previous = _normalized_visual_system(recent[0]) if recent else None
    affinity = ARTICLE_TYPE_THEME_AFFINITY.get(article_type, VISUAL_SYSTEM_ORDER)
    affinity_rank = {value: index for index, value in enumerate(affinity)}
    selected = min(
        VISUAL_SYSTEM_ORDER,
        key=lambda value: (
            value == previous,
            counts[value],
            affinity_rank.get(value, len(VISUAL_SYSTEM_ORDER)),
            VISUAL_SYSTEM_ORDER.index(value),
        ),
    )
    return selected, counts, previous


def apply_visual_system(
    plan: dict[str, Any],
    visual_system: str,
    *,
    recent_counts: Counter[str] | None = None,
    previous_visual_system: str | None = None,
    recommended_visual_system: str | None = None,
    history_window: int = 5,
) -> dict[str, Any]:
    """Apply a complete approved theme kit while preserving semantic structure."""
    if visual_system not in VISUAL_SYSTEM_ORDER:
        raise EditorialBriefCompileError(f"未知视觉主题：{visual_system}")
    revised = copy.deepcopy(plan)
    existing_metadata = revised.get("visual_system_metadata", {})
    existing_options = existing_metadata.get("available_visual_systems", [])
    if recent_counts is None and existing_options:
        recent_counts = Counter(
            {
                str(item["value"]): int(item.get("recent_use_count", 0))
                for item in existing_options
            }
        )
    previous_visual_system = (
        previous_visual_system
        if previous_visual_system is not None
        else existing_metadata.get("previous_visual_system")
    )
    recommended_visual_system = (
        recommended_visual_system
        or existing_metadata.get("recommended_visual_system")
        or visual_system
    )
    base_summary = (
        revised.get("editorial_narrative")
        or revised.get("editorial_brief_metadata", {}).get("narrative")
        or revised.get("summary", "")
    )
    revised["editorial_narrative"] = base_summary
    for slot in revised.get("slots", []):
        slot["variant"] = visual_system_variant(slot["component_type"], visual_system)
        slot["history_evidence"] = {
            **slot.get("history_evidence", {}),
            "selected_variant": slot["variant"],
        }

    catalog = VISUAL_SYSTEM_CATALOG[visual_system]
    counts = recent_counts or Counter()
    if existing_options:
        available_order = [
            str(item["value"])
            for item in existing_options
            if item.get("value") in VISUAL_SYSTEM_ORDER
        ]
    else:
        alternatives = sorted(
            (value for value in VISUAL_SYSTEM_ORDER if value != recommended_visual_system),
            key=lambda value: (
                value == previous_visual_system,
                counts[value],
                VISUAL_SYSTEM_ORDER.index(value),
            ),
        )
        available_order = [recommended_visual_system, *alternatives]
    revised["configuration"] = visual_system_configuration(visual_system)
    revised["style_mode"] = visual_system
    revised["visual_system"] = visual_system
    revised["plan_name"] = f"{catalog['label']} · 智能结构"
    revised["summary"] = f"{base_summary}；{catalog['description']}"
    revised["visual_system_metadata"] = {
        "visual_system": visual_system,
        "label": catalog["label"],
        "description": catalog["description"],
        "recent_use_count": counts[visual_system],
        "previous_visual_system": previous_visual_system,
        "recommended_visual_system": recommended_visual_system,
        "recommended_by_history": visual_system == recommended_visual_system,
        "switch_requires_planner_call": False,
        "shared_structure": True,
        "available_visual_systems": [
            {
                "value": value,
                "label": VISUAL_SYSTEM_CATALOG[value]["label"],
                "description": VISUAL_SYSTEM_CATALOG[value]["description"],
                "recent_use_count": counts[value],
            }
            for value in available_order
        ],
    }
    revised["difference_from_recent"] = [
        f"最近 {history_window} 篇中，{catalog['label']}使用 {counts[visual_system]} 次。",
        "优先避开上一篇冻结稿主题，再选择最近五篇中使用较少的主题。",
        "换主题只重渲染已批准的主题组件，不调用模型，也不改变正文、图片与组件锚点。",
    ]
    revised["structural_differences"] = [
        "主题切换前后共享组件语义、锚点、正文绑定和图片意图。",
        "仅配色、基础版式、装饰语言和主题组件变体不同。",
    ]
    return revised


def compile_editorial_brief_recommended(
    parsed: ParsedArticle,
    brief: EditorialBrief | dict[str, Any],
    history_window: int,
    recent_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile one semantic brief into one auto-selected, instantly switchable plan."""
    recent = recent_summaries or []
    base = compile_editorial_brief(parsed, brief, history_window, recent)
    article_type = str(base.get("editorial_brief_metadata", {}).get("article_type", ""))
    selected, counts, previous = recommend_visual_system(article_type, recent, history_window)
    plan = apply_visual_system(
        base,
        selected,
        recent_counts=counts,
        previous_visual_system=previous,
        recommended_visual_system=selected,
        history_window=history_window,
    )
    plan["plan_index"] = 1
    plan["recommendation"] = "recommended"
    plan["structure_fingerprint"] = _structure_fingerprint(base)
    return validate_plan_for_article(plan, parsed)


def compile_editorial_brief_variants(
    parsed: ParsedArticle,
    brief: EditorialBrief | dict[str, Any],
    history_window: int,
    recent_summaries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compile one semantic brief into two deterministic visual systems.

    Component semantics, anchors, bindings and image intents stay identical.
    Only approved visual tokens and component variants may differ.
    """
    recent = recent_summaries or []
    base = compile_editorial_brief(parsed, brief, history_window, recent)
    counts = _visual_system_counts(recent[-history_window:])
    soft_systems = ("light_reading", "warm_humanist", "youth_campus")
    structural_systems = ("editorial_contrast", "structured_grid", "future_tech")
    selected_systems = (
        min(soft_systems, key=lambda value: (counts[value], soft_systems.index(value))),
        min(structural_systems, key=lambda value: (counts[value], structural_systems.index(value))),
    )
    plans = [copy.deepcopy(base), copy.deepcopy(base)]

    labels = {
        value: (VISUAL_SYSTEM_CATALOG[value]["label"], VISUAL_SYSTEM_CATALOG[value]["description"])
        for value in VISUAL_SYSTEM_ORDER
    }
    for plan, visual_system in zip(plans, selected_systems, strict=True):
        for slot in plan.get("slots", []):
            slot["variant"] = visual_system_variant(slot["component_type"], visual_system)
            slot["history_evidence"] = {
                **slot.get("history_evidence", {}),
                "selected_variant": slot["variant"],
            }

        label, description = labels[visual_system]
        plan["configuration"] = visual_system_configuration(visual_system)
        plan["style_mode"] = visual_system
        plan["visual_system"] = visual_system
        plan["plan_name"] = f"{label} · 智能结构"
        plan["summary"] = f"{plan['summary']}；{description}"

    fingerprint = _structure_fingerprint(base)
    recommended = min(selected_systems, key=lambda value: (counts[value], selected_systems.index(value)))
    for index, plan in enumerate(plans, start=1):
        visual_system = plan["visual_system"]
        plan["plan_index"] = index
        plan["recommendation"] = "recommended" if visual_system == recommended else "alternative"
        plan["structure_fingerprint"] = fingerprint
        plan["visual_system_metadata"] = {
            "visual_system": visual_system,
            "recent_use_count": counts[visual_system],
            "recommended_by_history": visual_system == recommended,
            "switch_requires_planner_call": False,
            "shared_structure": True,
            "visual_distinction_contract": "d87.v1",
        }
        plan["difference_from_recent"] = [
            f"最近 {history_window} 篇中，{labels[visual_system][0]}使用 {counts[visual_system]} 次。",
            "本次分别从柔和组和结构组选择近期使用较少的视觉系统。",
            "视觉系统切换只改变已验证视觉 token，不重新调用模型，也不改变正文事实与组件锚点。",
        ]
        plan["structural_differences"] = [
            "两套方案共享组件语义、锚点、正文绑定和图片意图。",
            "配色、基础版式和已批准组件变体不同。",
        ]

    validated = [validate_plan_for_article(plan, parsed) for plan in plans]
    if len({plan["structure_fingerprint"] for plan in validated}) != 1:
        raise EditorialBriefCompileError("双视觉系统的共享结构指纹不一致")
    if validated[0]["configuration"] == validated[1]["configuration"]:
        raise EditorialBriefCompileError("双视觉系统未形成可感知的基础版式差异")
    for left, right in zip(validated[0].get("slots", []), validated[1].get("slots", []), strict=True):
        if left["variant"] == right["variant"]:
            raise EditorialBriefCompileError(
                f"组件 {left['component_type']} 未形成双视觉系统变体差异"
            )
    return validated
