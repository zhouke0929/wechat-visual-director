from __future__ import annotations

from typing import Any


COMPONENT_LIBRARY_VERSION = "wechat_components.v0.6.0"
RENDERER_VERSION = "preview_renderer.v0.9.2-four-systems"
PLAN_SCHEMA_VERSION = "visual_plan.v0.5"


VISUAL_SYSTEM_ORDER = (
    "light_reading",
    "warm_humanist",
    "editorial_contrast",
    "structured_grid",
)

VISUAL_SYSTEM_MARKERS = {
    "light_reading": "A",
    "warm_humanist": "B",
    "editorial_contrast": "C",
    "structured_grid": "D",
}


COMPONENT_CATALOG: dict[str, dict[str, Any]] = {
    "question_hook": {
        "label": "问题钩子",
        "primary_variant": "light_bubble",
        "primary_label": "轻盈气泡",
        "fallback_variant": "plain_question",
        "fallback_label": "朴素问题",
        "system_variants": {
            "light_reading": {"value": "light_bubble", "label": "轻盈·气泡提问"},
            "warm_humanist": {"value": "warm_letter_prompt", "label": "人文·信笺提问"},
            "editorial_contrast": {"value": "editorial_deck_question", "label": "编辑·导语提问"},
            "structured_grid": {"value": "grid_query_panel", "label": "网格·问题索引"},
        },
        "variant_statuses": {
            "light_bubble": "wechat_verified",
            "warm_letter_prompt": "wechat_candidate",
            "editorial_deck_question": "wechat_candidate",
            "grid_query_panel": "wechat_candidate",
            "plain_question": "wechat_verified",
        },
        "required_bindings": {"title": "one"},
        "status": "wechat_verified",
    },
    "numbered_insight": {
        "label": "编号观点",
        "primary_variant": "gradient_guide_label",
        "primary_label": "清亮观点列",
        "alternate_variant": "magazine_index",
        "alternate_label": "杂志索引卡",
        "fallback_variant": "plain_numbered_list",
        "fallback_label": "朴素编号列表",
        "system_variants": {
            "light_reading": {"value": "gradient_guide_label", "label": "轻盈·清亮观点列"},
            "warm_humanist": {"value": "scrapbook_index", "label": "人文·手帐索引"},
            "editorial_contrast": {"value": "magazine_index", "label": "编辑·杂志索引"},
            "structured_grid": {"value": "coordinate_index", "label": "网格·坐标观点表"},
        },
        "required_bindings": {"items": "many"},
        "status": "wechat_verified",
        "variant_statuses": {
            "gradient_guide_label": "wechat_verified",
            "magazine_index": "wechat_verified",
            "scrapbook_index": "wechat_candidate",
            "coordinate_index": "wechat_candidate",
            "plain_numbered_list": "wechat_verified",
        },
    },
    "evidence_callout": {
        "label": "证据强调",
        "primary_variant": "orbit_outline",
        "primary_label": "轨道描边框",
        "alternate_variant": "editorial_margin_quote",
        "alternate_label": "编辑批注引文",
        "fallback_variant": "plain_evidence_note",
        "fallback_label": "朴素证据注释",
        "system_variants": {
            "light_reading": {"value": "orbit_outline", "label": "轻盈·轨道描边"},
            "warm_humanist": {"value": "annotated_note", "label": "人文·批注便笺"},
            "editorial_contrast": {"value": "editorial_margin_quote", "label": "编辑·边注引文"},
            "structured_grid": {"value": "evidence_register", "label": "网格·证据登记"},
        },
        "required_bindings": {"evidence": "one"},
        "status": "wechat_verified",
        "variant_statuses": {
            "orbit_outline": "wechat_verified",
            "editorial_margin_quote": "wechat_verified",
            "annotated_note": "wechat_candidate",
            "evidence_register": "wechat_candidate",
            "plain_evidence_note": "wechat_verified",
        },
    },
    "before_after_timeline": {
        "label": "前后时间线",
        "primary_variant": "dual_node_timeline",
        "primary_label": "双节点时间线",
        "fallback_variant": "stacked_before_after",
        "fallback_label": "朴素上下对照",
        "required_bindings": {"before": "one", "after": "one"},
        "status": "wechat_verified",
    },
    "logic_path": {
        "label": "逻辑路径",
        "primary_variant": "warm_route_nodes",
        "primary_label": "四色路线节点",
        "alternate_variant": "folded_stair",
        "alternate_label": "折线阶梯",
        "fallback_variant": "plain_steps",
        "fallback_label": "朴素步骤",
        "system_variants": {
            "light_reading": {"value": "airy_route", "label": "轻盈·呼吸路线"},
            "warm_humanist": {"value": "warm_route_nodes", "label": "人文·暖色路线"},
            "editorial_contrast": {"value": "folded_stair", "label": "编辑·折线阶梯"},
            "structured_grid": {"value": "process_register", "label": "网格·流程登记"},
        },
        "required_bindings": {"items": "many"},
        "status": "wechat_verified",
        "variant_statuses": {
            "warm_route_nodes": "wechat_verified",
            "folded_stair": "wechat_verified",
            "airy_route": "wechat_candidate",
            "process_register": "wechat_candidate",
            "plain_steps": "wechat_verified",
        },
    },
    "concept_explainer": {
        "label": "概念解释",
        "primary_variant": "node_note_card",
        "primary_label": "节点说明卡",
        "fallback_variant": "plain_definition",
        "fallback_label": "朴素定义",
        "required_bindings": {"title": "one", "definition": "one"},
        "status": "wechat_verified",
    },
    "case_card": {
        "label": "案例卡片",
        "primary_variant": "story_file",
        "primary_label": "故事档案",
        "fallback_variant": "plain_case",
        "fallback_label": "朴素案例",
        "required_bindings": {"title": "one", "body": "one"},
        "status": "wechat_candidate",
    },
    "warning_note": {
        "label": "风险提示",
        "primary_variant": "risk_tape",
        "primary_label": "警示胶带",
        "fallback_variant": "plain_warning",
        "fallback_label": "朴素提示",
        "required_bindings": {"body": "one"},
        "status": "wechat_candidate",
    },
    "action_checklist": {
        "label": "行动清单",
        "primary_variant": "field_checklist",
        "primary_label": "现场核对单",
        "fallback_variant": "plain_checklist",
        "fallback_label": "朴素清单",
        "system_variants": {
            "light_reading": {"value": "soft_tick_list", "label": "轻盈·柔光勾选"},
            "warm_humanist": {"value": "field_checklist", "label": "人文·现场核对单"},
            "editorial_contrast": {"value": "proofing_checklist", "label": "编辑·校样清单"},
            "structured_grid": {"value": "audit_matrix", "label": "网格·审计矩阵"},
        },
        "required_bindings": {"items": "many"},
        "status": "wechat_candidate",
    },
    "faq_card": {
        "label": "问答卡片",
        "primary_variant": "editorial_qa",
        "primary_label": "编辑问答",
        "fallback_variant": "plain_qa",
        "fallback_label": "朴素问答",
        "system_variants": {
            "light_reading": {"value": "conversation_bubble", "label": "轻盈·对话气泡"},
            "warm_humanist": {"value": "advice_letter", "label": "人文·答疑信笺"},
            "editorial_contrast": {"value": "editorial_qa", "label": "编辑·问答专栏"},
            "structured_grid": {"value": "qa_register", "label": "网格·问答登记"},
        },
        "required_bindings": {"question": "one", "answer": "one"},
        "status": "wechat_candidate",
    },
    "comparison_card": {
        "label": "对比卡片",
        "primary_variant": "split_comparison",
        "primary_label": "双栏对照",
        "fallback_variant": "plain_comparison",
        "fallback_label": "朴素对照",
        "required_bindings": {"left": "one", "right": "one"},
        "status": "wechat_candidate",
    },
    "section_summary": {
        "label": "阶段小结",
        "primary_variant": "chapter_takeaway",
        "primary_label": "章节收束卡",
        "fallback_variant": "plain_summary",
        "fallback_label": "朴素小结",
        "required_bindings": {"items": "many"},
        "status": "wechat_candidate",
    },
}


def allowed_variants(component_type: str) -> set[str]:
    definition = COMPONENT_CATALOG[component_type]
    variants = {definition["primary_variant"], definition["fallback_variant"]}
    if definition.get("alternate_variant"):
        variants.add(definition["alternate_variant"])
    variants.update(
        item["value"] for item in definition.get("system_variants", {}).values()
    )
    return variants


def automatic_variants(component_type: str) -> list[str]:
    definition = COMPONENT_CATALOG[component_type]
    variants = [definition["primary_variant"]]
    if definition.get("alternate_variant"):
        variants.append(definition["alternate_variant"])
    return variants


def component_options(component_type: str) -> list[dict[str, str]]:
    definition = COMPONENT_CATALOG[component_type]
    statuses = definition.get("variant_statuses", {})
    system_variants = definition.get("system_variants")
    if system_variants:
        options = []
        seen: set[str] = set()
        for visual_system in VISUAL_SYSTEM_ORDER:
            item = system_variants.get(visual_system)
            if not item or item["value"] in seen:
                continue
            value = item["value"]
            options.append(
                {
                    "value": value,
                    "label": item["label"],
                    "kind": "primary" if not options else "alternate",
                    "marker": VISUAL_SYSTEM_MARKERS[visual_system],
                    "status": statuses.get(value, definition["status"]),
                }
            )
            seen.add(value)
        fallback = definition["fallback_variant"]
        options.append(
            {
                "value": fallback,
                "label": definition["fallback_label"],
                "kind": "fallback",
                "marker": "E",
                "status": statuses.get(fallback, definition["status"]),
            }
        )
        return options

    options = [
        {
            "value": definition["primary_variant"],
            "label": definition["primary_label"],
            "kind": "primary",
            "marker": "A",
            "status": statuses.get(definition["primary_variant"], definition["status"]),
        }
    ]
    if definition.get("alternate_variant"):
        options.append(
            {
                "value": definition["alternate_variant"],
                "label": definition["alternate_label"],
                "kind": "alternate",
                "marker": "B",
                "status": statuses.get(definition["alternate_variant"], definition["status"]),
            }
        )
    options.append(
        {
            "value": definition["fallback_variant"],
            "label": definition["fallback_label"],
            "kind": "fallback",
            "marker": "C" if definition.get("alternate_variant") else "B",
            "status": statuses.get(definition["fallback_variant"], definition["status"]),
        }
    )
    return options
