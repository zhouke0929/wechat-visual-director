"""Historical rules-only planning baseline, used by internal comparisons."""
from __future__ import annotations

import re
import copy
from collections import Counter
from typing import Any

from .component_opportunities import _build_candidates, _list_refs, component_opportunity_diagnostics
from .parser import ParsedArticle
from .plan_envelope import article_strong_limit, plan_envelope, structural_difference_count
from .plan_schema import validate_plan_for_article
from .image_intent import build_visual_intent, extract_display_label, readable_node_copy


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

def _block_number(block_id: str) -> int:
    return int(block_id.rsplit("-", 1)[-1])


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
        if (block.type in {"ordered_list", "unordered_list"} and 2 <= len(block.content) <= 4
                and readable_node_copy([extract_display_label(str(item)) for item in block.content])):
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
                    "title": str(previous.content) if title_ref and previous else subject,
                    "fact_anchors": [str(item) for item in block.content[:4]],
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
                        "title": str(block.content),
                        "fact_anchors": [],
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
                        "title": None,
                        "fact_anchors": [],
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
    negative_space: str,
    article_type: str,
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
                "visual_intent": build_visual_intent(
                    purpose=candidate["purpose"],
                    subject=candidate["subject"],
                    article_type=article_type,
                    title=candidate.get("title"),
                    fact_anchors=candidate.get("fact_anchors", []),
                    style_family=style_family,
                    palette_roles={
                        "data_policy": ["warm_ivory", "deep_navy", "muted_teal", "sunlit_yellow"],
                        "tutorial_steps": ["warm_ivory", "muted_teal", "coral_accent", "sunlit_yellow"],
                        "lively_growth": ["warm_ivory", "soft_sky", "coral_accent", "sunlit_yellow"],
                        "viewpoint_trend": ["warm_ivory", "deep_navy", "soft_sky", "coral_accent"],
                    }.get(article_type, ["warm_ivory", "deep_navy", "soft_sky"]),
                    tone=["清晰", "可信", "克制"],
                    negative_space=negative_space,
                ),
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
    article_type: str,
    history_window: int,
    slots: list[dict[str, Any]],
    image_slots: list[dict[str, Any]],
    configuration: dict[str, Any],
    recent_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    recent_message = (
        f"已读取最近 {min(len(recent_summaries), history_window)} 篇确认记录，并优先选择近期使用更少的具体变体。"
        if recent_summaries
        else f"当前没有可用的确认记录；保留最近 {history_window} 篇历史窗口配置。"
    )
    rich = index == 1
    payload: dict[str, Any] = {
        **plan_envelope(
            parsed, article_type=article_type, history_window=history_window, slots=slots,
            strong_limit=article_strong_limit(parsed) if rich else max(2, article_strong_limit(parsed) - 1),
        ),
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
        "configuration": configuration,
        "slots": slots,
        "image_slots": image_slots,
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
    strong_limit = article_strong_limit(parsed)
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
        negative_space="lower_right",
        article_type=article_type,
    )
    second_image_slots = _select_image_slots(
        image_candidates,
        preferred_purpose="atmosphere",
        limit=1,
        style_family="soft_flat_illustration",
        negative_space="lower_third",
        article_type=article_type,
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
            article_type=article_type,
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
            article_type=article_type,
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
        plan["component_diagnostics"] = {
            **opportunity_diagnostics,
            "requested_component_count": None,
            "selected_component_count": len(plan["slots"]),
            "selected_component_types": [
                slot["component_type"] for slot in plan["slots"]
            ],
            "compiler_adjustments": [],
        }
        validate_plan_for_article(plan, parsed)
    return plans
