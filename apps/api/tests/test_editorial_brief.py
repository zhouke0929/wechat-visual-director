from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from visual_director.brief_compiler import compile_editorial_brief, compile_editorial_brief_variants
from visual_director.editorial_brief import (
    EditorialBrief,
    normalize_editorial_brief_for_article,
    validate_editorial_brief_for_article,
)
from visual_director.main import create_app
from visual_director.parser import classify_article, parse_markdown
from visual_director.renderer import render_preview
from visual_director.text_planner import (
    MockTextPlannerProvider,
    TextPlannerRequest,
    build_text_planner_payload,
    generate_editorial_brief,
)


ROOT = Path(__file__).resolve().parents[3]


def _dev_samples() -> list[dict]:
    manifest = json.loads((ROOT / "samples" / "evaluation" / "v0.6-public-dev-set.json").read_text(encoding="utf-8"))
    return manifest["samples"]


def _visual_contrast_samples() -> list[dict]:
    manifest = json.loads(
        (ROOT / "samples" / "evaluation" / "v0.6-visual-contrast-set.json").read_text(
            encoding="utf-8"
        )
    )
    return manifest["samples"]


def _request(sample: dict) -> TextPlannerRequest:
    parsed = parse_markdown((ROOT / sample["path"]).read_text(encoding="utf-8"))
    return TextPlannerRequest(
        parsed=parsed,
        article_type=classify_article(parsed),
        history_window=5,
        recent_summaries=[],
        brand_config={},
    )


def _concept_request() -> TextPlannerRequest:
    parsed = parse_markdown(
        """# 测试文章

## 核心章节

### 什么是结构保护

结构保护是指主章节始终保留，只允许子标题进入概念组件。

补充语境必须继续作为普通正文出现。
"""
    )
    return TextPlannerRequest(
        parsed=parsed,
        article_type="viewpoint_trend",
        history_window=5,
        recent_summaries=[],
        brand_config={},
    )


def _concept_brief(request: TextPlannerRequest) -> EditorialBrief:
    raw = MockTextPlannerProvider().generate(request).model_dump(mode="json")
    raw["sections"] = [
        {
            "source_block_ids": ["block-003", "block-004", "block-005"],
            "semantic_role": "concept",
            "visual_priority": "high",
            "component_intent": "concept_explainer",
            "reasoning": "H3 与紧随段落构成概念定义。",
        }
    ]
    raw["image_intents"] = [
        {
            "anchor_block_id": "block-003",
            "source_block_ids": ["block-003", "block-004"],
            "purpose": "atmosphere",
            "necessity": "optional",
            "aspect_ratio": "16:9",
            "visual_metaphor": "稳定的文章结构",
            "forbidden_elements": ["text_in_model_image", "qr_code", "logo"],
        }
    ]
    return EditorialBrief.model_validate(raw)


def test_editorial_brief_forbids_unknown_fields_and_bad_refs() -> None:
    request = _request(_dev_samples()[4])
    brief = MockTextPlannerProvider().generate(request).model_dump(mode="json")
    brief["unknown"] = True
    with pytest.raises(ValidationError):
        EditorialBrief.model_validate(brief)

    valid = MockTextPlannerProvider().generate(request).model_copy(deep=True)
    valid.sections[0].source_block_ids = ["block-999"]
    with pytest.raises(ValueError, match="不存在"):
        validate_editorial_brief_for_article(valid, request.parsed)


def test_editorial_brief_rejects_component_and_block_type_mismatch() -> None:
    request = _request(_dev_samples()[4])
    brief = MockTextPlannerProvider().generate(request).model_copy(deep=True)
    paragraph_id = next(block.id for block in request.parsed.blocks if block.type == "paragraph")
    brief.sections[0].component_intent = "numbered_insight"
    brief.sections[0].semantic_role = "action_step"
    brief.sections[0].source_block_ids = [paragraph_id]
    with pytest.raises(ValueError, match="不兼容"):
        validate_editorial_brief_for_article(brief, request.parsed)


def test_normalizer_lowers_feature_heading_misclassified_as_concept() -> None:
    request = TextPlannerRequest(
        parsed=parse_markdown(
            """# 产品功能

## 解决方案

### 核心功能五：安全合规内置

路线审批的核心是安全。平台内置安全合规引擎。
"""
        ),
        article_type="data_policy",
        history_window=5,
        recent_summaries=[],
        brand_config={},
    )
    raw = MockTextPlannerProvider().generate(request).model_dump(mode="json")
    raw["sections"] = [
        {
            "source_block_ids": ["block-003", "block-004"],
            "semantic_role": "concept",
            "visual_priority": "high",
            "component_intent": "concept_explainer",
            "reasoning": "模型误判为概念。",
        }
    ]
    brief = EditorialBrief.model_validate(raw)

    normalized, adjustments = normalize_editorial_brief_for_article(brief, request.parsed)

    assert normalized.sections[0].component_intent == "plain"
    assert any(item["code"] == "component_intent_lowered_to_plain" for item in adjustments)


def test_normalizer_moves_image_out_of_component_middle_and_plan_compiles() -> None:
    request = _concept_request()
    brief = _concept_brief(request)

    normalized, adjustments = normalize_editorial_brief_for_article(brief, request.parsed)
    normalized_image = next(
        intent
        for intent in normalized.image_intents
        if set(intent.source_block_ids) == {"block-003", "block-004"}
    )
    assert normalized_image.anchor_block_id == "block-004"
    assert any(item["code"] == "image_anchor_moved_after_component" for item in adjustments)
    compile_editorial_brief(request.parsed, normalized, 5, [])


def test_normalizer_handles_mechanical_model_output_issues_without_repair() -> None:
    request = _request(_dev_samples()[4])
    raw = MockTextPlannerProvider().generate(request).model_dump(mode="json")
    raw.pop("schema_version")
    raw.pop("facts_locked")
    raw["image_intents"][0]["visual_metaphor"] = "用于表达理性核对路径的视觉隐喻" * 20
    anchor = raw["image_intents"][0]["anchor_block_id"]
    raw["image_intents"][0]["source_block_ids"] = [
        block_id
        for block_id in raw["image_intents"][0]["source_block_ids"]
        if block_id != anchor
    ]
    extra = copy.deepcopy(raw["sections"][0])
    extra["visual_priority"] = "low"
    raw["sections"].append(extra)

    normalized, adjustments = normalize_editorial_brief_for_article(raw, request.parsed)
    codes = {item["code"] for item in adjustments}
    assert "visual_metaphor_truncated" in codes
    assert "image_anchor_added_to_sources" in codes
    assert "excess_component_intent_lowered_to_plain" in codes
    assert len([item for item in normalized.sections if item.component_intent != "plain"]) == 4
    assert len(normalized.image_intents[0].visual_metaphor) == 160
    compile_editorial_brief(request.parsed, normalized, 5, [])


def test_normalizer_does_not_turn_article_h1_into_body_question_component() -> None:
    request = _request(_dev_samples()[6])
    raw = MockTextPlannerProvider().generate(request).model_dump(mode="json")
    raw["sections"] = [
        {
            "source_block_ids": ["block-001", "block-002"],
            "semantic_role": "reader_question",
            "visual_priority": "high",
            "component_intent": "question_hook",
            "reasoning": "标题提出核心问题。",
        }
    ]

    normalized, adjustments = normalize_editorial_brief_for_article(raw, request.parsed)
    assert normalized.sections[0].component_intent == "plain"
    assert any(item["code"] == "component_intent_lowered_to_plain" for item in adjustments)
    plan = compile_editorial_brief(request.parsed, normalized, 5, [])
    assert not plan["slots"]


def test_compiler_consumes_only_bound_blocks_and_preserves_context_copy() -> None:
    tutorial = _request(_dev_samples()[4])
    tutorial_brief = MockTextPlannerProvider().generate(tutorial).model_copy(deep=True)
    numbered = next(section for section in tutorial_brief.sections if section.component_intent == "action_checklist")
    numbered.source_block_ids = ["block-004", "block-005", "block-006"]
    tutorial_brief.sections = [numbered]
    tutorial_plan = compile_editorial_brief(tutorial.parsed, tutorial_brief, 5, [])
    numbered_slot = next(slot for slot in tutorial_plan["slots"] if slot["component_type"] == "action_checklist")
    assert numbered_slot["consume_block_ids"] == ["block-006"]
    tutorial_html = render_preview(tutorial.parsed, tutorial_plan)
    assert str(next(block.content for block in tutorial.parsed.blocks if block.id == "block-004")) in tutorial_html
    assert str(next(block.content for block in tutorial.parsed.blocks if block.id == "block-005")) in tutorial_html

    viewpoint = _concept_request()
    viewpoint_brief = _concept_brief(viewpoint)
    viewpoint_brief.image_intents = []
    viewpoint_plan = compile_editorial_brief(viewpoint.parsed, viewpoint_brief, 5, [])
    concept_slot = next(slot for slot in viewpoint_plan["slots"] if slot["component_type"] == "concept_explainer")
    assert concept_slot["consume_block_ids"] == ["block-003", "block-004"]
    viewpoint_html = render_preview(viewpoint.parsed, viewpoint_plan)
    assert str(next(block.content for block in viewpoint.parsed.blocks if block.id == "block-005")) in viewpoint_html


def test_compiler_maps_art_direction_to_frozen_palette_and_layout() -> None:
    request = _request(_dev_samples()[4])
    brief = MockTextPlannerProvider().generate(request).model_copy(deep=True)
    brief.art_direction.palette_roles = ["deep_navy", "warm_ivory", "coral_accent"]
    brief.art_direction.style_family = "editorial_paper_cut"

    plan = compile_editorial_brief(request.parsed, brief, 5, [])

    assert plan["style_mode"] == "ink_navy_editorial"
    assert plan["configuration"]["palette"]["primary"] == "#243B53"
    assert plan["configuration"]["palette"]["accent"] == "#B85C47"
    assert plan["configuration"]["heading_variant"] == "editorial_left_rule"
    assert plan["editorial_brief_metadata"]["palette_profile"] == "ink_navy_editorial"
    assert plan["slots"]
    assert "#243B53" in render_preview(request.parsed, plan)


def test_compiler_generates_two_visual_systems_with_one_shared_structure() -> None:
    request = _request(_visual_contrast_samples()[1])
    brief = MockTextPlannerProvider().generate(request)
    recent = [
        {"visual_system": "light_reading", "components": []},
        {"style_mode": "light_reading", "components": []},
    ]

    plans = compile_editorial_brief_variants(request.parsed, brief, 5, recent)

    assert [plan["visual_system"] for plan in plans] == ["warm_humanist", "editorial_contrast"]
    assert len({plan["structure_fingerprint"] for plan in plans}) == 1
    assert plans[0]["recommendation"] == "recommended"
    assert plans[1]["recommendation"] == "alternative"
    assert plans[0]["visual_system_metadata"]["switch_requires_planner_call"] is False
    assert plans[0]["configuration"] != plans[1]["configuration"]
    assert render_preview(request.parsed, plans[0]) != render_preview(request.parsed, plans[1])
    for left, right in zip(plans[0]["slots"], plans[1]["slots"], strict=True):
        assert left["component_type"] == right["component_type"]
        assert left["anchor_block_id"] == right["anchor_block_id"]
        assert left["consume_block_ids"] == right["consume_block_ids"]
        assert left["content_bindings"] == right["content_bindings"]
        assert left["variant"] != right["variant"]
    assert plans[0]["image_slots"] == plans[1]["image_slots"]


def test_visual_system_pool_rotates_both_groups_after_confirmed_history() -> None:
    request = _request(_visual_contrast_samples()[1])
    brief = MockTextPlannerProvider().generate(request)
    recent = [
        {"visual_system": "light_reading", "components": []},
        {"visual_system": "editorial_contrast", "components": []},
    ]

    plans = compile_editorial_brief_variants(request.parsed, brief, 5, recent)

    assert [plan["visual_system"] for plan in plans] == ["warm_humanist", "structured_grid"]
    assert plans[0]["configuration"]["palette"] != plans[1]["configuration"]["palette"]
    assert all(plan["visual_system_metadata"]["recent_use_count"] == 0 for plan in plans)


def test_h2_concept_is_lowered_but_adjacent_h3_definition_is_allowed() -> None:
    request = _concept_request()
    valid = _concept_brief(request)
    normalized, adjustments = normalize_editorial_brief_for_article(valid, request.parsed)
    plan = compile_editorial_brief(request.parsed, normalized, 5, [])
    concept = plan["slots"][0]
    assert concept["consume_block_ids"] == ["block-003", "block-004"]

    invalid = valid.model_dump(mode="json")
    invalid["sections"][0]["source_block_ids"] = ["block-002", "block-004"]
    normalized, adjustments = normalize_editorial_brief_for_article(invalid, request.parsed)
    assert normalized.sections[0].component_intent == "plain"
    assert any(item["code"] == "component_intent_lowered_to_plain" for item in adjustments)


@pytest.mark.parametrize("sample", _dev_samples(), ids=lambda item: item["id"])
def test_mock_planner_compiles_all_seven_dev_samples(sample: dict) -> None:
    request = _request(sample)
    result = generate_editorial_brief(MockTextPlannerProvider(), request)
    assert not result.fallback_used
    assert result.brief.article.article_type == sample["gold_article_type"]
    assert len([item for item in result.brief.sections if item.component_intent != "plain"]) <= 6
    assert len(result.brief.image_intents) <= 3

    plan = compile_editorial_brief(request.parsed, result.brief, 5, [])
    assert len(plan["slots"]) <= 6
    assert len(plan["image_slots"]) <= 3
    document = render_preview(request.parsed, plan)
    assert "width:100%" in document
    assert "width:390px" not in document


@pytest.mark.parametrize("sample", _visual_contrast_samples(), ids=lambda item: item["id"])
def test_mock_planner_compiles_visual_contrast_samples(sample: dict) -> None:
    request = _request(sample)
    result = generate_editorial_brief(MockTextPlannerProvider(), request)
    plan = compile_editorial_brief(request.parsed, result.brief, 5, [])

    assert not result.fallback_used
    assert plan["style_mode"] in {
        "ink_navy_editorial",
        "warm_coral_editorial",
        "sage_sunlit_editorial",
    }
    assert plan["configuration"]["palette"]["primary"].startswith("#")
    document = render_preview(request.parsed, plan)
    assert "width:100%" in document
    assert "width:390px" not in document


def test_provider_error_falls_back_to_rule_brief() -> None:
    class FailingProvider:
        provider = "failing"
        model = "failing-model"
        configured = True

        def generate(self, request: TextPlannerRequest):
            raise TimeoutError("probe timeout")

    request = _request(_dev_samples()[4])
    result = generate_editorial_brief(FailingProvider(), request)
    assert result.fallback_used
    assert "TimeoutError" in (result.fallback_reason or "")
    compile_editorial_brief(request.parsed, result.brief, 5, [])


def test_provider_payload_excludes_secrets_and_full_history() -> None:
    base = _request(_dev_samples()[4])
    request = TextPlannerRequest(
        parsed=base.parsed,
        article_type=base.article_type,
        history_window=1,
        recent_summaries=[
            {"components": [{"component_type": "logic_path", "variant": "folded_stair"}], "private_note": "hidden"},
            {"components": [{"component_type": "question_hook", "variant": "light_bubble"}]},
        ],
        brand_config={
            "brand_profile_version": "example_0.1",
            "account_name": "示例公众号",
            "app_secret": "must-not-leak",
            "fixed_footer": {"component": "cta-v1", "asset_path": "private/path.jpg"},
        },
    )
    payload = build_text_planner_payload(request)
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "must-not-leak" not in serialized
    assert "private/path.jpg" not in serialized
    assert "hidden" not in serialized
    assert len(payload["recent_history"]) == 1
    assert payload["component_opportunities"]["eligible_candidate_count"] >= 1
    assert payload["component_opportunities"]["eligible_component_types"]


def test_editorial_brief_api_returns_baseline_and_experimental_plan(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "brief.db"), text_planner_provider=MockTextPlannerProvider())
    markdown = (ROOT / _dev_samples()[4]["path"]).read_bytes()
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("sample.md", markdown, "text/markdown")},
        ).json()["task"]
        response = client.post(
            f'/api/v1/article-tasks/{created["id"]}/editorial-brief/generate',
            json={"expected_task_version": created["version"]},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["brief"]["schema_version"] == "editorial_brief.v0.1"
        assert payload["planner_run"]["provider"] == "mock_text_planner"
        assert payload["experimental_plan"]["plan_name"] == "智能规划 · Editorial Brief"
        diagnostics = payload["experimental_plan"]["component_diagnostics"]
        assert diagnostics["eligible_candidate_count"] >= diagnostics["selected_component_count"]
        assert diagnostics["selected_component_types"]
        assert len(payload["experimental_plans"]) == 2
        assert len({plan["structure_fingerprint"] for plan in payload["experimental_plans"]}) == 1
        assert payload["baseline_plan"]["recommendation"] == "recommended"


def test_host_agent_context_and_brief_use_no_second_provider_call(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "host-agent.db"))
    markdown = """---
title: 三步完成志愿核对
article_type: tutorial_steps
---
# 三步完成志愿核对

## 核对路径

1. 保存官方成绩
2. 核对准确位次
3. 记录专业限制

> 志愿表需要逐项验证。
"""
    parsed = parse_markdown(markdown)
    request = TextPlannerRequest(
        parsed=parsed,
        article_type="tutorial_steps",
        history_window=5,
        recent_summaries=[],
        brand_config={},
    )
    host_brief = MockTextPlannerProvider().generate(request).model_dump(mode="json")

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("host.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()["task"]
        context_response = client.get(
            f'/api/v1/article-tasks/{created["id"]}/editorial-brief/context'
        )
        assert context_response.status_code == 200
        context_payload = context_response.json()
        assert context_payload["expected_task_version"] == created["version"]
        assert context_payload["context"]["schema_version"] == "host_agent_planner_context.v0.1"
        assert context_payload["context"]["planner_input"]["article"]["blocks"]
        assert context_payload["context"]["execution_hint"]["same_agent_supported"] is True

        generated = client.post(
            f'/api/v1/article-tasks/{created["id"]}/generate-plans',
            json={
                "mode": "start",
                "planner": "host_agent",
                "expected_task_version": created["version"],
                "editorial_brief": host_brief,
                "host_model": "configured-by-host",
            },
        )
        assert generated.status_code == 202
        metadata = generated.json()["planner_metadata"]
        assert metadata["provider"] == "host_agent"
        assert metadata["model"] == "configured-by-host"
        assert metadata["planner_call_count"] == 0
        assert metadata["fallback_used"] is False
        plans = client.get(f'/api/v1/article-tasks/{created["id"]}/plans').json()["plans"]
        assert len(plans) == 2
        assert all(plan["planner_metadata"]["provider"] == "host_agent" for plan in plans)


def test_invalid_host_agent_brief_falls_back_to_rules_transparently(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "host-agent-fallback.db"))
    markdown = """# 三步完成志愿核对

## 核对路径

1. 保存官方成绩
2. 核对准确位次
3. 记录专业限制
"""
    with TestClient(app) as client:
        task = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("fallback.md", markdown.encode("utf-8"), "text/markdown")},
            data={"article_type": "tutorial_steps"},
        ).json()["task"]
        generated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={
                "mode": "start",
                "planner": "host_agent",
                "expected_task_version": task["version"],
                "editorial_brief": {"unexpected": True},
            },
        )
        assert generated.status_code == 202
        metadata = generated.json()["planner_metadata"]
        assert metadata["provider"] == "host_agent"
        assert metadata["fallback_used"] is True
        assert metadata["provider_error_code"] == "host_brief_invalid"
        assert "ValidationError" in metadata["fallback_reason"]
        assert len(client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"]) == 2
