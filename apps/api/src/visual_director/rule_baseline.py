"""Deterministic historical baseline for development fixtures and blind evaluation only."""
from __future__ import annotations

from typing import Any

from .editorial_brief import (
    ArtDirection, ArticleAnalysis, EditorialBrief, ImageIntent, SectionBrief, validate_editorial_brief_for_article,
)
from .planner import generate_plans
from .text_planner import TextPlannerRequest


ARTICLE_ANALYSIS: dict[str, dict[str, Any]] = {
    "data_policy": {
        "audience": ["需要核验信息的读者", "相关决策者"],
        "reader_task": "核对公开数据、规则与依据，并形成谨慎判断",
        "narrative": "从事实依据进入判断条件，再落到影响与行动",
        "tone": ["可信", "清晰", "克制"],
        "palette": ["muted_teal", "warm_ivory", "sunlit_yellow"],
    },
    "tutorial_steps": {
        "audience": ["需要完成具体任务的读者", "一线执行者"],
        "reader_task": "按顺序完成操作并避免关键遗漏",
        "narrative": "从任务目标进入步骤路径，最后完成复核",
        "tone": ["清晰", "有行动指引", "可信"],
        "palette": ["muted_teal", "warm_ivory", "coral_accent"],
    },
    "viewpoint_trend": {
        "audience": ["关注该议题的读者", "行业从业者"],
        "reader_task": "理解核心观点、证据与现实影响",
        "narrative": "从读者疑问进入观点解释，再回到现实选择",
        "tone": ["理性", "有洞察", "克制"],
        "palette": ["deep_navy", "warm_ivory", "coral_accent"],
    },
    "lively_growth": {
        "audience": ["关注人物、品牌或真实案例的读者"],
        "reader_task": "理解故事中的变化、经验与可迁移启发",
        "narrative": "从真实场景进入关键转折，再提炼经验与启发",
        "tone": ["亲和", "轻松", "有行动指引"],
        "palette": ["soft_sky", "warm_ivory", "sunlit_yellow"],
    },
}


SEMANTIC_ROLE = {
    "question_hook": "reader_question",
    "numbered_insight": "action_step",
    "evidence_callout": "key_evidence",
    "before_after_timeline": "comparison",
    "logic_path": "logic_sequence",
    "concept_explainer": "concept",
    "case_card": "case",
    "warning_note": "warning",
    "action_checklist": "checklist",
    "faq_card": "faq",
    "comparison_card": "comparison",
    "section_summary": "summary",
}


def _recent_patterns(recent_summaries: list[dict[str, Any]]) -> list[str]:
    patterns: list[str] = []
    for summary in recent_summaries[:5]:
        components = summary.get("components", [])
        values = [
            f"{item.get('component_type')}:{item.get('variant')}"
            for item in components
            if isinstance(item, dict) and item.get("component_type")
        ]
        if values:
            patterns.append(" + ".join(values[:3]))
    return patterns[:5]


def build_rule_based_brief(request: TextPlannerRequest) -> EditorialBrief:
    """Build the safe baseline in the same semantic contract used by future LLMs."""
    plan = generate_plans(
        request.parsed,
        request.article_type,
        request.history_window,
        request.recent_summaries,
    )[0]
    analysis = ARTICLE_ANALYSIS[request.article_type]
    strong_limit = min(6, max(3, 2 + len(request.parsed.blocks) // 8))
    sections = [
        SectionBrief(
            source_block_ids=slot["consume_block_ids"],
            semantic_role=SEMANTIC_ROLE[slot["component_type"]],
            visual_priority="high" if slot["emphasis"] == "primary" else "medium",
            component_intent=slot["component_type"],
            reasoning=slot["selection_reason"],
        )
        for slot in plan.get("slots", [])[:strong_limit]
    ]
    image_intents = [
        ImageIntent(
            anchor_block_id=slot["anchor_block_id"],
            source_block_ids=slot["source_block_ids"],
            purpose=slot["purpose"],
            necessity="recommended" if index == 0 else "optional",
            aspect_ratio=slot["aspect_ratio"],
            visual_metaphor=slot["visual_intent"]["subject"],
            visual_role=slot["visual_intent"].get("visual_role"),
            learning_objective=slot["visual_intent"].get("learning_objective"),
            layout_family=slot["visual_intent"].get("layout_family"),
            forbidden_elements=["text_in_model_image", "qr_code", "logo", "fabricated_data", "brand_cta"],
        )
        for index, slot in enumerate(plan.get("image_slots", [])[:3])
    ]
    brief = EditorialBrief(
        schema_version="editorial_brief.v0.1",
        article=ArticleAnalysis(
            article_type=request.article_type,
            audience=analysis["audience"],
            reader_task=analysis["reader_task"],
            narrative=analysis["narrative"],
        ),
        sections=sections,
        image_intents=image_intents,
        art_direction=ArtDirection(
            tone=analysis["tone"],
            palette_roles=analysis["palette"],
            style_family=(
                "soft_flat_illustration" if request.article_type == "lively_growth" else "editorial_paper_cut"
            ),
            avoid_recent_patterns=_recent_patterns(request.recent_summaries),
        ),
        facts_locked=True,
    )
    return validate_editorial_brief_for_article(brief, request.parsed)


class RuleTextPlannerProvider:
    provider = "rule_text_planner"
    model = "deterministic_editorial_brief"
    configured = False

    def generate(self, request: TextPlannerRequest) -> EditorialBrief:
        return build_rule_based_brief(request)


MockTextPlannerProvider = RuleTextPlannerProvider
