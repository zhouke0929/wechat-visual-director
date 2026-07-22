from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from visual_director.image_provider import (
    AgnesImageProvider,
    ImageProviderError,
    build_provider_prompt,
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


def test_provider_prompt_routes_article_style_without_leaking_raw_copy() -> None:
    atmosphere = build_provider_prompt(
        prompt_slot(
            purpose="atmosphere",
            subject="扫码了解华东师范大学3+1项目，官方注册，联系电话不要外发",
        ),
        "data_policy",
    )
    assert "扫码" not in atmosphere
    assert "华东师范大学" not in atmosphere
    assert "deep navy" in atmosphere
    assert "full-bleed editorial illustration" in atmosphere
    assert "no QR code" in atmosphere
    assert "no text" in atmosphere

    structured = build_provider_prompt(
        prompt_slot(purpose="structured_infographic", subject="冲稳保三个梯度", item_count=3),
        "tutorial_steps",
    )
    assert "exactly 3 large empty rounded content zones" in structured
    assert "later deterministic 3-node text overlay" in structured
    assert "forest green" in structured
    assert "冲稳保" not in structured


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


def test_agnes_provider_builds_official_payload_downloads_and_validates_image() -> None:
    requests: list[Any] = []
    responses = [
        FakeResponse(
            json.dumps({"created": 1, "data": [{"url": "https://storage.example.com/output.png"}]}).encode(),
            "application/json",
        ),
        FakeResponse(png_bytes(), "image/png"),
    ]

    def urlopen(request: Any, **_: Any) -> FakeResponse:
        requests.append(request)
        return responses.pop(0)

    provider = AgnesImageProvider(
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
        "model": "agnes-image-2.1-flash",
        "prompt": "Abstract editorial art inspired by: three learning paths, clean paper geometry",
        "size": "1K",
        "ratio": "4:3",
        "extra_body": {"response_format": "url"},
    }
    assert requests[0].headers["Authorization"] == "Bearer test-key-that-is-long-enough"
    assert generated.provider == "agnes"
    assert generated.content_type == "image/png"
    assert (generated.width, generated.height) == (1152, 864)
    assert generated.machine_checks["ratio_valid"] is True


def test_agnes_provider_retries_one_transient_failure_only() -> None:
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

    provider = AgnesImageProvider(
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


def test_agnes_provider_does_not_retry_auth_or_sensitive_prompt() -> None:
    calls = 0

    def unauthorized(request: Any, **_: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", None, BytesIO(b"secret upstream body"))

    provider = AgnesImageProvider(
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
    assert captured.value.code == "agnes_auth_failed"
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
    proxy_provider = AgnesImageProvider(
        api_key="test-key-that-is-long-enough",
        resolve_host=lambda *_args, **_kwargs: [(2, 1, 6, "", ("198.18.0.8", 443))],
    )
    proxy_provider._validate_image_url("https://storage.example.com/output.png")

    with pytest.raises(ImageProviderError) as literal:
        proxy_provider._validate_image_url("https://198.18.0.8/output.png")
    assert literal.value.code == "agnes_image_url_blocked"

    private_provider = AgnesImageProvider(
        api_key="test-key-that-is-long-enough",
        resolve_host=lambda *_args, **_kwargs: [(2, 1, 6, "", ("10.0.0.8", 443))],
    )
    with pytest.raises(ImageProviderError) as private:
        private_provider._validate_image_url("https://storage.example.com/output.png")
    assert private.value.code == "agnes_image_url_blocked"

def test_provider_factory_defaults_to_mock_and_allows_unconfigured_agnes() -> None:
    assert create_image_provider_from_env({}).provider == "mock"
    provider = create_image_provider_from_env({"VISUAL_DIRECTOR_IMAGE_PROVIDER": "agnes"})
    assert provider.provider == "agnes"
    assert provider.configured is False
    with pytest.raises(ImageProviderError) as captured:
        provider.generate(prompt="Abstract geometry", aspect_ratio="4:3", candidate_index=1)
    assert captured.value.code == "agnes_not_configured"


class FailingAgnesProvider:
    provider = "agnes"
    model = "agnes-image-2.1-flash"
    configured = True

    def generate(self, **_: Any) -> Any:
        raise ImageProviderError(
            "agnes_unavailable",
            "Agnes 服务暂时不可用，自动重试仍未成功。",
            retryable=True,
            http_status=503,
        )


def test_api_persists_sanitized_provider_failure_without_blocking_task(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "failed-provider.db"), image_provider=FailingAgnesProvider())
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
        assert failed.json()["error"]["code"] == "agnes_unavailable"
        assert failed.json()["error"]["retryable"] is True
        assert failed.json()["error"]["details"]["image_revision"] == 2

        state = client.get(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots'
        ).json()["items"][0]["state"]
        assert state["status"] == "failed"
        assert state["image_revision"] == 2
        assert state["candidates"] == []
        assert state["last_error"] == {
            "code": "agnes_unavailable",
            "message": "Agnes 服务暂时不可用，自动重试仍未成功。",
            "retryable": True,
        }
        assert client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]["status"] == "plan_selected"
