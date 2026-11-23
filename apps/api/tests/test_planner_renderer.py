import copy
import re
from pathlib import Path

import pytest

from visual_director.component_catalog import (
    AUTO_RECOMMENDABLE_VISUAL_SYSTEMS,
    COMPONENT_CATALOG,
    CORE_THEME_COMPONENTS,
    LEGACY_VISUAL_SYSTEM_ORDER,
    VISUAL_SYSTEM_ORDER,
    VISUAL_SYSTEM_MARKERS,
    component_options,
)
from visual_director.brief_compiler import (
    apply_visual_system,
    recommend_visual_system,
    visual_system_configuration,
    visual_system_variant,
)
from visual_director.components import render_component
from visual_director.delivery import build_clipboard_payload
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans, structural_difference_count
from visual_director.plan_schema import validate_plan_for_article
from visual_director.renderer import preserve_wechat_decorative_nodes, render_preview
from visual_director.theme_gallery import build_theme_gallery
from visual_director.theme_packs import bundled_theme_acceptance
from visual_director.theme_assets import referenced_theme_assets, theme_asset_metadata


ROOT = Path(__file__).resolve().parents[3]


def test_two_plans_are_structurally_different_and_safe() -> None:
    assert all(component["status"] in {"wechat_verified", "wechat_candidate"} for component in COMPONENT_CATALOG.values())
    article = parse_markdown(
        """# 志愿填报五步检查

先核对事实，再完成排序。

## 核对位次

1. 保存成绩
2. 查看一分一段表

> 位次比裸分更适合跨年比较。
"""
    )
    plans = generate_plans(article, "tutorial_steps", 5)
    assert len(plans) == 2
    assert structural_difference_count(plans) >= 2
    documents = [render_preview(article, plan) for plan in plans]
    assert documents[0] != documents[1]
    assert all("<script" not in document.lower() for document in documents)
    assert all("/api/v1/brand-assets/current/content" not in document for document in documents)
    assert all("志愿填报五步检查" in document for document in documents)


def test_visual_plan_v05_limits_component_and_image_density_and_is_deterministic() -> None:
    article = parse_markdown(
        """# AI 学习方式观察

## AI 学校与传统学校有什么不同？

先从学习目标看差异。

## 系统观念学习法的核心概念

系统观念学习法本质上是从目标倒推知识，并在行动中建立连接。

> 一个平台会根据注意力状态和掌握程度动态调整学习内容。

## 改革前后变化

- 过去先学习分散知识，再寻找用途；
- 现在先确定作品，再主动寻找知识。

## 三步行动路径

1. 先确定一个想完成的作品；
2. 倒推作品需要的能力；
3. 在行动中主动学习。

## 三个观察

- 学习时间更集中；
- 项目时间更完整；
- 教师角色更像教练。
"""
    )
    plans = generate_plans(article, "viewpoint_trend", 5)
    assert plans[0]["component_diagnostics"]["eligible_candidate_count"] >= len(plans[0]["slots"])
    assert plans[0]["component_diagnostics"]["selected_component_count"] == len(plans[0]["slots"])
    component_types = {
        slot["component_type"]
        for plan in plans
        for slot in plan["slots"]
    }
    assert component_types.issubset(set(COMPONENT_CATALOG))
    assert len(plans[0]["slots"]) <= 4
    assert len(plans[1]["slots"]) <= 3
    assert all(plan["schema_version"] == "visual_plan.v0.5" for plan in plans)
    assert all(plan["component_library_version"] == "wechat_components.v0.13.0" for plan in plans)
    assert all(0 <= len(plan["image_slots"]) <= 3 for plan in plans)
    assert plans[0]["image_slots"]
    assert all(slot["required"] is False for plan in plans for slot in plan["image_slots"])
    assert all(slot["purpose"] in {"atmosphere", "structured_infographic"} for plan in plans for slot in plan["image_slots"])
    assert all("provider_prompt" not in slot for plan in plans for slot in plan["image_slots"])
    first = render_preview(article, plans[0])
    second = render_preview(article, plans[0])
    assert first == second
    assert "<table" not in first
    assert "IMAGE PLAN" in first
    root_tag = first.split("<main", 1)[1].split(">", 1)[0]
    assert "background-color" not in root_tag
    assert "box-shadow" not in root_tag
    assert "padding:0 0 34px" in root_tag
    assert 'data-content-role="article-metadata-preview"' in first
    assert first.index('data-content-role="article-metadata-preview"') < first.index("<main")


def test_source_placeholder_images_do_not_leak_into_preview() -> None:
    article = parse_markdown(
        """# 图片引用试点

![随机占位图](https://picsum.photos/800/400?random=9)

## 三步路径

1. 明确目标
2. 核对信息
3. 形成行动
"""
    )
    plan = generate_plans(article, "tutorial_steps", 5)[0]
    document = render_preview(article, plan)
    assert "picsum.photos" not in document
    assert "![随机占位图]" not in document


def test_heading_hierarchy_suppresses_body_h1_and_numbers_only_h2_without_ordinal() -> None:
    article = parse_markdown(
        """---
title: Frontmatter 主标题
---
# 正文里的另一版主标题

## PART 01｜已有编号章节

### 章节内小标题

正文。

## 没有编号的总结章节

#### 更细一级提示
"""
    )
    plan = copy.deepcopy(generate_plans(article, "viewpoint_trend", 5)[0])
    plan["slots"] = []
    plan["image_slots"] = []
    document = render_preview(article, plan)

    assert "正文里的另一版主标题" not in document
    assert 'data-heading-level="2" data-auto-numbered="false"' in document
    assert 'data-heading-level="2" data-auto-numbered="true"' in document
    assert 'data-heading-level="3" data-auto-numbered="false"' in document
    assert 'data-heading-level="4" data-auto-numbered="false"' in document
    assert 'class="heading-number"' not in document
    assert "SECTION 02" in document


def test_short_scene_setter_is_not_a_conclusion_and_sources_stay_subordinate() -> None:
    article = parse_markdown(
        """# 七月录取问答

7月来了。

志愿已经提交，录取结果还没出，家长正在等待。

今天我们不罗列新闻，而是直接回答家长最关心的五个问题，并告诉你接下来应该做什么。

## 第一个问题

正文答案。

> 📊 **数据来源：** 浙江省教育考试院官方日程
"""
    )
    plan = copy.deepcopy(generate_plans(article, "viewpoint_trend", 5)[0])
    plan["slots"] = []
    plan["image_slots"] = []
    document = render_preview(article, plan)

    assert 'data-lead-kind="本文导读"' in document
    assert "先看结论" not in document
    assert 'data-content-role="source"' in document
    assert "font-size:12px" in document
    assert "<blockquote" not in document
    source_id = next(block.id for block in article.blocks if block.type == "source")
    generated = generate_plans(article, "viewpoint_trend", 5)
    assert all(
        source_id not in slot["consume_block_ids"]
        for candidate in generated
        for slot in candidate["slots"]
    )


def test_acceptance_samples_plan_five_to_seven_images_with_both_purposes() -> None:
    samples = [
        ("visual-contrast/01-volunteer-decision.md", "data_policy"),
        ("visual-contrast/02-goal-backcasting.md", "lively_growth"),
        ("structured/02-recent-ai-school.component-fixture.md", "viewpoint_trend"),
    ]
    selected_slots = []
    per_sample_counts = []
    for filename, article_type in samples:
        markdown = (ROOT / "samples" / "evaluation" / filename).read_text(encoding="utf-8")
        plans = generate_plans(parse_markdown(markdown), article_type, 5)
        selected = next(plan for plan in plans if plan["recommendation"] == "recommended")
        selected_slots.extend(selected["image_slots"])
        per_sample_counts.append(len(selected["image_slots"]))

    purposes = [slot["purpose"] for slot in selected_slots]
    assert per_sample_counts == [2, 2, 2]
    assert 5 <= len(selected_slots) <= 7
    assert purposes.count("atmosphere") >= 2
    assert purposes.count("structured_infographic") >= 2
    assert all(
        slot["fact_bindings"]["item_refs"] == []
        and slot["fact_bindings"]["title_ref"] is None
        for slot in selected_slots
        if slot["purpose"] == "atmosphere"
    )


def test_second_primary_variants_are_exposed_and_render_without_layout_tables() -> None:
    article = parse_markdown(
        """# 第二变体兼容检查

> 志愿表不是一次凭感觉排序，而是一组需要逐项验证的决策。

## 三步行动路径

1. 保存官方成绩截图
2. 核对准确位次
3. 检查专业限制
4. 提交前再次复核
"""
    )
    plans = generate_plans(article, "tutorial_steps", 5)
    target_variants = {
        "numbered_insight": "magazine_index",
        "evidence_callout": "editorial_margin_quote",
        "logic_path": "folded_stair",
    }
    rendered = []
    for component_type, candidate_variant in target_variants.items():
        options = component_options(component_type)
        assert [option["marker"] for option in options] == [
            *(VISUAL_SYSTEM_MARKERS[system] for system in LEGACY_VISUAL_SYSTEM_ORDER),
            "Z",
        ]
        candidate = next(option for option in options if option["value"] == candidate_variant)
        assert candidate["status"] == "wechat_verified"
        bindings = {
            "numbered_insight": {"items": [f"block-004:item:{index}" for index in range(4)]},
            "evidence_callout": {"evidence": "block-002"},
            "logic_path": {"items": [f"block-004:item:{index}" for index in range(4)]},
        }[component_type]
        rendered.append(render_component({"component_type": component_type, "variant": candidate_variant, "content_bindings": bindings}, article))
    assert all("<table" not in document.lower() for document in rendered)
    assert all("EDITOR'S NOTE" not in document for document in rendered)
    assert all("BACKCASTING" not in document for document in rendered)
    assert all("从终点出发" not in document for document in rendered)
    assert all("核对信息，再做决定" not in document for document in rendered)


def test_first_batch_components_have_distinct_system_morphologies() -> None:
    article = parse_markdown(
        """# 四系统组件测试

### AI 私塾和传统学校有什么不同？

两者在学习节奏、目标和反馈方式上存在明显差异。

> 志愿表不是一次凭感觉排序，而是一组需要逐项验证的决策。

## 四步行动路径

1. 保存官方成绩截图
2. 核对准确位次
3. 检查专业限制
4. 提交前再次复核
"""
    )
    question = next(block for block in article.blocks if block.type == "heading" and block.level == 3)
    answer = next(block for block in article.blocks if block.type == "paragraph")
    evidence = next(block for block in article.blocks if block.type == "quote")
    steps = next(block for block in article.blocks if block.type == "ordered_list")
    refs = [f"{steps.id}:item:{index}" for index in range(len(steps.content))]
    bindings = {
        "question_hook": {"title": question.id},
        "numbered_insight": {"items": refs},
        "evidence_callout": {"evidence": evidence.id},
        "logic_path": {"items": refs},
        "faq_card": {"question": question.id, "answer": answer.id},
        "action_checklist": {"items": refs},
    }
    systems = LEGACY_VISUAL_SYSTEM_ORDER

    for component_type, content_bindings in bindings.items():
        variants = [visual_system_variant(component_type, system) for system in systems]
        assert len(set(variants)) == len(systems)
        options = component_options(component_type)
        assert [option["marker"] for option in options] == [
            *(VISUAL_SYSTEM_MARKERS[system] for system in systems),
            "Z",
        ]
        assert [option["value"] for option in options[:len(systems)]] == variants
        documents = [
            render_component(
                {
                    "component_type": component_type,
                    "variant": variant,
                    "content_bindings": content_bindings,
                },
                article,
            )
            for variant in variants
        ]
        assert len(set(documents)) == len(systems)
        assert all("<table" not in document.lower() for document in documents)
        assert all("display:flex" not in document.lower() for document in documents)
        assert all("display:grid" not in document.lower() for document in documents)
        assert all("position:absolute" not in document.lower() for document in documents)


def test_step_heading_is_not_consumed_as_concept_explainer() -> None:
    article = parse_markdown(
        """# 五步核对

## 第三步：确认冲稳保

先检查前三项是否合理。

## 第四步：核对排序逻辑和兜底条件

检查志愿顺序，并准备兜底方案。

## 第五步：提交前复核

最后复核信息。
"""
    )
    plans = generate_plans(article, "tutorial_steps", 5)
    assert all(
        slot["component_type"] != "concept_explainer"
        for plan in plans
        for slot in plan["slots"]
    )
    document = render_preview(article, plans[0])
    assert "第四步：核对排序逻辑和兜底条件" in document
    assert "核心概念：<strong" not in document


def test_feature_heading_is_not_consumed_as_concept_explainer() -> None:
    article = parse_markdown(
        """# 产品功能

## 解决方案

### 核心功能五：安全合规内置

路线审批的核心是安全。平台内置安全合规引擎。

### 什么是合规校验

合规校验是指在提交前逐项核对政策要求。
"""
    )
    plans = generate_plans(article, "data_policy", 5)
    concept_slots = [
        slot
        for plan in plans
        for slot in plan["slots"]
        if slot["component_type"] == "concept_explainer"
    ]
    assert concept_slots
    assert all("block-003" not in slot["consume_block_ids"] for slot in concept_slots)
    assert all("block-005" in slot["consume_block_ids"] for slot in concept_slots)


def test_consecutive_concepts_render_as_one_theme_specific_glossary() -> None:
    article = parse_markdown(
        """# 新高考概念说明

## 新高考模式下的核心规则变化

### 院校专业组

新高考不再按学校加专业投档，而是按院校专业组投档，每个组有独立的选科要求和投档线。

### 等级赋分制

等级赋分制按照考生所在省份的排名比例换算成绩，用来降低不同年份卷面难度差异带来的影响。

### 选科要求与专业绑定

高校会在招生计划中明确专业组的选考科目要求，选科决定考生可以报考的专业组范围。

这一组术语之后的普通正文必须保留，不应被概念组件吞掉。
"""
    )
    plans = generate_plans(article, "data_policy", 5)
    grouped_slots = [
        slot
        for plan in plans
        for slot in plan["slots"]
        if slot["component_type"] == "concept_explainer"
        and "related_titles" in slot["content_bindings"]
    ]
    assert grouped_slots
    slot = grouped_slots[0]
    assert slot["consume_block_ids"] == [
        "block-003",
        "block-004",
        "block-005",
        "block-006",
        "block-007",
        "block-008",
    ]
    assert slot["content_bindings"]["related_titles"] == ["block-005", "block-007"]

    documents = []
    for visual_system in VISUAL_SYSTEM_ORDER:
        document = render_component(
            {
                **slot,
                "variant": visual_system_variant("concept_explainer", visual_system),
            },
            article,
                config=visual_system_configuration(visual_system),
        )
        documents.append(document)
        assert "院校专业组" in document
        assert "等级赋分制" in document
        assert "选科要求与专业绑定" in document
    assert len(set(documents)) == len(VISUAL_SYSTEM_ORDER)
    assert all("<table" not in document.lower() for document in documents)
    assert all("display:flex" not in document.lower() for document in documents)
    assert all("display:grid" not in document.lower() for document in documents)
    assert all("position:absolute" not in document.lower() for document in documents)

    preview = render_preview(article, plans[0])
    assert "这一组术语之后的普通正文必须保留" in preview


def test_plan_contract_rejects_unknown_variant_and_missing_block() -> None:
    article = parse_markdown(
        """# 三步练习

## 行动路径

1. 确定目标
2. 倒推能力
3. 开始行动
"""
    )
    plan = generate_plans(article, "tutorial_steps", 5)[0]
    assert plan["slots"]

    unknown = copy.deepcopy(plan)
    unknown["slots"][0]["variant"] = "forbidden_variant"
    with pytest.raises(ValueError, match="未知组件变体"):
        validate_plan_for_article(unknown, article)

    missing = copy.deepcopy(plan)
    missing["slots"][0]["content_bindings"] = {"items": ["block-999:item:0"]}
    with pytest.raises(ValueError, match="当前任务|内容块不存在|消费块"):
        validate_plan_for_article(missing, article)


def test_visual_plan_v05_rejects_components_that_consume_h1_or_h2() -> None:
    article = parse_markdown(
        """# 受保护标题

## 主章节不可被组件吞掉

1. 确定目标
2. 核对资料
3. 开始行动
"""
    )
    plan = generate_plans(article, "tutorial_steps", 5)[0]
    slot = plan["slots"][0]
    slot["consume_block_ids"] = ["block-002", *slot["consume_block_ids"]]
    slot["anchor_block_id"] = "block-002"
    with pytest.raises(ValueError, match="H1/H2 属于受保护结构"):
        validate_plan_for_article(plan, article)


def test_image_slot_contract_rejects_required_and_provider_fields() -> None:
    article = parse_markdown(
        """# 三步图片协议

## 行动路径

1. 确定目标
2. 倒推能力
3. 开始行动
"""
    )
    plan = generate_plans(article, "tutorial_steps", 5)[0]
    assert plan["image_slots"]

    required = copy.deepcopy(plan)
    required["image_slots"][0]["required"] = True
    with pytest.raises(ValueError, match="必须允许跳过"):
        validate_plan_for_article(required, article)

    provider_leak = copy.deepcopy(plan)
    provider_leak["image_slots"][0]["provider_prompt"] = "do not belong in VisualPlan"
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        validate_plan_for_article(provider_leak, article)


def test_visual_plan_v04_remains_readable_without_image_slots() -> None:
    article = parse_markdown(
        """# 旧任务兼容

## 三步行动

1. 选择方向
2. 核对资料
3. 提交结果
"""
    )
    legacy = copy.deepcopy(generate_plans(article, "tutorial_steps", 5)[0])
    legacy["schema_version"] = "visual_plan.v0.4"
    legacy.pop("image_slots")
    validated = validate_plan_for_article(legacy, article)
    assert validated["schema_version"] == "visual_plan.v0.4"
    assert validated["image_slots"] == []


def test_long_article_uses_semantic_components_with_plain_text_buffers() -> None:
    article = parse_markdown(
        """# 长文语义组件验收

## 第一章

### 案例：一位家长的核对过程

家长先保存官方截图，再逐项核对位次，最终发现原排序漏掉了专业限制。

这段经历说明速度不是第一目标。

真正重要的是形成可复查的依据。

### 为什么不能只看总分？

因为不同年份的分数分布不同，跨年比较时应优先核对位次和当年规则。

下面进入第二组判断。

每一步仍然要回到官方信息。

## 第二章

请注意：来源不明的内部排名存在明显风险，不要直接用于提交决策。

这条提醒之后先解释核对方法。

运营仍需保留最终人工审核。

### 提交前行动清单

1. 保存官方成绩截图
2. 核对一分一段表位次
3. 检查单科和体检限制
4. 提交前再次复核

完成清单后，再看两种方法的差异。

差异必须以原文事实为准。

### 两种判断方式对比

- 只看总分，操作快但跨年误差大
- 同时核对位次和规则，步骤更多但依据更完整

对比之后仍需回到个人目标。

不能把工具输出当成最终决定。

### 本章小结

- 先保存可追溯的官方材料
- 再核对位次、限制和顺序
- 最后由用户完成确认

文章最后保留普通正文作为收束。

这段正文不应被任何强组件消费。

还要提醒读者关注最新官方通知。

正式提交前再次人工复核。
"""
    )
    plans = generate_plans(article, "tutorial_steps", 5)
    primary = plans[0]
    semantic = {
        "case_card",
        "faq_card",
        "warning_note",
        "action_checklist",
        "comparison_card",
        "section_summary",
    }
    selected = {slot["component_type"] for slot in primary["slots"]}
    assert len(semantic.intersection(selected)) >= 5
    assert 5 <= len(primary["slots"]) <= 6
    positions = {block.id: index for index, block in enumerate(article.blocks)}
    occupied = [
        {positions[block_id] for block_id in slot["consume_block_ids"]}
        for slot in primary["slots"]
    ]
    for left, right in zip(occupied, occupied[1:], strict=False):
        assert min(right) - max(left) >= 2
    document = render_preview(article, primary)
    assert "家长先保存官方截图" in document
    assert "保存官方成绩截图" in document
    assert "CASE FILE" not in document
    assert "ACTION CHECKLIST" not in document
    assert "<table" not in document.lower()


def test_all_themes_cover_all_core_components_without_cross_theme_fallbacks() -> None:
    for component_type in CORE_THEME_COMPONENTS:
        definition = COMPONENT_CATALOG[component_type]
        system_variants = definition.get("system_variants", {})
        assert tuple(system_variants) == LEGACY_VISUAL_SYSTEM_ORDER
        variants = [
            visual_system_variant(component_type, visual_system)
            for visual_system in LEGACY_VISUAL_SYSTEM_ORDER
        ]
        assert len(set(variants)) == len(LEGACY_VISUAL_SYSTEM_ORDER)
        assert definition["fallback_variant"] not in variants


def test_editorial_comparison_uses_mobile_safe_columns() -> None:
    article = parse_markdown(
        """# 对比测试

## 两种路径

- 左侧是一段用于比较的较长中文内容
- 右侧是另一段用于比较的较长中文内容
"""
    )
    document = render_component(
        {
            "component_type": "comparison_card",
            "variant": "editorial_split",
            "content_bindings": {
                "left": "block-003:item:0",
                "right": "block-003:item:1",
            },
        },
        article,
    )
    assert "B / 对照观点" in document
    assert "COUNTERPOINT" not in document
    assert document.count("overflow-wrap:anywhere") >= 3


def test_rebuilt_theme_kits_include_rhythm_primitives_and_new_morphologies() -> None:
    themes = {item["id"]: item for item in build_theme_gallery()}
    assert {theme["status"] for theme in themes.values()} == {"theme_kit_v1_review"}
    for theme_id in VISUAL_SYSTEM_ORDER:
        theme = themes[theme_id]
        assert len(theme["rhythm_primitives"]) == 6
        assert {item["role"] for item in theme["rhythm_primitives"]} == {
            "section_heading",
            "subheading",
            "inline_emphasis",
            "image_caption",
            "divider",
            "closing_cta",
        }
        assert all(
            item["production_status"] == "production"
            and item["production_trigger"]
            for item in theme["rhythm_primitives"]
        )
        assert len(theme["components"]) == 12
        assert len({component["component_type"] for component in theme["components"]}) == 12
        assert len({component["variant"] for component in theme["components"]}) == 12
        assert theme["semantic_component_count"] == 12
        assert all(component["purpose"] and component["use_when"] for component in theme["components"])
    for theme_id in ("light_reading", "structured_grid"):
        theme = themes[theme_id]
        assert all(component["variant"] not in {
            "gradient_guide_label",
            "orbit_outline",
            "airy_before_after",
            "airy_definition",
            "soft_caution",
            "soft_tick_list",
            "soft_split",
            "airy_takeaway",
            "coordinate_index",
            "evidence_register",
            "change_register",
            "definition_register",
            "risk_register",
            "audit_matrix",
            "comparison_register",
            "summary_register",
        } for component in theme["components"])


def test_candidate_themes_have_distinct_reading_grammars_and_recommendation_gate() -> None:
    themes = {item["id"]: item for item in build_theme_gallery()}
    markers = {
        "oriental_archive": "bound-folio",
        "vintage_press": "clipping-stack",
        "natural_atlas": "field-log",
        "business_review": "signal-orbit",
        "cinematic_story": "storyboard-track",
    }
    for theme_id, marker in markers.items():
        assert marker in themes[theme_id]["full_preview_html"]


def test_theme_gallery_titles_keep_each_theme_hero_grammar() -> None:
    themes = {item["id"]: item for item in build_theme_gallery()}
    assert "AIRY READING" in themes["light_reading"]["full_preview_html"]
    assert "GRID<br>INDEX 01" in themes["structured_grid"]["full_preview_html"]
    expected_grammars = {
        "oriental_archive": "bound-folio-cover",
        "vintage_press": "front-page",
        "pop_poster": "poster-wall",
        "natural_atlas": "field-notebook-cover",
        "business_review": "market-pictorial-cover",
        "cinematic_story": "festival-program-cover",
    }
    for theme_id, grammar in expected_grammars.items():
        assert f'data-theme-grammar="{grammar}"' in themes[theme_id]["full_preview_html"]


def test_reader_facing_titles_do_not_leak_theme_notes_or_internal_versions() -> None:
    themes = {item["id"]: item for item in build_theme_gallery()}
    article = parse_markdown("# 把复杂选择变成一条清晰的行动路线\n\n正文内容。")
    base_plan = generate_plans(article, "viewpoint_trend", 5)[0]

    for theme_id, theme in themes.items():
        gallery_document = theme["full_preview_html"]
        assert "主题统一的是" not in gallery_document, theme_id
        assert "wechat_components" not in gallery_document, theme_id
        assert "组件库" not in gallery_document, theme_id

        plan = copy.deepcopy(base_plan)
        plan["visual_system"] = theme_id
        plan["configuration"] = visual_system_configuration(theme_id)
        article_document = render_preview(article, plan)
        assert "wechat_components" not in article_document, theme_id
        assert "组件库" not in article_document, theme_id


def test_candidate_theme_stickers_are_first_party_publication_assets() -> None:
    themes = {item["id"]: item for item in build_theme_gallery()}
    expected = {
        "oriental-branch.png",
        "press-tape.png",
        "pop-star.png",
        "atlas-leaf.png",
        "business-orbit.png",
        "cinema-clapper.png",
        "cinema-reel.png",
    }
    discovered: set[str] = set()
    for theme_id in {
        "oriental_archive",
        "vintage_press",
        "pop_poster",
        "natural_atlas",
        "business_review",
        "cinematic_story",
    }:
        discovered.update(name for _, name in referenced_theme_assets(themes[theme_id]["full_preview_html"]))
    assert expected <= discovered
    assert all(theme_asset_metadata(ROOT, name) is not None for name in discovered)


def test_stickers_overlay_components_without_creating_blank_flow_space() -> None:
    themes = {item["id"]: item for item in build_theme_gallery()}
    for theme_id in {
        "oriental_archive",
        "vintage_press",
        "pop_poster",
        "natural_atlas",
        "business_review",
        "cinematic_story",
    }:
        document = themes[theme_id]["full_preview_html"]
        assert 'data-decoration-layer="overlay" style="height:0;' in document
        assert 'data-theme-decoration=' in document

    business = themes["business_review"]["full_preview_html"]
    assert 'data-theme-decoration="business-diagram"' not in business
    assert 'width:75%;vertical-align:top' not in business


def test_cinematic_story_uses_distinct_film_narrative_grammar() -> None:
    document = {item["id"]: item for item in build_theme_gallery()}["cinematic_story"]["full_preview_html"]
    for marker in {
        "opening-credit",
        "storyboard-track",
        "screenplay-cue",
        "subtitle-cue",
        "shot-reverse-shot",
        "ticket-perforation",
    }:
        assert marker in document
    assert "border-top:18px solid" not in document
    assert "border-bottom:18px solid" not in document
    recent = [
        {"visual_system": theme_id}
        for theme_id in AUTO_RECOMMENDABLE_VISUAL_SYSTEMS
    ]
    selected, _, _ = recommend_visual_system(
        "viewpoint_trend",
        recent,
        history_window=len(recent),
        article_features={"paragraph_count": 12, "quote_count": 2},
    )
    assert selected in AUTO_RECOMMENDABLE_VISUAL_SYSTEMS
    assert selected not in {
        "oriental_archive",
        "vintage_press",
        "natural_atlas",
        "business_review",
        "cinematic_story",
    }


def test_reference_lists_remain_subdued_metadata_in_cinematic_theme() -> None:
    article = parse_markdown(
        """# 专业调整观察

高校专业调整需要结合具体培养条件判断。

## 可靠来源

- [教育部：本科专业目录](https://www.moe.gov.cn/example)
- [高校：专业培养方案](https://www.example.edu.cn/plan)
"""
    )
    plan = generate_plans(article, "data_policy", 5)[0]
    plan["visual_system"] = "cinematic_story"
    plan["configuration"] = visual_system_configuration("cinematic_story")
    document = render_preview(article, plan)
    assert 'data-content-role="reference-list"' in document
    assert "教育部：本科专业目录" in document
    assert "www.moe.gov.cn" in document
    assert "SHOT LIST / 行动清单" not in document
    assert 'data-theme-grammar="storyboard-track"' not in document


def test_case_detail_lists_keep_case_semantics_across_all_themes() -> None:
    article = parse_markdown(
        """# 同名专业观察

## 同一个专业名，为什么可能通向不同方向

### “低空技术与工程”就是一个现实样本

北航和北邮的官方介绍呈现出清晰差异。

- 北航依托航空宇航学科，强调飞行器全链条和系统工程能力。
- 北邮依托信息通信学科，强调通信网络与信息基础设施能力。
"""
    )
    plan = generate_plans(article, "data_policy", 5)[0]

    for theme_id in {
        "light_reading",
        "warm_humanities",
        "editorial_contrast",
        "structured_analysis",
        "youth_campus",
        "future_tech",
        "oriental_archive",
        "vintage_press",
        "pop_poster",
        "natural_atlas",
        "business_review",
        "cinematic_story",
    }:
        themed_plan = copy.deepcopy(plan)
        themed_plan["visual_system"] = theme_id
        themed_plan["configuration"] = visual_system_configuration(theme_id)
        document = render_preview(article, themed_plan)
        assert "行动清单" not in document
        assert "CHK" not in document
        assert "✓" not in document

        if theme_id in {
            "oriental_archive",
            "vintage_press",
            "pop_poster",
            "natural_atlas",
            "business_review",
            "cinematic_story",
        }:
            assert 'data-list-role="case_points"' in document, theme_id
            assert ("案例差异" in document) == (theme_id != "oriental_archive"), theme_id

    cinematic_plan = copy.deepcopy(plan)
    cinematic_plan["visual_system"] = "cinematic_story"
    cinematic_plan["configuration"] = visual_system_configuration("cinematic_story")
    cinematic = render_preview(article, cinematic_plan)
    assert "CASE NOTES / 案例差异" in cinematic
    assert "SHOT LIST / 行动清单" not in cinematic


def test_new_themes_use_distinct_composition_grammars_not_recolors() -> None:
    themes = {item["id"]: item for item in build_theme_gallery()}
    campus = themes["youth_campus"]
    future = themes["future_tech"]
    editorial = themes["editorial_contrast"]

    assert campus["english"] == "CAMPUS BULLETIN"
    assert future["english"] == "FUTURE EDITION"
    assert campus["configuration"]["palette"] != future["configuration"]["palette"]
    assert {
        component["variant"] for component in campus["components"]
    }.isdisjoint({
        component["variant"] for component in future["components"]
    })
    assert {
        component["variant"] for component in future["components"]
    }.isdisjoint({
        component["variant"] for component in editorial["components"]
    })
    assert "COURSE TICKETS" in campus["full_preview_html"]
    assert "NOTICEBOARD" in campus["full_preview_html"]
    assert "FUTURE EDITION" in future["full_preview_html"]
    assert "要点回收" not in future["full_preview_html"]
    assert "关键要点" not in future["full_preview_html"]
    assert "证据摘录" not in future["full_preview_html"]
    assert 'data-theme-grammar="signal-extract"' in future["full_preview_html"]
    assert 'data-theme-grammar="signal-junction"' in future["full_preview_html"]
    assert "FIELD INDEX" not in future["full_preview_html"]
    assert "MISSION LOG" not in future["full_preview_html"]
    assert "border-top:11px solid" not in future["full_preview_html"]


@pytest.mark.parametrize(
    ("theme_id", "heading_grammar", "quote_grammar", "extract_grammar", "auto_marker", "pair_labels"),
    [
        ("future_tech", "signal-junction", "signal-quotation", "signal-extract", "02", ("变化前", "变化后")),
        ("oriental_archive", "folio-heading", "folio-quotation", "margin-annotation", "卷 02", ("前", "后")),
    ],
)
def test_technology_and_folio_themes_use_structural_cues_instead_of_fixed_copy(
    theme_id, heading_grammar, quote_grammar, extract_grammar, auto_marker, pair_labels,
) -> None:
    article = parse_markdown(
        "# 测试文章\n\n本文从两个章节的阅读关系入手，讲清楚标题层级、正文重点和原文引语各自如何发挥作用。\n\n"
        "## 一、已写章节序号\n\n> 来自原稿的普通引语。\n\n"
        "## 未编号的章节\n\n测试段落，只说明原作者想说的内容。\n"
    )
    plan = generate_plans(article, "data_policy", 5)[0]
    plan["visual_system"] = theme_id
    plan["configuration"] = visual_system_configuration(theme_id)
    plan["slots"] = []
    rendered = render_preview(article, plan)
    assert rendered.count(f'data-theme-grammar="{heading_grammar}"') == 2
    assert "一、已写章节序号" in rendered
    assert "专题" not in rendered
    assert ">卷 01<" not in rendered
    assert f">{auto_marker}<" in rendered
    assert f'data-theme-grammar="{quote_grammar}"' in rendered
    assert "来自原稿的普通引语。" in rendered
    assert "证据摘录" not in rendered
    assert 'data-lead-kind="本文导读"' in rendered
    assert ">本文导读<" not in rendered

    theme = build_theme_gallery(theme_id=theme_id)[0]
    components = {item["component_type"]: item["html"] for item in theme["components"]}
    assert f'data-theme-grammar="{extract_grammar}"' in components["evidence_callout"]
    fixed_captions = ("证据摘录", "案例观察", "案例切片", "进程路径", "关键问题", "开篇提问", "要点回收", "观点索引", "风险提示")
    visible_copy = " ".join(re.sub(r"<[^>]*>", "", part) for part in components.values())
    assert not any(caption in visible_copy for caption in fixed_captions)
    assert all(f">{label}<" in components["before_after_timeline"] for label in pair_labels)
    assert ">01<" not in components["action_checklist"]


def test_future_evidence_capture_keeps_editable_text_in_clipboard() -> None:
    parsed = parse_markdown("# 试样\n\n先核对 **原始结果**，再说明变化的边界。")
    evidence = next(block for block in parsed.blocks if block.type == "paragraph")
    config = visual_system_configuration("future_tech")
    markup = render_component(
        {
            "component_type": "evidence_callout",
            "variant": visual_system_variant("evidence_callout", "future_tech"),
            "content_bindings": {"evidence": evidence.id},
        },
        parsed, config["palette"], config,
    )
    payload = build_clipboard_payload(
        {
            "frozen_html": preserve_wechat_decorative_nodes(f"<main>{markup}</main>"),
            "metadata": {"title": parsed.title},
        },
        [],
        lambda _: "",
    )
    assert 'data-theme-decoration="capture-trace"' in payload["html"]
    assert "<strong>原始结果</strong>" in payload["html"]
    assert payload["text"] == "先核对 原始结果，再说明变化的边界。"
    assert payload["image_count"] == 0


def test_folio_caution_keeps_original_copy_separate_from_the_seal() -> None:
    parsed = parse_markdown("# 试样\n\n请保留 **原始记录**，只在核实之后再改动。")
    note = next(block for block in parsed.blocks if block.type == "paragraph")
    variant = visual_system_variant("warning_note", "oriental_archive")
    slot = {"component_type": "warning_note", "variant": variant, "content_bindings": {"body": note.id}}
    config = visual_system_configuration("oriental_archive")
    markup = render_component(slot, parsed, config["palette"], config)
    assert 'data-theme-static="true" data-theme-decoration="caution-seal"' in markup
    assert ">留意</span>" in markup and "风险提示" not in markup
    assert 'caution-paper-fold' in markup
    assert ">请保留 <strong>原始记录</strong>，只在核实之后再改动。</p>" in markup
    assert "caution-seal" not in render_component(slot, parsed, config["palette"], {"theme_id": "other"})


def test_folio_list_tints_distinguish_grouped_notes_from_a_sequence_and_plain_lists() -> None:
    parsed = parse_markdown("# 试样\n\n- 先检查 **原稿**\n- 再核对来源")
    block = next(block for block in parsed.blocks if block.type == "unordered_list")
    items = [f"{block.id}:item:{i}" for i in range(2)]
    config = visual_system_configuration("oriental_archive")
    colors = config["palette"]

    for role, tint, whole_group in (
        ("action_checklist", colors["surface"], True),
        ("section_summary", colors["pale"], True),
        ("logic_path", colors["secondary_pale"], False),
        ("numbered_insight", None, False),
    ):
        slot = {
            "component_type": role,
            "variant": visual_system_variant(role, "oriental_archive"),
            "content_bindings": {"items": items},
        }
        markup = render_component(slot, parsed, colors, config)
        wrapper = re.search(r'<section [^>]*data-list-role="[^"]+"[^>]*>', markup).group()
        assert ("background-color:" in wrapper) == whole_group
        if tint:
            assert f"background-color:{tint};" in (wrapper if whole_group else markup)
        assert markup.index("先检查 <strong>原稿</strong>") < markup.index("再核对来源")
        assert not any(label in markup for label in ("行动清单", "阶段小结", "逻辑路径"))
        if role == "logic_path":
            assert re.findall(r'<span data-theme-static="true"[^>]*>(\d+)</span>', markup) == ["01", "02"]


def test_renderer_does_not_inject_decorative_semantic_slogans() -> None:
    source = (ROOT / "apps" / "api" / "src" / "visual_director" / "components.py").read_text(
        encoding="utf-8"
    )
    banned_copy = {
        "从终点出发",
        "倒推今天的行动",
        "让行动自然发生",
        "核对信息，再做决定",
        "先核对依据，再确认顺序",
        "READY WHEN YOU ARE",
        "KEY POINTS",
        "CHAPTER TAKEAWAY",
        "EVIDENCE REGISTER",
    }
    assert all(copy not in source for copy in banned_copy)


def test_light_reading_h2_uses_wechat_stable_thin_border() -> None:
    article = parse_markdown(
        """# 细线兼容性测试

导语保持普通正文。

## 先看清楚标题

正文继续。
"""
    )
    plan = copy.deepcopy(generate_plans(article, "viewpoint_trend", 5)[0])
    plan["slots"] = []
    plan["image_slots"] = []
    plan = apply_visual_system(plan, "light_reading", recent_summaries=[])

    document = render_preview(article, plan)

    assert "border-top:1px solid #DDBD61" in document
    assert "height:1px;margin:10px 0 0;background-color:#DDBD61" not in document
    assert "font-size:0;line-height:0" in document


def test_wechat_verification_is_scoped_to_legacy_variants_and_tested_bundled_packs() -> None:
    gallery = build_theme_gallery()
    themes = {theme["id"]: theme for theme in gallery}

    assert set(themes) == set(VISUAL_SYSTEM_ORDER)
    for visual_system, theme in themes.items():
        assert theme["status"] == "theme_kit_v1_review"
        assert len(theme["components"]) == len(CORE_THEME_COMPONENTS) == 12
        assert all(
            COMPONENT_CATALOG[component_type]["variant_statuses"][
                visual_system_variant(component_type, visual_system)
            ]
            == "wechat_verified"
            for component_type in CORE_THEME_COMPONENTS
        )
        status = ("wechat_verified" if visual_system in LEGACY_VISUAL_SYSTEM_ORDER or bundled_theme_acceptance(visual_system)
                  else "wechat_candidate")
        for component in theme["components"]:
            revised = (visual_system, component["component_type"]) in {
                ("light_reading", "logic_path"),
                ("warm_humanist", "question_hook"),
                ("warm_humanist", "logic_path"),
                ("editorial_contrast", "logic_path"),
                *(("future_tech", role) for role in CORE_THEME_COMPONENTS if role != "before_after_timeline"),
                *(("oriental_archive", role) for role in CORE_THEME_COMPONENTS),
            }
            assert component["status"] == ("wechat_candidate" if revised else status)


def test_light_reading_logic_path_keeps_steps_and_scope() -> None:
    parsed = parse_markdown("# 路线\n\n1. 先读 **原文** & 核对事实\n2. 再检查版式")
    steps = next(block for block in parsed.blocks if block.type == "ordered_list")
    slot = {
        "component_type": "logic_path",
        "variant": visual_system_variant("logic_path", "light_reading"),
        "content_bindings": {"items": [f"{steps.id}:item:0", f"{steps.id}:item:1"]},
    }
    config = visual_system_configuration("light_reading")
    markup = render_component(slot, parsed, config["palette"], config)
    assert 'data-theme-grammar="airy-connected-route"' in markup
    assert markup.count("先读 <strong>原文</strong> &amp; 核对事实") == 1
    assert markup.index("核对事实") < markup.index("再检查版式")
    assert markup.count("border-left:1px solid " + config["palette"]["sky"]) == 2
    assert markup.count('data-theme-decoration="airy-route-sprout"') == 1
    assert markup.count("border-radius:20px 4px 20px 5px") == 1
    assert markup.count("background-color:" + config["palette"]["secondary_pale"]) == 1
    assert 'data-theme-grammar="airy-connected-route"' not in render_component(
        slot, parsed, config["palette"], {**config, "theme_kit": "user_pack:demo"},
    )


def test_editorial_contrast_logic_path_keeps_the_staircase_in_the_gutter() -> None:
    parsed = parse_markdown("# 步骤\n\n1. 读 **原稿**\n2. 检查用词\n3. 再次核对")
    steps = next(block for block in parsed.blocks if block.type == "ordered_list")
    slot = {
        "component_type": "logic_path",
        "variant": visual_system_variant("logic_path", "editorial_contrast"),
        "content_bindings": {"items": [f"{steps.id}:item:{index}" for index in range(3)]},
    }
    config = visual_system_configuration("editorial_contrast")
    markup = render_component(slot, parsed, config["palette"], config)
    assert 'data-theme-grammar="editorial-step-folio"' in markup
    assert all(f"margin:0 0 7px {inset}px" in markup for inset in (24, 12, 0))
    assert markup.count("读 <strong>原稿</strong>") == 1
    assert markup.index("原稿") < markup.index("检查用词") < markup.index("再次核对")
    assert "editorial-step-folio" not in render_component(
        slot, parsed, config["palette"], {**config, "theme_kit": "user_pack:demo"},
    )


@pytest.mark.parametrize("theme", ["editorial_contrast", "warm_humanist"])
def test_logic_path_separates_only_explicit_step_titles_from_their_details(theme: str) -> None:
    parsed = parse_markdown(
        "# 步骤\n\n"
        "1. **先记录 & 核对。**\\\n   用不同日期观察市场，保留 **原始记录**。\n"
        "2. **先看营业时间。**\n"
        "3. 这句话虽然很长，但原文没有步骤小标题，不应该擅自从中拆出一个标题。\n"
        "4. **先核对** 单价和数量，再决定怎么整理结果。\n"
        "5. **不用先删掉重复照片。** 先复制原件，再检查 **重复项**。\n"
        "6. **注意：** 请保留原件。\n"
    )
    steps = next(block for block in parsed.blocks if block.type == "ordered_list")
    slot = {
        "component_type": "logic_path",
        "variant": visual_system_variant("logic_path", theme),
        "content_bindings": {"items": [f"{steps.id}:item:{index}" for index in range(len(steps.content))]},
    }
    config = visual_system_configuration(theme)
    markup = render_component(slot, parsed, config["palette"], config, visual_system=theme)
    detail_style = 'style="display:block;padding-top:2px;font-weight:400;"'
    formatted = (
        f'<strong style="font-weight:750;">先记录 &amp; 核对。</strong>\n'
        f'<span {detail_style}>用不同日期观察市场，保留 <strong>原始记录</strong>。</span>'
    )
    assert markup.count(detail_style) == 1
    assert formatted in markup
    assert "<strong>先看营业时间。</strong></p>" in markup
    assert f">{steps.content[2]}</p>" in markup
    assert "<strong>先核对</strong> 单价和数量，再决定怎么整理结果。" in markup
    assert "<strong>不用先删掉重复照片。</strong> 先复制原件，再检查 <strong>重复项</strong>。" in markup
    assert "<strong>注意：</strong> 请保留原件。" in markup
    payload = build_clipboard_payload({"frozen_html": f"<main>{markup}</main>", "metadata": {"title": parsed.title}}, [], lambda _: "")
    assert formatted in payload["html"]
    assert "先记录 & 核对。 用不同日期观察市场，保留 原始记录。" in " ".join(payload["text"].split())
    assert detail_style not in render_component(
        slot, parsed, config["palette"], {**config, "theme_kit": "user_pack:demo"}, visual_system="demo"
    )


def test_warm_humanist_revised_components_keep_content_and_scope() -> None:
    from visual_director.renderer import _render_fixed_footer

    config = visual_system_configuration("warm_humanist")
    other = {**config, "theme_kit": "user_pack:demo"}
    parsed = parse_markdown("# 手记\n\n## 要先读 **原文** 吗？\n\n1. 先观察\n2. 再记录")
    heading = next(block for block in parsed.blocks if block.type == "heading" and block.level == 2)
    steps = next(block for block in parsed.blocks if block.type == "ordered_list")
    for role, grammar, binding, expected in (
        ("question_hook", "warm-margin-question", {"title": heading.id}, "要先读 <strong>原文</strong> 吗？"),
        ("logic_path", "warm-stitched-notebook", {"items": [f"{steps.id}:item:0", f"{steps.id}:item:1"]}, "再记录"),
    ):
        slot = {"component_type": role, "variant": visual_system_variant(role, "warm_humanist"), "content_bindings": binding}
        markup = render_component(slot, parsed, config["palette"], config)
        assert grammar in markup and markup.count(expected) == 1
        assert grammar not in render_component(slot, parsed, other["palette"], other)
        if role == "logic_path":
            assert markup.index("先观察") < markup.index("再记录")

    footer = {"enabled": True, "text": "末尾 & 致谢", "asset_path": "asset.png", "alt_text": "品牌图"}
    markup = _render_fixed_footer(footer, config)
    assert 'data-theme-grammar="warm-letter-signoff"' in markup
    assert "末尾 &amp; 致谢" in markup
    assert 'src="/api/v1/brand-assets/current/content" alt="品牌图"' in markup
    assert "warm-letter-signoff" not in _render_fixed_footer(footer, other)
    assert _render_fixed_footer({**footer, "enabled": False}, config) == ""


def test_youth_campus_question_hook_uses_wechat_stable_rule() -> None:
    article = parse_markdown(
        """# 青春校园兼容测试

### 为什么有人需要一间不必消费太多的共享书房？
"""
    )
    question = next(
        block
        for block in article.blocks
        if block.type == "heading" and block.level == 3
    )

    document = render_component(
        {
            "component_type": "question_hook",
            "variant": "campus_notice_prompt",
            "content_bindings": {"title": question.id},
        },
        article,
    )

    assert "border-top:1px solid #58B9E4" in document
    assert "border-top:4px solid #F06A4B" in document
    assert "height:1px;margin:14px 0 0;background-color:#58B9E4" not in document


def test_editorial_question_mark_stays_on_one_line_in_wechat() -> None:
    article = parse_markdown(
        """# 编辑对比兼容测试

### 为什么有人需要一间不必消费太多的共享书房？
"""
    )
    question = next(
        block
        for block in article.blocks
        if block.type == "heading" and block.level == 3
    )

    document = render_component(
        {
            "component_type": "question_hook",
            "variant": "editorial_deck_question",
            "content_bindings": {"title": question.id},
        },
        article,
    )

    assert "width:18%" in document
    assert "white-space:nowrap;word-break:keep-all" in document
    assert ">Q.</span>" in document
    assert "width:52px" not in document


def test_theme_kits_do_not_inject_unbound_decorative_numbers() -> None:
    source = "\n".join(
        (
            (ROOT / "apps" / "api" / "src" / "visual_director" / filename).read_text(
                encoding="utf-8"
            )
            for filename in ("components.py", "renderer.py", "theme_gallery.py")
        )
    )
    banned_markers = {
        "BASE 01",
        "SHIFT 02",
        ">00<",
        ">03<",
        "LEAD<br>00",
        "FEATURE<br>00",
        "SECTION 01",
        "图 01",
        "FIG.01",
        "00 / NEXT",
        "NEXT ACTION / 01",
    }
    assert all(marker not in source for marker in banned_markers)


def test_all_theme_rhythm_primitives_are_wired_to_production_markdown() -> None:
    article = parse_markdown(
        """# 主题节奏正式链路

真正需要记住的是**核对官方信息**，而不是机械套模板。

---

## 进入下一阶段

![志愿核对流程示意](local-flow.png)

- 保存**官方截图**
- 记录准确位次
"""
    )
    base = copy.deepcopy(generate_plans(article, "tutorial_steps", 5)[0])
    base["slots"] = []
    base["image_slots"] = []
    brand_profile = {
        "standard_kicker": "公众号 · 阅读指南",
        "editorial_kicker": "EDITORIAL",
        "fixed_footer": {
            "enabled": True,
            "text": "固定品牌行动入口",
            "alt_text": "品牌固定页尾",
            "asset_path": "assets/brand/footer.jpg",
        },
    }
    expected_frames = {
        "light_reading": "airy_organic",
        "warm_humanist": "warm_storybook",
        "youth_campus": "campus_sticker",
        "editorial_contrast": "editorial_masthead",
        "structured_grid": "structured_ledger",
        "future_tech": "future_signal",
        "oriental_archive": "extended_oriental",
        "vintage_press": "extended_press",
        "pop_poster": "extended_pop",
        "natural_atlas": "extended_atlas",
        "business_review": "extended_business",
        "cinematic_story": "extended_cinema",
    }
    rendered: dict[str, str] = {}
    for visual_system in LEGACY_VISUAL_SYSTEM_ORDER:
        plan = copy.deepcopy(base)
        plan["configuration"] = visual_system_configuration(visual_system)
        document = render_preview(article, plan, brand_profile=brand_profile)
        frame = expected_frames[visual_system]
        assert 'data-content-role="inline-emphasis"' in document
        assert 'data-content-role="thematic-break"' in document
        assert f'data-image-frame="{frame}"' in document
        assert 'data-image-caption="志愿核对流程示意"' in document
        assert 'data-content-role="brand-cta"' in document
        rendered[visual_system] = document
    assert len(set(rendered.values())) == len(LEGACY_VISUAL_SYSTEM_ORDER)
