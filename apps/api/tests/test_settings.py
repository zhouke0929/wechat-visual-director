from __future__ import annotations

from pathlib import Path

from visual_director.settings import load_runtime_settings, read_env_file
from visual_director.text_planner import create_text_planner_provider_from_env


def test_runtime_settings_load_local_file_without_mutating_or_exposing_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "VISUAL_DIRECTOR_TEXT_PROVIDER=qwen_max\n"
        "DASHSCOPE_API_KEY='local-secret'\n"
        "QWEN_TEXT_MODEL=qwen3.7-max-2026-05-20\n",
        encoding="utf-8",
    )

    settings, source = load_runtime_settings(tmp_path, {"DASHSCOPE_API_KEY": "process-secret"})

    assert source == env_file
    assert settings["VISUAL_DIRECTOR_TEXT_PROVIDER"] == "qwen_max"
    assert settings["DASHSCOPE_API_KEY"] == "process-secret"
    assert read_env_file(env_file)["DASHSCOPE_API_KEY"] == "local-secret"


def test_text_planner_factory_supports_byok_qwen_and_safe_mock_default() -> None:
    assert create_text_planner_provider_from_env({}).provider == "mock_text_planner"
    provider = create_text_planner_provider_from_env(
        {
            "VISUAL_DIRECTOR_TEXT_PROVIDER": "qwen_max",
            "DASHSCOPE_API_KEY": "test-key",
            "QWEN_TEXT_MODEL": "qwen3.7-max-2026-05-20",
        }
    )
    assert provider.provider == "aliyun_qwen"
    assert provider.model == "qwen3.7-max-2026-05-20"
    assert provider.configured is True
