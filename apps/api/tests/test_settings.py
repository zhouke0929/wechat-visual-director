from __future__ import annotations

from pathlib import Path

from visual_director.settings import load_runtime_settings, read_env_file
from visual_director.text_planner import create_text_planner_provider_from_env


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


def test_text_planner_factory_uses_rule_fallback_and_ignores_retired_qwen_settings() -> None:
    default_provider = create_text_planner_provider_from_env({})
    assert default_provider.provider == "rule_text_planner"
    assert default_provider.configured is False
    provider = create_text_planner_provider_from_env(
        {
            "VISUAL_DIRECTOR_TEXT_PROVIDER": "qwen_max",
            "DASHSCOPE_API_KEY": "test-key",
            "QWEN_TEXT_MODEL": "qwen3.7-max-2026-05-20",
        }
    )
    assert provider.provider == "rule_text_planner"
    assert provider.model == "deterministic_editorial_brief"
    assert provider.configured is False
