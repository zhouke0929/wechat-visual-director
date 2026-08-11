from __future__ import annotations

import json
import urllib.error
import base64
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from visual_director.image_provider import (
    GeminiImageProvider,
    ImagesApiProvider,
    ImageProviderError,
    build_cover_prompt,
    build_provider_prompt,
    build_theme_fallback_cover,
    create_image_provider_from_env,
)
from visual_director.main import create_app
from visual_director.infographic_overlay import compose_structured_infographic


class FakeResponse:
    def __init__(self, content: bytes, content_type: str) -> None:
        self.content = content
        self.headers = {"Content-Type": content_type}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def read(self, limit: int | None = None) -> bytes:
        return self.content if limit is None else self.content[:limit]


def png_bytes(width: int = 1152, height: int = 864) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "#fffaf0").save(buffer, format="PNG")
    return buffer.getvalue()


def public_resolver(*_: Any, **__: Any) -> list[tuple[Any, ...]]:
    return [(2, 1, 6, "", ("8.8.8.8", 443))]


def prompt_slot(*, purpose: str, subject: str, item_count: int = 0) -> dict[str, Any]:
    return {
        "purpose": purpose,
        "visual_intent": {
            "subject": subject,
            "composition": "branching" if purpose == "structured_infographic" else "wide_scene",
            "style_family": "editorial_paper_cut",
            "negative_space": "lower_right" if purpose == "structured_infographic" else "lower_third",
        },
        "fact_bindings": {
            "title_ref": "block-001" if item_count else None,
            "item_refs": [f"block-002:item:{index}" for index in range(item_count)],
            "facts_locked": True,
        },
    }


def test_provider_prompt_routes_article_style_and_locks_infographic_copy() -> None:
    atmosphere = build_provider_prompt(
        prompt_slot(
            purpose="atmosphere",
            subject="扫码了解华东师范大学3+1项目，官方注册，联系电话不要外发",
        ),
        "data_policy",
    )
    assert "扫码" not in atmosphere
    assert "联系电话" not in atmosphere
    assert "深海军蓝" in atmosphere
    assert "语义插画" in atmosphere
    assert "二维码" in atmosphere
    assert "不要出现文字" in atmosphere

    structured = build_provider_prompt(
        {
            **prompt_slot(purpose="structured_infographic", subject="三张纸雕路标组成核对路径", item_count=3),
            "visual_intent": {
                **prompt_slot(
                    purpose="structured_infographic",
                    subject="三张纸雕路标组成核对路径",
                    item_count=3,
                )["visual_intent"],
                "palette_roles": ["warm_ivory", "muted_teal", "coral_accent"],
                "tone": ["清晰", "可信"],
            },
        },
        "tutorial_steps",
        infographic_title="填报前完成三项核对",
        infographic_items=["核对成绩和位次", "检查专业限制", "保留复核记录"],
    )
    assert "横版4:3插画型信息图" in structured
    assert "填报前完成三项核对" in structured
    assert "核对成绩和位次" in structured
    assert "严格文字白名单" in structured
    assert "低饱和青绿" in structured
    assert "核心场景隐喻" in structured
    assert "70%到85%" in structured
    assert "独立圆角框" in structured
    assert "节点1" not in structured
    assert "配色只用" in structured
    assert "空白底板" not in structured


def test_seedream_prompt_is_concise_provider_specific_and_rotates_scenes() -> None:
    slot = prompt_slot(
        purpose="atmosphere",
        subject="民办高校进入存量竞争，学校从扩张转向质量与特色建设",
    )
    first = build_provider_prompt(
        slot,
        "viewpoint_trend",
        prompt_profile="seedream",
        candidate_index=1,
    )
    second = build_provider_prompt(
        slot,
        "viewpoint_trend",
        prompt_profile="seedream",
        candidate_index=2,
    )
    assert first != second
    assert len(first) < 500
    assert "中央80%安全区" in first
    assert "不出现任何文字" in first
    assert "冷白或极浅灰" not in first

    infographic = build_provider_prompt(
        prompt_slot(purpose="structured_infographic", subject="三步核验路径", item_count=3),
        "tutorial_steps",
        infographic_title="填报前完成三项核对",
        infographic_items=["核对成绩和位次", "检查专业限制", "保留复核记录"],
        prompt_profile="seedream",
        candidate_index=1,
    )
    assert len(infographic) < 900
    assert "节点脚本" in infographic
    assert "严格文字白名单" in infographic
    assert "同一纸面世界" in infographic
    assert "70%到85%" in infographic


def test_seedream_future_tech_uses_editorial_collage_without_signpost_stage() -> None:
    slot = prompt_slot(
        purpose="atmosphere",
        subject="把课程作业改造成作品集的四步行动路径",
    )
    slot["visual_intent"].update(
        {
            "style_family": "editorial_tech_collage",
            "style_treatment": "editorial_spatial_collage",
            "article_art_direction": {
                "style_family": "editorial_tech_collage",
                "style_treatment": "editorial_spatial_collage",
                "surface_treatment": "future_signal_surface",
                "composition_family": "flowing_signal_path",
                "palette_roles": ["warm_ivory", "deep_navy", "muted_teal", "sunlit_yellow"],
                "tone": ["清晰", "前瞻", "有编辑感"],
            },
        }
    )
    prompt = build_provider_prompt(
        slot,
        "tutorial_steps",
        prompt_profile="seedream",
        candidate_index=1,
    )
    assert "科技编辑拼贴" in prompt
    assert "磨砂半透明薄片" in prompt
    assert "不使用路牌、站牌、塑料玩具" in prompt
    assert "上半部不得形成大面积空白" in prompt


def test_seedream_cover_prompt_and_local_theme_fallback_are_publishable() -> None:
    brief = {
        "title": "高校竞争从增量扩张走向质量分化",
        "article_type": "viewpoint_trend",
        "narrative": "从一宗流拍资产理解民办高校的新阶段",
        "reader_task": "帮助家长识别学校质量与长期办学能力",
        "visual_system": "youth_campus",
        "image_art_direction": {
            "style_family": "editorial_tech_collage",
            "surface_treatment": "future_signal_surface",
            "composition_family": "flowing_signal_path",
            "palette_roles": ["warm_ivory", "deep_navy", "muted_teal", "sunlit_yellow"],
            "tone": ["清晰", "前瞻", "有编辑感"],
        },
    }
    prompt = build_cover_prompt(brief, prompt_profile="seedream", candidate_index=1)
    assert len(prompt) < 650
    assert "5:4封面底图" in prompt
    assert "科技编辑拼贴" in prompt
    assert "磨砂半透明薄片" in prompt
    assert "禁止路牌、站牌、深色道路、塑料玩具" in prompt
    assert "不做信息图、多面板或并排步骤卡" in prompt
    assert "不出现文字" in prompt

    content = build_theme_fallback_cover(brief)
    with Image.open(BytesIO(content)) as image:
        assert image.format == "PNG"
        assert image.size == (1080, 864)


def test_deterministic_infographic_overlay_preserves_canvas_and_adds_copy() -> None:
    overlaid = compose_structured_infographic(
        png_bytes(1152, 864),
        title="提交前完成四项核对",
        items=["核对分数和位次", "检查专业限制", "确认志愿梯度", "由另一人独立复核"],
    )
    with Image.open(BytesIO(overlaid)) as image:
        assert image.format == "PNG"
        assert image.size == (1152, 864)
    assert overlaid != png_bytes(1152, 864)


def test_images_api_provider_builds_openai_payload_decodes_and_validates_image() -> None:
    requests: list[Any] = []
    responses = [
        FakeResponse(
            json.dumps(
                {
                    "created": 1,
                    "data": [{"b64_json": base64.b64encode(png_bytes()).decode("ascii")}],
                }
            ).encode(),
            "application/json",
        ),
    ]

    def urlopen(request: Any, **_: Any) -> FakeResponse:
        requests.append(request)
        return responses.pop(0)

    provider = ImagesApiProvider(
        api_key="test-key-that-is-long-enough",
        urlopen=urlopen,
        resolve_host=public_resolver,
        sleep=lambda _: None,
    )
    generated = provider.generate(
        prompt="Abstract editorial art inspired by: three learning paths, clean paper geometry",
        aspect_ratio="4:3",
        candidate_index=1,
    )

    request_payload = json.loads(requests[0].data.decode("utf-8"))
    assert request_payload == {
        "model": "gpt-image-2",
        "prompt": "Abstract editorial art inspired by: three learning paths, clean paper geometry",
        "size": "1536x1024",
        "n": 1,
    }
    assert requests[0].headers["Authorization"] == "Bearer test-key-that-is-long-enough"
    assert generated.provider == "images_api"
    assert generated.content_type == "image/png"
    assert (generated.width, generated.height) == (1152, 864)
    assert generated.machine_checks["ratio_valid"] is True


def test_images_api_provider_builds_ark_agent_plan_payload() -> None:
    requests: list[Any] = []
    responses = [
        FakeResponse(
            json.dumps(
                {
                    "created": 1,
                    "data": [{"b64_json": base64.b64encode(png_bytes(1312, 736)).decode("ascii")}],
                }
            ).encode(),
            "application/json",
        ),
    ]

    def urlopen(request: Any, **_: Any) -> FakeResponse:
        requests.append(request)
        return responses.pop(0)

    provider = ImagesApiProvider(
        api_key="agent-plan-test-key",
        endpoint="https://ark.cn-beijing.volces.com/api/plan/v3/images/generations",
        model="doubao-seedream-5.0-lite",
        protocol="ark_plan",
        size="2K",
        urlopen=urlopen,
        resolve_host=public_resolver,
        sleep=lambda _: None,
    )
    generated = provider.generate(
        prompt="A calm editorial illustration about choosing a learning path",
        aspect_ratio="16:9",
        candidate_index=1,
    )

    assert requests[0].full_url == "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"
    assert json.loads(requests[0].data.decode("utf-8")) == {
        "model": "doubao-seedream-5.0-lite",
        "prompt": "A calm editorial illustration about choosing a learning path",
        "size": "2K",
        "sequential_image_generation": "disabled",
        "response_format": "url",
    }
    assert requests[0].headers["Authorization"] == "Bearer agent-plan-test-key"
    assert generated.provider == "images_api"
    assert generated.machine_checks["ratio_valid"] is True


def test_images_api_provider_retries_one_transient_failure_only() -> None:
    calls = 0

    def urlopen(_: Any, **__: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.URLError("temporary")
        if calls == 2:
            return FakeResponse(
                json.dumps({"data": [{"url": "https://storage.example.com/output.png"}]}).encode(),
                "application/json",
            )
        return FakeResponse(png_bytes(1312, 736), "image/png")

    provider = ImagesApiProvider(
        api_key="test-key-that-is-long-enough",
        urlopen=urlopen,
        resolve_host=public_resolver,
        sleep=lambda _: None,
    )
    generated = provider.generate(
        prompt="Abstract editorial art inspired by: a calm wide learning scene",
        aspect_ratio="16:9",
        candidate_index=1,
    )
    assert calls == 3
    assert generated.machine_checks["ratio_valid"] is True


def test_images_api_provider_does_not_retry_auth_or_sensitive_prompt() -> None:
    calls = 0

    def unauthorized(request: Any, **_: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", None, BytesIO(b"secret upstream body"))

    provider = ImagesApiProvider(
        api_key="test-key-that-is-long-enough",
        urlopen=unauthorized,
        resolve_host=public_resolver,
        sleep=lambda _: None,
    )
    with pytest.raises(ImageProviderError) as captured:
        provider.generate(
            prompt="Abstract editorial art inspired by: branching paths",
            aspect_ratio="4:3",
            candidate_index=1,
        )
    assert captured.value.code == "image_api_auth_failed"
    assert captured.value.retryable is False
    assert "secret upstream body" not in captured.value.public_message
    assert calls == 1

    with pytest.raises(ImageProviderError) as sensitive:
        provider.generate(
            prompt="Abstract art based on 手机号 13800138000",
            aspect_ratio="4:3",
            candidate_index=1,
        )
    assert sensitive.value.code == "provider_prompt_sensitive"
    assert calls == 1


def test_image_url_validation_allows_proxy_fake_dns_but_keeps_private_ranges_blocked() -> None:
    proxy_provider = ImagesApiProvider(
        api_key="test-key-that-is-long-enough",
        resolve_host=lambda *_args, **_kwargs: [(2, 1, 6, "", ("198.18.0.8", 443))],
    )
    proxy_provider._validate_image_url("https://storage.example.com/output.png")

    with pytest.raises(ImageProviderError) as literal:
        proxy_provider._validate_image_url("https://198.18.0.8/output.png")
    assert literal.value.code == "image_api_url_blocked"

    private_provider = ImagesApiProvider(
        api_key="test-key-that-is-long-enough",
        resolve_host=lambda *_args, **_kwargs: [(2, 1, 6, "", ("10.0.0.8", 443))],
    )
    with pytest.raises(ImageProviderError) as private:
        private_provider._validate_image_url("https://storage.example.com/output.png")
    assert private.value.code == "image_api_url_blocked"


def test_gemini_provider_builds_native_interactions_payload() -> None:
    requests: list[Any] = []
    response = FakeResponse(
        json.dumps(
            {"output_image": {"data": base64.b64encode(png_bytes(1312, 736)).decode("ascii")}}
        ).encode(),
        "application/json",
    )

    def urlopen(request: Any, **_: Any) -> FakeResponse:
        requests.append(request)
        return response

    provider = GeminiImageProvider(
        api_key="gemini-test-key",
        urlopen=urlopen,
        resolve_host=public_resolver,
        sleep=lambda _: None,
    )
    generated = provider.generate(
        prompt="A calm editorial illustration with one clear learning path",
        aspect_ratio="16:9",
        candidate_index=1,
    )
    payload = json.loads(requests[0].data.decode("utf-8"))
    assert payload == {
        "model": "gemini-3.1-flash-image",
        "input": [
            {
                "type": "text",
                "text": "A calm editorial illustration with one clear learning path",
            }
        ],
        "response_format": {
            "type": "image",
            "mime_type": "image/png",
            "aspect_ratio": "16:9",
            "image_size": "1K",
        },
    }
    assert requests[0].headers["X-goog-api-key"] == "gemini-test-key"
    assert generated.provider == "gemini"
    assert generated.machine_checks["ratio_valid"] is True


def test_images_api_provider_rejects_local_or_credentialed_endpoints() -> None:
    for endpoint in (
        "https://localhost/v1/images/generations",
        "https://127.0.0.1/v1/images/generations",
        "https://user:password@example.com/v1/images/generations",
    ):
        with pytest.raises(ValueError):
            ImagesApiProvider(api_key="test-key", endpoint=endpoint)


def test_provider_factory_defaults_to_mock_and_supports_images_api_gemini_and_legacy_agnes() -> None:
    assert create_image_provider_from_env({}).provider == "mock"
    manual = create_image_provider_from_env({"VISUAL_DIRECTOR_IMAGE_PROVIDER": "manual"})
    assert manual.provider == "manual"
    assert manual.configured is False
    with pytest.raises(ImageProviderError) as manual_error:
        manual.generate(prompt="Abstract geometry", aspect_ratio="4:3", candidate_index=1)
    assert manual_error.value.code == "manual_upload_required"

    provider = create_image_provider_from_env({"VISUAL_DIRECTOR_IMAGE_PROVIDER": "images_api"})
    assert provider.provider == "images_api"
    assert provider.configured is False
    with pytest.raises(ImageProviderError) as captured:
        provider.generate(prompt="Abstract geometry", aspect_ratio="4:3", candidate_index=1)
    assert captured.value.code == "image_api_not_configured"

    gemini = create_image_provider_from_env({"VISUAL_DIRECTOR_IMAGE_PROVIDER": "gemini"})
    assert gemini.provider == "gemini"
    assert gemini.configured is False

    legacy = create_image_provider_from_env(
        {
            "VISUAL_DIRECTOR_IMAGE_PROVIDER": "agnes",
            "AGNES_API_KEY": "legacy-key",
        }
    )
    assert legacy.provider == "images_api"
    assert legacy.protocol == "extended"
    assert legacy.model == "agnes-image-2.1-flash"


class FailingImagesProvider:
    provider = "images_api"
    model = "gpt-image-2"
    configured = True

    def generate(self, **_: Any) -> Any:
        raise ImageProviderError(
            "image_api_unavailable",
            "图片服务暂时不可用，自动重试仍未成功。",
            retryable=True,
            http_status=503,
        )


def test_api_persists_sanitized_provider_failure_without_blocking_task(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "failed-provider.db"), image_provider=FailingImagesProvider())
    with TestClient(app) as client:
        markdown = """# 三步配图失败测试

## 行动路径

1. 确定目标
2. 倒推能力
3. 开始行动
"""
        task = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("failure.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()["task"]
        client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": task["version"]},
        )
        detail = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
        plan = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"][0]
        client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/select',
            json={"plan_id": plan["id"], "expected_task_version": detail["version"]},
        )
        listed = client.get(f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots').json()
        slot = listed["items"][0]

        failed = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots/{slot["image_slot_id"]}/generate',
            json={"mode": "start", "expected_image_revision": 1},
        )
        assert failed.status_code == 503
        assert failed.json()["error"]["code"] == "image_api_unavailable"
        assert failed.json()["error"]["retryable"] is True
        assert failed.json()["error"]["details"]["image_revision"] == 2

        state = client.get(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots'
        ).json()["items"][0]["state"]
        assert state["status"] == "failed"
        assert state["image_revision"] == 2
        assert state["candidates"] == []
        assert state["last_error"] == {
            "code": "image_api_unavailable",
            "message": "图片服务暂时不可用，自动重试仍未成功。",
            "retryable": True,
        }
        assert client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]["status"] == "plan_selected"
