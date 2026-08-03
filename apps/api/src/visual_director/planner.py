from __future__ import annotations

import re
import copy
from collections import Counter
from typing import Any

from .component_catalog import (
    COMPONENT_CATALOG,
    COMPONENT_LIBRARY_VERSION,
    PLAN_SCHEMA_VERSION,
    RENDERER_VERSION,
    automatic_variants,
)
from .parser import ContentBlock, ParsedArticle
from .plan_schema import validate_plan_for_article
from .editorial_brief import (
    adjacent_comparison_pair,
    adjacent_concept_pairs,
    is_concept_pair,
)


STYLE_LABELS = {
    "data_decision": "数据决策",
    "editorial_insight": "编辑洞察",
    "lively_science": "活力科普",
}

STYLE_PALETTES = {
    "data_decision": {
        "primary": "#0B7169",
        "secondary": "#F2C94C",
        "accent": "#EE6B4D",
        "sky": "#54B5DF",
        "pale": "#EAF7F4",
        "secondary_pale": "#FFF7D6",
        "accent_pale": "#FFF0E9",
        "sky_pale": "#EAF6FC",
        "surface": "#FFFEFA",
        "ink": "#20312E",
    },
    "editorial_insight": {
        "primary": "#315E68",
        "secondary": "#F0BB4F",
        "accent": "#E76F51",
        "sky": "#72B7D6",
        "pale": "#EDF4F5",
        "secondary_pale": "#FFF6DA",
        "accent_pale": "#FFF0EA",
        "sky_pale": "#EDF7FB",
        "surface": "#FFFEFA",
        "ink": "#253033",
    },
    "lively_science": {
        "primary": "#117C73",
        "secondary": "#F4C84A",
        "accent": "#F06A4B",
        "sky": "#58B9E4",
        "pale": "#E9F7F3",
        "secondary_pale": "#FFF7D5",
        "accent_pale": "#FFF0E9",
        "sky_pale": "#EAF7FD",
        "surface": "#FFFEFA",
        "ink": "#20312E",
    },
}

COMPONENT_COVERAGE_PRIORITIES = (
    "faq_card",
    "case_card",
    "action_checklist",
    "concept_explainer",
    "comparison_card",
    "warning_note",
    "section_summary",
    "question_hook",
    "logic_path",
    "before_after_timeline",
    "evidence_callout",
    "numbered_insight",
)

SEMANTIC_FAMILIES = {
    "question_hook": "question",
    "faq_card": "question",
    "before_after_timeline": "comparison",
    "comparison_card": "comparison",
}


def _base_usage(parsed: ParsedArticle) -> Counter[str]:
    usage: Counter[str] = Counter()
    usage["section_heading"] = sum(1 for block in parsed.blocks if block.type == "heading" and block.level != 1)
    usage["quote"] = sum(1 for block in parsed.blocks if block.type == "quote")
    usage["data_table"] = sum(1 for block in parsed.blocks if block.type == "table")
    usage["steps"] = sum(1 for block in parsed.blocks if block.type in {"ordered_list", "unordered_list"})
    usage["source"] = sum(1 for block in parsed.blocks if block.type == "source")
    return usage


def _list_refs(block: ContentBlock) -> list[str]:
    return [f"{block.id}:item:{index}" for index in range(len(block.content))]


def _candidate(
    component_type: str,
    consume: list[ContentBlock],
    bindings: dict[str, str | list[str]],
    reason: str,
    recent_counts: tuple[Counter[str], Counter[tuple[str, str]]],
) -> dict[str, Any]:
    definition = COMPONENT_CATALOG[component_type]
    component_counts, variant_counts = recent_counts
    variants = automatic_variants(component_type)
    selected_variant = min(
        variants,
        key=lambda value: (variant_counts[(component_type, value)], variants.index(value)),
    )
    default_variant = variants[0]
    avoided_variant = default_variant if selected_variant != default_variant else None
    return {
        "anchor_block_id": consume[0].id,
        "consume_block_ids": [block.id for block in consume],
        "semantic_role": component_type,
        "component_type": component_type,
        "variant": selected_variant,
        "fallback_variant": definition["fallback_variant"],
        "emphasis": "primary" if component_type in {"question_hook", "logic_path", "before_after_timeline"} else "secondary",
        "content_bindings": bindings,
        "selection_reason": reason,
        "history_evidence": {
            "recent_use_count": variant_counts[(component_type, selected_variant)],
            "component_use_count": component_counts[component_type],
            "selected_variant": selected_variant,
            "avoided_variant": avoided_variant,
            "penalty_applied": avoided_variant is not None,
        },
        "facts_locked": True,
    }


def _recent_counts(
    recent_summaries: list[dict[str, Any]],
) -> tuple[Counter[str], Counter[tuple[str, str]]]:
    component_counts: Counter[str] = Counter()
    variant_counts: Counter[tuple[str, str]] = Counter()
    for summary in recent_summaries:
        for component in summary.get("components", []):
            component_type = component.get("component_type") if isinstance(component, dict) else str(component)
            if component_type:
                component_counts[component_type] += 1
                if isinstance(component, dict) and component.get("variant"):
                    variant_counts[(component_type, str(component["variant"]))] += 1
    return component_counts, variant_counts


def _build_candidates(parsed: ParsedArticle, recent_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    blocks = parsed.blocks
    recent_counts = _recent_counts(recent_summaries)

    for index, block in enumerate(blocks):
        previous = blocks[index - 1] if index > 0 else None
        following = blocks[index + 1] if index + 1 < len(blocks) else None

        if block.type == "heading" and (block.level or 0) == 2:
            section_blocks = [block]
            for following_block in blocks[index + 1 :]:
                if following_block.type == "heading" and (following_block.level or 0) <= 2:
                    break
                section_blocks.append(following_block)
            pairs = adjacent_concept_pairs(
                [item.id for item in section_blocks],
                {item.id: item for item in blocks},
                require_concept_semantics=True,
            )
            if len(pairs) >= 2:
                bindings: dict[str, str | list[str]] = {
                    "title": pairs[0][0].id,
                    "definition": pairs[0][1].id,
                    "related_titles": [pair[0].id for pair in pairs[1:]],
                    "related_definitions": [pair[1].id for pair in pairs[1:]],
                }
                candidates.append(
                    _candidate(
                        "concept_explainer",
                        [item for pair in pairs for item in pair],
                        bindings,
                        f"同一主章节包含 {len(pairs)} 个连续且原文锁定的概念词条。",
                        recent_counts,
                    )
                )

        if block.type == "heading" and (block.level or 0) >= 3:
            heading = str(block.content)
            if re.search(r"[？?]|为什么|是什么|有什么|如何|是否", heading):
                candidates.append(
                    _candidate("question_hook", [block], {"title": block.id}, "章节标题明确提出读者核心问题。", recent_counts)
                )
                if following and following.type == "paragraph":
                    candidates.append(
                        _candidate(
                            "faq_card",
                            [block, following],
                            {"question": block.id, "answer": following.id},
                            "问句子标题与紧随答案构成可独立阅读的问答单元。",
                            recent_counts,
                        )
                    )
            if following and following.type == "paragraph" and re.search(r"案例|故事|实践|实录|样本", heading):
                candidates.append(
                    _candidate(
                        "case_card",
                        [block, following],
                        {"title": block.id, "body": following.id},
                        "案例子标题与紧随正文构成原文锁定的故事单元。",
                        recent_counts,
                    )
                )
            if (
                following
                and following.type == "paragraph"
                and is_concept_pair(heading, str(following.content))
            ):
                candidates.append(
                    _candidate(
                        "concept_explainer",
                        [block, following],
                        {"title": block.id, "definition": following.id},
                        "标题与紧随正文构成明确的概念及解释。",
                        recent_counts,
                    )
                )
            if following and following.type in {"ordered_list", "unordered_list"} and len(following.content) >= 2 and re.search(
                r"前后|对比|不同|变化|改革|传统|新旧|之前|之后", heading
            ):
                candidates.append(
                    _candidate(
                        "before_after_timeline",
                        [block, following],
                        {"before": f"{following.id}:item:0", "after": f"{following.id}:item:1"},
                        "章节包含明确的前后或旧新对照。",
                        recent_counts,
                    )
                )

        if block.type == "heading" and re.search(r"对比|区别|差异|两种|前后|新旧|风险与收益|利弊", str(block.content)):
            section_blocks = [block]
            for following_block in blocks[index + 1 :]:
                if (
                    following_block.type == "heading"
                    and (following_block.level or 0) <= (block.level or 0)
                ):
                    break
                section_blocks.append(following_block)
            pair = adjacent_comparison_pair(
                [item.id for item in section_blocks],
                {item.id: item for item in blocks},
            )
            if pair:
                candidates.append(
                    _candidate(
                        "comparison_card",
                        [pair[0], pair[1]],
                        {"left": pair[0].id, "right": pair[1].id},
                        "章节包含两段相邻且原文明确成对的对照内容。",
                        recent_counts,
                    )
                )

        if block.type == "quote":
            candidates.append(
                _candidate("evidence_callout", [block], {"evidence": block.id}, "原文包含可回溯的引语或来源说明。", recent_counts)
            )

        if block.type in {"paragraph", "quote"} and re.search(r"注意|风险|警惕|避免|不要|不可|谨防", str(block.content)):
            candidates.append(
                _candidate("warning_note", [block], {"body": block.id}, "原文明示风险或注意事项。", recent_counts)
            )

        if block.type in {"ordered_list", "unordered_list"} and 2 <= len(block.content) <= 10:
            # Lists commonly have one explanatory paragraph between the H2/H3
            # and the list. Use the nearest preceding heading inside the current
            # section instead of requiring immediate adjacency.
            heading_context = ""
            for context_block in reversed(blocks[:index]):
                if context_block.type == "heading":
                    heading_context = str(context_block.content)
                    break
            if re.search(r"清单|检查|准备|核对", heading_context):
                candidates.append(
                    _candidate("action_checklist", [block], {"items": _list_refs(block)}, "列表由清单或核对语义标题引导。", recent_counts)
                )
            if re.search(r"对比|区别|差异|优缺点|两种", heading_context) and len(block.content) >= 2:
                refs = _list_refs(block)
                candidates.append(
                    _candidate("comparison_card", [block], {"left": refs[0], "right": refs[1]}, "列表由明确对比语义标题引导。", recent_counts)
                )
            if re.search(r"小结|总结|结论|要点|回顾", heading_context):
                candidates.append(
                    _candidate("section_summary", [block], {"items": _list_refs(block)}, "列表用于阶段收束而非新增论述。", recent_counts)
                )
            if len(block.content) <= 5:
                candidates.append(
                    _candidate("numbered_insight", [block], {"items": _list_refs(block)}, "原文存在 2–5 个并列观点。", recent_counts)
                )
            if block.type == "ordered_list" and 3 <= len(block.content) <= 5:
                consume = [block]
                bindings: dict[str, str | list[str]] = {"items": _list_refs(block)}
                if previous and previous.type == "heading" and (previous.level or 0) >= 3:
                    consume = [previous, block]
                candidates.append(
                    _candidate("logic_path", consume, bindings, "原文存在 3–5 个有序步骤。", recent_counts)
                )

    return candidates


def component_opportunity_diagnostics(
    parsed: ParsedArticle,
    recent_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    candidates = _build_candidates(parsed, recent_summaries or [])
    type_counts = Counter(item["component_type"] for item in candidates)
    block_type_counts = Counter(block.type for block in parsed.blocks)
    return {
        "source_block_count": len(parsed.blocks),
        "source_block_types": dict(sorted(block_type_counts.items())),
        "eligible_candidate_count": len(candidates),
        "eligible_component_types": sorted(type_counts),
        "eligible_component_type_counts": dict(sorted(type_counts.items())),
        "candidate_anchors": [
            {
                "component_type": item["component_type"],
                "anchor_block_id": item["anchor_block_id"],
                "consume_block_ids": item["consume_block_ids"],
            }
            for item in candidates
        ],
    }


def _block_number(block_id: str) -> int:
    return int(block_id.rsplit("-", 1)[-1])


def _article_text_length(parsed: ParsedArticle) -> int:
    length = 0
    for block in parsed.blocks:
        if isinstance(block.content, list):
            for item in block.content:
                if isinstance(item, list):
                    length += sum(len(str(cell)) for cell in item)
                else:
                    length += len(str(item))
        else:
            length += len(str(block.content))
    return length


def component_coverage_target(
    parsed: ParsedArticle,
    recent_summaries: list[dict[str, Any]] | None = None,
) -> int:
    """Return a safe component floor bounded by real, non-overlapping candidates."""
    candidates = _build_candidates(parsed, recent_summaries or [])
    feasible = _select_candidates(
        candidates,
        COMPONENT_COVERAGE_PRIORITIES,
        6,
    )
    if not feasible:
        return 0

    text_length = _article_text_length(parsed)
    block_count = len(parsed.blocks)
    if text_length >= 4200 or block_count >= 45:
        desired = 6
    elif text_length >= 3200 or block_count >= 32:
        desired = 5
    elif text_length >= 1800 or block_count >= 22:
        desired = 4
    elif text_length >= 900 or block_count >= 12:
        desired = 3
    else:
        desired = 2
    return min(desired, len(feasible), 6)


def component_diversity_target(parsed: ParsedArticle, coverage_target: int) -> int:
    """Return the minimum number of distinct component morphologies.

    A long article with five cards but only two or three visual forms still
    feels templated. The target is bounded by the coverage target and never
    forces decorative components into a short article.
    """
    if coverage_target <= 1:
        return coverage_target
    if _article_text_length(parsed) >= 1800 or len(parsed.blocks) >= 22:
        return min(4, coverage_target)
    return min(3, coverage_target)


def _article_third(parsed: ParsedArticle, block_id: str) -> int:
    position = next(
        (index for index, block in enumerate(parsed.blocks) if block.id == block_id),
        0,
    )
    return min(2, (position * 3) // max(1, len(parsed.blocks)))


def supplement_component_coverage(
    parsed: ParsedArticle,
    selected_slots: list[dict[str, Any]],
    recent_summaries: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    """Fill weak-model gaps using only deterministic, fact-bound candidates.

    Existing model choices are preserved. Candidates that overlap, sit directly
    beside a strong component, or over-repeat a semantic family are skipped.
    Missing morphologies and uncovered article thirds are preferred so a long
    article does not merely satisfy a numeric card quota.
    """
    recent = recent_summaries or []
    target = component_coverage_target(parsed, recent)
    diversity_target = component_diversity_target(parsed, target)
    selected_types = {slot["component_type"] for slot in selected_slots}
    if len(selected_slots) >= target and len(selected_types) >= diversity_target:
        return copy.deepcopy(selected_slots), [], target

    candidates = _build_candidates(parsed, recent)
    priority = {
        component_type: index
        for index, component_type in enumerate(COMPONENT_COVERAGE_PRIORITIES)
    }
    ordered = sorted(
        candidates,
        key=lambda item: (
            priority.get(item["component_type"], len(priority)),
            item["anchor_block_id"],
        ),
    )
    selected = copy.deepcopy(selected_slots)
    consumed = {
        block_id
        for slot in selected
        for block_id in slot["consume_block_ids"]
    }
    consumed_numbers = {
        _block_number(block_id)
        for block_id in consumed
    }
    type_counts: Counter[str] = Counter(
        slot["component_type"] for slot in selected
    )
    family_counts: Counter[str] = Counter(
        SEMANTIC_FAMILIES.get(slot["component_type"], slot["component_type"])
        for slot in selected
    )
    adjustments: list[dict[str, str]] = []
    occupied_thirds = {
        _article_third(parsed, slot["anchor_block_id"])
        for slot in selected
    }

    for allow_repeat in (False, True):
        # Re-rank for current state: first introduce a new morphology, then
        # cover an unused part of the article, finally apply semantic priority.
        ranked = sorted(
            ordered,
            key=lambda item: (
                type_counts[item["component_type"]] > 0,
                _article_third(parsed, item["anchor_block_id"]) in occupied_thirds,
                priority.get(item["component_type"], len(priority)),
                item["anchor_block_id"],
            ),
        )
        for item in ranked:
            component_type = item["component_type"]
            family = SEMANTIC_FAMILIES.get(component_type, component_type)
            if not allow_repeat and type_counts[component_type] > 0:
                continue
            if type_counts[component_type] >= 2 or family_counts[family] >= 2:
                continue
            if consumed.intersection(item["consume_block_ids"]):
                continue
            numbers = {
                _block_number(block_id)
                for block_id in item["consume_block_ids"]
            }
            if any(
                abs(number - existing) <= 1
                for number in numbers
                for existing in consumed_numbers
            ):
                continue

            candidate = copy.deepcopy(item)
            candidate["selection_reason"] = (
                f"组件覆盖兜底：{candidate['selection_reason']}"
            )
            selected.append(candidate)
            consumed.update(candidate["consume_block_ids"])
            consumed_numbers.update(numbers)
            type_counts[component_type] += 1
            family_counts[family] += 1
            occupied_thirds.add(_article_third(parsed, candidate["anchor_block_id"]))
            adjustment_code = (
                "component_rhythm_candidate_added"
                if len(selected_slots) >= target
                else "component_coverage_candidate_added"
            )
            adjustments.append(
                {
                    "code": adjustment_code,
                    "component": component_type,
                    "source_block_ids": ",".join(candidate["consume_block_ids"]),
                    "reason": (
                        "整篇组件形态不足，使用原稿真实候选补充视觉节奏。"
                        if adjustment_code == "component_rhythm_candidate_added"
                        else "宿主选择低于当前文章的安全覆盖目标，使用原稿真实候选补齐。"
                    ),
                }
            )
            if len(selected) >= target and len(type_counts) >= diversity_target:
                break
        if len(selected) >= target and len(type_counts) >= diversity_target:
            break

    selected.sort(key=lambda item: item["anchor_block_id"])
    for index, item in enumerate(selected, 1):
        item["slot_id"] = f"slot-{index:03d}"
    return selected, adjustments, target


def _select_candidates(candidates: list[dict[str, Any]], priorities: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
    priority = {component_type: index for index, component_type in enumerate(priorities)}
    ordered = sorted(
        candidates,
        key=lambda item: (
            priority.get(item["component_type"], len(priority)),
            item["anchor_block_id"],
        ),
    )
    selected: list[dict[str, Any]] = []
    consumed: set[str] = set()
    consumed_numbers: set[int] = set()
    type_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    for item in ordered:
        if type_counts[item["component_type"]] >= 2:
            continue
        family = SEMANTIC_FAMILIES.get(item["component_type"], item["component_type"])
        if family_counts[family] >= 2:
            continue
        if consumed.intersection(item["consume_block_ids"]):
            continue
        numbers = {_block_number(block_id) for block_id in item["consume_block_ids"]}
        if any(abs(number - existing) <= 1 for number in numbers for existing in consumed_numbers):
            continue
        selected.append(copy.deepcopy(item))
        consumed.update(item["consume_block_ids"])
        consumed_numbers.update(numbers)
        type_counts[item["component_type"]] += 1
        family_counts[family] += 1
        if len(selected) >= limit:
            break
    selected.sort(key=lambda item: item["anchor_block_id"])
    for index, item in enumerate(selected, 1):
        item["slot_id"] = f"slot-{index:03d}"
    return selected


def _image_candidates(parsed: ParsedArticle) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    blocks = parsed.blocks
    for index, block in enumerate(blocks):
        previous = blocks[index - 1] if index > 0 else None
        if block.type in {"ordered_list", "unordered_list"} and 2 <= len(block.content) <= 4:
            source = [block]
            title_ref: str | None = None
            subject = "并列关系或步骤路径"
            if previous and previous.type == "heading" and previous.level != 1:
                source = [previous, block]
                title_ref = previous.id
                subject = str(previous.content)
            candidates.append(
                {
                    "anchor_block_id": block.id,
                    "source_block_ids": [item.id for item in source],
                    "purpose": "structured_infographic",
                    "required": False,
                    "reason": "将 2–4 个原文节点转为轻量结构图，文字和顺序继续由原文事实锁定。",
                    "aspect_ratio": "4:3",
                    "subject": subject,
                    "fact_bindings": {
                        "title_ref": title_ref,
                        "item_refs": _list_refs(block),
                        "facts_locked": True,
                    },
                }
            )

        if block.type == "heading" and block.level != 1:
            following = blocks[index + 1] if index + 1 < len(blocks) else None
            if following and following.type in {"paragraph", "ordered_list", "unordered_list"}:
                candidates.append(
                    {
                        "anchor_block_id": following.id,
                        "source_block_ids": [block.id, following.id],
                        "purpose": "atmosphere",
                        "required": False,
                        "reason": "为章节建立语义氛围和阅读停顿，不承载新的事实。",
                        "aspect_ratio": "16:9",
                        "subject": str(block.content),
                        "fact_bindings": {
                            "title_ref": None,
                            "item_refs": [],
                            "facts_locked": True,
                        },
                    }
                )

        # OCR/imported articles often arrive as a handful of long paragraphs
        # without H2 headings or Markdown lists. They still need visual pauses,
        # but a paragraph must never be promoted to a fact-bearing infographic.
        # Treat only substantial, non-tail paragraphs as atmosphere candidates;
        # selection below keeps adjacent candidates apart.
        if block.type == "paragraph" and index < len(blocks) - 2:
            paragraph = re.sub(r"\s+", " ", str(block.content)).strip()
            if len(paragraph) >= 120:
                candidates.append(
                    {
                        "anchor_block_id": block.id,
                        "source_block_ids": [block.id],
                        "purpose": "atmosphere",
                        "required": False,
                        "reason": "为长篇叙事建立视觉停顿；图片只表达章节氛围，不新增或改写事实。",
                        "aspect_ratio": "16:9",
                        "subject": paragraph,
                        "fact_bindings": {
                            "title_ref": None,
                            "item_refs": [],
                            "facts_locked": True,
                        },
                    }
                )
    return candidates


def _select_image_slots(
    candidates: list[dict[str, Any]],
    *,
    preferred_purpose: str,
    limit: int,
    style_family: str,
    composition: str,
    negative_space: str,
) -> list[dict[str, Any]]:
    ordered = sorted(
        candidates,
        key=lambda item: (item["purpose"] != preferred_purpose, item["anchor_block_id"]),
    )
    selected: list[dict[str, Any]] = []
    anchors: set[str] = set()
    selected_block_numbers: set[int] = set()
    for candidate in ordered:
        if candidate["anchor_block_id"] in anchors:
            continue
        block_number = int(candidate["anchor_block_id"].rsplit("-", 1)[-1])
        if any(abs(block_number - existing) <= 1 for existing in selected_block_numbers):
            continue
        selected.append(
            {
                "image_slot_id": f"image-slot-{len(selected) + 1:03d}",
                "anchor_block_id": candidate["anchor_block_id"],
                "source_block_ids": candidate["source_block_ids"],
                "placement": "after_anchor",
                "purpose": candidate["purpose"],
                "required": False,
                "reason": candidate["reason"],
                "aspect_ratio": candidate["aspect_ratio"],
                "visual_intent": {
                    "subject": candidate["subject"][:160],
                    "composition": composition if candidate["purpose"] == preferred_purpose else "wide_scene",
                    "style_family": style_family,
                    "palette_role": "plan_palette",
                    "negative_space": negative_space,
                },
                "fact_bindings": candidate["fact_bindings"],
                "history_evidence": {
                    "recent_use_count": 0,
                    "avoided_style_family": None,
                    "penalty_applied": False,
                },
            }
        )
        anchors.add(candidate["anchor_block_id"])
        selected_block_numbers.add(block_number)
        if len(selected) >= limit:
            break
    return selected


def _align_images_after_component_content(
    image_slots: list[dict[str, Any]],
    component_slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep image insertion outside the middle of a multi-block component."""
    aligned: list[dict[str, Any]] = []
    used_anchors: set[str] = set()
    for raw in image_slots:
        image_slot = copy.deepcopy(raw)
        containing = next(
            (
                slot
                for slot in component_slots
                if image_slot["anchor_block_id"] in slot["consume_block_ids"]
            ),
            None,
        )
        if containing is not None:
            anchor = containing["consume_block_ids"][-1]
            image_slot["anchor_block_id"] = anchor
            if anchor not in image_slot["source_block_ids"]:
                image_slot["source_block_ids"].append(anchor)
        if image_slot["anchor_block_id"] in used_anchors:
            continue
        used_anchors.add(image_slot["anchor_block_id"])
        image_slot["image_slot_id"] = f"image-slot-{len(aligned) + 1:03d}"
        aligned.append(image_slot)
    return aligned


def _plan(
    *,
    index: int,
    style: str,
    recommendation: str,
    parsed: ParsedArticle,
    history_window: int,
    slots: list[dict[str, Any]],
    image_slots: list[dict[str, Any]],
    configuration: dict[str, Any],
    recent_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    usage = _base_usage(parsed)
    for slot in slots:
        usage[slot["component_type"]] += 1
    recent_message = (
        f"已读取最近 {min(len(recent_summaries), history_window)} 篇确认记录，并优先选择近期使用更少的具体变体。"
        if recent_summaries
        else f"当前没有可用的确认记录；保留最近 {history_window} 篇历史窗口配置。"
    )
    rich = index == 1
    payload: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "revision": 1,
        "undo_stack": [],
        "task_id": None,
        "article_type": None,
        "component_library_version": COMPONENT_LIBRARY_VERSION,
        "renderer_version": RENDERER_VERSION,
        "history_window": history_window,
        "plan_index": index,
        "plan_name": f"{STYLE_LABELS[style]} · {'语义导航' if rich else '留白长读'}",
        "recommendation": recommendation,
        "style_mode": style,
        "summary": "用语义组件建立明确视线入口，并保留正文缓冲。" if rich else "减少强组件数量，用更连续的阅读节奏组织长文。",
        "difference_from_recent": [recent_message, "同一语义组件可以继续使用；固定 CTA 不参与新鲜度计算。"],
        "structural_differences": [
            "逐段组件插槽与内容块绑定",
            "强组件密度和出现位置不同",
            "列表在逻辑路径与编号观点之间按语义选择",
        ],
        "component_usage": dict(usage),
        "configuration": configuration,
        "slots": slots,
        "image_slots": image_slots,
        "quality_constraints": {
            "max_strong_components_in_a_row": 1,
            "max_strong_components_per_article": 3 if rich else 2,
            "avoid_recent_component_sequence": True,
            "facts_locked": True,
        },
    }
    return payload


def generate_plans(
    parsed: ParsedArticle,
    article_type: str,
    history_window: int,
    recent_summaries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    recent = recent_summaries or []
    if article_type == "data_policy":
        styles = ("data_decision", "editorial_insight")
    elif article_type == "tutorial_steps":
        styles = ("lively_science", "editorial_insight")
    elif article_type == "lively_growth":
        styles = ("lively_science", "data_decision")
    else:
        styles = ("editorial_insight", "lively_science")

    candidates = _build_candidates(parsed, recent)
    opportunity_diagnostics = component_opportunity_diagnostics(parsed, recent)
    image_candidates = _image_candidates(parsed)
    first_palette = STYLE_PALETTES[styles[0]]
    second_palette = STYLE_PALETTES[styles[1]]
    strong_limit = min(6, max(3, 2 + len(parsed.blocks) // 8))
    first_slots = _select_candidates(candidates, COMPONENT_COVERAGE_PRIORITIES, strong_limit)
    second_slots = _select_candidates(
        candidates,
        ("section_summary", "comparison_card", "warning_note", "action_checklist", "case_card", "faq_card", "concept_explainer", "numbered_insight", "evidence_callout", "before_after_timeline", "question_hook", "logic_path"),
        max(2, strong_limit - 1),
    )
    first_image_slots = _select_image_slots(
        image_candidates,
        preferred_purpose="structured_infographic",
        limit=2,
        style_family="editorial_paper_cut",
        composition="branching",
        negative_space="lower_right",
    )
    second_image_slots = _select_image_slots(
        image_candidates,
        preferred_purpose="atmosphere",
        limit=1,
        style_family="soft_flat_illustration",
        composition="wide_scene",
        negative_space="lower_third",
    )
    first_image_slots = _align_images_after_component_content(
        first_image_slots,
        first_slots,
    )
    second_image_slots = _align_images_after_component_content(
        second_image_slots,
        second_slots,
    )
    plans = [
        _plan(
            index=1,
            style=styles[0],
            recommendation="recommended",
            parsed=parsed,
            history_window=history_window,
            slots=first_slots,
            image_slots=first_image_slots,
            recent_summaries=recent,
            configuration={
                "heading_variant": "botanical_section",
                "key_point_variant": "open_highlight",
                "quote_variant": "floating_quote",
                "list_variant": "leaf_path",
                "table_variant": "compact_grid",
                "theme_kit": "airy_organic_v1",
                "accent": first_palette["primary"],
                "palette": first_palette,
            },
        ),
        _plan(
            index=2,
            style=styles[1],
            recommendation="alternative",
            parsed=parsed,
            history_window=history_window,
            slots=second_slots,
            image_slots=second_image_slots,
            recent_summaries=recent,
            configuration={
                "heading_variant": "editorial_left_rule",
                "key_point_variant": "concise_rule",
                "quote_variant": "centered_sentence",
                "list_variant": "compact_checklist",
                "table_variant": "highlighted_column",
                "accent": second_palette["primary"],
                "palette": second_palette,
            },
        ),
    ]
    for plan in plans:
        plan["article_type"] = article_type
        plan["component_diagnostics"] = {
            **opportunity_diagnostics,
            "requested_component_count": None,
            "selected_component_count": len(plan["slots"]),
            "selected_component_types": [
                slot["component_type"] for slot in plan["slots"]
            ],
            "compiler_adjustments": [],
        }
        plan["quality_constraints"]["max_strong_components_per_article"] = (
            strong_limit if plan["plan_index"] == 1 else max(2, strong_limit - 1)
        )
        validate_plan_for_article(plan, parsed)
    return plans


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
