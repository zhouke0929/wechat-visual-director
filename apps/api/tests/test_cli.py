from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from visual_director import cli


def test_cli_json_forces_utf8_when_windows_runner_defaults_to_cp1252() -> None:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "visual_director.cli",
            "task",
            "status",
            "missing-task",
            "--api-base",
            "http://127.0.0.1:1/api/v1",
            "--web-base",
            "http://127.0.0.1:1",
            "--json",
        ],
        capture_output=True,
        env=env,
        timeout=15,
        check=False,
    )
    payload = json.loads(result.stdout.decode("utf-8"))
    assert payload["ok"] is False
    assert any(ord(character) > 127 for character in payload["error"]["message"])


def test_web_probe_requires_current_workbench_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda url, **_kwargs: {
            "application": cli.WORKBENCH_ID,
            "application_version": cli.application_version(),
        }
        if url.endswith("/api/health")
        else None,
    )

    assert cli._probe_web("http://127.0.0.1:3000") is True

    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "application": cli.WORKBENCH_ID,
            "application_version": "0.1.0-alpha.1",
        },
    )
    assert cli._probe_web("http://127.0.0.1:3000") is False


def test_windows_batch_launch_supports_path_with_spaces(tmp_path: Path) -> None:
    if os.name != "nt":
        return
    shim_dir = tmp_path / "TRAE SOLO CN" / "tools" / "node"
    shim_dir.mkdir(parents=True)
    shim = shim_dir / "pnpm.CMD"
    shim.write_text("@echo off\r\necho host-shim-ok\r\n", encoding="ascii")

    launch = cli._platform_launch_command([str(shim), "dev"])
    result = subprocess.run(
        launch,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    assert "host-shim-ok" in result.stdout


def test_web_process_recognition_accepts_production_and_legacy_modes() -> None:
    assert cli._command_matches_service("web", "pnpm.CMD start -H 127.0.0.1 -p 3000")
    assert cli._command_matches_service("web", "pnpm.CMD dev -H 127.0.0.1 -p 3000")
    assert cli._command_matches_service(
        "web",
        r"node C:\app\node_modules\next\dist\bin\next start -H 127.0.0.1 -p 3000",
    )
    assert not cli._command_matches_service("web", "pnpm.CMD build")


def test_api_process_recognition_accepts_silent_and_legacy_hosts() -> None:
    assert cli._command_matches_service(
        "api",
        r"C:\app\pythonw.exe -m visual_director.service_host --port 8000",
    )
    assert cli._command_matches_service(
        "api",
        r"C:\app\python.exe -m uvicorn visual_director.main:app --port 8000",
    )
    assert not cli._command_matches_service("api", "python.exe unrelated.py")


def test_service_python_prefers_no_console_executable(tmp_path: Path) -> None:
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.write_bytes(b"")
    pythonw.write_bytes(b"")

    assert cli._service_python_executable(python, platform_name="nt") == str(
        pythonw.resolve()
    )
    assert cli._service_python_executable(python, platform_name="posix") == str(
        python.resolve()
    )


def test_image_context_exposes_theme_bound_host_requests(monkeypatch) -> None:
    args = cli.build_parser().parse_args(
        ["image", "context", "task-1", "--no-start", "--json"]
    )

    def fake_request(method: str, url: str, **_kwargs):
        assert method == "GET"
        if url.endswith("/article-tasks/task-1"):
            return {"task": {"selected_plan_id": "plan-1"}}
        assert url.endswith(
            "/article-tasks/task-1/plans/plan-1/host-image-context?asset_type=body_image"
        )
        return {
            "visual_system": "youth_campus",
            "plan_revision": 3,
            "prompt_version": "v1",
            "requests": [
                {
                    "request_id": "request-12345678",
                    "image_slot_id": "image-01",
                    "expected_plan_revision": 3,
                    "expected_image_revision": 1,
                    "prompt": "draw this",
                }
            ],
            "output_rules": ["do not auto accept"],
        }

    monkeypatch.setattr(cli, "_request_json", fake_request)
    payload = cli._image_context(args)

    assert payload["ok"] is True
    assert payload["schema_version"] == "host_image_context_result.v0.2"
    assert payload["requested_asset_type"] == "body_image"
    assert payload["visual_system"] == "youth_campus"
    assert payload["request_count"] == 1
    assert payload["next_action"] == "generate_images_with_host"


def test_image_import_posts_generated_file_as_human_review_candidate(
    monkeypatch, tmp_path: Path
) -> None:
    image_path = tmp_path / "host-output.png"
    image_path.write_bytes(b"host-image-bytes")
    args = cli.build_parser().parse_args(
        [
            "image",
            "import",
            "task-1",
            "--plan-id",
            "plan-1",
            "--slot-id",
            "image-01",
            "--request-id",
            "request-12345678",
            "--expected-plan-revision",
            "3",
            "--expected-image-revision",
            "1",
            "--file",
            str(image_path),
            "--host-name",
            "codex",
            "--host-model",
            "gpt-image-2",
            "--no-start",
            "--json",
        ]
    )
    captured = {}

    def fake_request(method: str, url: str, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return {
            "image_slot": {
                "image_revision": 2,
                "candidates": [{"id": "candidate-1", "provider": "host_agent"}],
            },
            "theme_compatibility": {
                "level": "partial",
                "generated_visual_system": "youth_campus",
                "target_visual_system": "future_tech",
            },
            "review_notice": "图片已作为候选插入，但生成时主题与当前主题不同，请人工确认。",
        }

    monkeypatch.setattr(cli, "_request_json", fake_request)
    payload = cli._image_import(args)

    assert captured["method"] == "POST"
    assert captured["url"].endswith(
        "/article-tasks/task-1/plans/plan-1/image-slots/image-01/host-import"
    )
    assert b"host-image-bytes" in captured["body"]
    assert payload["candidate_count"] == 1
    assert payload["image_revision"] == 2
    assert payload["theme_compatibility"]["level"] == "partial"
    assert "人工确认" in payload["review_notice"]
    assert payload["next_action"] == "human_review"


def test_cover_image_import_uses_cover_binding(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "host-cover.png"
    image_path.write_bytes(b"host-cover-bytes")
    args = cli.build_parser().parse_args(
        [
            "image",
            "import",
            "task-1",
            "--asset-type",
            "cover",
            "--plan-id",
            "plan-1",
            "--request-id",
            "cover-request-12345678",
            "--expected-plan-revision",
            "3",
            "--expected-cover-candidate-count",
            "2",
            "--file",
            str(image_path),
            "--host-name",
            "codex",
            "--host-model",
            "gpt-image-2",
            "--no-start",
            "--json",
        ]
    )
    captured = {}

    def fake_request(method: str, url: str, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return {
            "workspace": {
                "candidates": [
                    {"id": "cover-1"},
                    {"id": "cover-2"},
                    {"id": "cover-3", "provider": "host_agent"},
                ]
            },
            "review_notice": "封面已作为候选插入，请人工确认后再采用。",
        }

    monkeypatch.setattr(cli, "_request_json", fake_request)
    payload = cli._image_import(args)

    assert captured["method"] == "POST"
    assert captured["url"].endswith(
        "/article-tasks/task-1/plans/plan-1/cover-candidates/host-import"
    )
    assert b'expected_cover_candidate_count\"\r\n\r\n2' in captured["body"]
    assert b"host-cover-bytes" in captured["body"]
    assert payload["asset_type"] == "cover"
    assert payload["image_slot_id"] is None
    assert payload["candidate_count"] == 3
    assert payload["next_action"] == "human_review"


def test_empty_host_image_context_is_an_explicit_hard_stop(monkeypatch) -> None:
    args = cli.build_parser().parse_args(
        ["image", "context", "task-1", "--no-start", "--json"]
    )

    def fake_request(method: str, url: str, **_kwargs):
        if url.endswith("/article-tasks/task-1"):
            return {"task": {"selected_plan_id": "plan-1"}}
        return {
            "requested_asset_type": "body_image",
            "requests": [],
            "blocked_targets": [
                {"asset_type": "body_image", "reason": "no_image_slots"}
            ],
            "output_rules": ["requests 为空时必须停止"],
        }

    monkeypatch.setattr(cli, "_request_json", fake_request)
    payload = cli._image_context(args)

    assert payload["request_count"] == 0
    assert payload["next_action"] == "host_image_handoff_blocked"
    assert payload["blocked_targets"][0]["reason"] == "no_image_slots"


@pytest.mark.skipif(os.name == "nt", reason="POSIX virtualenv symlink behavior")
def test_service_python_keeps_virtualenv_symlink_on_posix(tmp_path: Path) -> None:
    system_python = tmp_path / "system" / "python3"
    virtualenv_python = tmp_path / "venv" / "bin" / "python"
    system_python.parent.mkdir(parents=True)
    virtualenv_python.parent.mkdir(parents=True)
    system_python.write_bytes(b"")
    virtualenv_python.symlink_to(system_python)

    assert cli._service_python_executable(
        virtualenv_python,
        platform_name="posix",
    ) == str(virtualenv_python)


def test_serve_reports_missing_static_workbench_build(
    tmp_path: Path, monkeypatch
) -> None:
    web_dir = tmp_path / "apps" / "web"
    (web_dir / "node_modules").mkdir(parents=True)
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": cli.application_version(),
            "image_provider_settings_schema_version": cli.IMAGE_PROVIDER_SETTINGS_SCHEMA_VERSION,
        },
    )
    monkeypatch.setattr(cli, "_probe_http", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: False)
    with pytest.raises(cli.CliError) as raised:
        cli._ensure_services(
            "http://127.0.0.1:8000/api/v1",
            "http://127.0.0.1:3000",
        )

    assert raised.value.code == "workbench_build_missing"


def test_doctor_json_reports_missing_services(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_probe_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_probe_http", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    exit_code = cli.run(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert payload["ok"] is False
    assert payload["core_ready"] is False
    assert payload["workbench_ready"] is False
    assert payload["warnings"] == ["core_api_not_running", "workbench_not_running"]


def test_doctor_does_not_report_mock_images_as_real_generation(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": "0.1.0-alpha.5",
            "image_provider_settings_schema_version": "image_provider_settings.v0.3",
            "image_provider": "mock",
            "image_provider_configured": True,
        },
    )
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    exit_code = cli.run(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["capabilities"]["image_generation"] is False
    assert payload["capabilities"]["mock_image_candidates"] is True
    assert payload["warnings"] == ["image_generation_mock_only"]


def test_doctor_distinguishes_ai_planning_from_rule_fallback(monkeypatch, capsys) -> None:
    def fake_probe(url: str, **_kwargs):
        if url.endswith("/health"):
            return {
                "status": "ok",
                "image_provider": "mock",
                "image_provider_configured": True,
                "text_planner_provider": "rule_text_planner",
                "text_planner_model": "deterministic_editorial_brief",
                "text_planner_configured": False,
            }
        return {"ready": False}

    monkeypatch.setattr(cli, "_probe_json", fake_probe)
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    assert cli.run(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["capabilities"]["ai_text_planning"] is False
    assert payload["capabilities"]["rule_text_planning"] is True
    assert payload["planners"]["text"]["provider"] == "rule_text_planner"
    assert "text_planning_rule_fallback" in payload["warnings"]


def test_doctor_reports_registered_host_skill(tmp_path: Path, monkeypatch, capsys) -> None:
    skill_root = tmp_path / ".agents" / "skills" / "wechat-visual-director"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: wechat-visual-director\ndescription: test\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VISUAL_DIRECTOR_HOST_HOME", str(tmp_path))
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "image_provider": "manual",
            "image_provider_configured": True,
        },
    )
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    assert cli.run(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["capabilities"]["host_skill_registered"] is True
    assert payload["host_integrations"]["skill"]["generic"]["registered"] is True


def test_doctor_reports_persistent_install_paths(tmp_path: Path, monkeypatch, capsys) -> None:
    project_root = tmp_path / "versions" / "0.1.0-alpha.5"
    data_root = tmp_path / "data"
    config_file = tmp_path / "config" / ".env.local"
    runtime_root = tmp_path / "runtime"
    project_root.mkdir(parents=True)
    data_root.mkdir()
    config_file.parent.mkdir()
    runtime_root.mkdir()
    (project_root / "VERSION").write_text("0.1.0-alpha.5\n", encoding="utf-8")
    config_file.write_text("", encoding="utf-8")

    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_INSTALL_ROOT", str(tmp_path))
    monkeypatch.setenv("VISUAL_DIRECTOR_DATA_ROOT", str(data_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_DB", str(data_root / "visual-director.db"))
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(config_file))
    monkeypatch.setenv("VISUAL_DIRECTOR_HOME", str(runtime_root))
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": "0.1.0-alpha.5",
            "image_provider_settings_schema_version": "image_provider_settings.v0.3",
            "image_provider": "mock",
            "image_provider_configured": True,
            "runtime_identity": {
                **cli._expected_runtime_identity(),
                "task_count": 0,
            },
        },
    )
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    assert cli.run(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["installation"] == {
        "version": "0.1.0-alpha.5",
        "mode": "persistent",
        "persistent": True,
        "install_root": str(tmp_path.resolve()),
        "app_root": str(project_root.resolve()),
        "data_root": str(data_root.resolve()),
        "config_file": str(config_file.resolve()),
        "runtime_root": str(runtime_root.resolve()),
        "running_version": "0.1.0-alpha.5",
        "version_match": True,
        "runtime_match": True,
        "expected_runtime_fingerprint": cli._expected_runtime_identity()["fingerprint"],
        "running_runtime_fingerprint": cli._expected_runtime_identity()["fingerprint"],
        "running_mode": "persistent",
        "running_data_root": str(data_root.resolve()),
        "running_database_path": str((data_root / "visual-director.db").resolve()),
        "running_task_count": 0,
    }


def test_doctor_rejects_same_version_api_with_wrong_runtime_data_root(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_root = tmp_path / "versions" / "0.1.0-alpha.19"
    data_root = tmp_path / "data"
    project_root.mkdir(parents=True)
    data_root.mkdir()
    (project_root / "VERSION").write_text("0.1.0-alpha.19\n", encoding="utf-8")
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_INSTALL_ROOT", str(tmp_path))
    monkeypatch.setenv("VISUAL_DIRECTOR_DATA_ROOT", str(data_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_DB", str(data_root / "visual-director.db"))
    source_database = tmp_path / "source" / "apps" / "api" / "data" / "visual-director.db"
    running_identity = cli.runtime_identity(
        project_root=tmp_path / "source",
        database_path=source_database,
    )
    running_identity["mode"] = "source"
    running_identity["fingerprint"] = "foreign-source-runtime"
    running_identity["task_count"] = 63
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": "0.1.0-alpha.19",
            "image_provider_settings_schema_version": "image_provider_settings.v0.3",
            "runtime_identity": running_identity,
        },
    )
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    assert cli.run(["doctor", "--json"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["core_ready"] is False
    assert payload["installation"]["version_match"] is True
    assert payload["installation"]["runtime_match"] is False
    assert payload["installation"]["running_mode"] == "source"
    assert payload["installation"]["running_task_count"] == 63
    assert "core_runtime_mismatch" in payload["warnings"]


def test_serve_refuses_same_version_api_with_wrong_runtime_data_root(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_root = tmp_path / "versions" / "0.1.0-alpha.19"
    data_root = tmp_path / "data"
    project_root.mkdir(parents=True)
    data_root.mkdir()
    (project_root / "VERSION").write_text("0.1.0-alpha.19\n", encoding="utf-8")
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_INSTALL_ROOT", str(tmp_path))
    monkeypatch.setenv("VISUAL_DIRECTOR_DATA_ROOT", str(data_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_DB", str(data_root / "visual-director.db"))
    running_identity = {
        **cli._expected_runtime_identity(),
        "mode": "source",
        "data_root": str((tmp_path / "source-data").resolve()),
        "database_path": str((tmp_path / "source-data" / "visual-director.db").resolve()),
        "fingerprint": "foreign-source-runtime",
        "task_count": 63,
    }
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": "0.1.0-alpha.19",
            "image_provider_settings_schema_version": "image_provider_settings.v0.3",
            "runtime_identity": running_identity,
        },
    )
    monkeypatch.setattr(cli, "_probe_http", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)

    assert cli.run(["serve", "--json"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "core_runtime_mismatch"
    assert payload["error"]["details"]["expected_mode"] == "persistent"
    assert payload["error"]["details"]["running_mode"] == "source"


def test_doctor_rejects_stale_api_after_persistent_upgrade(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_root = tmp_path / "versions" / "0.1.0-alpha.5"
    project_root.mkdir(parents=True)
    (project_root / "VERSION").write_text("0.1.0-alpha.5\n", encoding="utf-8")
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_INSTALL_ROOT", str(tmp_path))
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": "0.1.0-alpha.4",
            "image_provider_settings_schema_version": "image_provider_settings.v0.3",
            "image_provider": "mock",
            "image_provider_configured": True,
        },
    )
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    assert cli.run(["doctor", "--json"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["core_ready"] is False
    assert payload["installation"]["running_version"] == "0.1.0-alpha.4"
    assert payload["installation"]["version_match"] is False
    assert "core_version_mismatch" in payload["warnings"]


def test_serve_refuses_to_reuse_stale_api_after_persistent_upgrade(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_root = tmp_path / "versions" / "0.1.0-alpha.5"
    project_root.mkdir(parents=True)
    (project_root / "VERSION").write_text("0.1.0-alpha.5\n", encoding="utf-8")
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_INSTALL_ROOT", str(tmp_path))
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": "0.1.0-alpha.4",
            "image_provider_settings_schema_version": "image_provider_settings.v0.3",
        },
    )
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)

    assert cli.run(["serve", "--json"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "core_version_mismatch"
    assert payload["error"]["details"]["installed_version"] == "0.1.0-alpha.5"
    assert payload["error"]["details"]["running_version"] == "0.1.0-alpha.4"


def test_doctor_rejects_same_version_api_with_stale_settings_contract(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_root = tmp_path / "versions" / "0.1.0-alpha.7"
    project_root.mkdir(parents=True)
    (project_root / "VERSION").write_text("0.1.0-alpha.7\n", encoding="utf-8")
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_INSTALL_ROOT", str(tmp_path))
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": "0.1.0-alpha.7",
            "image_provider": "mock",
            "image_provider_configured": True,
        },
    )
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    assert cli.run(["doctor", "--json"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["installation"]["version_match"] is False
    assert "core_contract_mismatch" in payload["warnings"]


def test_serve_refuses_same_version_api_with_stale_settings_contract(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project_root = tmp_path / "versions" / "0.1.0-alpha.7"
    project_root.mkdir(parents=True)
    (project_root / "VERSION").write_text("0.1.0-alpha.7\n", encoding="utf-8")
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("VISUAL_DIRECTOR_INSTALL_ROOT", str(tmp_path))
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "application_version": "0.1.0-alpha.7",
        },
    )
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)

    assert cli.run(["serve", "--json"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "core_version_mismatch"
    assert payload["error"]["details"]["running_settings_schema"] is None


def test_serve_reports_reachable_but_incompatible_workbench(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "_probe_json",
        lambda url, **_kwargs: {
            "status": "ok",
            "application_version": cli.application_version(),
            "image_provider_settings_schema_version": cli.IMAGE_PROVIDER_SETTINGS_SCHEMA_VERSION,
        }
        if url.endswith("/health")
        else None,
    )
    monkeypatch.setattr(cli, "_probe_http", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: False)

    assert cli.run(["serve", "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "workbench_build_missing"
    assert payload["error"]["details"]["expected_version"] == cli.application_version()


def test_create_task_returns_agent_safe_result(tmp_path: Path, monkeypatch, capsys) -> None:
    article = tmp_path / "article.md"
    article.write_text(
        """---
title: 三步完成志愿核对
article_type: tutorial_steps
---
# 三步完成志愿核对

## 第一步

核对官方数据。
""",
        encoding="utf-8",
    )
    service_calls: list[tuple[str, str]] = []

    def fake_services(api_base: str, web_base: str, *, timeout: float) -> dict:
        service_calls.append((api_base, web_base))
        assert timeout == 45
        return {
            "api_health": {"status": "ok", "text_planner_configured": False},
            "web_ready": True,
            "started": {},
        }

    def fake_request(method: str, url: str, **kwargs) -> dict:
        if method == "POST" and url.endswith("/article-tasks"):
            assert "三步完成志愿核对".encode("utf-8") in kwargs["body"]
            assert kwargs["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
            return {
                "task": {"id": "task-123", "status": "created", "version": 1},
                "input_summary": {
                    "preflight_report": {
                        "status": "REVIEW",
                        "planning_allowed": True,
                        "draft_creation_allowed": False,
                    }
                },
                "review_path": "/tasks/task-123",
                "idempotency_replayed": False,
            }
        if method == "POST" and url.endswith("/article-tasks/task-123/generate-plans"):
            assert json.loads(kwargs["body"])["planner"] == "rule"
            return {"task_id": "task-123", "status": "analyzing"}
        if method == "GET" and url.endswith("/article-tasks/task-123"):
            return {"task": {"id": "task-123", "status": "plans_ready", "version": 3}}
        raise AssertionError((method, url))

    monkeypatch.setattr(cli, "_ensure_services", fake_services)
    monkeypatch.setattr(cli, "_request_json", fake_request)
    monkeypatch.setattr(cli.webbrowser, "open", lambda *_args, **_kwargs: True)

    exit_code = cli.run(
        [
            "task",
            "create",
            "--file",
            str(article),
            "--article-type",
            "tutorial_steps",
            "--open",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert service_calls
    assert payload == {
        "ok": True,
        "schema_version": "task_create_result.v0.2",
        "task_id": "task-123",
        "status": "plans_ready",
        "preflight_status": "REVIEW",
        "planning_allowed": True,
        "draft_creation_allowed": False,
        "findings": [],
        "idempotency_replayed": False,
        "plans_generated": True,
        "planner": "rule",
        "review_url": "http://127.0.0.1:8000/tasks/task-123",
        "opened": True,
        "next_action": "human_review",
        "command_completed": True,
        "background_service": True,
    }


def test_default_task_key_is_stable_until_source_changes(tmp_path: Path) -> None:
    article = tmp_path / "article.md"
    article.write_text("# First", encoding="utf-8")
    args = cli.build_parser().parse_args(["task", "create", "--file", str(article)])

    first = cli._default_task_idempotency_key(args, article)
    second = cli._default_task_idempotency_key(args, article)
    article.write_text("# Second", encoding="utf-8")
    changed = cli._default_task_idempotency_key(args, article)

    assert first == second
    assert first != changed


def test_task_context_returns_host_agent_contract(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "_request_json",
        lambda method, url, **_kwargs: {
            "task_id": "task-host",
            "expected_task_version": 2,
            "context": {
                "schema_version": "host_agent_planner_context.v0.1",
                "planner_input": {"article": {"blocks": []}},
                "json_schema": {"type": "object"},
            },
        },
    )

    exit_code = cli.run(["task", "context", "task-host", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["expected_task_version"] == 2
    assert payload["next_action"] == "write_editorial_brief"
    assert payload["context"]["schema_version"] == "host_agent_planner_context.v0.1"


def test_task_plan_submits_host_brief_and_reports_normalization(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    brief_path = tmp_path / "editorial-brief.json"
    brief_path.write_text(json.dumps({"schema_version": "editorial_brief.v0.1"}), encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "_ensure_services",
        lambda *_args, **_kwargs: {"api_health": {}, "web_ready": True, "started": {}},
    )

    def fake_request(method: str, url: str, **kwargs) -> dict:
        if method == "POST" and url.endswith("/article-tasks/task-host/generate-plans"):
            request = json.loads(kwargs["body"])
            assert request["planner"] == "host_agent"
            assert request["editorial_brief"]["schema_version"] == "editorial_brief.v0.1"
            assert request["host_model"] == "opencode-host"
            return {
                "planner_metadata": {
                    "provider": "host_agent",
                    "model": "opencode-host",
                    "fallback_used": False,
                    "normalization_count": 2,
                    "normalization_adjustments": [{"code": "safe_adjustment"}],
                }
            }
        if method == "GET" and url.endswith("/article-tasks/task-host"):
            return {"task": {"id": "task-host", "status": "plans_ready", "version": 4}}
        raise AssertionError((method, url))

    monkeypatch.setattr(cli, "_request_json", fake_request)
    exit_code = cli.run(
        [
            "task",
            "plan",
            "task-host",
            "--brief",
            str(brief_path),
            "--expected-task-version",
            "2",
            "--host-model",
            "opencode-host",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["planner_provider"] == "host_agent"
    assert payload["fallback_used"] is False
    assert payload["normalization_count"] == 2
    assert payload["next_action"] == "human_review"


def test_stop_refuses_pid_when_process_identity_does_not_match(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIRECTOR_HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "runtime.json").write_text(
        json.dumps({"processes": {"api": 123}, "api_base": "http://127.0.0.1:8000/api/v1"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "_process_command_line", lambda _pid: "python unrelated.py")

    payload, exit_code = cli._stop_services()

    assert exit_code == 6
    assert payload["ok"] is False
    assert payload["refused"]["api"]["reason"] == "process_identity_mismatch"
    assert (tmp_path / "runtime.json").is_file()


def test_create_task_missing_file_is_stable_json_error(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing.md"

    exit_code = cli.run(["task", "create", "--file", str(missing), "--no-start", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["ok"] is False
    assert payload["error"]["code"] == "input_file_not_found"
    assert payload["error"]["details"]["path"] == str(missing.resolve())


def test_task_status_maps_existing_api_response(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "_request_json",
        lambda *_args, **_kwargs: {
            "task": {"id": "task-456", "status": "plans_ready"},
            "input_summary": {
                "preflight_report": {
                    "status": "REVIEW",
                    "planning_allowed": True,
                    "draft_creation_allowed": False,
                }
            },
            "available_actions": ["view_plans", "select_plan"],
            "last_error": None,
        },
    )

    exit_code = cli.run(["task", "status", "task-456", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["task_id"] == "task-456"
    assert payload["next_action"] == "human_review"
    assert payload["review_url"].endswith("/tasks/task-456")


def test_http_preflight_error_uses_exit_code_four(monkeypatch, tmp_path: Path, capsys) -> None:
    article = tmp_path / "blocked.md"
    article.write_text("# 标题\n\n正文", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "_request_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            cli.CliError(
                "preflight_blocked",
                "Markdown 预检未通过",
                exit_code=4,
                details={"findings": ["sensitive_secret"]},
            )
        ),
    )

    exit_code = cli.run(["task", "create", "--file", str(article), "--no-start", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 4
    assert payload["error"]["code"] == "preflight_blocked"
    assert payload["error"]["details"]["findings"] == ["sensitive_secret"]
