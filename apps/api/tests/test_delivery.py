from __future__ import annotations

import json
import os
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

from visual_director.delivery import (
    WenyanPublisher,
    build_clipboard_payload,
    build_delivery_files,
    build_delivery_zip,
)


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


def test_delivery_bundle_contains_portable_wenyan_input(tmp_path: Path) -> None:
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
    assert "box-shadow:0 12px 40px" not in article
    assert "padding:0 24px 34px" not in article
    assert "padding:0 0 34px" in article
    assert "组件库 wechat_components.v0.6.0" not in article
    assert "width:390px" not in files["article.html"].decode("utf-8")
    assert "本地摘要" not in article

    archive = build_delivery_zip(files)
    with zipfile.ZipFile(BytesIO(archive)) as package:
        assert set(package.namelist()) == {
            "article.md",
            "article.html",
            "assets/body.png",
            "assets/cover.png",
            "manifest.json",
            "visual-director-theme.css",
        }
        manifest = json.loads(package.read("manifest.json"))
        assert manifest["revision_id"] == "revision-1"


def test_clipboard_payload_uses_absolute_local_asset_urls(tmp_path: Path) -> None:
    assets, _ = _assets(tmp_path)
    payload = build_clipboard_payload(
        _revision(),
        assets,
        lambda asset_id: f"http://127.0.0.1:8000/assets/{asset_id}",
    )
    assert 'src="http://127.0.0.1:8000/assets/body-id"' in payload["html"]
    assert payload["cover_url"].endswith("cover-id")
    assert "width:100%" in payload["html"]
    assert "width:390px" not in payload["html"]
    assert "background-color:#FFFEFA" not in payload["html"]
    assert "box-shadow:0 12px 40px" not in payload["html"]
    assert "padding:0 24px 34px" not in payload["html"]
    assert "组件库 wechat_components.v0.6.0" not in payload["html"]
    assert "测试标题" in payload["text"]


def test_wenyan_publisher_classifies_invalid_ip_without_exposing_credentials(tmp_path: Path, monkeypatch) -> None:
    command = tmp_path / "wenyan.exe"
    command.write_bytes(b"")
    monkeypatch.setenv("WECHAT_APP_ID", "private-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "private-secret")

    def runner(args, **kwargs):
        if "--version" in args:
            return subprocess.CompletedProcess(args, 0, stdout="2.0.11\n", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="40164 invalid ip 203.0.113.8 not in whitelist")

    publisher = WenyanPublisher(tmp_path, command=str(command), runner=runner)
    status = publisher.status()
    assert status["ready"] is True
    assert "private-app-id" not in json.dumps(status)
    assert "private-secret" not in json.dumps(status)

    result = publisher.publish({"article.md": b"# test", "visual-director-theme.css": b""})
    assert result.status == "failed"
    assert result.error["code"] == "wechat_ip_not_whitelisted"


def test_wenyan_publisher_launches_windows_cmd_shim(tmp_path: Path, monkeypatch) -> None:
    if os.name != "nt":
        return
    command = tmp_path / "wenyan.cmd"
    command.write_text(
        "@echo off\r\n"
        "if \"%1\"==\"--version\" (echo 2.0.11) else (echo 发布成功，Media ID: WINDOWS_CMD_MEDIA)\r\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WECHAT_APP_ID", "local-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "local-secret")
    publisher = WenyanPublisher(tmp_path, command=str(command))
    assert publisher.status()["ready"] is True
    result = publisher.publish({"article.md": b"# test", "visual-director-theme.css": b""})
    assert result.status == "succeeded"
    assert result.media_id == "WINDOWS_CMD_MEDIA"


def test_wenyan_publisher_accepts_confirmed_media_id_even_when_wrapper_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    command = tmp_path / "wenyan.exe"
    command.write_bytes(b"")
    monkeypatch.setenv("WECHAT_APP_ID", "local-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "local-secret")

    def runner(args, **kwargs):
        if "--version" in args:
            return subprocess.CompletedProcess(args, 0, stdout="2.0.11\n", stderr="")
        return subprocess.CompletedProcess(
            args,
            1,
            stdout='发布成功，{\"media_id\": \"CONFIRMED_MEDIA_002\"}',
            stderr="wrapper cleanup failed",
        )

    result = WenyanPublisher(tmp_path, command=str(command), runner=runner).publish(
        {"article.md": b"# test", "visual-director-theme.css": b""}
    )
    assert result.status == "succeeded"
    assert result.media_id == "CONFIRMED_MEDIA_002"


def test_wenyan_publisher_unknown_result_keeps_only_redacted_diagnostics(tmp_path: Path, monkeypatch) -> None:
    command = tmp_path / "wenyan.exe"
    command.write_bytes(b"")
    monkeypatch.setenv("WECHAT_APP_ID", "private-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "private-secret")

    def runner(args, **kwargs):
        if "--version" in args:
            return subprocess.CompletedProcess(args, 0, stdout="2.0.11\n", stderr="")
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="publish completed without a receipt",
            stderr="private-app-id private-secret",
        )

    result = WenyanPublisher(tmp_path, command=str(command), runner=runner).publish(
        {"article.md": b"# test", "visual-director-theme.css": b""}
    )
    assert result.status == "unknown"
    diagnostics = result.error["diagnostics"]
    assert diagnostics["return_code"] == 0
    assert diagnostics["stdout_chars"] > 0
    assert diagnostics["stderr_chars"] > 0
    assert diagnostics["media_id_detected"] is False
    serialized = json.dumps(result.error)
    assert "private-app-id" not in serialized
    assert "private-secret" not in serialized
