from __future__ import annotations

import copy
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .parser import ParsedArticle


EDITORIAL_BRIEF_SCHEMA_VERSION = "editorial_brief.v0.1"
EDITORIAL_BRIEF_NORMALIZER_VERSION = "editorial_brief_normalizer.v0.5-concept-semantic-guard"

CONCEPT_HEADING_RE = re.compile(r"什么是|核心概念|概念解释|概念定义|定义[：:]?")
NON_CONCEPT_HEADING_RE = re.compile(
    r"核心功能|功能[一二三四五六七八九十百0-9]+|痛点|信号|步骤|"
    r"第[一二三四五六七八九十百0-9]+步|答案|我们能帮|优势|下一步|行动清单|"
    r"怎么(?:做|操作|使用)|如何(?:操作|使用)"
)
CONCEPT_DEFINITION_RE = re.compile(r"是指|指的是|本质上是|定义为|可以理解为")


def is_concept_pair(heading: str, paragraph: str) -> bool:
    """Return whether an adjacent H3+ pair expresses a concept definition.

    Operational headings such as “核心功能五” must remain article structure,
    even if their paragraph contains a generic phrase such as “核心是”.
    """
    if CONCEPT_HEADING_RE.search(heading):
        return True
    if NON_CONCEPT_HEADING_RE.search(heading):
        return False
    return bool(CONCEPT_DEFINITION_RE.search(paragraph))

ArticleType = Literal["data_policy", "tutorial_steps", "viewpoint_trend", "lively_growth"]
ComponentIntent = Literal[
    "plain",
    "question_hook",
    "numbered_insight",
    "evidence_callout",
    "before_after_timeline",
    "logic_path",
    "concept_explainer",
    "case_card",
    "warning_note",
    "action_checklist",
    "faq_card",
    "comparison_card",
    "section_summary",
]


class ArticleAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article_type: ArticleType
    audience: list[str] = Field(min_length=1, max_length=4)
    reader_task: str = Field(min_length=1, max_length=120)
    narrative: str = Field(min_length=1, max_length=160)


class SectionBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_block_ids: list[str] = Field(min_length=1, max_length=8)
    semantic_role: Literal[
        "reader_question",
        "key_evidence",
        "action_step",
        "comparison",
        "concept",
        "logic_sequence",
        "case",
        "warning",
        "checklist",
        "faq",
        "summary",
        "plain_narrative",
    ]
    visual_priority: Literal["low", "medium", "high"]
    component_intent: ComponentIntent
    reasoning: str = Field(min_length=1, max_length=240)


class ImageIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_block_id: str = Field(pattern=r"^block-\d{3}$")
    source_block_ids: list[str] = Field(min_length=1, max_length=6)
    purpose: Literal["atmosphere", "structured_infographic"]
    necessity: Literal["optional", "recommended"]
    aspect_ratio: Literal["4:3", "16:9"]
    visual_metaphor: str = Field(min_length=1, max_length=160)
    forbidden_elements: list[
        Literal[
            "text_in_model_image",
            "qr_code",
            "logo",
            "official_seal",
            "fabricated_data",
            "brand_cta",
        ]
    ] = Field(min_length=3, max_length=6)

    @model_validator(mode="after")
    def validate_image_safety(self) -> "ImageIntent":
        if self.anchor_block_id not in self.source_block_ids:
            raise ValueError("图片锚点必须包含在 source_block_ids 中")
        required = {"text_in_model_image", "qr_code", "logo"}
        if not required.issubset(set(self.forbidden_elements)):
            raise ValueError("图片禁用项必须包含文字、二维码和 Logo")
        return self


class ArtDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: list[str] = Field(min_length=1, max_length=4)
    palette_roles: list[
        Literal[
            "deep_navy",
            "muted_teal",
            "warm_ivory",
            "coral_accent",
            "sunlit_yellow",
            "soft_sky",
        ]
    ] = Field(min_length=2, max_length=5)
    style_family: Literal["editorial_paper_cut", "soft_flat_illustration", "clean_3d_geometry"]
    avoid_recent_patterns: list[str] = Field(max_length=5)


class EditorialBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["editorial_brief.v0.1"]
    article: ArticleAnalysis
    sections: list[SectionBrief] = Field(max_length=12)
    image_intents: list[ImageIntent] = Field(max_length=3)
    art_direction: ArtDirection
    facts_locked: Literal[True]

    @model_validator(mode="after")
    def validate_brief_limits(self) -> "EditorialBrief":
        strong_sections = [section for section in self.sections if section.component_intent != "plain"]
        if len(strong_sections) > 6:
            raise ValueError("每篇文章的强组件建议不能超过 6 个")
        anchors = [intent.anchor_block_id for intent in self.image_intents]
        if len(anchors) != len(set(anchors)):
            raise ValueError("同一个内容块不能放置多个图片槽")
        return self


def _is_component_heading(block: object) -> bool:
    """Only body subheadings may be transformed into semantic components.

    H1 is the article title and H2 defines the primary article skeleton.  Both
    must remain visible, stable structural assets (D85).
    """
    return block.type == "heading" and (block.level or 0) >= 3


def _adjacent_concept_pair(
    source_block_ids: list[str],
    blocks: dict[str, object],
    *,
    require_concept_semantics: bool = False,
) -> tuple[object, object] | None:
    """Return an H3+ heading and its immediately following definition paragraph.

    The adjacency check is performed against the complete article order, not a
    filtered source list.  This prevents a broad model reference from silently
    pairing an H2 with an unrelated later paragraph (D86).
    """
    requested = set(source_block_ids)
    ordered = list(blocks.values())
    for index, block in enumerate(ordered[:-1]):
        following = ordered[index + 1]
        if (
            block.id in requested
            and following.id in requested
            and _is_component_heading(block)
            and following.type == "paragraph"
            and (
                not require_concept_semantics
                or is_concept_pair(str(block.content), str(following.content))
            )
        ):
            return block, following
    return None


def _section_bound_block_ids(section: SectionBrief, blocks: dict[str, object]) -> list[str]:
    if section.component_intent == "plain":
        return []
    requested = set(section.source_block_ids)
    source_blocks = [block for block_id, block in blocks.items() if block_id in requested]
    headings = [block for block in source_blocks if _is_component_heading(block)]
    paragraphs = [block for block in source_blocks if block.type == "paragraph"]
    lists = [block for block in source_blocks if block.type in {"ordered_list", "unordered_list"}]
    evidence = [block for block in source_blocks if block.type in {"quote", "paragraph"}]
    if section.component_intent == "question_hook" and headings:
        return [headings[0].id]
    if section.component_intent == "numbered_insight" and lists and 2 <= len(lists[0].content) <= 5:
        return [lists[0].id]
    if section.component_intent == "evidence_callout" and evidence:
        return [evidence[0].id]
    if section.component_intent == "before_after_timeline" and lists and len(lists[0].content) >= 2:
        return [lists[0].id]
    if (
        section.component_intent == "logic_path"
        and lists
        and lists[0].type == "ordered_list"
        and 3 <= len(lists[0].content) <= 5
    ):
        return [lists[0].id]
    if section.component_intent == "concept_explainer":
        pair = _adjacent_concept_pair(
            section.source_block_ids,
            blocks,
            require_concept_semantics=True,
        )
        if pair:
            return [pair[0].id, pair[1].id]
    if section.component_intent in {"case_card", "faq_card"}:
        pair = _adjacent_concept_pair(section.source_block_ids, blocks)
        if pair:
            return [pair[0].id, pair[1].id]
    if section.component_intent == "warning_note" and evidence:
        return [evidence[0].id]
    if section.component_intent in {"action_checklist", "section_summary"} and lists and 2 <= len(lists[0].content) <= 6:
        return [lists[0].id]
    if section.component_intent == "comparison_card" and lists and len(lists[0].content) >= 2:
        return [lists[0].id]
    return []


def _section_compatible(section: SectionBrief, blocks: dict[str, object]) -> bool:
    return section.component_intent == "plain" or bool(_section_bound_block_ids(section, blocks))


def _structured_image_compatible(intent: ImageIntent, blocks: dict[str, object]) -> bool:
    source_blocks = [blocks[block_id] for block_id in intent.source_block_ids]
    return any(
        block.type in {"ordered_list", "unordered_list"} and 2 <= len(block.content) <= 4
        for block in source_blocks
    )


def normalize_editorial_brief_for_article(
    brief: EditorialBrief | dict,
    parsed: ParsedArticle,
) -> tuple[EditorialBrief, list[dict[str, str]]]:
    """Safely lower unsupported preferences without changing facts or references."""
    blocks = {block.id: block for block in parsed.blocks}
    block_ids = set(blocks)
    adjustments: list[dict[str, str]] = []
    if isinstance(brief, EditorialBrief):
        contract = brief
    else:
        prepared = copy.deepcopy(brief)
        prepared["schema_version"] = EDITORIAL_BRIEF_SCHEMA_VERSION
        prepared["facts_locked"] = True

        sections = prepared.get("sections")
        if isinstance(sections, list):
            priority = {"high": 0, "medium": 1, "low": 2}
            strong_indices = [
                index
                for index, section in enumerate(sections)
                if isinstance(section, dict) and section.get("component_intent") not in {None, "plain"}
            ]
            strong_limit = min(6, max(3, 2 + len(parsed.blocks) // 8))
            if len(strong_indices) > strong_limit:
                keep = set(
                    sorted(
                        strong_indices,
                        key=lambda index: (priority.get(sections[index].get("visual_priority"), 3), index),
                    )[:strong_limit]
                )
                for index in strong_indices:
                    if index in keep:
                        continue
                    previous = sections[index].get("component_intent")
                    sections[index]["component_intent"] = "plain"
                    adjustments.append(
                        {
                            "code": "excess_component_intent_lowered_to_plain",
                            "location": f"sections[{index}]",
                            "from": str(previous),
                            "reason": f"强组件超过当前文章长度对应的 {strong_limit} 个质量上限",
                        }
                    )

        image_intents = prepared.get("image_intents")
        if isinstance(image_intents, list):
            for index, intent in enumerate(image_intents):
                if not isinstance(intent, dict):
                    continue
                metaphor = intent.get("visual_metaphor")
                if isinstance(metaphor, str) and len(metaphor) > 160:
                    intent["visual_metaphor"] = metaphor[:160]
                    adjustments.append(
                        {
                            "code": "visual_metaphor_truncated",
                            "location": f"image_intents[{index}].visual_metaphor",
                            "from": f"{len(metaphor)} chars",
                            "reason": "超过 Provider 语义字段安全长度",
                        }
                    )
                anchor = intent.get("anchor_block_id")
                source_ids = intent.get("source_block_ids")
                if isinstance(anchor, str) and anchor in block_ids and isinstance(source_ids, list) and anchor not in source_ids:
                    intent["source_block_ids"] = [anchor, *source_ids][:6]
                    adjustments.append(
                        {
                            "code": "image_anchor_added_to_sources",
                            "location": f"image_intents[{index}].source_block_ids",
                            "from": anchor,
                            "reason": "VisualPlan 要求图片锚点包含在来源块中",
                        }
                    )
                forbidden = intent.get("forbidden_elements")
                if not isinstance(forbidden, list):
                    forbidden = []
                for required in ("text_in_model_image", "qr_code", "logo"):
                    if required not in forbidden:
                        forbidden.append(required)
                intent["forbidden_elements"] = forbidden[:6]

        contract = EditorialBrief.model_validate(prepared)

    normalized = contract.model_copy(deep=True)
    consumed: set[str] = set()

    for index, section in enumerate(normalized.sections):
        missing = set(section.source_block_ids) - block_ids
        if missing:
            raise ValueError(f"组件建议引用了不存在的原文块：{sorted(missing)}")
        if section.component_intent == "plain":
            continue
        bound_ids = _section_bound_block_ids(section, blocks)
        overlap = consumed.intersection(bound_ids)
        if overlap or not bound_ids:
            previous = section.component_intent
            section.component_intent = "plain"
            adjustments.append(
                {
                    "code": "component_intent_lowered_to_plain",
                    "location": f"sections[{index}]",
                    "from": previous,
                    "reason": "重复消费原文块" if overlap else "组件偏好与当前原文块类型不兼容",
                }
            )
            continue
        consumed.update(bound_ids)

    active_components = []
    for section in normalized.sections:
        if section.component_intent == "plain":
            continue
        active_components.append(_section_bound_block_ids(section, blocks))

    normalized_images: list[ImageIntent] = []
    used_anchors: set[str] = set()
    for index, intent in enumerate(normalized.image_intents):
        missing = set(intent.source_block_ids) - block_ids
        if missing:
            raise ValueError(f"图片建议引用了不存在的原文块：{sorted(missing)}")
        if intent.purpose == "structured_infographic" and not _structured_image_compatible(intent, blocks):
            intent.purpose = "atmosphere"
            intent.necessity = "optional"
            intent.aspect_ratio = "16:9"
            adjustments.append(
                {
                    "code": "structured_image_lowered_to_atmosphere",
                    "location": f"image_intents[{index}]",
                    "from": "structured_infographic",
                    "reason": "没有可锁定 2–4 个原文列表事实的内容块",
                }
            )
        containing_component = next(
            (
                consumed_blocks
                for consumed_blocks in active_components
                if intent.anchor_block_id in consumed_blocks
                and intent.anchor_block_id != consumed_blocks[-1]
            ),
            None,
        )
        if containing_component:
            safe_anchor = containing_component[-1]
            if safe_anchor in intent.source_block_ids and safe_anchor not in used_anchors:
                previous_anchor = intent.anchor_block_id
                intent.anchor_block_id = safe_anchor
                adjustments.append(
                    {
                        "code": "image_anchor_moved_after_component",
                        "location": f"image_intents[{index}]",
                        "from": previous_anchor,
                        "reason": "图片不能插入组件消费内容的中间",
                    }
                )
            else:
                adjustments.append(
                    {
                        "code": "image_intent_removed_for_component_collision",
                        "location": f"image_intents[{index}]",
                        "from": intent.anchor_block_id,
                        "reason": "找不到不破坏组件完整性的安全图片锚点",
                    }
                )
                continue
        if intent.anchor_block_id in used_anchors:
            adjustments.append(
                {
                    "code": "duplicate_image_anchor_removed",
                    "location": f"image_intents[{index}]",
                    "from": intent.anchor_block_id,
                    "reason": "规范化后图片锚点重复",
                }
            )
            continue
        used_anchors.add(intent.anchor_block_id)
        normalized_images.append(intent)

    normalized.image_intents = normalized_images
    return validate_editorial_brief_for_article(normalized, parsed), adjustments


def validate_editorial_brief_for_article(
    brief: EditorialBrief | dict,
    parsed: ParsedArticle,
) -> EditorialBrief:
    contract = brief if isinstance(brief, EditorialBrief) else EditorialBrief.model_validate(brief)
    blocks = {block.id: block for block in parsed.blocks}
    block_ids = set(blocks)
    consumed_by_components: set[str] = set()

    for section in contract.sections:
        missing = set(section.source_block_ids) - block_ids
        if missing:
            raise ValueError(f"组件建议引用了不存在的原文块：{sorted(missing)}")
        if section.component_intent == "plain":
            continue
        bound_ids = _section_bound_block_ids(section, blocks)
        overlap = consumed_by_components.intersection(bound_ids)
        if overlap:
            raise ValueError(f"多个强组件不能重复消费同一原文块：{sorted(overlap)}")
        consumed_by_components.update(bound_ids)
        if not bound_ids:
            raise ValueError(
                f"组件意图 {section.component_intent} 与原文块类型不兼容：{section.source_block_ids}"
            )

    for intent in contract.image_intents:
        missing = set(intent.source_block_ids) - block_ids
        if missing:
            raise ValueError(f"图片建议引用了不存在的原文块：{sorted(missing)}")
        if intent.purpose == "structured_infographic":
            if not _structured_image_compatible(intent, blocks):
                raise ValueError("结构信息图只能引用包含 2–4 个条目的原文列表")

    return contract
