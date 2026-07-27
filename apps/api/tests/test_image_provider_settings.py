from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from visual_director.main import create_app
from visual_director.settings import read_env_file, update_env_file


IMAGE_ENV_KEYS = (
    "VISUAL_DIRECTOR_IMAGE_PROVIDER",
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
        "# existing settings\nOTHER_SETTING=keep\nAGNES_API_KEY=old-value\n",
        encoding="utf-8",
    )

    update_env_file(
        env_file,
        {
            "VISUAL_DIRECTOR_IMAGE_PROVIDER": "agnes",
            "AGNES_API_KEY": "new-secret",
        },
    )

    assert read_env_file(env_file) == {
        "OTHER_SETTING": "keep",
        "AGNES_API_KEY": "new-secret",
        "VISUAL_DIRECTOR_IMAGE_PROVIDER": "agnes",
    }
    contents = env_file.read_text(encoding="utf-8")
    assert contents.count("AGNES_API_KEY=") == 1
    assert not list(tmp_path.glob(".*.tmp"))


def test_image_settings_write_only_key_and_hot_reload(monkeypatch, tmp_path: Path) -> None:
    app, env_file = _isolated_settings_app(monkeypatch, tmp_path)
    secret = "agnes-test-secret-never-return"

    with TestClient(app) as client:
        initial = client.get("/api/v1/settings/image-provider")
        assert initial.status_code == 200
        assert initial.json()["settings"]["mode"] == "mock"
        assert initial.json()["settings"]["api_key_configured"] is False

        denied = client.put(
            "/api/v1/settings/image-provider",
            json={"mode": "agnes", "api_key": secret},
        )
        assert denied.status_code == 403

        saved = client.put(
            "/api/v1/settings/image-provider",
            headers={"X-Settings-Intent": "local-operator"},
            json={"mode": "agnes", "api_key": secret},
        )
        assert saved.status_code == 200
        body = saved.json()
        assert body["settings"]["mode"] == "agnes"
        assert body["settings"]["active_provider"] == "agnes"
        assert body["settings"]["api_key_configured"] is True
        assert body["settings"]["real_generation_available"] is True
        assert body["settings"]["restart_required"] is False
        assert secret not in saved.text
        assert not any("api_key" in key.lower() and key != "api_key_configured" for key in body["settings"])

        refreshed = client.get("/api/v1/settings/image-provider")
        assert refreshed.json()["settings"]["api_key_configured"] is True
        assert secret not in refreshed.text

    assert read_env_file(env_file)["AGNES_API_KEY"] == secret
    assert read_env_file(env_file)["VISUAL_DIRECTOR_IMAGE_PROVIDER"] == "agnes"


def test_image_settings_can_clear_key_without_deleting_other_values(monkeypatch, tmp_path: Path) -> None:
    app, env_file = _isolated_settings_app(monkeypatch, tmp_path)
    update_env_file(
        env_file,
        {
            "OTHER_SETTING": "keep",
            "VISUAL_DIRECTOR_IMAGE_PROVIDER": "agnes",
            "AGNES_API_KEY": "to-be-cleared",
        },
    )
    # The app was created before the test fixture wrote the file; saving still
    # rereads the current private file and hot-reloads the provider.
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/settings/image-provider",
            headers={"X-Settings-Intent": "local-operator"},
            json={"mode": "manual", "clear_api_key": True},
        )
        assert response.status_code == 200
        settings = response.json()["settings"]
        assert settings["mode"] == "manual"
        assert settings["active_provider"] == "manual"
        assert settings["api_key_configured"] is False
        assert "to-be-cleared" not in response.text

    values = read_env_file(env_file)
    assert values["OTHER_SETTING"] == "keep"
    assert values["AGNES_API_KEY"] == ""


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
        update_env_file(env_file, {"AGNES_API_KEY": f"line-one{os.linesep}line-two"})
    except ValueError as error:
        assert "forbidden character" in str(error)
    else:
        raise AssertionError("multiline environment value should be rejected")
