from __future__ import annotations

from typing import Any

from .theme_extensions import (
    EXTENDED_THEME_IDS,
    EXTENDED_THEME_KITS,
    extended_component_label,
    extended_variant_name,
)


COMPONENT_LIBRARY_VERSION = "wechat_components.v0.13.0"
RENDERER_VERSION = "preview_renderer.v0.18.0-theme-expansion"
PLAN_SCHEMA_VERSION = "visual_plan.v0.5"


VISUAL_SYSTEM_ORDER = (
    "light_reading",
    "warm_humanist",
    "youth_campus",
    "editorial_contrast",
    "structured_grid",
    "future_tech",
) + EXTENDED_THEME_IDS

# Candidate themes remain visible in the gallery and manual theme switcher, but
# they must not enter an operator's draft automatically before visual approval.
PRODUCTION_VISUAL_SYSTEMS = (
    "light_reading",
    "warm_humanist",
    "youth_campus",
    "editorial_contrast",
    "structured_grid",
    "future_tech",
)
AUTO_RECOMMENDABLE_VISUAL_SYSTEMS = PRODUCTION_VISUAL_SYSTEMS + ("pop_poster",)

VISUAL_SYSTEM_MARKERS = {
    "light_reading": "A",
    "warm_humanist": "B",
    "youth_campus": "C",
    "editorial_contrast": "D",
    "structured_grid": "E",
    "future_tech": "F",
    **{
        theme_id: marker
        for theme_id, marker in zip(EXTENDED_THEME_IDS, ("G", "H", "I", "J", "K", "L"), strict=True)
    },
}

VISUAL_SYSTEM_CATALOG: dict[str, dict[str, Any]] = {
    "light_reading": {
        "label": "轻盈阅读",
        "english": "AIRY READING",
        "description": "用开放式标题、叶片线条、漂浮批注和少量柔色块组织教育科普长文。",
        "ideal_for": ["通用科普", "教育解读", "长文阅读"],
        "personality": ["清透", "亲和", "低压迫感"],
        "palette": ["#117C73", "#58B9E4", "#F4C84A", "#FFFEFA"],
        "status": "theme_kit_v1_review",
    },
    "warm_humanist": {
        "label": "温暖人文",
        "english": "WARM HUMANIST",
        "description": "用纸张感、暖珊瑚色和手作细节增强成长故事与人物内容的叙事温度。",
        "ideal_for": ["成长故事", "生涯规划", "人物内容"],
        "personality": ["温暖", "叙事", "有人情味"],
        "palette": ["#8E4B3B", "#D66B4D", "#D7A83E", "#FFFCF7"],
        "status": "theme_kit_v1_review",
    },
    "youth_campus": {
        "label": "青春校园",
        "english": "CAMPUS BULLETIN",
        "description": "用课程票根、活页纸、公告栏和手账批注承接校园活动、学生成长与升学热点。",
        "ideal_for": ["校园活动", "学生成长", "升学热点"],
        "personality": ["明快", "有参与感", "年轻"],
        "palette": ["#2D6CDF", "#FFC857", "#F06F8F", "#FFFEFB"],
        "status": "theme_kit_v1_review",
    },
    "editorial_contrast": {
        "label": "编辑对比",
        "english": "EDITORIAL CONTRAST",
        "description": "用杂志式大字号、锐利分隔和克制对比建立观点文章的编辑秩序。",
        "ideal_for": ["观点评论", "趋势观察", "人物访谈"],
        "personality": ["鲜明", "编辑感", "有判断力"],
        "palette": ["#243B53", "#B85C47", "#D6A84B", "#FFFDF8"],
        "status": "theme_kit_v1_review",
    },
    "structured_grid": {
        "label": "理性网格",
        "english": "STRUCTURED GRID",
        "description": "用栏目索引、数据轨道、坐标轴和非对称表格组织政策、流程与专业信息。",
        "ideal_for": ["数据政策", "步骤教程", "专业介绍"],
        "personality": ["理性", "清晰", "高信息密度"],
        "palette": ["#526A43", "#779B91", "#D7A83F", "#FFFDF8"],
        "status": "theme_kit_v1_review",
    },
    "future_tech": {
        "label": "未来科技",
        "english": "FUTURE EDITION",
        "description": "用极光色带、错位留白、杂志式大字号和轻盈数据视觉组织 AI 教育、科技趋势与专业前沿。",
        "ideal_for": ["AI 教育", "科技趋势", "专业前沿"],
        "personality": ["前沿", "轻盈", "科学杂志"],
        "palette": ["#304B8E", "#5CCBC1", "#FF826E", "#FEFEFF"],
        "status": "theme_kit_v1_review",
    },
}

for _theme_id, _theme_kit in EXTENDED_THEME_KITS.items():
    VISUAL_SYSTEM_CATALOG[_theme_id] = {
        "label": _theme_kit["label"],
        "english": _theme_kit["english"],
        "description": _theme_kit["description"],
        "ideal_for": list(_theme_kit["ideal_for"]),
        "personality": list(_theme_kit["personality"]),
        "palette": list(_theme_kit["palette"]),
        "status": "candidate_approved" if _theme_id == "pop_poster" else "candidate_theme_lab",
        "auto_recommendable": _theme_id in AUTO_RECOMMENDABLE_VISUAL_SYSTEMS,
    }

CORE_THEME_COMPONENTS = (
    "numbered_insight",
    "concept_explainer",
    "evidence_callout",
    "action_checklist",
    "before_after_timeline",
    "warning_note",
    "comparison_card",
    "section_summary",
)


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
            "youth_campus": {"value": "campus_notice_prompt", "label": "校园·公告票根提问"},
            "editorial_contrast": {"value": "editorial_deck_question", "label": "编辑·导语提问"},
            "structured_grid": {"value": "grid_query_panel", "label": "网格·问题索引"},
            "future_tech": {"value": "holo_query", "label": "科技·研究问题页"},
        },
        "variant_statuses": {
            "light_bubble": "wechat_verified",
            "warm_letter_prompt": "wechat_candidate",
            "campus_notice_prompt": "wechat_candidate",
            "editorial_deck_question": "wechat_candidate",
            "grid_query_panel": "wechat_candidate",
            "holo_query": "wechat_candidate",
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
            "light_reading": {"value": "leaf_index_ribbon", "label": "轻盈·叶片索引带"},
            "warm_humanist": {"value": "scrapbook_index", "label": "人文·页边故事索引"},
            "youth_campus": {"value": "course_ticket_stack", "label": "校园·课程票根列"},
            "editorial_contrast": {"value": "magazine_index", "label": "编辑·头条索引"},
            "structured_grid": {"value": "data_spine", "label": "网格·数据脊柱"},
            "future_tech": {"value": "spectrum_nodes", "label": "科技·实验索引"},
        },
        "required_bindings": {"items": "many"},
        "status": "wechat_verified",
        "variant_statuses": {
            "gradient_guide_label": "wechat_verified",
            "course_ticket_stack": "wechat_candidate",
            "leaf_index_ribbon": "wechat_candidate",
            "data_spine": "wechat_candidate",
            "magazine_index": "wechat_verified",
            "scrapbook_index": "wechat_candidate",
            "coordinate_index": "wechat_candidate",
            "spectrum_nodes": "wechat_candidate",
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
            "light_reading": {"value": "floating_quote_note", "label": "轻盈·漂浮批注"},
            "warm_humanist": {"value": "annotated_note", "label": "人文·明信片引文"},
            "youth_campus": {"value": "megaphone_quote", "label": "校园·广播站摘录"},
            "editorial_contrast": {"value": "editorial_margin_quote", "label": "编辑·跨栏引文"},
            "structured_grid": {"value": "evidence_margin", "label": "网格·证据边注"},
            "future_tech": {"value": "pulse_quote", "label": "科技·观察证据"},
        },
        "required_bindings": {"evidence": "one"},
        "status": "wechat_verified",
        "variant_statuses": {
            "orbit_outline": "wechat_verified",
            "megaphone_quote": "wechat_candidate",
            "floating_quote_note": "wechat_candidate",
            "evidence_margin": "wechat_candidate",
            "editorial_margin_quote": "wechat_verified",
            "annotated_note": "wechat_candidate",
            "evidence_register": "wechat_candidate",
            "pulse_quote": "wechat_candidate",
            "plain_evidence_note": "wechat_verified",
        },
    },
    "before_after_timeline": {
        "label": "前后时间线",
        "primary_variant": "dual_node_timeline",
        "primary_label": "双节点时间线",
        "fallback_variant": "stacked_before_after",
        "fallback_label": "朴素上下对照",
        "system_variants": {
            "light_reading": {"value": "paired_current", "label": "轻盈·双流转折"},
            "warm_humanist": {"value": "stitched_before_after", "label": "人文·翻页转折"},
            "youth_campus": {"value": "split_page_flip", "label": "校园·翻页对照"},
            "editorial_contrast": {"value": "editorial_before_after", "label": "编辑·断栏对照"},
            "structured_grid": {"value": "shift_axis", "label": "网格·变化坐标轴"},
            "future_tech": {"value": "vector_shift", "label": "科技·状态迁移"},
        },
        "variant_statuses": {
            "airy_before_after": "wechat_candidate",
            "split_page_flip": "wechat_candidate",
            "paired_current": "wechat_candidate",
            "shift_axis": "wechat_candidate",
            "stitched_before_after": "wechat_candidate",
            "editorial_before_after": "wechat_candidate",
            "change_register": "wechat_candidate",
            "vector_shift": "wechat_candidate",
            "dual_node_timeline": "wechat_verified",
            "stacked_before_after": "wechat_verified",
        },
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
            "youth_campus": {"value": "club_route_map", "label": "校园·社团路线图"},
            "editorial_contrast": {"value": "folded_stair", "label": "编辑·折线阶梯"},
            "structured_grid": {"value": "process_register", "label": "网格·流程登记"},
            "future_tech": {"value": "orbit_route", "label": "科技·极光路径"},
        },
        "required_bindings": {"items": "many"},
        "status": "wechat_verified",
        "variant_statuses": {
            "warm_route_nodes": "wechat_verified",
            "folded_stair": "wechat_verified",
            "airy_route": "wechat_candidate",
            "club_route_map": "wechat_candidate",
            "process_register": "wechat_candidate",
            "orbit_route": "wechat_candidate",
            "plain_steps": "wechat_verified",
        },
    },
    "concept_explainer": {
        "label": "概念解释",
        "primary_variant": "node_note_card",
        "primary_label": "节点说明卡",
        "fallback_variant": "plain_definition",
        "fallback_label": "朴素定义",
        "system_variants": {
            "light_reading": {"value": "open_definition_note", "label": "轻盈·开放定义"},
            "warm_humanist": {"value": "note_definition", "label": "人文·折页定义"},
            "youth_campus": {"value": "notebook_term", "label": "校园·活页词条"},
            "editorial_contrast": {"value": "editorial_definition", "label": "编辑·术语切片"},
            "structured_grid": {"value": "coordinate_definition", "label": "网格·坐标定义"},
            "future_tech": {"value": "hologram_term", "label": "科技·透明定义页"},
        },
        "variant_statuses": {
            "airy_definition": "wechat_candidate",
            "notebook_term": "wechat_candidate",
            "open_definition_note": "wechat_candidate",
            "coordinate_definition": "wechat_candidate",
            "note_definition": "wechat_candidate",
            "editorial_definition": "wechat_candidate",
            "definition_register": "wechat_candidate",
            "hologram_term": "wechat_candidate",
            "node_note_card": "wechat_verified",
            "plain_definition": "wechat_verified",
        },
        "required_bindings": {"title": "one", "definition": "one"},
        "status": "wechat_verified",
    },
    "case_card": {
        "label": "案例卡片",
        "primary_variant": "story_file",
        "primary_label": "故事档案",
        "fallback_variant": "plain_case",
        "fallback_label": "朴素案例",
        "system_variants": {
            "youth_campus": {"value": "polaroid_story", "label": "校园·相册故事页"},
            "future_tech": {"value": "prototype_file", "label": "科技·原型档案"},
        },
        "variant_statuses": {
            "polaroid_story": "wechat_candidate",
            "prototype_file": "wechat_candidate",
            "plain_case": "wechat_verified",
        },
        "required_bindings": {"title": "one", "body": "one"},
        "status": "wechat_candidate",
    },
    "warning_note": {
        "label": "风险提示",
        "primary_variant": "risk_tape",
        "primary_label": "警示胶带",
        "fallback_variant": "plain_warning",
        "fallback_label": "朴素提示",
        "system_variants": {
            "light_reading": {"value": "corner_flag", "label": "轻盈·折角提醒"},
            "warm_humanist": {"value": "taped_caution", "label": "人文·书签提醒"},
            "youth_campus": {"value": "sticky_alert", "label": "校园·便签提醒"},
            "editorial_contrast": {"value": "margin_caution", "label": "编辑·红线警示"},
            "structured_grid": {"value": "risk_flag", "label": "网格·风险旗标"},
            "future_tech": {"value": "anomaly_alert", "label": "科技·异常扫描条"},
        },
        "variant_statuses": {
            "soft_caution": "wechat_candidate",
            "sticky_alert": "wechat_candidate",
            "corner_flag": "wechat_candidate",
            "risk_flag": "wechat_candidate",
            "taped_caution": "wechat_candidate",
            "margin_caution": "wechat_candidate",
            "risk_register": "wechat_candidate",
            "anomaly_alert": "wechat_candidate",
            "risk_tape": "wechat_candidate",
            "plain_warning": "wechat_verified",
        },
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
            "light_reading": {"value": "leaf_check_path", "label": "轻盈·叶脉清单"},
            "warm_humanist": {"value": "field_checklist", "label": "人文·缝线行动页"},
            "youth_campus": {"value": "punch_card_list", "label": "校园·打卡票据"},
            "editorial_contrast": {"value": "proofing_checklist", "label": "编辑·校样标记"},
            "structured_grid": {"value": "audit_track", "label": "网格·审计轨道"},
            "future_tech": {"value": "mission_nodes", "label": "科技·实验任务单"},
        },
        "required_bindings": {"items": "many"},
        "status": "wechat_candidate",
        "variant_statuses": {
            "leaf_check_path": "wechat_candidate",
            "soft_tick_list": "wechat_candidate",
            "punch_card_list": "wechat_candidate",
            "audit_track": "wechat_candidate",
            "audit_matrix": "wechat_candidate",
            "mission_nodes": "wechat_candidate",
        },
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
            "youth_campus": {"value": "campus_dialogue", "label": "校园·同伴问答"},
            "editorial_contrast": {"value": "editorial_qa", "label": "编辑·问答专栏"},
            "structured_grid": {"value": "qa_register", "label": "网格·问答登记"},
            "future_tech": {"value": "console_dialogue", "label": "科技·现场问答记录"},
        },
        "variant_statuses": {
            "conversation_bubble": "wechat_candidate",
            "advice_letter": "wechat_candidate",
            "campus_dialogue": "wechat_candidate",
            "editorial_qa": "wechat_candidate",
            "qa_register": "wechat_candidate",
            "console_dialogue": "wechat_candidate",
            "plain_qa": "wechat_verified",
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
        "system_variants": {
            "light_reading": {"value": "orbit_comparison", "label": "轻盈·环流对照"},
            "warm_humanist": {"value": "postcard_split", "label": "人文·相册对页"},
            "youth_campus": {"value": "debate_cards", "label": "校园·辩题对页"},
            "editorial_contrast": {"value": "editorial_split", "label": "编辑·对开版面"},
            "structured_grid": {"value": "split_ledger", "label": "网格·错位账页"},
            "future_tech": {"value": "dual_channel", "label": "科技·双页对照"},
        },
        "variant_statuses": {
            "soft_split": "wechat_candidate",
            "debate_cards": "wechat_candidate",
            "orbit_comparison": "wechat_candidate",
            "split_ledger": "wechat_candidate",
            "postcard_split": "wechat_candidate",
            "editorial_split": "wechat_candidate",
            "comparison_register": "wechat_candidate",
            "dual_channel": "wechat_candidate",
            "split_comparison": "wechat_candidate",
            "plain_comparison": "wechat_verified",
        },
        "required_bindings": {"left": "one", "right": "one"},
        "status": "wechat_candidate",
    },
    "section_summary": {
        "label": "阶段小结",
        "primary_variant": "chapter_takeaway",
        "primary_label": "章节收束卡",
        "fallback_variant": "plain_summary",
        "fallback_label": "朴素小结",
        "system_variants": {
            "light_reading": {"value": "mint_closing_field", "label": "轻盈·薄荷收束场"},
            "warm_humanist": {"value": "letter_takeaway", "label": "人文·落款收束"},
            "youth_campus": {"value": "noticeboard_takeaway", "label": "校园·公告栏小结"},
            "editorial_contrast": {"value": "editorial_takeaway", "label": "编辑·末版摘要"},
            "structured_grid": {"value": "executive_strip", "label": "网格·执行摘要条"},
            "future_tech": {"value": "signal_core", "label": "科技·研究结论页"},
        },
        "variant_statuses": {
            "airy_takeaway": "wechat_candidate",
            "noticeboard_takeaway": "wechat_candidate",
            "mint_closing_field": "wechat_candidate",
            "executive_strip": "wechat_candidate",
            "letter_takeaway": "wechat_candidate",
            "editorial_takeaway": "wechat_candidate",
            "summary_register": "wechat_candidate",
            "signal_core": "wechat_candidate",
            "chapter_takeaway": "wechat_candidate",
            "plain_summary": "wechat_verified",
        },
        "required_bindings": {"items": "many"},
        "status": "wechat_candidate",
    },
}

# New themes register their own deterministic morphology without adding more
# component-specific conditionals to this catalog. The renderer resolves these
# names through theme_extensions.py, while legacy themes keep their reviewed
# variants untouched.
for _component_type, _definition in COMPONENT_CATALOG.items():
    _system_variants = _definition.setdefault("system_variants", {})
    _variant_statuses = _definition.setdefault("variant_statuses", {})
    for _theme_id in EXTENDED_THEME_IDS:
        _variant = extended_variant_name(_theme_id, _component_type)
        _system_variants[_theme_id] = {
            "value": _variant,
            "label": extended_component_label(_theme_id, _component_type),
        }
        _variant_statuses[_variant] = "candidate_theme_lab"


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
                "marker": "Z",
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
