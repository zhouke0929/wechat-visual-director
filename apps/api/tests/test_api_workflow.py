from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from visual_director.main import _fit_cover, create_app
from visual_director.delivery import WenyanPublishResult
from visual_director.image_provider import MockImageProvider
from visual_director.text_planner import MockTextPlannerProvider


class _SuccessfulWenyanPublisher:
    def __init__(self) -> None:
        self.publish_count = 0

    def status(self) -> dict:
        return {
            "schema_version": "publisher_status.v0.1",
            "provider": "wenyan",
            "installed": True,
            "version": "2.0.11",
            "minimum_version": "2.0.1",
            "recommended_version": "2.0.11",
            "credentials_configured": True,
            "credential_source": "local_env_file",
            "ip_whitelist": "operator_confirmation_required",
            "ready": True,
            "warnings": [],
            "install_command": "npm install -g @wenyan-md/cli@2.0.11",
        }

    def publish(self, files: dict[str, bytes]) -> WenyanPublishResult:
        self.publish_count += 1
        assert "article.md" in files
        assert b"asset://" not in files["article.md"]
        assert b"<h1" not in files["article.md"]
        assert b"padding:0 24px 34px" not in files["article.md"]
        return WenyanPublishResult(status="succeeded", media_id="REAL_MEDIA_001", error=None)


def test_cover_fit_preserves_both_edges_of_wide_source() -> None:
    source = Image.new("RGB", (1600, 900), "#55aa66")
    for x in range(100):
        for y in range(900):
            source.putpixel((x, y), (220, 40, 40))
            source.putpixel((1599 - x, y), (40, 70, 220))
    buffer = BytesIO()
    source.save(buffer, format="PNG")

    fitted = _fit_cover(buffer.getvalue())

    with Image.open(BytesIO(fitted)) as cover:
        assert cover.size == (1080, 864)
        assert cover.getpixel((0, 432))[0] > 180
        assert cover.getpixel((1079, 432))[2] > 180


class _FailThenSucceedWenyanPublisher(_SuccessfulWenyanPublisher):
    def publish(self, files: dict[str, bytes]) -> WenyanPublishResult:
        self.publish_count += 1
        assert "article.md" in files
        if self.publish_count == 1:
            return WenyanPublishResult(
                status="failed",
                media_id=None,
                error={
                    "code": "invalid_ip_whitelist",
                    "message": "当前出口 IP 未加入公众号白名单",
                    "retryable": True,
                },
            )
        return WenyanPublishResult(status="succeeded", media_id="REAL_MEDIA_RETRY_001", error=None)


def _png_bytes(width: int = 960, height: int = 540, color: tuple[int, int, int] = (30, 124, 112)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _prepare_publication_ready_task(client: TestClient) -> tuple[dict, dict]:
    markdown = """---
title: 三步完成志愿核对
article_type: tutorial_steps
---
# 三步完成志愿核对

先明确目标，再核对证据，最后形成行动清单。

## 行动路径

1. 明确目标院校
2. 核对官方位次
3. 形成志愿梯度

> 志愿表不是一次凭感觉排序，而是一组需要逐项验证的决策。
"""
    created = client.post(
        "/api/v1/article-tasks",
        files={"markdown_file": ("publication.md", markdown.encode("utf-8"), "text/markdown")},
    )
    assert created.status_code == 201
    task = created.json()["task"]
    cover = client.post(
        f'/api/v1/article-tasks/{task["id"]}/preflight/findings/missing_cover/replace-asset',
        data={"expected_task_version": task["version"]},
        files={"image_file": ("cover.png", _png_bytes(1080, 864), "image/png")},
    )
    assert cover.status_code == 200
    task = cover.json()["task"]
    generated = client.post(
        f'/api/v1/article-tasks/{task["id"]}/generate-plans',
        json={"mode": "start", "expected_task_version": task["version"]},
    )
    assert generated.status_code == 202
    task = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
    plan = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"][0]
    selected = client.post(
        f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/select',
        json={"plan_id": plan["id"], "expected_task_version": task["version"]},
    )
    assert selected.status_code == 200
    task = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
    slots = client.get(
        f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots'
    ).json()["items"]
    for item in slots:
        skipped = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots/{item["image_slot_id"]}/skip',
            json={"expected_image_revision": item["state"]["image_revision"]},
        )
        assert skipped.status_code == 200
    task = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
    return task, plan


def _freeze_publication(client: TestClient, task: dict, key: str = "freeze-publication") -> dict:
    response = client.post(
        f'/api/v1/article-tasks/{task["id"]}/publication-revisions',
        headers={"Idempotency-Key": key, "X-Operator-Id": "operator"},
        json={
            "expected_task_version": task["version"],
            "metadata": {
                "author": "示例号",
                "digest": "一份可以逐项执行的志愿核对清单。",
                "content_source_url": "",
                "show_cover_pic": True,
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def test_batch_delete_tasks_removes_local_records_and_assets_but_keeps_other_tasks(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "batch-delete.db"))
    with TestClient(app) as client:
        task, _ = _prepare_publication_ready_task(client)
        revision = _freeze_publication(client, task, key="freeze-for-delete")["revision"]
        retained = client.post(
            "/api/v1/article-tasks",
            files={
                "markdown_file": (
                    "retained.md",
                    b"---\ntitle: Retained task\n---\n# Retained task\n\nKeep this task.",
                    "text/markdown",
                )
            },
        ).json()["task"]

        repository = app.state.repository
        replacement = repository.connection.execute(
            "SELECT output_filename FROM preflight_asset_replacements WHERE task_id = ?",
            (task["id"],),
        ).fetchone()
        assert replacement is not None
        image_path = repository.image_asset_dir / replacement["output_filename"]
        publication_dir = repository.publication_asset_dir / revision["id"]
        assert image_path.exists()
        assert publication_dir.exists()

        response = client.post(
            "/api/v1/article-tasks/batch-delete",
            json={"task_ids": [task["id"], "missing-task", task["id"]]},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["schema_version"] == "task_batch_delete_result.v0.1"
        assert result["deleted_count"] == 1
        assert result["deleted_task_ids"] == [task["id"]]
        assert result["missing_task_ids"] == ["missing-task"]
        assert result["asset_cleanup_warnings"] == []
        assert client.get(f'/api/v1/article-tasks/{task["id"]}').status_code == 404
        assert client.get(f'/api/v1/article-tasks/{retained["id"]}').status_code == 200
        assert not image_path.exists()
        assert not publication_dir.exists()
        assert repository.connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE id = ?",
            (task["id"],),
        ).fetchone()[0] == 0
        for table in (
            "artifacts",
            "plans",
            "plan_revisions",
            "audit_events",
            "recent_article_component_summaries",
            "image_slot_states",
            "image_candidates",
            "cover_candidates",
            "preflight_asset_replacements",
            "publication_revisions",
            "draft_slots",
            "draft_operations",
        ):
            count = repository.connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE task_id = ?",
                (task["id"],),
            ).fetchone()[0]
            assert count == 0, table


def test_batch_delete_tasks_requires_at_least_one_id(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "batch-delete-validation.db"))
    with TestClient(app) as client:
        response = client.post("/api/v1/article-tasks/batch-delete", json={"task_ids": []})

    assert response.status_code == 422


def test_batch_delete_tasks_blocks_unknown_draft_operations(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIRECTOR_ENABLE_MOCK_FAILURES", "1")
    app = create_app(str(tmp_path / "batch-delete-active-draft.db"))
    with TestClient(app) as client:
        task, _ = _prepare_publication_ready_task(client)
        frozen = _freeze_publication(client, task, key="freeze-before-guarded-delete")
        unknown = client.post(
            f'/api/v1/publication-revisions/{frozen["revision"]["id"]}/draft-operations',
            headers={"Idempotency-Key": "unknown-before-delete"},
            json={
                "expected_task_version": frozen["task"]["version"],
                "draft_slot": "primary",
                "simulation_mode": "unknown",
            },
        ).json()

        blocked = client.post(
            "/api/v1/article-tasks/batch-delete",
            json={"task_ids": [task["id"]]},
        )
        assert blocked.status_code == 409
        assert "结果未知" in blocked.json()["error"]["message"]

        resolved = client.post(
            f'/api/v1/draft-operations/{unknown["operation"]["id"]}/resolve-unknown',
            headers={"Idempotency-Key": "resolve-before-delete", "X-Operator-Id": "product_owner"},
            json={
                "expected_task_version": unknown["task"]["version"],
                "expected_operation_version": unknown["operation"]["version"],
                "outcome": "confirmed_not_created",
                "evidence": "已核对公众号后台，确认没有产生草稿。",
            },
        )
        assert resolved.status_code == 200
        deleted = client.post(
            "/api/v1/article-tasks/batch-delete",
            json={"task_ids": [task["id"]]},
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted_count"] == 1


def test_create_task_idempotency_replays_and_rejects_conflicting_source(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "idempotency.db"))
    markdown = """---
title: 三步核对志愿
article_type: tutorial_steps
---
# 三步核对志愿

## 第一步

核对官方数据。
"""
    headers = {"Idempotency-Key": "create-task-stable-key"}
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/article-tasks",
            headers=headers,
            files={"markdown_file": ("article.md", markdown.encode("utf-8"), "text/markdown")},
        )
        replay = client.post(
            "/api/v1/article-tasks",
            headers=headers,
            files={"markdown_file": ("article.md", markdown.encode("utf-8"), "text/markdown")},
        )
        conflict = client.post(
            "/api/v1/article-tasks",
            headers=headers,
            files={
                "markdown_file": (
                    "changed.md",
                    markdown.replace("核对官方数据", "复核录取规则").encode("utf-8"),
                    "text/markdown",
                )
            },
        )

    assert first.status_code == 201
    assert first.json()["idempotency_replayed"] is False
    assert replay.status_code == 201
    assert replay.json()["idempotency_replayed"] is True
    assert replay.json()["task"]["id"] == first.json()["task"]["id"]
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "version_conflict"


def test_create_generate_preview_and_change_selection(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    with TestClient(app) as client:
        markdown = """---
title: 五步核对
article_type: tutorial_steps
---
# 五步核对

先核对事实。

## 第一步

1. 保存成绩
2. 查看位次
"""
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("sample.md", markdown.encode("utf-8"), "text/markdown")},
            data={"account_id": "default"},
        )
        assert created.status_code == 201
        task = created.json()["task"]

        generated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": task["version"]},
        )
        assert generated.status_code == 202

        detail = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
        assert detail["status"] == "plans_ready"
        plans = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"]
        assert len(plans) == 2
        preview = client.get(plans[0]["preview_url"])
        assert preview.status_code == 200
        assert "width:100%" in preview.text
        assert "width:390px" not in preview.text

        first = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plans[0]["id"]}/select',
            json={"plan_id": plans[0]["id"], "expected_task_version": detail["version"]},
        )
        assert first.status_code == 200
        second = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plans[1]["id"]}/select',
            json={"plan_id": plans[1]["id"], "expected_task_version": first.json()["version"]},
        )
        assert second.status_code == 200
        assert second.json()["selection_change_count"] == 1
        history = app.state.repository.list_recent_component_summaries("default", 5)
        assert history == []


def test_create_task_returns_preflight_report_and_preserves_original(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "preflight.db"))
    with TestClient(app) as client:
        markdown = "\ufeff---\r\ntitle: 结构预检\r\n---\r\n# 结构预检\r\n\r\n## 第一节\r\n\r\n正文。\r\n"
        response = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("preflight.md", markdown.encode("utf-8"), "text/markdown")},
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["review_path"] == f'/tasks/{payload["task"]["id"]}'
        report = payload["input_summary"]["preflight_report"]
        assert report["status"] == "REVIEW"
        assert {item["code"] for item in report["findings"]} == {"missing_cover"}
        task = app.state.repository.get_task(payload["task"]["id"])
        assert task["markdown"] == markdown
        assert task["normalized_markdown"].startswith("---\n")
        assert task["source_hash"] != task["normalized_hash"]


def test_publication_draft_metadata_autosaves_without_changing_task_version(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "publication-draft-autosave.db"))
    with TestClient(app) as client:
        task = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("draft.md", "# 自动保存\n\n正文。".encode("utf-8"), "text/markdown")},
        ).json()["task"]
        saved = client.patch(
            f'/api/v1/article-tasks/{task["id"]}/publication-draft',
            headers={"X-Operator-Id": "operator"},
            json={
                "author": "示例号",
                "digest": "刷新页面后仍然保留",
                "content_source_url": "https://example.com/source",
                "show_cover_pic": False,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["metadata"]["digest"] == "刷新页面后仍然保留"
        detail = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
        assert detail["version"] == task["version"]
        assert detail["publication_draft_metadata"] == saved.json()["metadata"]
        events = app.state.repository.list_audit_events(task["id"])
        assert events[-1]["event_type"] == "publication_draft_autosaved"


def test_create_task_rejects_hard_block_and_planner_rejects_heading_jump(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "preflight-gates.db"))
    with TestClient(app) as client:
        blocked = client.post(
            "/api/v1/article-tasks",
            files={
                "markdown_file": (
                    "secret.md",
                    b"# title\n\nAPI_KEY=" + b"sk-" + b"sensitive-secret-value",
                    "text/markdown",
                )
            },
        )
        assert blocked.status_code == 422
        assert blocked.json()["error"]["code"] == "preflight_blocked"

        conflicted_markdown = """---
title: 标题 A
cover: ./cover.jpg
---
# 标题 A

## 正文

#### 跳级小节

内容。
"""
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("conflict.md", conflicted_markdown.encode("utf-8"), "text/markdown")},
        )
        assert created.status_code == 201
        task = created.json()["task"]
        generated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": task["version"]},
        )
        assert generated.status_code == 409
        assert generated.json()["error"]["code"] == "preflight_confirmation_required"


def test_acknowledge_preflight_warning_records_evidence_and_unlocks_clean_draft_gate(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "preflight-ack.db"))
    with TestClient(app) as client:
        markdown = """---
title: 后台长标题
cover: ./cover.jpg
---
# 正文视觉标题

只有一段正文，没有章节标题。
"""
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("ack.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()
        task = created["task"]
        report = created["input_summary"]["preflight_report"]
        assert report["planning_allowed"] is True
        assert report["draft_creation_allowed"] is False

        first = client.post(
            f'/api/v1/article-tasks/{task["id"]}/preflight/findings/title_source_conflict/acknowledge',
            headers={"X-Operator-Id": "operator"},
            json={"expected_task_version": task["version"], "block_id": None},
        )
        assert first.status_code == 200
        second = client.post(
            f'/api/v1/article-tasks/{task["id"]}/preflight/findings/no_sections/acknowledge',
            headers={"X-Operator-Id": "operator"},
            json={"expected_task_version": first.json()["task"]["version"], "block_id": None},
        )
        assert second.status_code == 200
        resolved_report = second.json()["input_summary"]["preflight_report"]
        assert resolved_report["draft_creation_allowed"] is False
        assert next(item for item in resolved_report["findings"] if item["code"] == "cover_requires_import").get("resolved_at") is None
        cover = client.post(
            f'/api/v1/article-tasks/{task["id"]}/preflight/findings/cover_requires_import/replace-asset',
            headers={"X-Operator-Id": "operator"},
            data={"expected_task_version": second.json()["task"]["version"]},
            files={"image_file": ("cover.png", _png_bytes(1080, 864), "image/png")},
        )
        assert cover.status_code == 200
        final_report = cover.json()["input_summary"]["preflight_report"]
        assert final_report["draft_creation_allowed"] is True
        assert all(item.get("resolved_by") == "operator" for item in final_report["findings"])
        events = app.state.repository.list_audit_events(task["id"])
        assert [item["event_type"] for item in events].count("preflight_acknowledged") == 2


def test_draft_blocking_asset_cannot_be_acknowledged(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "preflight-asset.db"))
    with TestClient(app) as client:
        markdown = """# 资产检查

## 正文

内容。
"""
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("asset.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()
        response = client.post(
            f'/api/v1/article-tasks/{created["task"]["id"]}/preflight/findings/missing_cover/acknowledge',
            json={"expected_task_version": created["task"]["version"], "block_id": None},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "finding_not_acknowledgeable"


def test_replace_cover_and_source_image_resolves_findings_without_mutating_markdown(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "preflight-replacements.db"))
    with TestClient(app) as client:
        markdown = """---
title: 资产替换测试
cover: https://picsum.photos/900/383
---
# 资产替换测试

## 正文

![章节占位图](https://picsum.photos/800/400?random=1)
"""
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("replacement.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()
        task = created["task"]
        report = created["input_summary"]["preflight_report"]
        image_finding = next(item for item in report["findings"] if item["code"] == "placeholder_image")

        cover = client.post(
            f'/api/v1/article-tasks/{task["id"]}/preflight/findings/placeholder_cover/replace-asset',
            headers={"X-Operator-Id": "operator"},
            data={"expected_task_version": task["version"]},
            files={"image_file": ("cover.png", _png_bytes(1080, 864), "image/png")},
        )
        assert cover.status_code == 200
        cover_payload = cover.json()
        assert cover_payload["input_summary"]["preflight_report"]["draft_creation_allowed"] is False

        body_image = client.post(
            f'/api/v1/article-tasks/{task["id"]}/preflight/findings/placeholder_image/replace-asset',
            headers={"X-Operator-Id": "operator"},
            data={
                "expected_task_version": cover_payload["task"]["version"],
                "block_id": image_finding["block_id"],
            },
            files={"image_file": ("body.png", _png_bytes(), "image/png")},
        )
        assert body_image.status_code == 200
        body_payload = body_image.json()
        resolved_report = body_payload["input_summary"]["preflight_report"]
        assert resolved_report["draft_creation_allowed"] is True
        resolved_image = next(item for item in resolved_report["findings"] if item["code"] == "placeholder_image")
        assert resolved_image["resolution_action"] == "REPLACE_ASSET"
        content_url = resolved_image["resolution_evidence"]["content_url"]
        assert client.get(content_url).status_code == 200
        stored = app.state.repository.get_task(task["id"])
        assert stored["markdown"] == markdown
        assert "picsum.photos" in stored["normalized_markdown"]

        generated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": body_payload["task"]["version"]},
        )
        assert generated.status_code == 202
        plan = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"][0]
        preview = client.get(plan["preview_url"])
        assert preview.status_code == 200
        assert content_url in preview.text
        assert "SOURCE IMAGE · WAITING" not in preview.text
        events = app.state.repository.list_audit_events(task["id"])
        assert [item["event_type"] for item in events].count("preflight_asset_replaced") == 2


def test_replace_preflight_asset_rejects_small_image_and_keeps_finding_open(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "preflight-small-image.db"))
    with TestClient(app) as client:
        markdown = """# 小图测试

## 正文

内容。
"""
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("small.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()
        response = client.post(
            f'/api/v1/article-tasks/{created["task"]["id"]}/preflight/findings/missing_cover/replace-asset',
            data={"expected_task_version": created["task"]["version"]},
            files={"image_file": ("small.png", _png_bytes(320, 180), "image/png")},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "image_too_small"
        detail = client.get(f'/api/v1/article-tasks/{created["task"]["id"]}').json()
        finding = next(
            item for item in detail["input_summary"]["preflight_report"]["findings"]
            if item["code"] == "missing_cover"
        )
        assert finding.get("resolved_at") is None


def test_publication_freeze_is_immutable_idempotent_and_locks_editing(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "publication-freeze.db"))
    with TestClient(app) as client:
        task, plan = _prepare_publication_ready_task(client)
        source_before = app.state.repository.get_task(task["id"])["source_hash"]
        normalized_before = app.state.repository.get_task(task["id"])["normalized_hash"]
        readiness = client.get(f'/api/v1/article-tasks/{task["id"]}/publication-readiness')
        assert readiness.status_code == 200
        assert readiness.json()["ready"] is True
        assert set(readiness.json()["checks"].values()) == {"pass"}

        frozen = _freeze_publication(client, task)
        revision = frozen["revision"]
        frozen_task = frozen["task"]
        assert revision["lifecycle_status"] == "active"
        assert frozen_task["status"] == "publication_frozen"
        assert frozen_task["active_publication_revision_id"] == revision["id"]
        assert revision["compatibility_report"]["status"] == "pass"
        assets = app.state.repository.list_publication_assets(revision["id"])
        assert assets
        assert all(item["output_sha256"] for item in assets)

        preview = client.get(revision["preview_url"])
        assert preview.status_code == 200
        assert "三步完成志愿核对" in preview.text
        assert len(preview.content) > 1000
        assert "asset://" not in preview.text
        assert "/api/v1/brand-assets/current/content" not in preview.text
        assert app.state.repository.get_task(task["id"])["source_hash"] == source_before
        assert app.state.repository.get_task(task["id"])["normalized_hash"] == normalized_before

        replay = _freeze_publication(client, task)
        assert replay["revision"]["id"] == revision["id"]
        assert len(client.get(f'/api/v1/article-tasks/{task["id"]}/publication-revisions').json()["items"]) == 1

        locked = client.patch(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/slots/{plan["slots"][0]["slot_id"]}',
            json={
                "variant": plan["slots"][0]["fallback_variant"],
                "expected_plan_revision": plan["revision"],
                "reason": "operator_manual_switch",
            },
        )
        assert locked.status_code == 409
        assert locked.json()["error"]["code"] == "publication_revision_locked"


def test_publication_gate_detects_tampered_selected_asset(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "publication-asset-integrity.db"))
    with TestClient(app) as client:
        task, _ = _prepare_publication_ready_task(client)
        cover = next(
            item
            for item in app.state.repository.list_preflight_asset_replacements(task["id"])
            if item["asset_role"] == "cover"
        )
        cover_path, _ = app.state.repository.get_preflight_asset(cover["id"])
        cover_path.write_bytes(_png_bytes(1080, 864, (190, 70, 50)))

        readiness = client.get(f'/api/v1/article-tasks/{task["id"]}/publication-readiness')
        assert readiness.status_code == 200
        assert readiness.json()["ready"] is False
        assert "selected_asset_hash_mismatch" in {item["code"] for item in readiness.json()["blockers"]}


def test_continue_editing_supersedes_revision_and_reopens_working_copy(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "publication-continue.db"))
    with TestClient(app) as client:
        task, plan = _prepare_publication_ready_task(client)
        frozen = _freeze_publication(client, task)
        revision = frozen["revision"]
        continued = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/continue-editing',
            headers={"X-Operator-Id": "operator"},
            json={"expected_task_version": frozen["task"]["version"]},
        )
        assert continued.status_code == 200
        reopened = continued.json()["task"]
        assert reopened["status"] == "plan_selected"
        assert reopened["active_publication_revision_id"] is None
        assert client.get(f'/api/v1/publication-revisions/{revision["id"]}').json()["lifecycle_status"] == "superseded"

        changed = client.patch(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/slots/{plan["slots"][0]["slot_id"]}',
            json={
                "variant": plan["slots"][0]["fallback_variant"],
                "expected_plan_revision": plan["revision"],
                "reason": "operator_manual_switch",
            },
        )
        assert changed.status_code == 200


def test_mock_draft_success_is_idempotent_and_occupies_explicit_slot(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "mock-draft-success.db"))
    with TestClient(app) as client:
        task, _ = _prepare_publication_ready_task(client)
        assert app.state.repository.list_recent_component_summaries("default", 5) == []
        frozen = _freeze_publication(client, task)
        revision = frozen["revision"]
        request = {
            "expected_task_version": frozen["task"]["version"],
            "draft_slot": "primary",
            "simulation_mode": "success",
        }
        created = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/draft-operations',
            headers={"Idempotency-Key": "mock-success", "X-Operator-Id": "operator"},
            json=request,
        )
        assert created.status_code == 200
        operation = created.json()["operation"]
        assert operation["provider"] == "mock"
        assert operation["status"] == "succeeded"
        assert operation["media_id"].startswith("MOCK_MEDIA_")
        assert created.json()["task"]["status"] == "mock_draft_created"
        history = app.state.repository.list_recent_component_summaries("default", 5)
        assert len(history) == 1
        frozen_plan = app.state.repository.get_publication_revision(revision["id"])["visual_plan"]
        assert history[0]["components"] == [
            {"component_type": slot["component_type"], "variant": slot["variant"]}
            for slot in frozen_plan["slots"]
        ]

        replay = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/draft-operations',
            headers={"Idempotency-Key": "mock-success", "X-Operator-Id": "operator"},
            json=request,
        )
        assert replay.status_code == 200
        assert replay.json()["operation"]["id"] == operation["id"]

        continued = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/continue-editing',
            json={"expected_task_version": created.json()["task"]["version"]},
        )
        reopened = continued.json()["task"]
        refrozen = _freeze_publication(client, reopened, "freeze-second")
        assert refrozen["revision"]["suggested_draft_slot"] == "draft-2"
        wrong_slot = client.post(
            f'/api/v1/publication-revisions/{refrozen["revision"]["id"]}/draft-operations',
            headers={"Idempotency-Key": "wrong-slot"},
            json={
                "expected_task_version": refrozen["task"]["version"],
                "draft_slot": "primary",
                "simulation_mode": "success",
            },
        )
        assert wrong_slot.status_code == 409


def test_mock_draft_fail_once_retry_and_unknown_resolution(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_DIRECTOR_ENABLE_MOCK_FAILURES", "1")
    app = create_app(str(tmp_path / "mock-draft-failures.db"))
    with TestClient(app) as client:
        task, _ = _prepare_publication_ready_task(client)
        frozen = _freeze_publication(client, task)
        revision = frozen["revision"]
        failed = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/draft-operations',
            headers={"Idempotency-Key": "mock-fail-once"},
            json={
                "expected_task_version": frozen["task"]["version"],
                "draft_slot": "primary",
                "simulation_mode": "fail_once",
            },
        ).json()
        assert failed["operation"]["status"] == "failed"
        retried = client.post(
            f'/api/v1/draft-operations/{failed["operation"]["id"]}/retry',
            headers={"Idempotency-Key": "mock-retry"},
            json={
                "expected_task_version": failed["task"]["version"],
                "expected_operation_version": failed["operation"]["version"],
            },
        )
        assert retried.status_code == 200
        assert retried.json()["operation"]["status"] == "succeeded"

        continued = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/continue-editing',
            json={"expected_task_version": retried.json()["task"]["version"]},
        ).json()["task"]
        refrozen = _freeze_publication(client, continued, "freeze-unknown")
        unknown = client.post(
            f'/api/v1/publication-revisions/{refrozen["revision"]["id"]}/draft-operations',
            headers={"Idempotency-Key": "mock-unknown"},
            json={
                "expected_task_version": refrozen["task"]["version"],
                "draft_slot": "draft-2",
                "simulation_mode": "unknown",
            },
        ).json()
        assert unknown["operation"]["status"] == "unknown"
        blocked = client.post(
            f'/api/v1/publication-revisions/{refrozen["revision"]["id"]}/continue-editing',
            json={"expected_task_version": unknown["task"]["version"]},
        )
        assert blocked.status_code == 409
        forbidden = client.post(
            f'/api/v1/draft-operations/{unknown["operation"]["id"]}/resolve-unknown',
            headers={"Idempotency-Key": "resolve-forbidden", "X-Operator-Id": "operator"},
            json={
                "expected_task_version": unknown["task"]["version"],
                "expected_operation_version": unknown["operation"]["version"],
                "outcome": "confirmed_not_created",
                "evidence": "运营已核对后台草稿箱，确认不存在对应草稿。",
            },
        )
        assert forbidden.status_code == 403
        resolved = client.post(
            f'/api/v1/draft-operations/{unknown["operation"]["id"]}/resolve-unknown',
            headers={"Idempotency-Key": "resolve-unknown", "X-Operator-Id": "product_owner"},
            json={
                "expected_task_version": unknown["task"]["version"],
                "expected_operation_version": unknown["operation"]["version"],
                "outcome": "confirmed_not_created",
                "evidence": "运营已核对后台草稿箱，确认不存在对应草稿。",
            },
        )
        assert resolved.status_code == 200
        assert resolved.json()["operation"]["status"] == "failed"
        assert resolved.json()["operation"]["last_error"]["retryable"] is True


def test_intelligent_planner_calls_once_and_returns_two_visual_systems(tmp_path: Path) -> None:
    provider = MockTextPlannerProvider()
    app = create_app(str(tmp_path / "intelligent.db"), text_planner_provider=provider)
    with TestClient(app) as client:
        markdown = """---
title: 三步完成升学判断
article_type: tutorial_steps
---
# 三步完成升学判断

先明确目标，再核对证据，最后形成行动清单。

## 行动路径

1. 明确目标院校
2. 核对官方位次
3. 形成志愿梯度

> 志愿表不是一次凭感觉排序，而是一组需要逐项验证的决策。
"""
        task = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("intelligent.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()["task"]
        generated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={
                "mode": "start",
                "planner": "intelligent",
                "expected_task_version": task["version"],
            },
        )
        assert generated.status_code == 202
        assert generated.json()["planner_call_count"] == 1

        payload = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()
        plans = payload["plans"]
        assert payload["comparison"]["shared_structure"] is True
        assert len(plans) == 2
        assert {plan["visual_system"] for plan in plans} == {"light_reading", "editorial_contrast"}
        assert len({plan["structure_fingerprint"] for plan in plans}) == 1
        assert all(plan["planner_metadata"]["planner_call_count"] == 1 for plan in plans)
        assert all(plan["planner_metadata"]["provider"] == "mock_text_planner" for plan in plans)

        def semantic_slots(plan: dict) -> list[tuple]:
            return [
                (
                    slot["slot_id"],
                    slot["component_type"],
                    slot["anchor_block_id"],
                    tuple(slot["consume_block_ids"]),
                    slot["semantic_role"],
                )
                for slot in plan["slots"]
            ]

        assert semantic_slots(plans[0]) == semantic_slots(plans[1])
        assert plans[0]["image_slots"] == plans[1]["image_slots"]
        assert plans[0]["preview_content_hash"] != plans[1]["preview_content_hash"]


def test_switch_single_slot_create_revision_undo_once_and_audit(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "revisions.db"))
    with TestClient(app) as client:
        markdown = """---
title: 三步规划
article_type: tutorial_steps
---
# 三步规划

先确定目标，再开始行动。

## 三步行动路径

1. 确定目标
2. 倒推能力
3. 主动学习
"""
        created = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("sample.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()["task"]
        client.post(
            f'/api/v1/article-tasks/{created["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": created["version"]},
        )
        plan = client.get(f'/api/v1/article-tasks/{created["id"]}/plans').json()["plans"][0]
        slot = next(item for item in plan["slots"] if item["component_type"] == "logic_path")
        original_hash = plan["preview_content_hash"]
        original_source_hash = app.state.repository.get_task(created["id"])["source_hash"]

        changed = client.patch(
            f'/api/v1/article-tasks/{created["id"]}/plans/{plan["id"]}/slots/{slot["slot_id"]}',
            json={
                "variant": slot["fallback_variant"],
                "expected_plan_revision": 1,
                "reason": "operator_manual_switch",
            },
        )
        assert changed.status_code == 200
        assert changed.json()["revision"] == 2
        assert changed.json()["planner_called"] is False
        assert changed.json()["preview_content_hash"] != original_hash
        assert changed.json()["plan"]["revision"] == 2
        assert changed.json()["plan"]["preview_url"] == changed.json()["preview_url"]
        assert changed.json()["plan"]["slots"][0]["variant_options"]
        assert app.state.repository.get_task(created["id"])["source_hash"] == original_source_hash

        revisions = client.get(
            f'/api/v1/article-tasks/{created["id"]}/plans/{plan["id"]}/revisions'
        ).json()["items"]
        assert [item["revision"] for item in revisions] == [2, 1]

        restored = client.post(
            f'/api/v1/article-tasks/{created["id"]}/plans/{plan["id"]}/undo',
            json={"expected_plan_revision": 2},
        )
        assert restored.status_code == 200
        assert restored.json()["revision"] == 3
        assert restored.json()["preview_content_hash"] == original_hash
        assert restored.json()["can_undo"] is False
        assert restored.json()["plan"]["revision"] == 3
        assert restored.json()["plan"]["preview_url"] == restored.json()["preview_url"]

        repeated = client.post(
            f'/api/v1/article-tasks/{created["id"]}/plans/{plan["id"]}/undo',
            json={"expected_plan_revision": 3},
        )
        assert repeated.status_code == 409
        assert repeated.json()["error"]["code"] == "nothing_to_undo"

        events = app.state.repository.list_audit_events(created["id"])
        event_types = [event["event_type"] for event in events]
        assert "component_variant_switched" in event_types
        assert "plan_change_undone" in event_types


def test_confirmed_variant_history_chooses_fresher_variant_without_removing_component(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "history.db"))
    repository = app.state.repository
    repository.record_confirmed_component_summary(
        account_id="default",
        task_id="confirmed-1",
        components=[{"component_type": "logic_path", "variant": "warm_route_nodes"}],
    )
    repository.record_confirmed_component_summary(
        account_id="default",
        task_id="confirmed-2",
        components=[{"component_type": "logic_path", "variant": "warm_route_nodes"}],
    )

    with TestClient(app) as client:
        markdown = """# 三步历史测试

## 行动路径

1. 确定目标
2. 倒推能力
3. 主动学习
"""
        task = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("history.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()["task"]
        client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": task["version"]},
        )
        plans = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"]
        assert "已读取最近 2 篇确认记录" in plans[0]["difference_from_recent"][0]
        assert "具体变体" in plans[0]["difference_from_recent"][0]
        logic_slots = [
            slot
            for plan in plans
            for slot in plan["slots"]
            if slot["component_type"] == "logic_path"
        ]
        assert logic_slots
        assert all(slot["variant"] == "folded_stair" for slot in logic_slots)
        assert all(slot["history_evidence"]["penalty_applied"] for slot in logic_slots)
        assert all(slot["history_evidence"]["avoided_variant"] == "warm_route_nodes" for slot in logic_slots)
        assert all(slot["history_evidence"]["component_use_count"] == 2 for slot in logic_slots)


def test_mock_image_candidate_generate_accept_regenerate_skip_and_replace(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "images.db"), image_provider=MockImageProvider())
    with TestClient(app) as client:
        markdown = """# 三步配图测试

## 行动路径

1. 确定目标
2. 倒推能力
3. 开始行动
"""
        task = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("images.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()["task"]
        client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": task["version"]},
        )
        detail = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
        plans = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"]
        selected = plans[0]
        unselected = plans[1]
        client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/select',
            json={"plan_id": selected["id"], "expected_task_version": detail["version"]},
        )

        blocked = client.get(
            f'/api/v1/article-tasks/{task["id"]}/plans/{unselected["id"]}/image-slots'
        )
        assert blocked.status_code == 409

        listed = client.get(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/image-slots'
        )
        assert listed.status_code == 200
        item = listed.json()["items"][0]
        assert item["state"]["status"] == "planned"
        assert item["state"]["image_revision"] == 1

        generated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/image-slots/{item["image_slot_id"]}/generate',
            json={"mode": "start", "expected_image_revision": 1},
        )
        assert generated.status_code == 200
        state = generated.json()["image_slot"]
        assert generated.json()["provider_mode"] == "mock"
        assert state["status"] == "generated"
        assert state["image_revision"] == 2
        assert len(state["candidates"]) == 1
        first_candidate = state["candidates"][0]
        assert first_candidate["provider"] == "mock"
        assert first_candidate["raw_content_url"]
        image_response = client.get(first_candidate["content_url"])
        assert image_response.status_code == 200
        assert image_response.headers["content-type"].startswith("image/png")
        raw_response = client.get(first_candidate["raw_content_url"])
        assert raw_response.status_code == 200
        assert raw_response.content == image_response.content

        verification_blocked = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/image-slots/{item["image_slot_id"]}/candidates/{first_candidate["id"]}/accept',
            json={"expected_image_revision": 2},
        )
        assert verification_blocked.status_code == 422
        assert verification_blocked.json()["error"]["code"] == "image_text_verification_required"

        accepted = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/image-slots/{item["image_slot_id"]}/candidates/{first_candidate["id"]}/accept',
            json={"expected_image_revision": 2, "text_verified": True},
        )
        state = accepted.json()["image_slot"]
        assert state["status"] == "accepted"
        assert state["selected_candidate_id"] == first_candidate["id"]
        assert state["image_revision"] == 3
        accepted_preview = client.get(selected["preview_url"])
        assert first_candidate["content_url"] in accepted_preview.text
        assert f'width="{first_candidate["width"]}"' in accepted_preview.text
        assert f'height="{first_candidate["height"]}"' in accepted_preview.text
        assert "decoding=\"sync\"" in accepted_preview.text

        regenerated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/image-slots/{item["image_slot_id"]}/generate',
            json={"mode": "regenerate", "expected_image_revision": 3},
        )
        state = regenerated.json()["image_slot"]
        assert len(state["candidates"]) == 2
        assert state["selected_candidate_id"] == first_candidate["id"]
        assert state["image_revision"] == 4

        fallback = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/image-slots/{item["image_slot_id"]}/generate',
            json={"mode": "fallback", "expected_image_revision": 4},
        )
        assert fallback.status_code == 200
        state = fallback.json()["image_slot"]
        fallback_candidate = state["candidates"][-1]
        assert fallback_candidate["provider"] == "deterministic_fallback"
        assert fallback_candidate["machine_checks"]["text_consistency"]["status"] == "passed"
        assert client.get(fallback_candidate["content_url"]).content != client.get(
            fallback_candidate["raw_content_url"]
        ).content
        assert state["image_revision"] == 5

        skipped = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/image-slots/{item["image_slot_id"]}/skip',
            json={"expected_image_revision": 5},
        )
        state = skipped.json()["image_slot"]
        assert state["status"] == "skipped"
        assert state["selected_candidate_id"] is None
        assert state["image_revision"] == 6
        skipped_preview = client.get(selected["preview_url"])
        assert f'id="{item["image_slot_id"]}"' not in skipped_preview.text

        replaced = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{selected["id"]}/image-slots/{item["image_slot_id"]}/replace',
            data={"expected_image_revision": "6"},
            files={"image_file": ("replacement.png", image_response.content, "image/png")},
        )
        assert replaced.status_code == 200
        state = replaced.json()["image_slot"]
        assert state["status"] == "replaced"
        assert state["decision"] == "replaced"
        assert state["selected_candidate_id"] is not None
        assert state["image_revision"] == 7
        replaced_candidate = next(
            candidate for candidate in state["candidates"] if candidate["id"] == state["selected_candidate_id"]
        )
        replaced_preview = client.get(selected["preview_url"])
        assert replaced_candidate["content_url"] in replaced_preview.text


def test_cover_planner_generates_crops_and_selects_controlled_cover(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "cover-planner.db"), image_provider=MockImageProvider())
    with TestClient(app) as client:
        markdown = """# 三步完成志愿核对

先明确目标，再核对证据，最后形成行动清单。

## 行动路径

1. 明确目标院校
2. 核对官方位次
3. 形成志愿梯度
"""
        task = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("cover.md", markdown.encode("utf-8"), "text/markdown")},
            data={"article_type": "tutorial_steps"},
        ).json()["task"]
        client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": task["version"]},
        )
        task = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
        plan = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"][0]
        selected = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/select',
            json={"plan_id": plan["id"], "expected_task_version": task["version"]},
        ).json()
        task_version = selected["version"]

        workspace = client.get(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/cover-candidates'
        ).json()
        assert workspace["cover_brief"]["output_size"] == "1080x864"
        assert workspace["cover_brief"]["text_policy"] == "image_only"
        generated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/cover-candidates/generate',
            json={"expected_task_version": task_version},
        )
        assert generated.status_code == 200
        candidate = generated.json()["candidate"]
        assert candidate["source_type"] == "ai_generated"
        assert (candidate["width"], candidate["height"]) == (1080, 864)
        content = client.get(candidate["content_url"])
        with Image.open(BytesIO(content.content)) as image:
            assert image.size == (1080, 864)

        adopted = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/cover-candidates/{candidate["id"]}/select',
            json={"expected_task_version": task_version},
        )
        assert adopted.status_code == 200
        assert adopted.json()["workspace"]["selected_cover"]["width"] == 1080
        assert adopted.json()["workspace"]["candidates"][0]["selected"] is True


def test_cover_planner_reuses_accepted_body_image_without_mutating_it(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "cover-reuse.db"), image_provider=MockImageProvider())
    with TestClient(app) as client:
        markdown = """# 长文封面复用

## 路线说明

1. 明确目标
2. 核对证据
3. 形成行动
"""
        task = client.post(
            "/api/v1/article-tasks",
            files={"markdown_file": ("reuse.md", markdown.encode("utf-8"), "text/markdown")},
        ).json()["task"]
        client.post(
            f'/api/v1/article-tasks/{task["id"]}/generate-plans',
            json={"mode": "start", "expected_task_version": task["version"]},
        )
        task = client.get(f'/api/v1/article-tasks/{task["id"]}').json()["task"]
        plan = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()["plans"][0]
        selected = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/select',
            json={"plan_id": plan["id"], "expected_task_version": task["version"]},
        ).json()
        slots = client.get(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots'
        ).json()["items"]
        assert slots
        slot = slots[0]
        generated = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots/{slot["image_slot_id"]}/generate',
            json={"mode": "start", "expected_image_revision": slot["state"]["image_revision"]},
        ).json()["image_slot"]
        body_candidate = generated["candidates"][0]
        original_bytes = client.get(body_candidate["content_url"]).content
        client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots/{slot["image_slot_id"]}/candidates/{body_candidate["id"]}/accept',
            json={"expected_image_revision": generated["image_revision"], "text_verified": True},
        )
        workspace = client.get(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/cover-candidates'
        ).json()
        source = next(item for item in workspace["reuse_sources"] if item["source_type"] == "accepted_body_image")
        reused = client.post(
            f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/cover-candidates/reuse',
            json={
                "expected_task_version": selected["version"],
                "source_type": source["source_type"],
                "source_id": source["source_id"],
            },
        )
        assert reused.status_code == 200
        assert reused.json()["candidate"]["source_type"] == "accepted_body_image"
        assert reused.json()["candidate"]["model"] == "deterministic_cover_fit_v2"
        assert (
            reused.json()["candidate"]["machine_checks"]["cover_fit"]
            == "1080x864_contain_over_soft_backdrop"
        )
        assert client.get(body_candidate["content_url"]).content == original_bytes


def test_wenyan_draft_uses_frozen_revision_and_replays_without_duplicate(tmp_path: Path) -> None:
    publisher = _SuccessfulWenyanPublisher()
    app = create_app(str(tmp_path / "wenyan-draft.db"), wenyan_publisher=publisher)
    with TestClient(app) as client:
        task, _ = _prepare_publication_ready_task(client)
        frozen = _freeze_publication(client, task, "freeze-for-wenyan")
        revision = frozen["revision"]
        frozen_task = frozen["task"]
        payload = {
            "expected_task_version": frozen_task["version"],
            "draft_slot": revision["suggested_draft_slot"],
        }
        created = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/wenyan-draft',
            headers={"Idempotency-Key": "wenyan-real-1", "X-Operator-Id": "operator"},
            json=payload,
        )
        assert created.status_code == 200, created.text
        result = created.json()
        assert result["operation"]["provider"] == "wenyan"
        assert result["operation"]["is_mock"] is False
        assert result["operation"]["status"] == "succeeded"
        assert result["operation"]["media_id"] == "REAL_MEDIA_001"
        assert result["task"]["status"] == "wechat_draft_created"

        replay = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/wenyan-draft',
            headers={"Idempotency-Key": "wenyan-real-1", "X-Operator-Id": "operator"},
            json=payload,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["idempotency_replayed"] is True
        assert replay.json()["operation"]["id"] == result["operation"]["id"]
        assert publisher.publish_count == 1

        bundle = client.get(f'/api/v1/publication-revisions/{revision["id"]}/bundle')
        assert bundle.status_code == 200
        assert bundle.headers["content-type"] == "application/zip"


def test_failed_wenyan_draft_can_retry_once_without_creating_a_new_operation(tmp_path: Path) -> None:
    publisher = _FailThenSucceedWenyanPublisher()
    app = create_app(str(tmp_path / "wenyan-draft-retry.db"), wenyan_publisher=publisher)
    with TestClient(app) as client:
        task, _ = _prepare_publication_ready_task(client)
        frozen = _freeze_publication(client, task, "freeze-for-wenyan-retry")
        revision = frozen["revision"]
        failed = client.post(
            f'/api/v1/publication-revisions/{revision["id"]}/wenyan-draft',
            headers={"Idempotency-Key": "wenyan-fail-1", "X-Operator-Id": "operator"},
            json={
                "expected_task_version": frozen["task"]["version"],
                "draft_slot": revision["suggested_draft_slot"],
            },
        )
        assert failed.status_code == 200, failed.text
        failed_result = failed.json()
        assert failed_result["operation"]["status"] == "failed"
        assert failed_result["task"]["status"] == "wechat_draft_failed"

        retried = client.post(
            f'/api/v1/draft-operations/{failed_result["operation"]["id"]}/wenyan-retry',
            headers={"Idempotency-Key": "wenyan-retry-1", "X-Operator-Id": "operator"},
            json={
                "expected_task_version": failed_result["task"]["version"],
                "expected_operation_version": failed_result["operation"]["version"],
            },
        )
        assert retried.status_code == 200, retried.text
        retry_result = retried.json()
        assert retry_result["idempotency_replayed"] is False
        assert retry_result["operation"]["id"] == failed_result["operation"]["id"]
        assert retry_result["operation"]["status"] == "succeeded"
        assert retry_result["operation"]["media_id"] == "REAL_MEDIA_RETRY_001"
        assert retry_result["task"]["status"] == "wechat_draft_created"
        assert publisher.publish_count == 2

        replay = client.post(
            f'/api/v1/draft-operations/{failed_result["operation"]["id"]}/wenyan-retry',
            headers={"Idempotency-Key": "wenyan-retry-1", "X-Operator-Id": "operator"},
            json={
                "expected_task_version": failed_result["task"]["version"],
                "expected_operation_version": failed_result["operation"]["version"],
            },
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["idempotency_replayed"] is True
        assert publisher.publish_count == 2
