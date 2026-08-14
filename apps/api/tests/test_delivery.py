from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

from visual_director.delivery import build_clipboard_payload, build_delivery_files, build_delivery_zip
from visual_director.wechat_publisher import WechatDraftPublisher


def _revision() -> dict:
    return {
        "id": "revision-1",
        "frozen_html": (
            '<!doctype html><html><body><main style="width:390px;background-color:#FFFEFA;'
            'box-shadow:0 12px 40px rgba(27,41,38,.10);padding:0 24px 34px;">'
            '<header style="padding:34px 0 22px;border-bottom:1px solid #123;">'
            "<h1>测试标题</h1><p>组件库 wechat_components.v0.6.0</p></header>"
            '<h1 style="color:#123">测试标题</h1><img src="asset://body-one" />'
            "</main></body></html>"
        ),
        "frozen_html_hash": "frozen-hash",
        "asset_manifest_hash": "manifest-hash",
        "metadata": {
            "title": "测试标题",
            "author": "运营",
            "digest": "本地摘要",
            "content_source_url": "https://example.com/source",
            "show_cover_pic": True,
        },
    }


def _assets(tmp_path: Path) -> tuple[list[dict], dict[str, tuple[Path, str]]]:
    cover = tmp_path / "cover.png"
    body = tmp_path / "body.png"
    cover.write_bytes(b"cover-bytes")
    body.write_bytes(b"body-bytes")
    assets = [
        {
            "id": "cover-id",
            "asset_token": "cover",
            "asset_role": "cover",
            "relative_filename": "cover.png",
            "content_type": "image/png",
            "output_sha256": "cover-hash",
            "width": 1080,
            "height": 864,
        },
        {
            "id": "body-id",
            "asset_token": "body-one",
            "asset_role": "planned_image",
            "relative_filename": "body.png",
            "content_type": "image/png",
            "output_sha256": "body-hash",
            "width": 960,
            "height": 540,
        },
    ]
    return assets, {"cover-id": (cover, "image/png"), "body-id": (body, "image/png")}


def test_delivery_bundle_contains_portable_provider_neutral_input(tmp_path: Path) -> None:
    assets, paths = _assets(tmp_path)
    files = build_delivery_files(_revision(), assets, lambda asset_id: paths[asset_id])
    article = files["article.md"].decode("utf-8")
    assert "title: 测试标题" in article
    assert "cover: ./assets/cover.png" in article
    assert 'src="./assets/body.png"' in article
    assert "asset://" not in article
    assert "width:100%" in article
    assert "width:390px" not in article
    assert "background-color:#FFFEFA" not in article
    assert "padding:0 0 34px" in article
    assert "组件库 wechat_components.v0.6.0" not in article

    archive = build_delivery_zip(files)
    with zipfile.ZipFile(BytesIO(archive)) as package:
        assert set(package.namelist()) == {
            "article.md",
            "article.html",
            "assets/body.png",
            "assets/cover.png",
            "manifest.json",
        }
        manifest = json.loads(package.read("manifest.json"))
        assert manifest["schema_version"] == "visual_director_delivery.v0.2"


def test_clipboard_payload_uses_absolute_local_asset_urls(tmp_path: Path) -> None:
    assets, _ = _assets(tmp_path)
    payload = build_clipboard_payload(
        _revision(), assets, lambda asset_id: f"http://127.0.0.1:8000/assets/{asset_id}"
    )
    assert 'src="http://127.0.0.1:8000/assets/body-id"' in payload["html"]
    assert payload["cover_url"].endswith("cover-id")
    assert "width:100%" in payload["html"]
    assert "测试标题" in payload["text"]


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.payload


def test_wechat_publisher_classifies_invalid_ip_without_exposing_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_APP_ID", "private-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "private-secret")
    publisher = WechatDraftPublisher(
        tmp_path,
        requester=lambda request, **kwargs: _Response({"errcode": 40164, "errmsg": "invalid ip"}),
    )
    status = publisher.status()
    assert status["ready"] is True
    assert "private-app-id" not in json.dumps(status)
    assets, paths = _assets(tmp_path)
    result = publisher.publish(_revision(), assets, lambda asset_id: paths[asset_id])
    assert result.status == "failed"
    assert result.error["code"] == "wechat_ip_not_whitelisted"


def test_wechat_publisher_uploads_assets_and_creates_draft(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_APP_ID", "local-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "local-secret")
    draft_payloads: list[dict] = []
    upload_count = 0

    def requester(request, **kwargs):
        nonlocal upload_count
        if "/token?" in request.full_url:
            return _Response({"access_token": "memory-only-token", "expires_in": 7200})
        if "/material/add_material?" in request.full_url:
            upload_count += 1
            return _Response({"media_id": f"MEDIA_{upload_count}", "url": f"https://mmbiz.qpic.cn/{upload_count}"})
        if "/draft/add?" in request.full_url:
            draft_payloads.append(json.loads(request.data.decode("utf-8")))
            return _Response({"media_id": "DRAFT_MEDIA_001"})
        raise AssertionError(request.full_url)

    assets, paths = _assets(tmp_path)
    result = WechatDraftPublisher(tmp_path, requester=requester).publish(
        _revision(), assets, lambda asset_id: paths[asset_id]
    )
    assert result.status == "succeeded"
    assert result.media_id == "DRAFT_MEDIA_001"
    assert upload_count == 2
    article = draft_payloads[0]["articles"][0]
    assert article["thumb_media_id"] == "MEDIA_1"
    assert 'src="https://mmbiz.qpic.cn/2"' in article["content"]
    assert article["digest"] == "本地摘要"


def test_wechat_publisher_marks_create_draft_timeout_unknown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_APP_ID", "private-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "private-secret")

    def requester(request, **kwargs):
        if "/token?" in request.full_url:
            return _Response({"access_token": "private-token", "expires_in": 7200})
        if "/material/add_material?" in request.full_url:
            return _Response({"media_id": "MEDIA", "url": "https://mmbiz.qpic.cn/body"})
        raise TimeoutError("timed out")

    assets, paths = _assets(tmp_path)
    result = WechatDraftPublisher(tmp_path, requester=requester).publish(
        _revision(), assets, lambda asset_id: paths[asset_id]
    )
    assert result.status == "unknown"
    assert result.error["retryable"] is False
    serialized = json.dumps(result.error)
    assert "private-app-id" not in serialized
    assert "private-secret" not in serialized
    assert "private-token" not in serialized
