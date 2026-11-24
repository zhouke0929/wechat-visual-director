from __future__ import annotations

from pathlib import Path

from visual_director.settings import load_runtime_settings, read_env_file


def test_runtime_settings_load_local_file_without_mutating_or_exposing_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "VISUAL_DIRECTOR_IMAGE_PROVIDER=images_api\n"
        "IMAGE_API_KEY='local-secret'\n"
        "IMAGE_API_MODEL=seedream-test\n",
        encoding="utf-8",
    )

    settings, source = load_runtime_settings(tmp_path, {"IMAGE_API_KEY": "process-secret"})

    assert source == env_file
    assert settings["VISUAL_DIRECTOR_IMAGE_PROVIDER"] == "images_api"
    assert settings["IMAGE_API_KEY"] == "process-secret"
    assert read_env_file(env_file)["IMAGE_API_KEY"] == "local-secret"
