from __future__ import annotations

import copy

import pytest

from visual_director.image_intent import (
    apply_theme_to_image_slot,
    build_art_direction_snapshot,
    build_visual_intent,
    evaluate_theme_compatibility,
    extract_display_label,
    infer_structured_layout,
    resolve_display_copy,
    strip_structural_title_prefix,
)
from visual_director.parser import parse_markdown
from visual_director.plan_schema import ArticleImageArtDirection, ImageVisualIntent, validate_plan_for_article
from visual_director.planner import generate_plans
from visual_director.visual_dna import (
    ARTICLE_THEME_MANIFESTS,
    IMAGE_STYLE_MANIFESTS,
    build_visual_signature,
    resolve_article_image_direction,
)


def test_layout_inference_uses_article_relationships() -> None:
    assert infer_structured_layout(
        "提交前核对流程",
        ["先保存官方截图", "再核对准确位次", "最后检查专业限制"],
    ) == ("linear_progression", "explain_sequence")
    assert infer_structured_layout(
        "改革前后差异",
        ["过去按学校投档", "现在按院校专业组投档"],
    ) == ("binary_comparison", "compare_options")
    assert infer_structured_layout(
        "三阶段演变",
        ["2024年启动", "2025年试点", "2026年落地"],
    ) == ("timeline", "show_evolution")
    assert infer_structured_layout(
        "三种培养选择",
        ["研究导向路径", "应用导向路径", "交叉培养路径"],
    ) == ("comparison_matrix", "compare_options")


def test_future_destination_does_not_turn_action_sequence_into_timeline() -> None:
    assert infer_structured_layout(
        "一条依次经过报考条件、培养方案和未来出口的核对路径",
        [
            "查看当年招生专业目录",
            "阅读当年招生章程与选科要求",
            "对照培养方案",
            "判断未来出口是否符合个人计划",
        ],
    ) == ("linear_progression", "explain_sequence")


def test_host_layout_suggestion_cannot_override_source_relationship() -> None:
    intent = build_visual_intent(
        purpose="structured_infographic",
        subject="提交前核对流程",
        article_type="tutorial_steps",
        title="三步核对",
        fact_anchors=["先保存官方截图", "再核对准确位次", "最后检查专业限制"],
        requested_visual_role="compare_options",
        requested_layout_family="comparison_matrix",
    )
    assert intent["visual_role"] == "explain_sequence"
    assert intent["layout_family"] == "linear_progression"
    assert intent["intent_version"] == "image_visual_intent.v3"


def test_visual_grammar_uses_exact_short_labels_and_concrete_scene() -> None:
    intent = build_visual_intent(
        purpose="structured_infographic",
        subject="专业选择前的四项核对路径",
        article_type="tutorial_steps",
        title="专业选择前先核对",
        fact_anchors=[
            "**招生专业目录**：查看学校当年实际招生专业",
            "阅读当年招生章程与选科要求，确认报考限制",
            "对照培养方案，判断课程结构是否匹配",
        ],
        style_family="soft_flat_illustration",
    )
    grammar = intent["visual_grammar"]
    assert grammar["scene_metaphor"] == "一条可行走的学习路线串起连续行动"
    assert grammar["text_mode"] == "label_only"
    assert grammar["display_labels"] == [
        "招生专业目录",
        "招生章程与选科要求",
        "培养方案",
    ]
    assert len(grammar["node_visuals"]) == 3
    assert "圆角卡片" not in grammar["connector_language"]
    title, labels = resolve_display_copy(
        intent,
        "专业选择前先核对",
        intent["fact_anchors"],
    )
    assert title == "专业选择前先核对"
    assert labels == grammar["display_labels"]
    assert grammar["content_occupancy"] == "dense_70_85"
    assert grammar["edge_treatment"] == "open_illustrated_edge"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("第二层：看懂专业选择", "看懂专业选择"),
        ("第三步｜核对成绩和位次", "核对成绩和位次"),
        ("PART 02 · 判断未来出口", "判断未来出口"),
        ("二、先完成四步改造，再考虑视觉包装", "先完成四步改造，再考虑视觉包装"),
        ("（三）沉淀结果证据", "沉淀结果证据"),
        ("(4) 保留关键决策", "保留关键决策"),
        ("01 / 重新定义问题", "重新定义问题"),
        ("普通语义标题", "普通语义标题"),
    ],
)
def test_structural_title_prefix_is_removed_without_rewriting_suffix(source: str, expected: str) -> None:
    assert strip_structural_title_prefix(source) == expected


def test_theme_switch_changes_only_future_generation_art_direction() -> None:
    original = {
        "visual_intent": {
            "style_family": "editorial_paper_cut",
            "style_treatment": "tactile_editorial_collage",
            "palette_roles": ["warm_ivory"],
            "palette_intent": ["warm_ivory"],
            "visual_grammar": {
                "decorative_motifs": ["自然纸张毛边"],
                "edge_treatment": "deckled_paper_frame",
            },
        }
    }
    revised = apply_theme_to_image_slot(original, "future_tech")
    assert original["visual_intent"]["style_family"] == "editorial_paper_cut"
    assert revised["visual_intent"]["style_family"] == "editorial_tech_collage"
    assert revised["visual_intent"]["style_treatment"] == "editorial_spatial_collage"
    assert revised["visual_intent"]["visual_grammar"]["edge_treatment"] == "layered_translucent_edge"


def test_theme_compatibility_is_explainable_and_non_blocking() -> None:
    snapshot = build_art_direction_snapshot(
        visual_system="youth_campus",
        visual_intent={
            "style_family": "editorial_paper_cut",
            "style_treatment": "tactile_editorial_collage",
            "palette_roles": ["warm_ivory", "soft_sky"],
        },
        plan_revision=3,
    )
    assert evaluate_theme_compatibility(snapshot, "youth_campus")["level"] == "compatible"
    assert evaluate_theme_compatibility(snapshot, "light_reading")["level"] == "partial"
    assert evaluate_theme_compatibility(snapshot, "future_tech")["level"] == "incompatible"


def test_visual_dna_manifests_are_independent_and_preserve_current_style_tendencies() -> None:
    assert all("compatible_styles" not in manifest for manifest in ARTICLE_THEME_MANIFESTS.values())
    assert all("compatible_themes" not in manifest for manifest in IMAGE_STYLE_MANIFESTS.values())
    expected = {
        "light_reading": "soft_flat_illustration",
        "warm_humanist": "editorial_paper_cut",
        "youth_campus": "editorial_paper_cut",
        "editorial_contrast": "editorial_paper_cut",
        "structured_grid": "clean_3d_geometry",
        "future_tech": "editorial_tech_collage",
    }
    for visual_system, style_family in expected.items():
        for article_type in ("data_policy", "tutorial_steps", "viewpoint_trend", "lively_growth"):
            direction = resolve_article_image_direction(
                visual_system=visual_system,
                article_type=article_type,
            )
            assert direction["style_family"] == style_family
            assert direction["schema_version"] == "article_image_art_direction.v0.1"
            assert set(direction["score_breakdown"]) == {
                "content_fit",
                "theme_fit",
                "novelty",
                "provider_reliability",
            }


def test_extended_themes_resolve_distinct_image_capabilities_without_pair_matrix() -> None:
    expected = {
        ("oriental_archive", "viewpoint_trend"): "oriental_ink_folio",
        ("vintage_press", "data_policy"): "archival_halftone_collage",
        ("pop_poster", "tutorial_steps"): "graphic_poster_collage",
        ("natural_atlas", "lively_growth"): "botanical_field_illustration",
        ("business_review", "data_policy"): "executive_signal_editorial",
        ("cinematic_story", "viewpoint_trend"): "cinematic_storyboard_collage",
    }
    for (visual_system, article_type), style_family in expected.items():
        direction = resolve_article_image_direction(
            visual_system=visual_system,
            article_type=article_type,
            provider_profile="seedream",
        )
        assert direction["style_family"] == style_family
        assert direction["score_breakdown"]["theme_fit"] > 0.9
        assert direction["visual_system"] == visual_system

    # A content mismatch can still select a different independent capability;
    # this proves the registry is scored rather than theme-bound.
    assert resolve_article_image_direction(
        visual_system="vintage_press",
        article_type="lively_growth",
    )["style_family"] == "editorial_paper_cut"

    assert ARTICLE_THEME_MANIFESTS["business_review"]["palette_family"] == "executive_signal"
    assert ARTICLE_THEME_MANIFESTS["cinematic_story"]["palette_family"] == "festival_warm"


def test_extended_visual_dna_values_are_accepted_by_the_plan_contract() -> None:
    cases = {
        "oriental_archive": "viewpoint_trend",
        "vintage_press": "data_policy",
        "pop_poster": "tutorial_steps",
        "natural_atlas": "lively_growth",
        "business_review": "data_policy",
        "cinematic_story": "viewpoint_trend",
    }
    for visual_system, article_type in cases.items():
        direction = resolve_article_image_direction(
            visual_system=visual_system,
            article_type=article_type,
            provider_profile="seedream",
        )
        ArticleImageArtDirection.model_validate(direction)
        intent = build_visual_intent(
            purpose="structured_infographic",
            subject="核验一所学校的专业培养条件",
            title="填报前完成三项核验",
            fact_anchors=["核对培养方案", "核对师资平台", "追踪真实去向"],
            article_type=article_type,
            style_family=direction["style_family"],
            palette_roles=direction["palette_roles"],
            tone=direction["tone"],
        )
        intent["article_art_direction"] = direction
        intent["visual_grammar"]["edge_treatment"] = direction["edge_treatment"]
        ImageVisualIntent.model_validate(intent)


def test_recent_visual_signature_rotates_more_than_article_theme() -> None:
    first = resolve_article_image_direction(
        visual_system="youth_campus",
        article_type="lively_growth",
    )
    repeated = {
        "visual_signature": {
            "image_style_family": first["style_family"],
            "palette_variant": first["palette_variant"],
            "surface_treatment": first["surface_treatment"],
            "composition_family": first["composition_family"],
            "scene_family": first["scene_family"],
        }
    }
    revised = resolve_article_image_direction(
        visual_system="youth_campus",
        article_type="lively_growth",
        recent_summaries=[repeated] * 5,
    )
    assert (
        revised["style_family"],
        revised["palette_variant"],
        revised["surface_treatment"],
        revised["composition_family"],
    ) != (
        first["style_family"],
        first["palette_variant"],
        first["surface_treatment"],
        first["composition_family"],
    )
    assert revised["history_window_used"] == 5


def test_visual_signature_contains_no_article_copy_or_image_bytes() -> None:
    direction = resolve_article_image_direction(
        visual_system="warm_humanist",
        article_type="viewpoint_trend",
    )
    signature = build_visual_signature(
        {
            "visual_system": "warm_humanist",
            "article_type": "viewpoint_trend",
            "image_art_direction": direction,
            "image_slots": [
                {"visual_intent": {"layout_family": "timeline"}},
                {"visual_intent": {"layout_family": "semantic_scene"}},
            ],
        }
    )
    assert signature["article_theme"] == "warm_humanist"
    assert signature["layout_families"] == ["timeline", "semantic_scene"]
    assert "title" not in signature
    assert "content" not in signature


def test_display_label_never_summarizes_source() -> None:
    source = "查看学校当年招生专业目录，确认该专业是否实际招生"
    label = extract_display_label(source)
    assert label in source
    assert len(label) <= 14
    long_source = "结合学校公开的升学、就业与校企合作信息，判断主要出口是否符合个人计划。"
    assert extract_display_label(long_source) == "升学、就业与校企合作信息"


def test_generated_plan_contains_explainable_visual_intent() -> None:
    article = parse_markdown(
        """# 志愿填报前先完成核对

## 提交前核对流程

1. 先保存官方成绩截图
2. 再核对准确位次
3. 最后检查专业限制

完成这些核对后再开始志愿排序。
"""
    )
    plan = generate_plans(article, "tutorial_steps", 5)[0]
    structured = next(slot for slot in plan["image_slots"] if slot["purpose"] == "structured_infographic")
    intent = structured["visual_intent"]
    assert intent["visual_role"] == "explain_sequence"
    assert intent["layout_family"] == "linear_progression"
    assert intent["learning_objective"]
    assert intent["fact_anchors"] == [
        "先保存官方成绩截图",
        "再核对准确位次",
        "最后检查专业限制",
    ]
    assert intent["style_treatment"] == "tactile_editorial_collage"
    assert intent["palette_intent"]
    assert intent["visual_grammar"]["display_labels"] == intent["fact_anchors"]


def test_fact_anchors_must_be_exact_article_copy() -> None:
    article = parse_markdown(
        """# 核对流程

## 三步行动

1. 保存官方截图
2. 核对准确位次
3. 检查专业限制
"""
    )
    plan = generate_plans(article, "tutorial_steps", 5)[0]
    tampered = copy.deepcopy(plan)
    tampered["image_slots"][0]["visual_intent"]["fact_anchors"][0] = "保证一定被录取"
    with pytest.raises(ValueError, match="事实锚点未逐字绑定原文"):
        validate_plan_for_article(tampered, article)


def test_legacy_visual_intent_is_upgraded_when_read() -> None:
    article = parse_markdown(
        """# 核对流程

## 三步行动

1. 保存官方截图
2. 核对准确位次
3. 检查专业限制
"""
    )
    legacy = copy.deepcopy(generate_plans(article, "tutorial_steps", 5)[0])
    visual_intent = legacy["image_slots"][0]["visual_intent"]
    for key in (
        "visual_role",
        "learning_objective",
        "fact_anchors",
        "layout_family",
        "style_treatment",
        "palette_intent",
        "intent_version",
        "article_type",
        "visual_grammar",
    ):
        visual_intent.pop(key, None)
    validated = validate_plan_for_article(legacy, article)
    upgraded = validated["image_slots"][0]["visual_intent"]
    assert upgraded["intent_version"] == "image_visual_intent.v2"
    assert upgraded["layout_family"] == "linear_progression"
    assert upgraded["visual_role"] == "explain_sequence"
    assert upgraded["visual_grammar"]["display_labels"] == [
        "保存官方截图",
        "核对准确位次",
        "检查专业限制",
    ]
