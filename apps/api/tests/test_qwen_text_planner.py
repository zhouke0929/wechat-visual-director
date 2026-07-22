from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from visual_director.parser import classify_article, parse_markdown
from visual_director.text_planner import (
    MockTextPlannerProvider,
    QwenTextPlannerProvider,
    TextPlannerRequest,
    generate_editorial_brief,
)


TEST_API_KEY = "sk-" + "test-key-never-logged"


ROOT = Path(__file__).resolve().parents[3]


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def read(self, limit: int | None = None) -> bytes:
        return self.payload if limit is None else self.payload[:limit]


def planner_request() -> TextPlannerRequest:
    markdown = (ROOT / "samples" / "evaluation" / "05-tutorial-steps.md").read_text(encoding="utf-8")
    parsed = parse_markdown(markdown)
    return TextPlannerRequest(
        parsed=parsed,
        article_type=classify_article(parsed),
        history_window=5,
        recent_summaries=[],
        brand_config={},
    )


def response_payload(content: str, prompt_tokens: int = 1000, completion_tokens: int = 500) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def test_qwen_provider_uses_json_mode_non_thinking_and_records_cost() -> None:
    request = planner_request()
    brief = MockTextPlannerProvider().generate(request).model_dump_json()
    sent: list[Any] = []

    def urlopen(http_request: Any, **_: Any) -> FakeResponse:
        sent.append(http_request)
        return FakeResponse(response_payload(brief))

    provider = QwenTextPlannerProvider(
        api_key=TEST_API_KEY,
        model="qwen3.6-flash",
        urlopen=urlopen,
    )
    result = generate_editorial_brief(provider, request)

    assert not result.fallback_used
    assert result.repair_count == 0
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
    assert result.estimated_cost_yuan == 0.0048
    body = json.loads(sent[0].data.decode("utf-8"))
    assert body["response_format"] == {"type": "json_object"}
    assert body["enable_thinking"] is False
    assert body["temperature"] == 0.2
    assert "max_tokens" not in body
    assert TEST_API_KEY not in sent[0].data.decode("utf-8")


def test_qwen_fixed_max_snapshot_is_supported_and_uses_frozen_price() -> None:
    request = planner_request()
    brief = MockTextPlannerProvider().generate(request).model_dump_json()

    def urlopen(_: Any, **__: Any) -> FakeResponse:
        return FakeResponse(response_payload(brief, prompt_tokens=1000, completion_tokens=500))

    provider = QwenTextPlannerProvider(
        api_key=TEST_API_KEY,
        model="qwen3.7-max-2026-05-20",
        urlopen=urlopen,
    )
    result = generate_editorial_brief(provider, request)

    assert not result.fallback_used
    assert result.model == "qwen3.7-max-2026-05-20"
    assert result.estimated_cost_yuan == 0.03


def test_qwen_provider_repairs_invalid_json_once() -> None:
    request = planner_request()
    brief = MockTextPlannerProvider().generate(request).model_dump_json()
    responses = [
        FakeResponse(response_payload('{"schema_version":"wrong"}', 800, 50)),
        FakeResponse(response_payload(brief, 1100, 500)),
    ]
    sent: list[Any] = []

    def urlopen(http_request: Any, **_: Any) -> FakeResponse:
        sent.append(http_request)
        return responses.pop(0)

    provider = QwenTextPlannerProvider(
        api_key=TEST_API_KEY,
        model="qwen3.7-max",
        urlopen=urlopen,
    )
    result = generate_editorial_brief(provider, request)

    assert not result.fallback_used
    assert result.repair_count == 1
    assert result.input_tokens == 1900
    assert result.output_tokens == 550
    assert len(sent) == 2
    repair_body = json.loads(sent[1].data.decode("utf-8"))
    assert "上一轮 JSON 未通过严格校验" in repair_body["messages"][1]["content"]


def test_qwen_provider_invalid_after_repair_falls_back_and_keeps_cost() -> None:
    request = planner_request()
    invalid = '{"schema_version":"wrong"}'
    responses = [
        FakeResponse(response_payload(invalid, 800, 50)),
        FakeResponse(response_payload(invalid, 900, 60)),
    ]

    def urlopen(_: Any, **__: Any) -> FakeResponse:
        return responses.pop(0)

    provider = QwenTextPlannerProvider(
        api_key=TEST_API_KEY,
        model="qwen3.6-flash",
        urlopen=urlopen,
    )
    result = generate_editorial_brief(provider, request)

    assert result.fallback_used
    assert result.provider_error_code == "qwen_output_invalid_after_repair"
    assert result.repair_count == 1
    assert result.input_tokens == 1700
    assert result.output_tokens == 110
    assert result.estimated_cost_yuan > 0


def test_qwen_provider_safely_normalizes_unsupported_component_preference() -> None:
    request = planner_request()
    brief = MockTextPlannerProvider().generate(request).model_copy(deep=True)
    brief.sections[0].component_intent = "numbered_insight"
    brief.sections[0].semantic_role = "action_step"

    def urlopen(_: Any, **__: Any) -> FakeResponse:
        return FakeResponse(response_payload(brief.model_dump_json()))

    provider = QwenTextPlannerProvider(
        api_key=TEST_API_KEY,
        model="qwen3.6-flash",
        urlopen=urlopen,
    )
    result = generate_editorial_brief(provider, request)

    assert not result.fallback_used
    assert result.repair_count == 0
    assert result.normalization_count == 1
    assert result.brief.sections[0].component_intent == "plain"
    assert result.normalization_adjustments[0]["code"] == "component_intent_lowered_to_plain"
