from __future__ import annotations

import json
from pathlib import Path

from visual_director import cli


def test_doctor_json_reports_missing_services(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_probe_json", lambda *_args, **_kwargs: None)
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
                "text_planner_provider": "mock_text_planner",
                "text_planner_model": "deterministic_editorial_brief",
                "text_planner_configured": True,
            }
        return {"ready": False}

    monkeypatch.setattr(cli, "_probe_json", fake_probe)
    monkeypatch.setattr(cli, "_probe_web", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "pnpm.cmd")

    assert cli.run(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["capabilities"]["ai_text_planning"] is False
    assert payload["capabilities"]["rule_text_planning"] is True
    assert payload["planners"]["text"]["provider"] == "mock_text_planner"
    assert "text_planning_rule_fallback" in payload["warnings"]


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
        "idempotency_replayed": False,
        "plans_generated": True,
        "planner": "rule",
        "review_url": "http://127.0.0.1:3000/tasks/task-123",
        "opened": True,
        "next_action": "human_review",
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
