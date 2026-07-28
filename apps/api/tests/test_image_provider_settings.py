from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from visual_director.main import create_app
from visual_director.settings import read_env_file, update_env_file


IMAGE_ENV_KEYS = (
    "VISUAL_DIRECTOR_IMAGE_PROVIDER",
    "IMAGE_API_KEY",
    "IMAGE_API_ENDPOINT",
    "IMAGE_API_MODEL",
    "IMAGE_API_PROTOCOL",
    "IMAGE_API_SIZE",
    "GEMINI_API_KEY",
    "GEMINI_IMAGE_ENDPOINT",
    "GEMINI_IMAGE_MODEL",
    "GEMINI_IMAGE_SIZE",
    "AGNES_API_KEY",
    "AGNES_IMAGE_ENDPOINT",
    "AGNES_IMAGE_MODEL",
    "AGNES_IMAGE_SIZE",
)


def _isolated_settings_app(monkeypatch, tmp_path: Path):
    for key in IMAGE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / "private" / ".env.local"
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(env_file))
    return create_app(str(tmp_path / "settings.db")), env_file


def test_update_env_file_is_atomic_and_preserves_unrelated_lines(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "# existing settings\nOTHER_SETTING=keep\nIMAGE_API_KEY=old-value\n",
        encoding="utf-8",
    )

    update_env_file(
        env_file,
        {
            "VISUAL_DIRECTOR_IMAGE_PROVIDER": "images_api",
            "IMAGE_API_KEY": "new-secret",
        },
    )

    assert read_env_file(env_file) == {
        "OTHER_SETTING": "keep",
        "IMAGE_API_KEY": "new-secret",
        "VISUAL_DIRECTOR_IMAGE_PROVIDER": "images_api",
    }
    contents = env_file.read_text(encoding="utf-8")
    assert contents.count("IMAGE_API_KEY=") == 1
    assert not list(tmp_path.glob(".*.tmp"))


def test_image_settings_write_only_key_and_hot_reload(monkeypatch, tmp_path: Path) -> None:
    app, env_file = _isolated_settings_app(monkeypatch, tmp_path)
    secret = "images-test-secret-never-return"

    with TestClient(app) as client:
        initial = client.get("/api/v1/settings/image-provider")
        assert initial.status_code == 200
        assert initial.json()["settings"]["mode"] == "mock"
        assert initial.json()["settings"]["api_key_configured"] is False

        denied = client.put(
            "/api/v1/settings/image-provider",
            json={"mode": "images_api", "api_key": secret},
        )
        assert denied.status_code == 403

        saved = client.put(
            "/api/v1/settings/image-provider",
            headers={"X-Settings-Intent": "local-operator"},
            json={
                "mode": "images_api",
                "api_key": secret,
                "endpoint": "https://api.openai.com/v1/images/generations",
                "model": "gpt-image-2",
                "protocol": "openai",
                "size": "auto",
            },
        )
        assert saved.status_code == 200
        body = saved.json()
        assert body["settings"]["schema_version"] == "image_provider_settings.v0.2"
        assert body["settings"]["mode"] == "images_api"
        assert body["settings"]["active_provider"] == "images_api"
        assert body["settings"]["api_key_configured"] is True
        assert body["settings"]["real_generation_available"] is True
        assert body["settings"]["restart_required"] is False
        assert secret not in saved.text
        assert not any("api_key" in key.lower() and key != "api_key_configured" for key in body["settings"])

        refreshed = client.get("/api/v1/settings/image-provider")
        assert refreshed.json()["settings"]["api_key_configured"] is True
        assert secret not in refreshed.text

    assert read_env_file(env_file)["IMAGE_API_KEY"] == secret
    assert read_env_file(env_file)["VISUAL_DIRECTOR_IMAGE_PROVIDER"] == "images_api"


def test_image_settings_accept_ark_agent_plan_without_replacing_key(monkeypatch, tmp_path: Path) -> None:
    app, env_file = _isolated_settings_app(monkeypatch, tmp_path)
    update_env_file(
        env_file,
        {
            "VISUAL_DIRECTOR_IMAGE_PROVIDER": "images_api",
            "IMAGE_API_KEY": "agent-plan-secret-never-return",
            "IMAGE_API_ENDPOINT": "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            "IMAGE_API_MODEL": "old-model",
            "IMAGE_API_PROTOCOL": "ark",
            "IMAGE_API_SIZE": "1K",
        },
    )

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/settings/image-provider",
            headers={"X-Settings-Intent": "local-operator"},
            json={
                "mode": "images_api",
                "endpoint": "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations",
                "model": "doubao-seedream-5.0-lite",
                "protocol": "ark_plan",
                "size": "2K",
            },
        )
        assert response.status_code == 200
        settings = response.json()["settings"]
        assert settings["mode"] == "images_api"
        assert settings["api_key_configured"] is True
        images_api = settings["providers"]["images_api"]
        assert images_api["endpoint"] == "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"
        assert images_api["model"] == "doubao-seedream-5.0-lite"
        assert images_api["protocol"] == "ark_plan"
        assert images_api["size"] == "2K"
        assert images_api["api_key_configured"] is True
        assert "agent-plan-secret-never-return" not in response.text

    values = read_env_file(env_file)
    assert values["IMAGE_API_KEY"] == "agent-plan-secret-never-return"
    assert values["IMAGE_API_PROTOCOL"] == "ark_plan"
    assert values["IMAGE_API_SIZE"] == "2K"


def test_image_settings_can_clear_key_without_deleting_other_values(monkeypatch, tmp_path: Path) -> None:
    app, env_file = _isolated_settings_app(monkeypatch, tmp_path)
    update_env_file(
        env_file,
        {
            "OTHER_SETTING": "keep",
            "VISUAL_DIRECTOR_IMAGE_PROVIDER": "images_api",
            "IMAGE_API_KEY": "to-be-cleared",
            "AGNES_API_KEY": "legacy-key-must-not-resurface",
        },
    )
    # The app was created before the test fixture wrote the file; saving still
    # rereads the current private file and hot-reloads the provider.
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/settings/image-provider",
            headers={"X-Settings-Intent": "local-operator"},
            json={"mode": "images_api", "clear_api_key": True},
        )
        assert response.status_code == 200
        settings = response.json()["settings"]
        assert settings["mode"] == "images_api"
        assert settings["active_provider"] == "images_api"
        assert settings["api_key_configured"] is False
        assert "to-be-cleared" not in response.text

    values = read_env_file(env_file)
    assert values["OTHER_SETTING"] == "keep"
    assert values["IMAGE_API_KEY"] == ""
    assert values["AGNES_API_KEY"] == "legacy-key-must-not-resurface"


def test_gemini_settings_use_a_separate_write_only_key(monkeypatch, tmp_path: Path) -> None:
    app, env_file = _isolated_settings_app(monkeypatch, tmp_path)
    secret = "gemini-secret-never-return"

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/settings/image-provider",
            headers={"X-Settings-Intent": "local-operator"},
            json={
                "mode": "gemini",
                "api_key": secret,
                "model": "gemini-3.1-flash-image",
                "size": "2K",
            },
        )
        assert response.status_code == 200
        settings = response.json()["settings"]
        assert settings["mode"] == "gemini"
        assert settings["active_provider"] == "gemini"
        assert settings["providers"]["gemini"]["size"] == "2K"
        assert settings["api_key_configured"] is True
        assert secret not in response.text

    values = read_env_file(env_file)
    assert values["GEMINI_API_KEY"] == secret
    assert "IMAGE_API_KEY" not in values


def test_image_settings_refuse_to_override_process_environment(monkeypatch, tmp_path: Path) -> None:
    for key in IMAGE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env.local"
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(env_file))
    monkeypatch.setenv("VISUAL_DIRECTOR_IMAGE_PROVIDER", "manual")
    app = create_app(str(tmp_path / "managed.db"))

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/settings/image-provider",
            headers={"X-Settings-Intent": "local-operator"},
            json={"mode": "mock"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "image_settings_environment_managed"

    assert not env_file.exists()


def test_env_writer_rejects_multiline_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    try:
        update_env_file(env_file, {"IMAGE_API_KEY": f"line-one{os.linesep}line-two"})
    except ValueError as error:
        assert "forbidden character" in str(error)
    else:
        raise AssertionError("multiline environment value should be rejected")
