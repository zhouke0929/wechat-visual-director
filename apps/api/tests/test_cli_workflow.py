"""Verify the actual CLI/HTTP handoff, including a recoverable invalid first brief."""
import json
import os
import threading
import time

import uvicorn

from visual_director import cli


def test_cli_from_new_manuscript_to_one_reviewable_draft(tmp_path, monkeypatch, capsys):
    for key in list(os.environ):
        if key.startswith(("VISUAL_DIRECTOR_", "WECHAT_", "OPENAI_", "GEMINI_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("VISUAL_DIRECTOR_HOME", str(tmp_path / "runtime"))
    monkeypatch.setenv("VISUAL_DIRECTOR_DB", str(tmp_path / "isolated.db"))
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(tmp_path / "isolated.env"))
    monkeypatch.setenv("VISUAL_DIRECTOR_THEME_PACK_DIR", str(tmp_path / "themes"))
    monkeypatch.setenv("VISUAL_DIRECTOR_IMAGE_PROVIDER", "manual")
    from visual_director.main import create_app
    app = create_app()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline
            time.sleep(0.02)
        web = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
        api = web + "/api/v1"
        opened = []
        monkeypatch.setattr(cli.webbrowser, "open", lambda url, **kw: opened.append(url) or True)

        def task(*args, success=True):
            code = cli.run(["task", *args, "--api-base", api, "--web-base", web, "--json"])
            result = json.loads(capsys.readouterr().out)
            assert (code == 0) == success, json.dumps(result, ensure_ascii=False)
            return result

        markdown = tmp_path / "article.md"
        markdown.write_text("# 街角记事\n\n出门绕了一段路，路边有三株新发芽的树。\n", encoding="utf-8")
        create = ["create", "--file", str(markdown), "--no-start", "--open"]
        manuscript = task(*create)
        task_id = manuscript["task_id"]
        assert manuscript["review_url"] is None and not opened
        assert task(*create)["idempotency_replayed"] is True
        assert task("list")["total"] == 0 and task("list", "--include-unplanned")["total"] == 1
        assert task("open", task_id, success=False)["error"]["code"] == "plan_not_ready"
        context = task("context", task_id)
        version = context["expected_task_version"]
        brief_file = tmp_path / "brief.json"
        brief_file.write_text("{}", encoding="utf-8")
        submit = ["plan", task_id, "--brief", str(brief_file), "--expected-task-version", str(version), "--no-start"]
        invalid = task(*submit, success=False)["error"]
        assert invalid["code"] == "host_brief_invalid" and invalid["details"]["next_action"] == "revise_editorial_brief"
        assert task("context", task_id)["expected_task_version"] == version
        assert task("list")["total"] == 0 and not opened
        brief_file.write_text(json.dumps({
            "schema_version": "editorial_brief.v0.1",
            "article": {"article_type": context["context"]["planner_input"]["requested_article_type"],
                        "audience": ["读者"], "reader_task": "阅读街角观察", "narrative": "保留自然叙述。"},
            "art_direction": {"tone": ["安静"], "palette_roles": ["warm_ivory", "muted_teal"],
                              "style_family": "editorial_paper_cut", "avoid_recent_patterns": []},
            "sections": [], "image_intents": [], "facts_locked": True,
        }, ensure_ascii=False), encoding="utf-8")
        ready = task(*submit)
        assert ready["status"] == "plan_selected" and ready["review_url"] == f"{web}/tasks/{task_id}"
        assert task("list")["items"][0]["review_url"] == ready["review_url"]
        assert task(*submit, success=False)["error"]["code"] == "plan_already_exists"
        replay = task(*create)
        assert replay["idempotency_replayed"] and replay["review_url"] == ready["review_url"]
        assert opened == [ready["review_url"]]
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.state.repository.connection.close()
