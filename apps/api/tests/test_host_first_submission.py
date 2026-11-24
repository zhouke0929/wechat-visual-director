"""The host owns planning; only a successfully persisted first plan is user-facing."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import threading

from fastapi.testclient import TestClient
import pytest

import visual_director.main as main


FIXTURES = Path(__file__).resolve().parents[3] / "samples" / "showcase"
MARKDOWN = (FIXTURES / "01-campus-project-portfolio.md").read_bytes()
API = "/api/v1/article-tasks"


def create(client, key=None):
    result = client.post(API, files={"markdown_file": ("portfolio.md", MARKDOWN, "text/markdown")},
                         headers={"Idempotency-Key": key} if key else {})
    assert result.status_code == 201, result.text
    return result.json()


def brief_body(version):
    brief = json.loads((FIXTURES / "brief-01-campus-project-portfolio.json").read_text(encoding="utf8"))
    return {"mode": "start", "expected_task_version": version, "planner": "host_agent", "editorial_brief": brief}


def test_upgrade_actions_follow_real_plan_and_original_image_advice_is_actionable(tmp_path):
    app = main.create_app(str(tmp_path / "old-states.db"))
    with TestClient(app) as client:
        created = create(client)
        task = created["task"]
        url = f"{API}/{task['id']}"
        db = app.state.repository.connection
        with db:
            db.execute("UPDATE tasks SET status='analyzing' WHERE id=?", (task["id"],))
        assert client.get(url).json()["available_actions"] == ["submit_host_brief"]
        assert client.post(f"{url}/generate-plans", json=brief_body(task["version"])).status_code == 202
        with db:
            db.execute("UPDATE tasks SET status='failed' WHERE id=?", (task["id"],))
        actions = client.get(url).json()["available_actions"]
        assert "view_plans" in actions and "submit_host_brief" not in actions
        source = "# 校刊\n\n#### 图注\n\n![校园旧照](photos/campus.png)"
        uploaded = client.post(API, files={"markdown_file": ("campus.md", source.encode(), "text/markdown")})
        assert uploaded.status_code == 201
        data = uploaded.json()
        warnings = {w["code"]: w["message"] for w in data["input_summary"]["warnings"]}
        assert "source_images_deferred" not in warnings
        assert "上传" in warnings["source_image_requires_import"]
        assert client.get(f"{API}/{data['task']['id']}").json()["available_actions"] == ["fix_source"]


@pytest.mark.parametrize("alter", ["unset", "rule", "intelligent", "missing_brief", "bad_brief", "bad_type"])
def test_wrong_route_or_invalid_host_json_is_repairable_without_writes(tmp_path, alter):
    with TestClient(main.create_app(str(tmp_path / "first.db"))) as client:
        task = create(client)["task"]
        url = f"{API}/{task['id']}"
        initial = client.get(url).json()
        body = brief_body(task["version"])
        if alter == "unset":
            del body["planner"], body["editorial_brief"]
        elif alter in {"rule", "intelligent"}:
            body["planner"] = alter
        elif alter == "missing_brief":
            del body["editorial_brief"]
        else:
            body["editorial_brief"] = {"unexpected": True} if alter == "bad_brief" else ["not", "a", "brief"]
        failed = client.post(f"{url}/generate-plans", json=body)
        assert failed.status_code == 422, failed.text
        error = failed.json()["error"]
        assert error["code"] == "host_brief_invalid"
        assert error["details"]["issues"] and all("path" in i and i["message"] for i in error["details"]["issues"])
        assert error["details"]["next_action"] == "revise_editorial_brief"
        assert error["details"]["expected_task_version"] == task["version"]
        assert client.get(url).json() == initial
        assert client.get(f"{url}/plans").json()["plans"] == []
        repaired = client.post(f"{url}/generate-plans", json=brief_body(task["version"]))
        assert repaired.status_code == 202, repaired.text
        assert repaired.json()["planner_metadata"]["fallback_used"] is False


def test_recent_tasks_count_search_pagination_and_handoff_use_persisted_plans(tmp_path):
    with TestClient(main.create_app(str(tmp_path / "visibility.db"))) as client:
        a = create(client, "public-first")
        b = create(client, "still-private")
        assert a["review_path"] is None and b["review_path"] is None
        assert client.get(API).json()["items"] == []
        search = {"page": 1, "page_size": 1, "q": "课程作业"}
        assert client.get(API, params=search).json()["total"] == 0
        assert client.get(API, params={**search, "scope": "all"}).json()["total"] == 2
        url = f"{API}/{a['task']['id']}"
        body = brief_body(a["task"]["version"])
        del body["planner"]  # omission is not a back door into rule planning
        result = client.post(f"{url}/generate-plans", json=body)
        assert result.status_code == 202, result.text
        link = f"/tasks/{a['task']['id']}"
        summary = client.get(API, params=search).json()
        assert summary["total"] == summary["total_pages"] == 1
        assert not summary["has_next"]
        assert [item["review_path"] for item in summary["items"]] == [link]
        assert client.get(API, params={**search, "page": 2}).json()["items"] == []
        assert client.get(url).json()["review_path"] == create(client, "public-first")["review_path"] == link
        assert len(client.get(API).json()["items"]) == 1
        assert f"{API}/{{task_id}}/editorial-brief/generate" not in client.get("/openapi.json").json()["paths"]
        assert client.post(f"{url}/editorial-brief/generate", json={"expected_task_version": 1}).status_code in (404, 405)


def test_completely_foreign_blocks_are_not_equivalent_to_intentionally_plain(tmp_path):
    with TestClient(main.create_app(str(tmp_path / "source-grounding.db"))) as client:
        task = create(client)["task"]
        url = f"{API}/{task['id']}"
        body = brief_body(task["version"])
        brief = body["editorial_brief"]
        for choice in brief["sections"] + brief["image_intents"]:
            choice["source_block_ids"] = ["block-999"]
            if "anchor_block_id" in choice:
                choice["anchor_block_id"] = "block-999"
        initial = client.get(url).json()
        for sections in [brief["sections"], []]:
            brief["sections"] = sections
            rejected = client.post(f"{url}/generate-plans", json=body)
            assert rejected.status_code == 422, rejected.text
            assert "block_id" in rejected.json()["error"]["details"]["issues"][0]["message"]
            assert client.get(url).json() == initial
        brief["sections"], brief["image_intents"] = [], []
        assert client.post(f"{url}/generate-plans", json=body).status_code == 202


def test_two_service_instances_racing_to_save_preserve_exactly_one_plan(tmp_path, monkeypatch):
    path = str(tmp_path / "concurrent.db")
    render = main.render_preview
    both_writers = threading.Barrier(2, timeout=12)

    def concurrent_render(*args, **kwargs):
        html = render(*args, **kwargs)
        both_writers.wait()
        return html

    with TestClient(main.create_app(path)) as one, TestClient(main.create_app(path)) as two:
        task = create(one)["task"]
        url = f"{API}/{task['id']}"
        monkeypatch.setattr(main, "render_preview", concurrent_render)
        with ThreadPoolExecutor(max_workers=2) as pool:
            writes = list(pool.map(lambda client: client.post(f"{url}/generate-plans", json=brief_body(task["version"])), [one, two]))
        assert sorted(r.status_code for r in writes) == [202, 409]
        conflict = next(r for r in writes if r.status_code == 409)
        assert conflict.json()["error"]["code"] == "plan_already_exists"
        plans = two.get(f"{url}/plans").json()["plans"]
        assert len(plans) == 1
        assert two.get(url).json()["task"]["selected_plan_id"] == plans[0]["id"]


@pytest.mark.parametrize("legacy,heading_jump", [(False, False), (True, False), (True, True)])
def test_long_narrative_is_agent_advice_not_a_user_gate(tmp_path, legacy, heading_jump):
    text = ("我在老街边上看着行人来来往往，阳光从屋檐缓慢移过去，路边的小铺开始摆好今天的桌椅。" * 4)
    source = "---\nschema_version: wechat_article.v1\narticle_type: viewpoint_trend\n---\n# 街上的一日\n\n"
    source += ("####" if heading_jump else "##") + " 上午\n\n" + "\n\n".join(text for _ in range(10))
    app = main.create_app(str(tmp_path / "narrative.db"))
    with TestClient(app) as client:
        created = client.post(API, files={"markdown_file": ("街上的一日.md", source.encode(), "text/markdown")})
        assert created.status_code == 201
        task = created.json()["task"]
        url = f"{API}/{task['id']}"
        summary = created.json()["input_summary"]
        assert "source_structure_too_flat" not in str(summary)
        if legacy:
            # Recreate a pending task exactly in the pre-migration shape. It must not
            # acquire a fake acknowledgement or lose the distinct structural error.
            old = {"code": "source_structure_too_flat", "resolution_policy": "EDIT_SOURCE",
                   "planning_blocking": True, "draft_blocking": False, "message": "旧版误阻断"}
            report = summary["preflight_report"]
            report["findings"].append(old)
            report.update(ruleset_version="preflight_rules.v0.2-semantic-structure", planning_allowed=False)
            summary["warnings"].append({"code": old["code"], "message": old["message"]})
            conn = app.state.repository.connection
            def seed_old():
                with conn:
                    conn.execute("UPDATE tasks SET input_summary_json = ? WHERE id = ?",
                                 (json.dumps(summary), task["id"]))
            def raw():
                return conn.execute("SELECT input_summary_json FROM tasks WHERE id = ?", (task["id"],)).fetchone()[0]
            seed_old()
        report = client.get(url).json()["input_summary"]["preflight_report"]
        assert report["planning_allowed"] is (not heading_jump)
        assert "source_structure_too_flat" not in str(report)
        context = client.get(f"{url}/editorial-brief/context").json()["context"]
        assert [a["code"] for a in context["planner_input"]["structure_advice"]] == ["source_structure_too_flat"]
        body = brief_body(task["version"])
        body["editorial_brief"].update(sections=[], image_intents=[])
        if legacy:
            assert "source_structure_too_flat" in raw()  # reads and failed requests never write back
        result = client.post(f"{url}/generate-plans", json=body)
        if heading_jump:
            assert result.status_code == 409
            assert [f["code"] for f in result.json()["error"]["details"]["findings"]] == ["heading_level_jump"]
            assert "source_structure_too_flat" in raw()
        else:
            assert result.status_code == 202, result.text
            assert client.get(url).json()["input_summary"]["preflight_report"]["draft_creation_allowed"] is False
            if legacy:
                assert "source_structure_too_flat" not in raw()
                seed_old()  # already published/reviewable reports must not be rewritten
                assert client.get(url).json()["input_summary"] == summary
                assert "source_structure_too_flat" in raw()


def test_stale_version_or_failed_insert_leaves_no_visible_half_plan(tmp_path):
    app = main.create_app(str(tmp_path / "rollback.db"))
    with TestClient(app, raise_server_exceptions=False) as client:
        task = create(client)["task"]
        url = f"{API}/{task['id']}"
        initial = client.get(url).json()
        stale = client.post(f"{url}/generate-plans", json=brief_body(task["version"] + 1))
        assert stale.status_code == 409 and stale.json()["error"]["code"] == "version_conflict"
        repo = app.state.repository
        with repo.connection:
            repo.connection.execute("CREATE TRIGGER fail_revision BEFORE INSERT ON plan_revisions "
                                    "BEGIN SELECT RAISE(ABORT, 'intentional fault'); END;")
        failed = client.post(f"{url}/generate-plans", json=brief_body(task["version"]))
        assert failed.status_code == 500
        assert client.get(url).json() == initial
        assert not client.get(API).json()["items"]
        assert repo.connection.execute("SELECT count(*) FROM artifacts WHERE task_id=?", (task["id"],)).fetchone()[0] == 0
        with repo.connection:
            repo.connection.execute("DROP TRIGGER fail_revision")
        assert client.post(f"{url}/generate-plans", json=brief_body(task["version"])).status_code == 202


def test_replaying_first_submit_cannot_overwrite_edits_cover_image_or_revisions(tmp_path):
    with TestClient(main.create_app(str(tmp_path / "assets.db"))) as client:
        task = create(client)["task"]
        url = f"{API}/{task['id']}"
        submit = client.post(f"{url}/generate-plans", json=brief_body(task["version"]))
        assert submit.status_code == 202, submit.text
        plan = client.get(f"{url}/plans").json()["plans"][0]
        purl = f"{url}/plans/{plan['id']}"
        editor = client.get(f"{url}/content-editor").json()
        edit = client.patch(f"{url}/content-editor", json={"target": "title", "content": "已人工修改的标题",
                                                            "expected_revision": editor["revision"]})
        assert edit.is_success, edit.text
        slot = client.get(f"{purl}/image-slots").json()["items"][0]
        asset = FIXTURES.parents[1] / "site/assets/generated/campus-portfolio-scene.webp"
        replace = client.post(f"{purl}/image-slots/{slot['image_slot_id']}/replace",
                              data={"expected_image_revision": str(slot["state"]["image_revision"])},
                              files={"image_file": (asset.name, asset.read_bytes(), "image/webp")})
        assert replace.is_success, replace.text
        cover = client.post(f"{purl}/cover-candidates/fallback",
                            json={"mode": "start", "expected_task_version": client.get(url).json()["task"]["version"]})
        assert cover.is_success, cover.text
        endpoints = [url, f"{url}/content-editor", f"{purl}/revisions", f"{purl}/image-slots", f"{purl}/cover-candidates"]
        before = [client.get(endpoint).json() for endpoint in endpoints]
        for version in (task["version"], before[0]["task"]["version"]):
            conflict = client.post(f"{url}/generate-plans", json=brief_body(version))
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "plan_already_exists"
        assert [client.get(endpoint).json() for endpoint in endpoints] == before
