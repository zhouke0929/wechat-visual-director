from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from visual_director import cli
from visual_director.main import create_app
from visual_director.onboarding import PublicIpProbe, WechatConnectionProbe
from visual_director.settings import read_env_file


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class _WechatPublisherReady:
    def status(self) -> dict:
        return {
            "schema_version": "publisher_status.v0.3",
            "provider": "wechat_api",
            "transport": "built_in",
            "credentials_configured": True,
            "ready": True,
            "warnings": [],
        }


class _WechatProbeReady:
    def __init__(self) -> None:
        self.calls = 0

    def probe(self, app_id: str, app_secret: str) -> dict:
        self.calls += 1
        assert app_id == "fake-app-id"
        assert app_secret == "fake-secret-never-return"
        return {
            "ok": True,
            "schema_version": "wechat_connection_probe.v0.1",
            "code": "wechat_connection_ready",
            "message": "ready",
            "retryable": False,
            "checked_at": "2026-08-05T00:00:00+00:00",
            "provider_code": None,
            "access_token_persisted": False,
            "draft_created": False,
        }


class _PublicIpReady:
    def __init__(self) -> None:
        self.calls = 0

    def probe(self) -> dict:
        self.calls += 1
        return {
            "ok": True,
            "schema_version": "public_ip_probe.v0.1",
            "code": "public_ip_detected",
            "message": "ready",
            "public_ip": "203.0.113.8",
            "ip_version": 4,
            "checked_at": "2026-08-05T00:00:00+00:00",
            "external_request_performed": True,
        }


def _app(monkeypatch, tmp_path: Path):
    for key in (
        "WECHAT_APP_ID",
        "WECHAT_APP_SECRET",
        "VISUAL_DIRECTOR_IMAGE_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / "private" / ".env.local"
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(env_file))
    wechat_probe = _WechatProbeReady()
    public_ip_probe = _PublicIpReady()
    app = create_app(
        str(tmp_path / "onboarding.db"),
        wechat_publisher=_WechatPublisherReady(),
        wechat_connection_probe=wechat_probe,
        public_ip_probe=public_ip_probe,
    )
    return app, env_file, wechat_probe, public_ip_probe


def test_setup_preferences_are_machine_scoped_and_local_only(monkeypatch, tmp_path: Path) -> None:
    app, _env_file, wechat_probe, public_ip_probe = _app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        initial = client.get("/api/v1/settings/setup-preferences")
        assert initial.json()["settings"]["target_mode"] == "typeset_only"

        denied = client.put(
            "/api/v1/settings/setup-preferences",
            json={"target_mode": "full_delivery"},
        )
        assert denied.status_code == 403

        saved = client.put(
            "/api/v1/settings/setup-preferences",
            headers={"X-Settings-Intent": "local-operator"},
            json={"target_mode": "full_delivery"},
        )
        assert saved.status_code == 200
        assert saved.json()["settings"]["target_mode"] == "full_delivery"

    assert wechat_probe.calls == 0
    assert public_ip_probe.calls == 0
    preferences_path = tmp_path / "private" / "setup-preferences.json"
    assert json.loads(preferences_path.read_text(encoding="utf-8"))["target_mode"] == "full_delivery"


def test_wechat_credentials_are_write_only_and_probe_creates_no_draft(monkeypatch, tmp_path: Path) -> None:
    app, env_file, probe, _public_ip = _app(monkeypatch, tmp_path)
    secret = "fake-secret-never-return"
    with TestClient(app) as client:
        saved = client.put(
            "/api/v1/settings/wechat-publisher",
            headers={"X-Settings-Intent": "local-operator"},
            json={
                "app_id": "fake-app-id",
                "app_secret": secret,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["settings"]["credentials_configured"] is True
        assert saved.json()["settings"]["secrets_returned"] is False
        assert "ip_whitelist_confirmed" not in saved.json()["settings"]
        assert secret not in saved.text
        assert "fake-app-id" not in saved.text

        checked = client.post(
            "/api/v1/settings/wechat-publisher/probe",
            headers={"X-Settings-Intent": "local-operator"},
        )
        assert checked.status_code == 200
        assert checked.json()["ok"] is True
        assert checked.json()["access_token_persisted"] is False
        assert checked.json()["draft_created"] is False
        assert secret not in checked.text

        settings = client.get("/api/v1/settings/wechat-publisher").json()["settings"]
        assert settings["connection_probe"]["ok"] is True
        assert secret not in json.dumps(settings)

    assert probe.calls == 1
    values = read_env_file(env_file)
    assert values["WECHAT_APP_ID"] == "fake-app-id"
    assert values["WECHAT_APP_SECRET"] == secret


def test_full_delivery_capability_becomes_ready_after_explicit_probe(monkeypatch, tmp_path: Path) -> None:
    app, _env_file, _probe, _public_ip = _app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        headers = {"X-Settings-Intent": "local-operator"}
        client.put(
            "/api/v1/settings/setup-preferences",
            headers=headers,
            json={"target_mode": "full_delivery"},
        )
        client.put(
            "/api/v1/settings/wechat-publisher",
            headers=headers,
            json={"app_id": "fake-app-id", "app_secret": "fake-secret-never-return"},
        )
        before = client.get("/api/v1/settings/capabilities").json()["settings"]
        assert before["complete_for_target"] is False
        assert before["next_action"] == "configure_image_provider"

        image_saved = client.put(
            "/api/v1/settings/image-provider",
            headers=headers,
            json={
                "mode": "images_api",
                "api_key": "fake-image-key",
                "endpoint": "https://example.invalid/v1/images/generations",
                "model": "fake-image-model",
                "protocol": "openai",
                "size": "auto",
            },
        )
        assert image_saved.status_code == 200
        client.post("/api/v1/settings/wechat-publisher/probe", headers=headers)
        ready = client.get("/api/v1/settings/capabilities").json()["settings"]
        assert ready["complete_for_target"] is True
        assert ready["next_action"] == "create_article"
        assert ready["capabilities"]["wechat_draft"]["connection_ok"] is True


def test_public_ip_probe_is_explicit_and_persists_only_a_hash(monkeypatch, tmp_path: Path) -> None:
    app, _env_file, _wechat, probe = _app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.get("/api/v1/settings/capabilities")
        assert probe.calls == 0
        response = client.post(
            "/api/v1/settings/network/public-ip-probe",
            headers={"X-Settings-Intent": "local-operator"},
        )
        assert response.status_code == 200
        assert response.json()["public_ip"] == "203.0.113.8"
        assert probe.calls == 1

    status_text = (tmp_path / "private" / "provider-status.json").read_text(encoding="utf-8")
    assert "public_ip_sha256" in status_text
    assert "203.0.113.8" not in status_text


def test_wechat_probe_classifies_ip_whitelist_without_leaking_credentials() -> None:
    def opener(_request, **_kwargs):
        return _Response(b'{"errcode":40164,"errmsg":"invalid ip"}')

    result = WechatConnectionProbe(opener=opener).probe("app-id", "top-secret")
    assert result["ok"] is False
    assert result["code"] == "wechat_ip_not_whitelisted"
    assert "top-secret" not in json.dumps(result)


def test_public_ip_adapter_validates_provider_response() -> None:
    responses = iter([b"not-an-ip", b'{"ip":"203.0.113.9"}'])

    def opener(_request, **_kwargs):
        return _Response(next(responses))

    result = PublicIpProbe(endpoints=("https://one.invalid", "https://two.invalid"), opener=opener).probe()
    assert result["ok"] is True
    assert result["public_ip"] == "203.0.113.9"


def test_cli_public_ip_uses_shared_adapter(monkeypatch, capsys) -> None:
    class _Probe:
        def __init__(self, **_kwargs) -> None:
            pass

        def probe(self) -> dict:
            return {"ok": True, "schema_version": "public_ip_probe.v0.1", "public_ip": "203.0.113.10"}

    monkeypatch.setattr(cli, "PublicIpProbe", _Probe)
    assert cli.run(["network", "public-ip", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["public_ip"] == "203.0.113.10"
