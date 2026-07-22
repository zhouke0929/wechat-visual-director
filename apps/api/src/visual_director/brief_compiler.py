from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any

from .component_catalog import COMPONENT_CATALOG, automatic_variants
from .editorial_brief import (
    EditorialBrief,
    SectionBrief,
    is_concept_pair,
    validate_editorial_brief_for_article,
)
from .parser import ContentBlock, ParsedArticle
from .plan_schema import validate_plan_for_article
from .planner import generate_plans


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
        requested = {block.id for block in blocks}
        for index, block in enumerate(parsed.blocks[:-1]):
            following = parsed.blocks[index + 1]
            if (
                block.id in requested
                and following.id in requested
                and block.type == "heading"
                and (block.level or 0) >= 3
                and following.type == "paragraph"
                and is_concept_pair(str(block.content), str(following.content))
            ):
                return {"title": block.id, "definition": following.id}
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
    if component in {"action_checklist", "section_summary"} and lists:
        return {"items": _item_refs(lists[0], 6)}
    if component == "comparison_card" and lists and len(lists[0].content) >= 2:
        refs = _item_refs(lists[0], 2)
        return {"left": refs[0], "right": refs[1]}
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
            "audience": contract.article.audience,
            "reader_task": contract.article.reader_task,
            "tone": contract.art_direction.tone,
            "palette_roles": contract.art_direction.palette_roles,
            "palette_profile": palette_profile,
            "style_family": contract.art_direction.style_family,
            "avoid_recent_patterns": contract.art_direction.avoid_recent_patterns,
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
            "heading_variant": "numbered_marker",
            "key_point_variant": "warm_note",
            "quote_variant": "side_quote",
            "list_variant": "vertical_numbered",
            "table_variant": "compact_grid",
            "accent": LIGHT_READING_PALETTE["primary"],
            "palette": copy.deepcopy(LIGHT_READING_PALETTE),
        }
    if visual_system == "warm_humanist":
        warm_palette = ART_DIRECTION_PALETTES["warm_coral_editorial"]
        return {
            "heading_variant": "numbered_marker",
            "key_point_variant": "warm_note",
            "quote_variant": "side_quote",
            "list_variant": "vertical_numbered",
            "table_variant": "compact_grid",
            "accent": warm_palette["primary"],
            "palette": copy.deepcopy(warm_palette),
        }
    if visual_system == "structured_grid":
        grid_palette = ART_DIRECTION_PALETTES["sage_sunlit_editorial"]
        return {
            "heading_variant": "editorial_left_rule",
            "key_point_variant": "concise_rule",
            "quote_variant": "centered_sentence",
            "list_variant": "compact_checklist",
            "table_variant": "highlighted_column",
            "accent": grid_palette["primary"],
            "palette": copy.deepcopy(grid_palette),
        }
    editorial_palette = ART_DIRECTION_PALETTES["ink_navy_editorial"]
    return {
        "heading_variant": "editorial_left_rule",
        "key_point_variant": "concise_rule",
        "quote_variant": "centered_sentence",
        "list_variant": "compact_checklist",
        "table_variant": "highlighted_column",
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
        elif value in {"warm_humanist", "structured_grid"}:
            counts[str(value)] += 1
        elif value in editorial_modes:
            counts["editorial_contrast"] += 1
    return counts


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
    soft_systems = ("light_reading", "warm_humanist")
    structural_systems = ("editorial_contrast", "structured_grid")
    selected_systems = (
        min(soft_systems, key=lambda value: (counts[value], soft_systems.index(value))),
        min(structural_systems, key=lambda value: (counts[value], structural_systems.index(value))),
    )
    plans = [copy.deepcopy(base), copy.deepcopy(base)]

    labels = {
        "light_reading": ("轻盈阅读", "以浅色、低压迫感的阅读系统呈现。"),
        "editorial_contrast": ("编辑对比", "以鲜明的杂志编辑层级呈现。"),
        "warm_humanist": ("温暖人文", "以暖调、亲和且有叙事温度的系统呈现。"),
        "structured_grid": ("理性网格", "以清晰网格和秩序感组织数据与流程。"),
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
