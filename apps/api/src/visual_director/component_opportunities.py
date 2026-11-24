"""Source-grounded suggestions for the host. This module never chooses or creates a plan."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .component_catalog import COMPONENT_CATALOG, automatic_variants
from .parser import ContentBlock, ParsedArticle
from .editorial_brief import (
    adjacent_comparison_pair,
    adjacent_concept_pairs,
    is_concept_pair,
    is_parallel_analysis_heading,
    is_reader_question_heading,
)


_WARNING_LABEL = r"风险(?:提示|提醒)|(?:安全)?注意事项|安全提示|使用限制|适用限制|警告"
_WARNING_LEAD_RE = re.compile(
    rf"^(?:(?:{_WARNING_LABEL})\s*[：:]|请注意|需要注意[：:]|切勿|务必|谨防|严禁|请勿)"
)
_WARNING_HEADING_RE = re.compile(rf"^(?:{_WARNING_LABEL})[：:]?$")
_WARNING_INSTRUCTION_RE = re.compile(r"^(?:不要|不得|禁止|必须|应先|不能|不适用)")


def _is_automatic_warning(block: ContentBlock, previous: ContentBlock | None) -> bool:
    # A quoted instruction may be addressed to a model or to someone in the
    # story. A substring cannot establish that it warns this article's reader.
    if block.type != "paragraph":
        return False
    body = str(block.content).strip()
    return bool(
        _WARNING_LEAD_RE.match(body)
        or (
            previous
            and previous.type == "heading"
            and _WARNING_HEADING_RE.fullmatch(str(previous.content).strip())
            and _WARNING_INSTRUCTION_RE.match(body)
        )
    )


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
            # Consecutive, parallel pairs give more evidence than an isolated
            # short heading: at least one paragraph must actually discuss its
            # named term or explicitly define it.
            if len(pairs) >= 2 and any(
                str(h.content).strip() in str(p.content)
                or is_concept_pair(str(h.content), str(p.content), allow_implicit=False)
                for h, p in pairs
            ):
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
            concept_pair = bool(
                following
                and following.type == "paragraph"
                and is_concept_pair(heading, str(following.content))
            )
            if (
                is_reader_question_heading(heading)
                and not concept_pair
                and not is_parallel_analysis_heading(
                    block.id,
                    {item.id: item for item in blocks},
                )
            ):
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
            if concept_pair and is_concept_pair(heading, str(following.content), allow_implicit=False):
                candidates.append(
                    _candidate(
                        "concept_explainer",
                        [block, following],
                        {"title": block.id, "definition": following.id},
                        "标题与紧随正文构成明确的概念及解释。",
                        recent_counts,
                    )
                )
        if (
            block.type == "heading" and (block.level or 0) >= 2
            and following and following.type in {"ordered_list", "unordered_list"}
            and len(following.content) == 2
            and re.search(r"前后|新旧|之前.*之后|旧版.*新版", str(block.content))
        ):
            # A chapter title can identify the relationship without becoming
            # part of the component: keep H2 in the article's outline.
            candidates.append(
                _candidate(
                    "before_after_timeline",
                    [following] if block.level == 2 else [block, following],
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

        # Quotation formatting alone is not evidence. Keep personal remarks and
        # pull quotes in the ordinary quote renderer; the host may still select
        # evidence explicitly when the surrounding argument supports it.
        if block.type == "quote" and re.search(
            r"(?:数据|统计|调查|研究|报告|公告|年报|条例|规定)[^。！？\n]{0,24}"
            r"(?:显示|表明|发现|指出|规定|要求|披露|明确)",
            str(block.content),
        ):
            candidates.append(
                _candidate("evidence_callout", [block], {"evidence": block.id}, "引用含明确的数据、研究或规则归因线索；仍需宿主核对证据语义，不代表来源真实性已经验证。", recent_counts)
            )

        if _is_automatic_warning(block, previous):
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
            if re.search(r"对比|区别|差异|优缺点|两种", heading_context) and len(block.content) == 2:
                refs = _list_refs(block)
                candidates.append(
                    _candidate("comparison_card", [block], {"left": refs[0], "right": refs[1]}, "列表由明确对比语义标题引导。", recent_counts)
                )
            if re.search(r"小结|总结|结论|要点|回顾", heading_context) and len(block.content) <= 6:
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
