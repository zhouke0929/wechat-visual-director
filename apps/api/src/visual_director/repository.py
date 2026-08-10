from __future__ import annotations

import json
import hashlib
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PUBLICATION_DRAFT_METADATA = {
    "author": "",
    "digest": "",
    "content_source_url": "",
    "show_cover_pic": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotFoundError(LookupError):
    pass


class VersionConflictError(RuntimeError):
    pass


class PublicationLockedError(VersionConflictError):
    pass


class Repository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
            self.image_asset_dir = Path(database_path).parent / "image-assets"
        else:
            self.image_asset_dir = Path.cwd() / ".tmp-image-assets"
        self.publication_asset_dir = self.image_asset_dir.parent / "publication-assets"
        self.image_asset_dir.mkdir(parents=True, exist_ok=True)
        self.publication_asset_dir.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.lock = threading.RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY,
              account_id TEXT NOT NULL,
              title TEXT NOT NULL,
              article_type TEXT,
              status TEXT NOT NULL,
              history_window INTEGER NOT NULL,
              brand_profile_version TEXT NOT NULL,
              fixed_footer_asset_version TEXT NOT NULL,
              selected_plan_id TEXT,
              version INTEGER NOT NULL,
              selection_change_count INTEGER NOT NULL DEFAULT 0,
              markdown TEXT NOT NULL,
              source_hash TEXT NOT NULL,
              input_summary_json TEXT NOT NULL,
              progress_json TEXT NOT NULL,
              last_error_json TEXT,
              publication_draft_metadata_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              plan_id TEXT NOT NULL,
              html TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plans (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              plan_index INTEGER NOT NULL,
              plan_json TEXT NOT NULL,
              artifact_id TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plan_revisions (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              plan_id TEXT NOT NULL,
              revision INTEGER NOT NULL,
              plan_json TEXT NOT NULL,
              artifact_id TEXT NOT NULL,
              change_reason TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(plan_id, revision)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recent_article_component_summaries (
              id TEXT PRIMARY KEY,
              account_id TEXT NOT NULL,
              task_id TEXT NOT NULL,
              publication_revision_id TEXT,
              summary_json TEXT NOT NULL,
              confirmed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS image_slot_states (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              plan_id TEXT NOT NULL,
              image_slot_id TEXT NOT NULL,
              status TEXT NOT NULL,
              image_revision INTEGER NOT NULL,
              selected_candidate_id TEXT,
              decision TEXT NOT NULL,
              last_error_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(plan_id, image_slot_id)
            );
            CREATE TABLE IF NOT EXISTS image_candidates (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              plan_id TEXT NOT NULL,
              image_slot_id TEXT NOT NULL,
              candidate_index INTEGER NOT NULL,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              provider_prompt TEXT NOT NULL,
              prompt_sha256 TEXT NOT NULL,
              status TEXT NOT NULL,
              output_filename TEXT NOT NULL,
              raw_output_filename TEXT,
              content_type TEXT NOT NULL,
              output_sha256 TEXT NOT NULL,
              raw_output_sha256 TEXT,
              width INTEGER NOT NULL,
              height INTEGER NOT NULL,
              latency_ms INTEGER NOT NULL,
              machine_checks_json TEXT NOT NULL,
              human_decision TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cover_candidates (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              plan_id TEXT NOT NULL,
              candidate_index INTEGER NOT NULL,
              source_type TEXT NOT NULL,
              source_resource_id TEXT,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              provider_prompt TEXT NOT NULL,
              prompt_sha256 TEXT NOT NULL,
              output_filename TEXT NOT NULL,
              content_type TEXT NOT NULL,
              output_sha256 TEXT NOT NULL,
              width INTEGER NOT NULL,
              height INTEGER NOT NULL,
              latency_ms INTEGER NOT NULL,
              machine_checks_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS blind_review_submissions (
              id TEXT PRIMARY KEY,
              eval_set_id TEXT NOT NULL,
              reviewer_id TEXT NOT NULL,
              sample_id TEXT NOT NULL,
              assignment_token TEXT NOT NULL,
              response_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(eval_set_id, reviewer_id, sample_id)
            );
            CREATE TABLE IF NOT EXISTS preflight_asset_replacements (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              asset_key TEXT NOT NULL,
              finding_code TEXT NOT NULL,
              block_id TEXT,
              asset_role TEXT NOT NULL,
              original_source TEXT,
              output_filename TEXT NOT NULL,
              content_type TEXT NOT NULL,
              output_sha256 TEXT NOT NULL,
              width INTEGER NOT NULL,
              height INTEGER NOT NULL,
              replaced_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(task_id, asset_key)
            );
            CREATE TABLE IF NOT EXISTS publication_revisions (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              revision_number INTEGER NOT NULL,
              plan_id TEXT NOT NULL,
              plan_revision INTEGER NOT NULL,
              lifecycle_status TEXT NOT NULL,
              normalized_hash TEXT NOT NULL,
              preflight_report_hash TEXT NOT NULL,
              visual_plan_json TEXT NOT NULL,
              visual_plan_hash TEXT NOT NULL,
              frozen_html TEXT NOT NULL,
              frozen_html_hash TEXT NOT NULL,
              structure_hash TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              metadata_hash TEXT NOT NULL,
              asset_manifest_json TEXT NOT NULL,
              asset_manifest_hash TEXT NOT NULL,
              compatibility_report_json TEXT NOT NULL,
              compatibility_report_hash TEXT NOT NULL,
              frozen_by TEXT NOT NULL,
              frozen_at TEXT NOT NULL,
              superseded_at TEXT,
              UNIQUE(task_id, revision_number),
              UNIQUE(id, task_id),
              FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS publication_assets (
              id TEXT PRIMARY KEY,
              revision_id TEXT NOT NULL,
              asset_token TEXT NOT NULL,
              asset_role TEXT NOT NULL,
              source_resource_type TEXT NOT NULL,
              source_resource_id TEXT NOT NULL,
              block_id TEXT,
              image_slot_id TEXT,
              relative_filename TEXT NOT NULL,
              content_type TEXT NOT NULL,
              output_sha256 TEXT NOT NULL,
              width INTEGER NOT NULL,
              height INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(revision_id, asset_token),
              UNIQUE(revision_id, asset_role, source_resource_id),
              FOREIGN KEY(revision_id) REFERENCES publication_revisions(id)
            );
            CREATE TABLE IF NOT EXISTS draft_slots (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              slot_key TEXT NOT NULL,
              successful_media_id TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(task_id, slot_key),
              UNIQUE(id, task_id),
              FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS draft_operations (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              revision_id TEXT NOT NULL,
              draft_slot_id TEXT NOT NULL,
              provider TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              status TEXT NOT NULL,
              version INTEGER NOT NULL,
              simulation_mode TEXT NOT NULL,
              media_id TEXT,
              confirmation_json TEXT NOT NULL,
              last_error_json TEXT,
              resolution_json TEXT,
              confirmed_by TEXT NOT NULL,
              confirmed_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(revision_id, draft_slot_id),
              UNIQUE(idempotency_key),
              FOREIGN KEY(revision_id, task_id) REFERENCES publication_revisions(id, task_id),
              FOREIGN KEY(draft_slot_id, task_id) REFERENCES draft_slots(id, task_id)
            );
            CREATE TABLE IF NOT EXISTS draft_operation_steps (
              id TEXT PRIMARY KEY,
              operation_id TEXT NOT NULL,
              step_key TEXT NOT NULL,
              sequence_no INTEGER NOT NULL,
              status TEXT NOT NULL,
              version INTEGER NOT NULL,
              attempt_count INTEGER NOT NULL,
              input_hash TEXT NOT NULL,
              output_json TEXT,
              last_error_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(operation_id, step_key),
              UNIQUE(operation_id, sequence_no),
              FOREIGN KEY(operation_id) REFERENCES draft_operations(id)
            );
            CREATE TABLE IF NOT EXISTS idempotency_records (
              id TEXT PRIMARY KEY,
              scope TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              request_hash TEXT NOT NULL,
              resource_type TEXT NOT NULL,
              resource_id TEXT,
              response_json TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(scope, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_plans_task ON plans(task_id, plan_index);
            CREATE INDEX IF NOT EXISTS idx_plan_revisions_plan ON plan_revisions(plan_id, revision DESC);
            CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_events(task_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_recent_components_account ON recent_article_component_summaries(account_id, confirmed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_image_states_plan ON image_slot_states(plan_id, image_slot_id);
            CREATE INDEX IF NOT EXISTS idx_image_candidates_slot ON image_candidates(plan_id, image_slot_id, candidate_index);
            CREATE INDEX IF NOT EXISTS idx_cover_candidates_plan ON cover_candidates(task_id, plan_id, candidate_index);
            CREATE INDEX IF NOT EXISTS idx_blind_review_progress ON blind_review_submissions(eval_set_id, reviewer_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_preflight_assets_task ON preflight_asset_replacements(task_id, asset_key);
            CREATE INDEX IF NOT EXISTS idx_publication_revisions_task ON publication_revisions(task_id, revision_number DESC);
            CREATE INDEX IF NOT EXISTS idx_publication_assets_revision ON publication_assets(revision_id, asset_token);
            CREATE INDEX IF NOT EXISTS idx_draft_slots_task ON draft_slots(task_id, slot_key);
            CREATE INDEX IF NOT EXISTS idx_draft_operations_task ON draft_operations(task_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_draft_steps_operation ON draft_operation_steps(operation_id, sequence_no);
            """
        )
        image_state_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(image_slot_states)").fetchall()
        }
        if "last_error_json" not in image_state_columns:
            self.connection.execute("ALTER TABLE image_slot_states ADD COLUMN last_error_json TEXT")
        image_candidate_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(image_candidates)").fetchall()
        }
        if "raw_output_filename" not in image_candidate_columns:
            self.connection.execute("ALTER TABLE image_candidates ADD COLUMN raw_output_filename TEXT")
        if "raw_output_sha256" not in image_candidate_columns:
            self.connection.execute("ALTER TABLE image_candidates ADD COLUMN raw_output_sha256 TEXT")
        task_columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(tasks)").fetchall()}
        if "normalized_markdown" not in task_columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN normalized_markdown TEXT")
        if "normalized_hash" not in task_columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN normalized_hash TEXT")
        if "active_publication_revision_id" not in task_columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN active_publication_revision_id TEXT")
        if "publication_draft_metadata_json" not in task_columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN publication_draft_metadata_json TEXT")
        history_columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(recent_article_component_summaries)").fetchall()
        }
        if "publication_revision_id" not in history_columns:
            self.connection.execute(
                "ALTER TABLE recent_article_component_summaries ADD COLUMN publication_revision_id TEXT"
            )
        self.connection.execute(
            "UPDATE tasks SET normalized_markdown = markdown WHERE normalized_markdown IS NULL"
        )
        self.connection.execute(
            "UPDATE tasks SET normalized_hash = source_hash WHERE normalized_hash IS NULL"
        )
        self.connection.execute(
            "UPDATE tasks SET publication_draft_metadata_json = ? WHERE publication_draft_metadata_json IS NULL",
            (json.dumps(DEFAULT_PUBLICATION_DRAFT_METADATA, ensure_ascii=False),),
        )
        self.connection.commit()
        self._backfill_frozen_visual_history()

    def _backfill_frozen_visual_history(self) -> None:
        """Recover lightweight theme history for databases created before D328."""
        rows = self.connection.execute(
            """SELECT t.id AS task_id, t.account_id, p.id AS revision_id,
                      p.visual_plan_json, p.frozen_at
               FROM tasks t
               JOIN publication_revisions p ON p.id = (
                   SELECT p2.id FROM publication_revisions p2
                   WHERE p2.task_id = t.id
                   ORDER BY p2.revision_number DESC LIMIT 1
               )
               WHERE NOT EXISTS (
                   SELECT 1 FROM recent_article_component_summaries h
                   WHERE h.account_id = t.account_id AND h.task_id = t.id
               )"""
        ).fetchall()
        if not rows:
            return
        with self.lock:
            for row in rows:
                plan = json.loads(row["visual_plan_json"])
                self._record_confirmed_component_summary_locked(
                    account_id=str(row["account_id"]),
                    task_id=str(row["task_id"]),
                    visual_system=plan.get("visual_system") or plan.get("style_mode"),
                    structure_fingerprint=plan.get("structure_fingerprint"),
                    publication_revision_id=str(row["revision_id"]),
                    components=[
                        {"component_type": slot["component_type"], "variant": slot["variant"]}
                        for slot in plan.get("slots", [])
                    ],
                    now=str(row["frozen_at"]),
                )
            self.connection.commit()

    @staticmethod
    def _progress(status: str = "pending") -> list[dict[str, Any]]:
        labels = (
            ("parse_input", "解析 Markdown"),
            ("content_director", "识别文章类型"),
            ("load_context", "读取品牌与历史"),
            ("visual_planner", "生成推荐稿"),
            ("validate_plans", "校验结构差异"),
            ("render_plan_previews", "渲染 390px 预览"),
        )
        return [
            {"key": key, "label": label, "status": status, "started_at": None, "finished_at": None, "message": None}
            for key, label in labels
        ]

    def create_task(
        self,
        *,
        account_id: str,
        title: str,
        article_type: str,
        markdown: str,
        source_hash: str,
        normalized_markdown: str,
        normalized_hash: str,
        input_summary: dict[str, Any],
        history_window: int = 5,
        idempotency_key: str | None = None,
        request_hash: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if bool(idempotency_key) != bool(request_hash):
            raise ValueError("idempotency_key and request_hash must be provided together")
        task_id, now = str(uuid.uuid4()), utc_now()
        progress = self._progress()
        progress[0].update(status="succeeded", started_at=now, finished_at=now)
        with self.lock:
            if idempotency_key and request_hash:
                existing = self._idempotent_resource(
                    scope="task_create",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if existing is not None:
                    resource_type, resource_id = existing
                    if resource_type != "article_task":
                        raise VersionConflictError("Idempotency-Key points to another resource type")
                    return self.get_task(resource_id), True
            self.connection.execute(
                """INSERT INTO tasks (
                    id, account_id, title, article_type, status, history_window,
                    brand_profile_version, fixed_footer_asset_version, selected_plan_id,
                    version, selection_change_count, markdown, source_hash, input_summary_json,
                    progress_json, last_error_json, created_at, updated_at,
                    normalized_markdown, normalized_hash, publication_draft_metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    account_id,
                    title,
                    article_type,
                    "created",
                    history_window,
                    "example_0.1",
                    "none",
                    None,
                    1,
                    0,
                    markdown,
                    source_hash,
                    json.dumps(input_summary, ensure_ascii=False),
                    json.dumps(progress, ensure_ascii=False),
                    None,
                    now,
                    now,
                    normalized_markdown,
                    normalized_hash,
                    json.dumps(DEFAULT_PUBLICATION_DRAFT_METADATA, ensure_ascii=False),
                ),
            )
            if idempotency_key and request_hash:
                self._record_idempotency_locked(
                    scope="task_create",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_type="article_task",
                    resource_id=task_id,
                    response=None,
                    now=now,
                )
            self.connection.commit()
        return self.get_task(task_id), False

    def list_tasks(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
        return [self._task_from_row(row) for row in rows]

    def delete_tasks(self, task_ids: list[str]) -> dict[str, Any]:
        """Delete local task records and their generated assets as one database operation."""
        normalized_ids = list(dict.fromkeys(task_id.strip() for task_id in task_ids if task_id.strip()))
        if not normalized_ids:
            raise ValueError("请至少选择一个历史任务")

        placeholders = ",".join("?" for _ in normalized_ids)
        with self.lock:
            existing_rows = self.connection.execute(
                f"SELECT id FROM tasks WHERE id IN ({placeholders})",
                normalized_ids,
            ).fetchall()
            existing_ids = [str(row["id"]) for row in existing_rows]
            existing_set = set(existing_ids)
            missing_ids = [task_id for task_id in normalized_ids if task_id not in existing_set]
            if not existing_ids:
                return {
                    "deleted_task_ids": [],
                    "missing_task_ids": missing_ids,
                    "asset_cleanup_warnings": [],
                }

            task_placeholders = ",".join("?" for _ in existing_ids)
            active_operation = self.connection.execute(
                f"""SELECT task_id FROM draft_operations
                WHERE task_id IN ({task_placeholders}) AND status IN ('running', 'unknown')
                LIMIT 1""",
                existing_ids,
            ).fetchone()
            if active_operation is not None:
                raise VersionConflictError("所选任务中仍有草稿同步正在进行或结果未知，请先处理后再删除")
            revision_rows = self.connection.execute(
                f"SELECT id FROM publication_revisions WHERE task_id IN ({task_placeholders})",
                existing_ids,
            ).fetchall()
            revision_ids = [str(row["id"]) for row in revision_rows]
            operation_rows = self.connection.execute(
                f"SELECT id FROM draft_operations WHERE task_id IN ({task_placeholders})",
                existing_ids,
            ).fetchall()
            operation_ids = [str(row["id"]) for row in operation_rows]

            asset_filenames: set[str] = set()
            for row in self.connection.execute(
                f"SELECT output_filename, raw_output_filename FROM image_candidates WHERE task_id IN ({task_placeholders})",
                existing_ids,
            ).fetchall():
                asset_filenames.add(Path(str(row["output_filename"])).name)
                if row["raw_output_filename"]:
                    asset_filenames.add(Path(str(row["raw_output_filename"])).name)
            for table in ("cover_candidates", "preflight_asset_replacements"):
                rows = self.connection.execute(
                    f"SELECT output_filename FROM {table} WHERE task_id IN ({task_placeholders})",
                    existing_ids,
                ).fetchall()
                asset_filenames.update(Path(str(row["output_filename"])).name for row in rows)

            try:
                if operation_ids:
                    operation_placeholders = ",".join("?" for _ in operation_ids)
                    self.connection.execute(
                        f"DELETE FROM draft_operation_steps WHERE operation_id IN ({operation_placeholders})",
                        operation_ids,
                    )
                self.connection.execute(
                    f"DELETE FROM draft_operations WHERE task_id IN ({task_placeholders})",
                    existing_ids,
                )
                self.connection.execute(
                    f"DELETE FROM draft_slots WHERE task_id IN ({task_placeholders})",
                    existing_ids,
                )
                if revision_ids:
                    revision_placeholders = ",".join("?" for _ in revision_ids)
                    self.connection.execute(
                        f"DELETE FROM publication_assets WHERE revision_id IN ({revision_placeholders})",
                        revision_ids,
                    )
                self.connection.execute(
                    f"DELETE FROM publication_revisions WHERE task_id IN ({task_placeholders})",
                    existing_ids,
                )
                for table in (
                    "preflight_asset_replacements",
                    "cover_candidates",
                    "image_candidates",
                    "image_slot_states",
                    "plan_revisions",
                    "plans",
                    "artifacts",
                    "audit_events",
                ):
                    self.connection.execute(
                        f"DELETE FROM {table} WHERE task_id IN ({task_placeholders})",
                        existing_ids,
                    )
                resource_ids = existing_ids + revision_ids + operation_ids
                if resource_ids:
                    resource_placeholders = ",".join("?" for _ in resource_ids)
                    self.connection.execute(
                        f"DELETE FROM idempotency_records WHERE resource_id IN ({resource_placeholders})",
                        resource_ids,
                    )
                self.connection.execute(
                    f"DELETE FROM tasks WHERE id IN ({task_placeholders})",
                    existing_ids,
                )
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

        cleanup_warnings: list[str] = []
        for filename in asset_filenames:
            try:
                (self.image_asset_dir / filename).unlink(missing_ok=True)
            except OSError:
                cleanup_warnings.append(filename)
        publication_root = self.publication_asset_dir.resolve()
        for revision_id in revision_ids:
            revision_dir = (self.publication_asset_dir / revision_id).resolve()
            if revision_dir.parent != publication_root:
                cleanup_warnings.append(revision_id)
                continue
            try:
                shutil.rmtree(revision_dir, ignore_errors=False)
            except FileNotFoundError:
                pass
            except OSError:
                cleanup_warnings.append(revision_id)

        return {
            "deleted_task_ids": existing_ids,
            "missing_task_ids": missing_ids,
            "asset_cleanup_warnings": cleanup_warnings,
        }

    def get_task(self, task_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise NotFoundError("任务不存在")
        return self._task_from_row(row)

    def save_publication_draft_metadata(
        self,
        *,
        task_id: str,
        metadata: dict[str, Any],
        operator_id: str,
    ) -> dict[str, Any]:
        self.assert_task_editable(task_id)
        normalized = {
            "author": str(metadata.get("author") or ""),
            "digest": str(metadata.get("digest") or ""),
            "content_source_url": str(metadata.get("content_source_url") or ""),
            "show_cover_pic": bool(metadata.get("show_cover_pic", True)),
        }
        now = utc_now()
        with self.lock:
            self.connection.execute(
                "UPDATE tasks SET publication_draft_metadata_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(normalized, ensure_ascii=False), now, task_id),
            )
            self._record_event_locked(
                task_id,
                "publication_draft_autosaved",
                {"operator_id": operator_id, "metadata": normalized},
                now,
            )
            self.connection.commit()
        return {"metadata": normalized, "saved_at": now}

    def acknowledge_preflight_finding(
        self,
        *,
        task_id: str,
        finding_code: str,
        block_id: str | None,
        expected_version: int,
        resolved_by: str,
    ) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task["version"] != expected_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        input_summary = task["input_summary"]
        report = input_summary.get("preflight_report") or {}
        findings = report.get("findings") or []
        finding = next(
            (
                item
                for item in findings
                if item.get("code") == finding_code and item.get("block_id") == block_id
            ),
            None,
        )
        if finding is None:
            raise NotFoundError("预检问题不存在")
        if finding.get("resolution_policy") != "ACKNOWLEDGE":
            raise ValueError("该问题不能通过知情确认解决")
        if finding.get("resolved_at"):
            return task

        now = utc_now()
        finding.update(
            {
                "resolved_at": now,
                "resolved_by": resolved_by,
                "resolution_action": "ACKNOWLEDGE",
            }
        )
        self._refresh_preflight_permissions(report)
        with self.lock:
            self.connection.execute(
                "UPDATE tasks SET input_summary_json = ?, version = version + 1, updated_at = ? WHERE id = ?",
                (json.dumps(input_summary, ensure_ascii=False), now, task_id),
            )
            self._record_event_locked(
                task_id,
                "preflight_acknowledged",
                {
                    "finding_code": finding_code,
                    "block_id": block_id,
                    "resolved_by": resolved_by,
                    "preflight_report_hash": hashlib.sha256(
                        json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                },
                now,
            )
            self.connection.commit()
        return self.get_task(task_id)

    @staticmethod
    def _refresh_preflight_permissions(report: dict[str, Any]) -> None:
        findings = report.get("findings") or []
        unresolved = [item for item in findings if not item.get("resolved_at")]
        report["planning_allowed"] = report.get("status") != "BLOCK" and not any(
            item.get("planning_blocking") for item in unresolved
        )
        report["draft_creation_allowed"] = report.get("status") != "BLOCK" and not any(
            item.get("draft_blocking") or item.get("resolution_policy") == "ACKNOWLEDGE"
            for item in unresolved
        )

    def replace_preflight_asset(
        self,
        *,
        task_id: str,
        finding_code: str,
        block_id: str | None,
        expected_version: int,
        content: bytes,
        content_type: str,
        extension: str,
        width: int,
        height: int,
        replaced_by: str,
    ) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task["version"] != expected_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        input_summary = task["input_summary"]
        report = input_summary.get("preflight_report") or {}
        findings = report.get("findings") or []
        finding = next(
            (
                item
                for item in findings
                if item.get("code") == finding_code and item.get("block_id") == block_id
            ),
            None,
        )
        if finding is None:
            raise NotFoundError("预检资产问题不存在")
        if finding.get("resolution_policy") != "REPLACE_ASSET":
            raise ValueError("该问题不能通过替换资产解决")

        asset_role = "cover" if finding_code in {"missing_cover", "placeholder_cover", "cover_requires_import"} else "body_image"
        asset_key = "cover" if asset_role == "cover" else f"body:{block_id}"
        previous_filename: str | None = None
        asset_id = str(uuid.uuid4())
        filename = f"preflight-{asset_id}{extension}"
        target = self.image_asset_dir / filename
        target.write_bytes(content)
        output_sha256 = hashlib.sha256(content).hexdigest()
        now = utc_now()
        original_source = None
        if isinstance(finding.get("details"), dict):
            original_source = finding["details"].get("source")
        finding.update(
            {
                "resolved_at": now,
                "resolved_by": replaced_by,
                "resolution_action": "REPLACE_ASSET",
                "resolution_evidence": {
                    "asset_id": asset_id,
                    "asset_role": asset_role,
                    "content_url": f"/api/v1/preflight-assets/{asset_id}/content",
                    "content_type": content_type,
                    "output_sha256": output_sha256,
                    "width": width,
                    "height": height,
                },
            }
        )
        self._refresh_preflight_permissions(report)
        try:
            with self.lock:
                previous = self.connection.execute(
                    "SELECT output_filename FROM preflight_asset_replacements WHERE task_id = ? AND asset_key = ?",
                    (task_id, asset_key),
                ).fetchone()
                if previous:
                    previous_filename = str(previous["output_filename"])
                self.connection.execute(
                    "DELETE FROM preflight_asset_replacements WHERE task_id = ? AND asset_key = ?",
                    (task_id, asset_key),
                )
                self.connection.execute(
                    """INSERT INTO preflight_asset_replacements VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        asset_id,
                        task_id,
                        asset_key,
                        finding_code,
                        block_id,
                        asset_role,
                        original_source,
                        filename,
                        content_type,
                        output_sha256,
                        width,
                        height,
                        replaced_by,
                        now,
                        now,
                    ),
                )
                updated = self.connection.execute(
                    """UPDATE tasks
                    SET input_summary_json = ?, version = version + 1, updated_at = ?
                    WHERE id = ? AND version = ?""",
                    (json.dumps(input_summary, ensure_ascii=False), now, task_id, expected_version),
                )
                if updated.rowcount != 1:
                    raise VersionConflictError("任务已被更新，请刷新后重试")
                self._record_event_locked(
                    task_id,
                    "preflight_asset_replaced",
                    {
                        "finding_code": finding_code,
                        "block_id": block_id,
                        "asset_id": asset_id,
                        "asset_role": asset_role,
                        "output_sha256": output_sha256,
                        "width": width,
                        "height": height,
                        "replaced_by": replaced_by,
                    },
                    now,
                )
                self.connection.commit()
        except Exception:
            with self.lock:
                self.connection.rollback()
            target.unlink(missing_ok=True)
            raise
        if previous_filename:
            old_filename = Path(previous_filename).name
            if old_filename != filename:
                (self.image_asset_dir / old_filename).unlink(missing_ok=True)
        return self.get_task(task_id)

    def list_preflight_asset_replacements(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM preflight_asset_replacements WHERE task_id = ? ORDER BY asset_key",
            (task_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "task_id": row["task_id"],
                "asset_key": row["asset_key"],
                "finding_code": row["finding_code"],
                "block_id": row["block_id"],
                "asset_role": row["asset_role"],
                "original_source": row["original_source"],
                "content_type": row["content_type"],
                "output_sha256": row["output_sha256"],
                "width": row["width"],
                "height": row["height"],
                "content_url": f'/api/v1/preflight-assets/{row["id"]}/content',
            }
            for row in rows
        ]

    def get_preflight_asset(self, asset_id: str) -> tuple[Path, str]:
        row = self.connection.execute(
            "SELECT output_filename, content_type FROM preflight_asset_replacements WHERE id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("预检替换资产不存在")
        filename = Path(str(row["output_filename"])).name
        path = self.image_asset_dir / filename
        if not path.is_file():
            raise NotFoundError("预检替换资产文件不存在")
        return path, str(row["content_type"])

    def _task_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "account_id": row["account_id"],
            "title": row["title"],
            "article_type": row["article_type"],
            "status": row["status"],
            "history_window": row["history_window"],
            "brand_profile_version": row["brand_profile_version"],
            "fixed_footer_asset_version": row["fixed_footer_asset_version"],
            "selected_plan_id": row["selected_plan_id"],
            "active_publication_revision_id": row["active_publication_revision_id"],
            "derived_from_task_id": None,
            "version": row["version"],
            "selection_change_count": row["selection_change_count"],
            "markdown": row["markdown"],
            "source_hash": row["source_hash"],
            "normalized_markdown": row["normalized_markdown"],
            "normalized_hash": row["normalized_hash"],
            "input_summary": json.loads(row["input_summary_json"]),
            "progress": json.loads(row["progress_json"]),
            "last_error": json.loads(row["last_error_json"]) if row["last_error_json"] else None,
            "publication_draft_metadata": (
                json.loads(row["publication_draft_metadata_json"])
                if row["publication_draft_metadata_json"]
                else dict(DEFAULT_PUBLICATION_DRAFT_METADATA)
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def start_generation(self, task_id: str, expected_version: int) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task["version"] != expected_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        now = utc_now()
        progress = task["progress"]
        for step in progress:
            step.update(status="running", started_at=now, finished_at=None, message=None)
        with self.lock:
            self.connection.execute(
                "UPDATE tasks SET status = 'analyzing', version = version + 1, progress_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(progress, ensure_ascii=False), now, task_id),
            )
            self.connection.commit()
        return self.get_task(task_id)

    def save_plans(self, task_id: str, plans: list[dict[str, Any]], html_documents: list[str]) -> dict[str, Any]:
        now = utc_now()
        with self.lock:
            created_plan_ids: list[str] = []
            old_cover_assets = self.connection.execute(
                "SELECT output_filename FROM cover_candidates WHERE task_id = ?",
                (task_id,),
            ).fetchall()
            self.connection.execute("DELETE FROM cover_candidates WHERE task_id = ?", (task_id,))
            old_assets = self.connection.execute(
                "SELECT output_filename, raw_output_filename FROM image_candidates WHERE task_id = ?",
                (task_id,),
            ).fetchall()
            self.connection.execute("DELETE FROM image_candidates WHERE task_id = ?", (task_id,))
            self.connection.execute("DELETE FROM image_slot_states WHERE task_id = ?", (task_id,))
            for row in old_assets:
                filename = Path(str(row["output_filename"])).name
                (self.image_asset_dir / filename).unlink(missing_ok=True)
                if row["raw_output_filename"]:
                    raw_filename = Path(str(row["raw_output_filename"])).name
                    (self.image_asset_dir / raw_filename).unlink(missing_ok=True)
            for row in old_cover_assets:
                filename = Path(str(row["output_filename"])).name
                (self.image_asset_dir / filename).unlink(missing_ok=True)
            self.connection.execute(
                "DELETE FROM plan_revisions WHERE plan_id IN (SELECT id FROM plans WHERE task_id = ?)",
                (task_id,),
            )
            self.connection.execute("DELETE FROM plans WHERE task_id = ?", (task_id,))
            self.connection.execute("DELETE FROM artifacts WHERE task_id = ?", (task_id,))
            for plan, document in zip(plans, html_documents, strict=True):
                plan_id, artifact_id = str(uuid.uuid4()), str(uuid.uuid4())
                created_plan_ids.append(plan_id)
                payload = {
                    **plan,
                    "id": plan_id,
                    "task_id": task_id,
                    "revision": 1,
                    "undo_stack": [],
                    "preview_artifact_id": artifact_id,
                    "preview_content_hash": hashlib.sha256(document.encode("utf-8")).hexdigest(),
                }
                self.connection.execute(
                    "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)",
                    (artifact_id, task_id, plan_id, document, now),
                )
                self.connection.execute(
                    "INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?)",
                    (plan_id, task_id, plan["plan_index"], json.dumps(payload, ensure_ascii=False), artifact_id, now),
                )
                self.connection.execute(
                    "INSERT INTO plan_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        task_id,
                        plan_id,
                        1,
                        json.dumps(payload, ensure_ascii=False),
                        artifact_id,
                        "generated",
                        now,
                    ),
                )
                self._record_event_locked(
                    task_id,
                    "plan_generated",
                    {"plan_id": plan_id, "revision": 1, "component_count": len(payload.get("slots", []))},
                    now,
                )
            task = self.get_task(task_id)
            progress = task["progress"]
            for step in progress:
                step.update(status="succeeded", finished_at=now)
            if len(created_plan_ids) == 1:
                selected_plan_id = created_plan_ids[0]
                self.connection.execute(
                    """UPDATE tasks SET status = 'plan_selected', selected_plan_id = ?,
                    version = version + 1, progress_json = ?, updated_at = ? WHERE id = ?""",
                    (selected_plan_id, json.dumps(progress, ensure_ascii=False), now, task_id),
                )
                self._record_event_locked(
                    task_id,
                    "plan_auto_selected",
                    {"plan_id": selected_plan_id, "reason": "single_recommendation"},
                    now,
                )
            else:
                self.connection.execute(
                    "UPDATE tasks SET status = 'plans_ready', version = version + 1, progress_json = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(progress, ensure_ascii=False), now, task_id),
                )
            self.connection.commit()
        return self.get_task(task_id)

    def list_plans(self, task_id: str) -> list[dict[str, Any]]:
        self.get_task(task_id)
        rows = self.connection.execute("SELECT plan_json FROM plans WHERE task_id = ? ORDER BY plan_index", (task_id,)).fetchall()
        return [json.loads(row["plan_json"]) for row in rows]

    def get_plan(self, task_id: str, plan_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT plan_json FROM plans WHERE task_id = ? AND id = ?",
            (task_id, plan_id),
        ).fetchone()
        if row is None:
            raise NotFoundError("方案不存在")
        return json.loads(row["plan_json"])

    def get_plan_revision(self, task_id: str, plan_id: str, revision: int) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT plan_json FROM plan_revisions WHERE task_id = ? AND plan_id = ? AND revision = ?",
            (task_id, plan_id, revision),
        ).fetchone()
        if row is None:
            raise NotFoundError("方案修订不存在")
        return json.loads(row["plan_json"])

    def list_plan_revisions(self, task_id: str, plan_id: str) -> list[dict[str, Any]]:
        self.get_plan(task_id, plan_id)
        rows = self.connection.execute(
            "SELECT revision, change_reason, artifact_id, created_at FROM plan_revisions WHERE task_id = ? AND plan_id = ? ORDER BY revision DESC",
            (task_id, plan_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_plan_revision(
        self,
        *,
        task_id: str,
        plan_id: str,
        plan: dict[str, Any],
        html_document: str,
        change_reason: str,
        event_type: str,
        event_payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.get_plan(task_id, plan_id)
        now = utc_now()
        artifact_id = str(uuid.uuid4())
        payload = {
            **plan,
            "id": plan_id,
            "task_id": task_id,
            "preview_artifact_id": artifact_id,
            "preview_content_hash": hashlib.sha256(html_document.encode("utf-8")).hexdigest(),
        }
        with self.lock:
            self.connection.execute(
                "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)",
                (artifact_id, task_id, plan_id, html_document, now),
            )
            self.connection.execute(
                "UPDATE plans SET plan_json = ?, artifact_id = ? WHERE task_id = ? AND id = ?",
                (json.dumps(payload, ensure_ascii=False), artifact_id, task_id, plan_id),
            )
            self.connection.execute(
                "INSERT INTO plan_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    task_id,
                    plan_id,
                    payload["revision"],
                    json.dumps(payload, ensure_ascii=False),
                    artifact_id,
                    change_reason,
                    now,
                ),
            )
            self._record_event_locked(
                task_id,
                event_type,
                {**event_payload, "plan_id": plan_id, "revision": payload["revision"]},
                now,
            )
            self.connection.commit()
        return payload

    def _record_event_locked(self, task_id: str, event_type: str, payload: dict[str, Any], now: str) -> None:
        self.connection.execute(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), task_id, event_type, json.dumps(payload, ensure_ascii=False), now),
        )

    def list_audit_events(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT event_type, payload_json, created_at FROM audit_events WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        return [
            {"event_type": row["event_type"], "payload": json.loads(row["payload_json"]), "created_at": row["created_at"]}
            for row in rows
        ]

    def record_confirmed_component_summary(
        self,
        *,
        account_id: str,
        task_id: str,
        components: list[dict[str, Any]],
        visual_system: str | None = None,
        structure_fingerprint: str | None = None,
    ) -> None:
        now = utc_now()
        with self.lock:
            self._record_confirmed_component_summary_locked(
                account_id=account_id,
                task_id=task_id,
                components=components,
                visual_system=visual_system,
                structure_fingerprint=structure_fingerprint,
                publication_revision_id="manual-confirmed",
                now=now,
            )
            self.connection.commit()

    def _record_confirmed_component_summary_locked(
        self,
        *,
        account_id: str,
        task_id: str,
        components: list[dict[str, Any]],
        visual_system: str | None,
        structure_fingerprint: str | None,
        publication_revision_id: str,
        now: str,
    ) -> None:
        self.connection.execute(
            "DELETE FROM recent_article_component_summaries WHERE account_id = ? AND task_id = ?",
            (account_id, task_id),
        )
        self.connection.execute(
            """INSERT INTO recent_article_component_summaries
            (id, account_id, task_id, publication_revision_id, summary_json, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                account_id,
                task_id,
                publication_revision_id,
                json.dumps(
                    {
                        "components": components,
                        "visual_system": visual_system,
                        "structure_fingerprint": structure_fingerprint,
                    },
                    ensure_ascii=False,
                ),
                now,
            ),
        )

    def _record_publication_history_locked(
        self,
        *,
        task: dict[str, Any],
        revision: dict[str, Any],
        now: str,
    ) -> None:
        plan = revision["visual_plan"]
        self._record_confirmed_component_summary_locked(
            account_id=task["account_id"],
            task_id=task["id"],
            visual_system=plan.get("visual_system") or plan.get("style_mode"),
            structure_fingerprint=plan.get("structure_fingerprint"),
            publication_revision_id=revision["id"],
            components=[
                {"component_type": slot["component_type"], "variant": slot["variant"]}
                for slot in plan.get("slots", [])
            ],
            now=now,
        )

    def list_recent_component_summaries(self, account_id: str, limit: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """SELECT summary_json FROM recent_article_component_summaries
            WHERE account_id = ? AND publication_revision_id IS NOT NULL
            ORDER BY confirmed_at DESC LIMIT ?""",
            (account_id, limit),
        ).fetchall()
        return [json.loads(row["summary_json"]) for row in rows]

    def select_plan(self, task_id: str, plan_id: str, expected_version: int) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task["version"] != expected_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        plan = self.connection.execute("SELECT id FROM plans WHERE task_id = ? AND id = ?", (task_id, plan_id)).fetchone()
        if plan is None:
            raise NotFoundError("方案不存在")
        changes = task["selection_change_count"] + (1 if task["selected_plan_id"] and task["selected_plan_id"] != plan_id else 0)
        now = utc_now()
        with self.lock:
            self.connection.execute(
                "UPDATE tasks SET selected_plan_id = ?, status = 'plan_selected', selection_change_count = ?, version = version + 1, updated_at = ? WHERE id = ?",
                (plan_id, changes, now, task_id),
            )
            self.connection.commit()
        return self.get_task(task_id)

    def get_artifact(self, artifact_id: str) -> str:
        row = self.connection.execute("SELECT html FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        if row is None:
            raise NotFoundError("预览产物不存在")
        return str(row["html"])

    def get_artifact_record(self, artifact_id: str) -> dict[str, str]:
        row = self.connection.execute(
            "SELECT task_id, plan_id, html FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("预览产物不存在")
        return {"task_id": row["task_id"], "plan_id": row["plan_id"], "html": row["html"]}

    def add_cover_candidate(
        self,
        *,
        task_id: str,
        plan_id: str,
        source_type: str,
        source_resource_id: str | None,
        provider: str,
        model: str,
        provider_prompt: str,
        content: bytes,
        content_type: str,
        extension: str,
        width: int,
        height: int,
        latency_ms: int,
        machine_checks: dict[str, Any],
    ) -> dict[str, Any]:
        self.get_plan(task_id, plan_id)
        existing = self.list_cover_candidates(task_id, plan_id)
        if len(existing) >= 8:
            raise VersionConflictError("单个方案最多保留 8 个封面候选")
        candidate_id = str(uuid.uuid4())
        filename = f"cover-{candidate_id}{extension}"
        target = self.image_asset_dir / filename
        target.write_bytes(content)
        now = utc_now()
        try:
            with self.lock:
                self.connection.execute(
                    """INSERT INTO cover_candidates
                    (id, task_id, plan_id, candidate_index, source_type, source_resource_id,
                     provider, model, provider_prompt, prompt_sha256, output_filename, content_type,
                     output_sha256, width, height, latency_ms, machine_checks_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate_id,
                        task_id,
                        plan_id,
                        len(existing) + 1,
                        source_type,
                        source_resource_id,
                        provider,
                        model,
                        provider_prompt,
                        hashlib.sha256(provider_prompt.encode("utf-8")).hexdigest(),
                        filename,
                        content_type,
                        hashlib.sha256(content).hexdigest(),
                        width,
                        height,
                        latency_ms,
                        json.dumps(machine_checks, ensure_ascii=False),
                        now,
                    ),
                )
                self._record_event_locked(
                    task_id,
                    "cover_candidate_added",
                    {
                        "plan_id": plan_id,
                        "candidate_id": candidate_id,
                        "source_type": source_type,
                        "source_resource_id": source_resource_id,
                        "provider": provider,
                    },
                    now,
                )
                self.connection.commit()
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return self.get_cover_candidate(candidate_id)

    @staticmethod
    def _cover_candidate_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "plan_id": row["plan_id"],
            "candidate_index": row["candidate_index"],
            "source_type": row["source_type"],
            "source_resource_id": row["source_resource_id"],
            "provider": row["provider"],
            "model": row["model"],
            "provider_prompt": row["provider_prompt"],
            "output_sha256": row["output_sha256"],
            "content_type": row["content_type"],
            "width": row["width"],
            "height": row["height"],
            "latency_ms": row["latency_ms"],
            "machine_checks": json.loads(row["machine_checks_json"]),
            "created_at": row["created_at"],
            "content_url": f'/api/v1/cover-candidates/{row["id"]}/content',
        }

    def list_cover_candidates(self, task_id: str, plan_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """SELECT * FROM cover_candidates
            WHERE task_id = ? AND plan_id = ? ORDER BY candidate_index""",
            (task_id, plan_id),
        ).fetchall()
        return [self._cover_candidate_from_row(row) for row in rows]

    def get_cover_candidate(self, candidate_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM cover_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("封面候选不存在")
        return self._cover_candidate_from_row(row)

    def get_cover_candidate_asset(self, candidate_id: str) -> tuple[Path, str]:
        row = self.connection.execute(
            "SELECT output_filename, content_type FROM cover_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("封面候选不存在")
        path = self.image_asset_dir / Path(str(row["output_filename"])).name
        if not path.is_file():
            raise NotFoundError("封面候选文件不存在")
        return path, str(row["content_type"])

    def ensure_image_slot_states(self, task_id: str, plan_id: str, image_slots: list[dict[str, Any]]) -> None:
        self.get_plan(task_id, plan_id)
        now = utc_now()
        with self.lock:
            for slot in image_slots:
                self.connection.execute(
                    """INSERT OR IGNORE INTO image_slot_states
                    (id, task_id, plan_id, image_slot_id, status, image_revision, selected_candidate_id, decision, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'planned', 1, NULL, 'pending', ?, ?)""",
                    (str(uuid.uuid4()), task_id, plan_id, slot["image_slot_id"], now, now),
                )
            self.connection.commit()

    def _candidate_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "plan_id": row["plan_id"],
            "image_slot_id": row["image_slot_id"],
            "candidate_index": row["candidate_index"],
            "provider": row["provider"],
            "model": row["model"],
            "provider_prompt": row["provider_prompt"],
            "prompt_sha256": row["prompt_sha256"],
            "status": row["status"],
            "content_type": row["content_type"],
            "output_sha256": row["output_sha256"],
            "raw_output_sha256": row["raw_output_sha256"],
            "width": row["width"],
            "height": row["height"],
            "latency_ms": row["latency_ms"],
            "machine_checks": json.loads(row["machine_checks_json"]),
            "human_decision": row["human_decision"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "content_url": f'/api/v1/image-candidates/{row["id"]}/content',
            "raw_content_url": (
                f'/api/v1/image-candidates/{row["id"]}/raw-content'
                if row["raw_output_filename"]
                else None
            ),
        }

    def list_image_candidates(self, task_id: str, plan_id: str, image_slot_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """SELECT * FROM image_candidates
            WHERE task_id = ? AND plan_id = ? AND image_slot_id = ?
            ORDER BY candidate_index""",
            (task_id, plan_id, image_slot_id),
        ).fetchall()
        return [self._candidate_from_row(row) for row in rows]

    def _image_state_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "task_id": row["task_id"],
            "plan_id": row["plan_id"],
            "image_slot_id": row["image_slot_id"],
            "status": row["status"],
            "image_revision": row["image_revision"],
            "selected_candidate_id": row["selected_candidate_id"],
            "decision": row["decision"],
            "last_error": json.loads(row["last_error_json"]) if row["last_error_json"] else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "candidates": self.list_image_candidates(row["task_id"], row["plan_id"], row["image_slot_id"]),
        }

    def list_image_slot_states(self, task_id: str, plan_id: str) -> list[dict[str, Any]]:
        self.get_plan(task_id, plan_id)
        rows = self.connection.execute(
            "SELECT * FROM image_slot_states WHERE task_id = ? AND plan_id = ? ORDER BY image_slot_id",
            (task_id, plan_id),
        ).fetchall()
        return [self._image_state_from_row(row) for row in rows]

    def get_image_slot_state(self, task_id: str, plan_id: str, image_slot_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            """SELECT * FROM image_slot_states
            WHERE task_id = ? AND plan_id = ? AND image_slot_id = ?""",
            (task_id, plan_id, image_slot_id),
        ).fetchone()
        if row is None:
            raise NotFoundError("图片槽状态不存在")
        return self._image_state_from_row(row)

    def get_image_candidate(self, candidate_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM image_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("图片候选不存在")
        return self._candidate_from_row(row)

    def add_image_candidate(
        self,
        *,
        task_id: str,
        plan_id: str,
        image_slot_id: str,
        expected_image_revision: int,
        provider: str,
        model: str,
        provider_prompt: str,
        content: bytes,
        content_type: str,
        extension: str,
        width: int,
        height: int,
        latency_ms: int,
        machine_checks: dict[str, Any],
        raw_content: bytes | None = None,
        auto_select: bool = False,
    ) -> dict[str, Any]:
        state = self.get_image_slot_state(task_id, plan_id, image_slot_id)
        if state["image_revision"] != expected_image_revision:
            raise VersionConflictError("图片槽已被更新，请刷新后重试")
        existing = state["candidates"]
        model_candidate_count = sum(1 for item in existing if item["provider"] != "manual_upload")
        if provider != "manual_upload" and model_candidate_count >= 3:
            raise VersionConflictError("单个图片槽最多保留 3 个模型候选")
        candidate_id = str(uuid.uuid4())
        filename = f"{candidate_id}{extension}"
        target = self.image_asset_dir / filename
        target.write_bytes(content)
        raw_bytes = raw_content if raw_content is not None else content
        raw_filename = f"raw-{candidate_id}{extension}"
        raw_target = self.image_asset_dir / raw_filename
        raw_target.write_bytes(raw_bytes)
        now = utc_now()
        candidate_index = len(existing) + 1
        human_decision = "accepted" if auto_select else "pending"
        state_status = "replaced" if auto_select else "generated"
        selected_candidate_id = candidate_id if auto_select else state["selected_candidate_id"]
        decision = "replaced" if auto_select else state["decision"]
        try:
            with self.lock:
                self.connection.execute(
                    """INSERT INTO image_candidates
                    (id, task_id, plan_id, image_slot_id, candidate_index, provider, model,
                     provider_prompt, prompt_sha256, status, output_filename, raw_output_filename,
                     content_type, output_sha256, raw_output_sha256, width, height, latency_ms,
                     machine_checks_json, human_decision, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate_id,
                        task_id,
                        plan_id,
                        image_slot_id,
                        candidate_index,
                        provider,
                        model,
                        provider_prompt,
                        hashlib.sha256(provider_prompt.encode("utf-8")).hexdigest(),
                        filename,
                        raw_filename,
                        content_type,
                        hashlib.sha256(content).hexdigest(),
                        hashlib.sha256(raw_bytes).hexdigest(),
                        width,
                        height,
                        latency_ms,
                        json.dumps(machine_checks, ensure_ascii=False),
                        human_decision,
                        now,
                        now,
                    ),
                )
                self.connection.execute(
                    """UPDATE image_slot_states
                    SET status = ?, image_revision = image_revision + 1, selected_candidate_id = ?, decision = ?,
                        last_error_json = NULL, updated_at = ?
                    WHERE task_id = ? AND plan_id = ? AND image_slot_id = ?""",
                    (state_status, selected_candidate_id, decision, now, task_id, plan_id, image_slot_id),
                )
                self._record_event_locked(
                    task_id,
                    "image_candidate_added",
                    {
                        "plan_id": plan_id,
                        "image_slot_id": image_slot_id,
                        "candidate_id": candidate_id,
                        "candidate_index": candidate_index,
                        "provider": provider,
                        "auto_selected": auto_select,
                    },
                    now,
                )
                self.connection.commit()
        except Exception:
            target.unlink(missing_ok=True)
            raw_target.unlink(missing_ok=True)
            raise
        return self.get_image_slot_state(task_id, plan_id, image_slot_id)

    def mark_image_slot_failed(
        self,
        *,
        task_id: str,
        plan_id: str,
        image_slot_id: str,
        expected_image_revision: int,
        error: dict[str, Any],
    ) -> dict[str, Any]:
        state = self.get_image_slot_state(task_id, plan_id, image_slot_id)
        if state["image_revision"] != expected_image_revision:
            raise VersionConflictError("图片槽已被更新，请刷新后重试")
        now = utc_now()
        public_error = {
            "code": str(error.get("code") or "image_provider_failed"),
            "message": str(error.get("message") or "图片生成失败"),
            "retryable": bool(error.get("retryable")),
        }
        with self.lock:
            self.connection.execute(
                """UPDATE image_slot_states
                SET status = 'failed', image_revision = image_revision + 1,
                    last_error_json = ?, updated_at = ?
                WHERE task_id = ? AND plan_id = ? AND image_slot_id = ?""",
                (json.dumps(public_error, ensure_ascii=False), now, task_id, plan_id, image_slot_id),
            )
            self._record_event_locked(
                task_id,
                "image_generation_failed",
                {
                    "plan_id": plan_id,
                    "image_slot_id": image_slot_id,
                    "error_code": public_error["code"],
                    "retryable": public_error["retryable"],
                },
                now,
            )
            self.connection.commit()
        return self.get_image_slot_state(task_id, plan_id, image_slot_id)

    def decide_image_slot(
        self,
        *,
        task_id: str,
        plan_id: str,
        image_slot_id: str,
        expected_image_revision: int,
        decision: str,
        candidate_id: str | None = None,
    ) -> dict[str, Any]:
        state = self.get_image_slot_state(task_id, plan_id, image_slot_id)
        if state["image_revision"] != expected_image_revision:
            raise VersionConflictError("图片槽已被更新，请刷新后重试")
        if decision not in {"accepted", "skipped"}:
            raise ValueError("未知图片决策")
        if decision == "accepted":
            candidate = next((item for item in state["candidates"] if item["id"] == candidate_id), None)
            if candidate is None:
                raise NotFoundError("图片候选不存在")
        now = utc_now()
        selected = candidate_id if decision == "accepted" else None
        with self.lock:
            if decision == "accepted":
                self.connection.execute(
                    """UPDATE image_candidates SET human_decision = 'rejected', updated_at = ?
                    WHERE task_id = ? AND plan_id = ? AND image_slot_id = ? AND human_decision = 'accepted'""",
                    (now, task_id, plan_id, image_slot_id),
                )
                self.connection.execute(
                    "UPDATE image_candidates SET human_decision = 'accepted', updated_at = ? WHERE id = ?",
                    (now, candidate_id),
                )
            self.connection.execute(
                """UPDATE image_slot_states
                SET status = ?, image_revision = image_revision + 1, selected_candidate_id = ?, decision = ?,
                    last_error_json = NULL, updated_at = ?
                WHERE task_id = ? AND plan_id = ? AND image_slot_id = ?""",
                (decision, selected, decision, now, task_id, plan_id, image_slot_id),
            )
            self._record_event_locked(
                task_id,
                "image_slot_decided",
                {
                    "plan_id": plan_id,
                    "image_slot_id": image_slot_id,
                    "decision": decision,
                    "candidate_id": selected,
                },
                now,
            )
            self.connection.commit()
        return self.get_image_slot_state(task_id, plan_id, image_slot_id)

    def get_image_candidate_asset(self, candidate_id: str) -> tuple[Path, str]:
        row = self.connection.execute(
            "SELECT output_filename, content_type FROM image_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("图片候选不存在")
        filename = Path(str(row["output_filename"])).name
        path = self.image_asset_dir / filename
        if not path.is_file():
            raise NotFoundError("图片候选文件不存在")
        return path, str(row["content_type"])

    def get_raw_image_candidate_asset(self, candidate_id: str) -> tuple[Path, str]:
        row = self.connection.execute(
            "SELECT raw_output_filename, content_type FROM image_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None or not row["raw_output_filename"]:
            raise NotFoundError("图片原始候选不存在")
        filename = Path(str(row["raw_output_filename"])).name
        path = self.image_asset_dir / filename
        if not path.is_file():
            raise NotFoundError("图片原始候选文件不存在")
        return path, str(row["content_type"])

    def assert_task_editable(self, task_id: str) -> None:
        task = self.get_task(task_id)
        if task.get("active_publication_revision_id"):
            raise PublicationLockedError("当前版本已冻结，请先选择继续修改")

    def _idempotent_resource(
        self,
        *,
        scope: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[str, str] | None:
        row = self.connection.execute(
            """SELECT request_hash, resource_type, resource_id
            FROM idempotency_records WHERE scope = ? AND idempotency_key = ?""",
            (scope, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise VersionConflictError("Idempotency-Key 已用于不同请求")
        return str(row["resource_type"]), str(row["resource_id"])

    def get_idempotent_resource(
        self,
        *,
        scope: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[str, str] | None:
        return self._idempotent_resource(
            scope=scope,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )

    def _record_idempotency_locked(
        self,
        *,
        scope: str,
        idempotency_key: str,
        request_hash: str,
        resource_type: str,
        resource_id: str,
        response: dict[str, Any] | None,
        now: str,
    ) -> None:
        self.connection.execute(
            """INSERT INTO idempotency_records
            (id, scope, idempotency_key, request_hash, resource_type, resource_id, response_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                scope,
                idempotency_key,
                request_hash,
                resource_type,
                resource_id,
                json.dumps(response, ensure_ascii=False) if response is not None else None,
                now,
            ),
        )

    @staticmethod
    def _publication_revision_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "revision_number": row["revision_number"],
            "plan_id": row["plan_id"],
            "plan_revision": row["plan_revision"],
            "lifecycle_status": row["lifecycle_status"],
            "normalized_hash": row["normalized_hash"],
            "preflight_report_hash": row["preflight_report_hash"],
            "visual_plan": json.loads(row["visual_plan_json"]),
            "visual_plan_hash": row["visual_plan_hash"],
            "frozen_html": row["frozen_html"],
            "frozen_html_hash": row["frozen_html_hash"],
            "structure_hash": row["structure_hash"],
            "metadata": json.loads(row["metadata_json"]),
            "metadata_hash": row["metadata_hash"],
            "asset_manifest": json.loads(row["asset_manifest_json"]),
            "asset_manifest_hash": row["asset_manifest_hash"],
            "compatibility_report": json.loads(row["compatibility_report_json"]),
            "compatibility_report_hash": row["compatibility_report_hash"],
            "frozen_by": row["frozen_by"],
            "frozen_at": row["frozen_at"],
            "superseded_at": row["superseded_at"],
        }

    def get_publication_revision(self, revision_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM publication_revisions WHERE id = ?",
            (revision_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("冻结版本不存在")
        return self._publication_revision_from_row(row)

    def list_publication_revisions(self, task_id: str) -> list[dict[str, Any]]:
        self.get_task(task_id)
        rows = self.connection.execute(
            "SELECT * FROM publication_revisions WHERE task_id = ? ORDER BY revision_number DESC",
            (task_id,),
        ).fetchall()
        return [self._publication_revision_from_row(row) for row in rows]

    def list_publication_assets(self, revision_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM publication_assets WHERE revision_id = ? ORDER BY asset_token",
            (revision_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "revision_id": row["revision_id"],
                "asset_token": row["asset_token"],
                "asset_role": row["asset_role"],
                "source_resource_type": row["source_resource_type"],
                "source_resource_id": row["source_resource_id"],
                "block_id": row["block_id"],
                "image_slot_id": row["image_slot_id"],
                "relative_filename": row["relative_filename"],
                "content_type": row["content_type"],
                "output_sha256": row["output_sha256"],
                "width": row["width"],
                "height": row["height"],
                "content_url": f'/api/v1/publication-assets/{row["id"]}/content',
            }
            for row in rows
        ]

    def get_publication_asset(self, asset_id: str) -> tuple[Path, str]:
        row = self.connection.execute(
            "SELECT revision_id, relative_filename, content_type FROM publication_assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("冻结资产不存在")
        filename = Path(str(row["relative_filename"])).name
        path = self.publication_asset_dir / str(row["revision_id"]) / filename
        if not path.is_file():
            raise NotFoundError("冻结资产完整性校验失败")
        return path, str(row["content_type"])

    def create_publication_revision(
        self,
        *,
        task_id: str,
        expected_task_version: int,
        idempotency_key: str,
        request_hash: str,
        revision: dict[str, Any],
        assets: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        replay = self._idempotent_resource(
            scope="freeze",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay:
            return self.get_publication_revision(replay[1]), self.get_task(task_id)

        revision_id = str(revision["id"])
        temp_dir = self.publication_asset_dir / f".tmp-{revision_id}"
        final_dir = self.publication_asset_dir / revision_id
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            for asset in assets:
                filename = Path(str(asset["relative_filename"])).name
                if filename != asset["relative_filename"]:
                    raise ValueError("冻结资产文件名不安全")
                (temp_dir / filename).write_bytes(asset["content"])

            now = utc_now()
            with self.lock:
                task = self.get_task(task_id)
                if task["version"] != expected_task_version:
                    raise VersionConflictError("任务已被更新，请刷新后重试")
                if task.get("active_publication_revision_id"):
                    raise VersionConflictError("已有有效冻结版本")
                revision_number = int(
                    self.connection.execute(
                        "SELECT COALESCE(MAX(revision_number), 0) + 1 AS value FROM publication_revisions WHERE task_id = ?",
                        (task_id,),
                    ).fetchone()["value"]
                )
                self.connection.execute(
                    """INSERT INTO publication_revisions
                    (id, task_id, revision_number, plan_id, plan_revision, lifecycle_status,
                     normalized_hash, preflight_report_hash, visual_plan_json, visual_plan_hash,
                     frozen_html, frozen_html_hash, structure_hash, metadata_json, metadata_hash,
                     asset_manifest_json, asset_manifest_hash, compatibility_report_json,
                     compatibility_report_hash, frozen_by, frozen_at, superseded_at)
                    VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                    (
                        revision_id,
                        task_id,
                        revision_number,
                        revision["plan_id"],
                        revision["plan_revision"],
                        revision["normalized_hash"],
                        revision["preflight_report_hash"],
                        json.dumps(revision["visual_plan"], ensure_ascii=False),
                        revision["visual_plan_hash"],
                        revision["frozen_html"],
                        revision["frozen_html_hash"],
                        revision["structure_hash"],
                        json.dumps(revision["metadata"], ensure_ascii=False),
                        revision["metadata_hash"],
                        json.dumps(revision["asset_manifest"], ensure_ascii=False),
                        revision["asset_manifest_hash"],
                        json.dumps(revision["compatibility_report"], ensure_ascii=False),
                        revision["compatibility_report_hash"],
                        revision["frozen_by"],
                        now,
                    ),
                )
                for asset in assets:
                    self.connection.execute(
                        """INSERT INTO publication_assets
                        (id, revision_id, asset_token, asset_role, source_resource_type,
                         source_resource_id, block_id, image_slot_id, relative_filename,
                         content_type, output_sha256, width, height, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            asset["id"],
                            revision_id,
                            asset["asset_token"],
                            asset["asset_role"],
                            asset["source_resource_type"],
                            asset["source_resource_id"],
                            asset.get("block_id"),
                            asset.get("image_slot_id"),
                            asset["relative_filename"],
                            asset["content_type"],
                            asset["output_sha256"],
                            asset["width"],
                            asset["height"],
                            now,
                        ),
                    )
                updated = self.connection.execute(
                    """UPDATE tasks SET active_publication_revision_id = ?, status = 'publication_frozen',
                    version = version + 1, updated_at = ? WHERE id = ? AND version = ?""",
                    (revision_id, now, task_id, expected_task_version),
                )
                if updated.rowcount != 1:
                    raise VersionConflictError("任务已被更新，请刷新后重试")
                self._record_event_locked(
                    task_id,
                    "revision_frozen",
                    {
                        "revision_id": revision_id,
                        "revision_number": revision_number,
                        "frozen_html_hash": revision["frozen_html_hash"],
                        "asset_manifest_hash": revision["asset_manifest_hash"],
                        "frozen_by": revision["frozen_by"],
                    },
                    now,
                )
                self._record_publication_history_locked(task=task, revision=revision, now=now)
                self._record_idempotency_locked(
                    scope="freeze",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_type="publication_revision",
                    resource_id=revision_id,
                    response=None,
                    now=now,
                )
                if final_dir.exists():
                    raise VersionConflictError("冻结资产目录冲突")
                temp_dir.replace(final_dir)
                self.connection.commit()
        except Exception:
            with self.lock:
                self.connection.rollback()
            shutil.rmtree(temp_dir, ignore_errors=True)
            shutil.rmtree(final_dir, ignore_errors=True)
            raise
        return self.get_publication_revision(revision_id), self.get_task(task_id)

    def suggested_draft_slot(self, task_id: str) -> str:
        rows = self.connection.execute(
            "SELECT slot_key, successful_media_id FROM draft_slots WHERE task_id = ?",
            (task_id,),
        ).fetchall()
        succeeded = {str(row["slot_key"]) for row in rows if row["successful_media_id"]}
        if "primary" not in succeeded:
            return "primary"
        index = 2
        while f"draft-{index}" in succeeded:
            index += 1
        return f"draft-{index}"

    def has_blocking_draft_operation(self, task_id: str) -> str | None:
        row = self.connection.execute(
            """SELECT status FROM draft_operations
            WHERE task_id = ? AND status IN ('running', 'unknown') ORDER BY created_at DESC LIMIT 1""",
            (task_id,),
        ).fetchone()
        return str(row["status"]) if row else None

    def _draft_operation_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        slot = self.connection.execute(
            "SELECT slot_key FROM draft_slots WHERE id = ?",
            (row["draft_slot_id"],),
        ).fetchone()
        steps = self.connection.execute(
            "SELECT * FROM draft_operation_steps WHERE operation_id = ? ORDER BY sequence_no",
            (row["id"],),
        ).fetchall()
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "revision_id": row["revision_id"],
            "draft_slot": slot["slot_key"],
            "provider": row["provider"],
            "status": row["status"],
            "version": row["version"],
            "simulation_mode": row["simulation_mode"],
            "media_id": row["media_id"],
            "is_mock": row["provider"] == "mock",
            "confirmation": json.loads(row["confirmation_json"]),
            "last_error": json.loads(row["last_error_json"]) if row["last_error_json"] else None,
            "resolution": json.loads(row["resolution_json"]) if row["resolution_json"] else None,
            "confirmed_by": row["confirmed_by"],
            "confirmed_at": row["confirmed_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "steps": [
                {
                    "step_key": step["step_key"],
                    "sequence_no": step["sequence_no"],
                    "status": step["status"],
                    "version": step["version"],
                    "attempt_count": step["attempt_count"],
                    "output": json.loads(step["output_json"]) if step["output_json"] else None,
                    "last_error": json.loads(step["last_error_json"]) if step["last_error_json"] else None,
                }
                for step in steps
            ],
        }

    def get_draft_operation(self, operation_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM draft_operations WHERE id = ?",
            (operation_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("草稿操作不存在")
        return self._draft_operation_from_row(row)

    def list_draft_operations(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM draft_operations WHERE task_id = ? ORDER BY created_at DESC",
            (task_id,),
        ).fetchall()
        return [self._draft_operation_from_row(row) for row in rows]

    def continue_editing_publication(
        self,
        *,
        revision_id: str,
        expected_task_version: int,
        operator_id: str,
    ) -> dict[str, Any]:
        revision = self.get_publication_revision(revision_id)
        task_id = revision["task_id"]
        task = self.get_task(task_id)
        if task["version"] != expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        if task.get("active_publication_revision_id") != revision_id or revision["lifecycle_status"] != "active":
            raise VersionConflictError("冻结版本已失效")
        if self.has_blocking_draft_operation(task_id):
            raise VersionConflictError("存在进行中或结果未知的草稿操作，暂不能继续修改")
        now = utc_now()
        with self.lock:
            self.connection.execute(
                """UPDATE publication_revisions SET lifecycle_status = 'superseded', superseded_at = ?
                WHERE id = ? AND lifecycle_status = 'active'""",
                (now, revision_id),
            )
            self.connection.execute(
                """UPDATE draft_operations SET status = 'superseded', version = version + 1, updated_at = ?
                WHERE revision_id = ? AND status IN ('pending', 'failed')""",
                (now, revision_id),
            )
            updated = self.connection.execute(
                """UPDATE tasks SET active_publication_revision_id = NULL, status = 'plan_selected',
                version = version + 1, updated_at = ? WHERE id = ? AND version = ?""",
                (now, task_id, expected_task_version),
            )
            if updated.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("任务已被更新，请刷新后重试")
            self._record_event_locked(
                task_id,
                "publication_revision_superseded",
                {"revision_id": revision_id, "operator_id": operator_id},
                now,
            )
            self.connection.commit()
        return self.get_task(task_id)

    def create_mock_draft_operation(
        self,
        *,
        revision_id: str,
        draft_slot: str,
        expected_task_version: int,
        idempotency_key: str,
        request_hash: str,
        simulation_mode: str,
        confirmed_by: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        replay = self._idempotent_resource(
            scope="create_mock_draft",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay:
            operation = self.get_draft_operation(replay[1])
            return operation, self.get_task(operation["task_id"])

        revision = self.get_publication_revision(revision_id)
        task_id = revision["task_id"]
        task = self.get_task(task_id)
        if task["version"] != expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        if task.get("active_publication_revision_id") != revision_id or revision["lifecycle_status"] != "active":
            raise VersionConflictError("冻结版本不是当前有效版本")
        if self.has_blocking_draft_operation(task_id):
            raise VersionConflictError("存在进行中或结果未知的草稿操作")
        suggested = self.suggested_draft_slot(task_id)
        if draft_slot != suggested:
            raise VersionConflictError(f"当前草稿槽应为 {suggested}")

        existing = self.connection.execute(
            """SELECT op.id FROM draft_operations AS op
            JOIN draft_slots AS slot ON slot.id = op.draft_slot_id
            WHERE op.revision_id = ? AND slot.slot_key = ?""",
            (revision_id, draft_slot),
        ).fetchone()
        if existing:
            operation = self.get_draft_operation(str(existing["id"]))
            now = utc_now()
            with self.lock:
                self._record_idempotency_locked(
                    scope="create_mock_draft",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_type="draft_operation",
                    resource_id=operation["id"],
                    response=None,
                    now=now,
                )
                self.connection.commit()
            return operation, task

        now = utc_now()
        operation_id = str(uuid.uuid4())
        media_id = f"MOCK_MEDIA_{operation_id.replace('-', '')[:12].upper()}" if simulation_mode == "success" else None
        final_status = {"success": "succeeded", "fail_once": "failed", "unknown": "unknown"}[simulation_mode]
        task_status = {
            "succeeded": "mock_draft_created",
            "failed": "mock_draft_failed",
            "unknown": "mock_draft_unknown",
        }[final_status]
        confirmation = {
            "revision_id": revision_id,
            "normalized_hash": revision["normalized_hash"],
            "preflight_report_hash": revision["preflight_report_hash"],
            "frozen_html_hash": revision["frozen_html_hash"],
            "asset_manifest_hash": revision["asset_manifest_hash"],
            "confirmed_by": confirmed_by,
            "confirmed_at": now,
        }
        last_error = (
            {"code": "mock_draft_failed", "message": "模拟草稿创建明确失败", "retryable": True}
            if final_status == "failed"
            else (
                {"code": "mock_draft_unknown", "message": "模拟草稿创建结果未知", "retryable": False}
                if final_status == "unknown"
                else None
            )
        )
        with self.lock:
            slot_row = self.connection.execute(
                "SELECT id, successful_media_id FROM draft_slots WHERE task_id = ? AND slot_key = ?",
                (task_id, draft_slot),
            ).fetchone()
            if slot_row and slot_row["successful_media_id"]:
                raise VersionConflictError("草稿槽已被成功草稿占用")
            slot_id = str(slot_row["id"]) if slot_row else str(uuid.uuid4())
            if slot_row is None:
                self.connection.execute(
                    "INSERT INTO draft_slots (id, task_id, slot_key, successful_media_id, created_at) VALUES (?, ?, ?, NULL, ?)",
                    (slot_id, task_id, draft_slot, now),
                )
            self.connection.execute(
                """INSERT INTO draft_operations
                (id, task_id, revision_id, draft_slot_id, provider, idempotency_key, status,
                 version, simulation_mode, media_id, confirmation_json, last_error_json,
                 resolution_json, confirmed_by, confirmed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'mock', ?, ?, 1, ?, ?, ?, ?, NULL, ?, ?, ?, ?)""",
                (
                    operation_id,
                    task_id,
                    revision_id,
                    slot_id,
                    idempotency_key,
                    final_status,
                    simulation_mode,
                    media_id,
                    json.dumps(confirmation, ensure_ascii=False),
                    json.dumps(last_error, ensure_ascii=False) if last_error else None,
                    confirmed_by,
                    now,
                    now,
                    now,
                ),
            )
            step_defs = (
                ("validate_frozen_artifact", 1, "succeeded"),
                ("map_assets", 2, "succeeded"),
                ("create_draft", 3, final_status),
            )
            for step_key, sequence_no, status in step_defs:
                output = (
                    {"is_mock": True, "media_id": media_id}
                    if step_key == "create_draft" and status == "succeeded"
                    else ({"is_mock": True} if status == "succeeded" else None)
                )
                step_error = last_error if step_key == "create_draft" and status in {"failed", "unknown"} else None
                self.connection.execute(
                    """INSERT INTO draft_operation_steps
                    (id, operation_id, step_key, sequence_no, status, version, attempt_count,
                     input_hash, output_json, last_error_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        operation_id,
                        step_key,
                        sequence_no,
                        status,
                        revision["frozen_html_hash"],
                        json.dumps(output, ensure_ascii=False) if output else None,
                        json.dumps(step_error, ensure_ascii=False) if step_error else None,
                        now,
                        now,
                    ),
                )
            if media_id:
                self.connection.execute(
                    "UPDATE draft_slots SET successful_media_id = ? WHERE id = ?",
                    (media_id, slot_id),
                )
            updated = self.connection.execute(
                """UPDATE tasks SET status = ?, version = version + 1, updated_at = ?
                WHERE id = ? AND version = ? AND active_publication_revision_id = ?""",
                (task_status, now, task_id, expected_task_version, revision_id),
            )
            if updated.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("任务已被更新，请刷新后重试")
            self._record_event_locked(
                task_id,
                "draft_creation_confirmed",
                confirmation | {"operation_id": operation_id, "draft_slot": draft_slot, "provider": "mock"},
                now,
            )
            self._record_event_locked(
                task_id,
                f"mock_draft_{final_status}",
                {"operation_id": operation_id, "revision_id": revision_id, "media_id": media_id},
                now,
            )
            self._record_idempotency_locked(
                scope="create_mock_draft",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_type="draft_operation",
                resource_id=operation_id,
                response=None,
                now=now,
            )
            self.connection.commit()
        return self.get_draft_operation(operation_id), self.get_task(task_id)

    def begin_wenyan_draft_operation(
        self,
        *,
        revision_id: str,
        draft_slot: str,
        expected_task_version: int,
        idempotency_key: str,
        request_hash: str,
        confirmed_by: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        replay = self._idempotent_resource(
            scope="create_wenyan_draft",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay:
            operation = self.get_draft_operation(replay[1])
            return operation, self.get_task(operation["task_id"]), True

        revision = self.get_publication_revision(revision_id)
        task_id = revision["task_id"]
        task = self.get_task(task_id)
        if task["version"] != expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        if task.get("active_publication_revision_id") != revision_id or revision["lifecycle_status"] != "active":
            raise VersionConflictError("冻结版本不是当前有效版本")
        if self.has_blocking_draft_operation(task_id):
            raise VersionConflictError("存在进行中或结果未知的草稿操作")
        if draft_slot != self.suggested_draft_slot(task_id):
            raise VersionConflictError(f"当前草稿槽应为 {self.suggested_draft_slot(task_id)}")

        existing = self.connection.execute(
            """SELECT op.id FROM draft_operations AS op
            JOIN draft_slots AS slot ON slot.id = op.draft_slot_id
            WHERE op.revision_id = ? AND slot.slot_key = ?""",
            (revision_id, draft_slot),
        ).fetchone()
        if existing:
            operation = self.get_draft_operation(str(existing["id"]))
            now = utc_now()
            with self.lock:
                self._record_idempotency_locked(
                    scope="create_wenyan_draft",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_type="draft_operation",
                    resource_id=operation["id"],
                    response=None,
                    now=now,
                )
                self.connection.commit()
            return operation, task, True

        now = utc_now()
        operation_id = str(uuid.uuid4())
        slot_row = self.connection.execute(
            "SELECT id, successful_media_id FROM draft_slots WHERE task_id = ? AND slot_key = ?",
            (task_id, draft_slot),
        ).fetchone()
        if slot_row and slot_row["successful_media_id"]:
            raise VersionConflictError("草稿槽已被成功草稿占用")
        slot_id = str(slot_row["id"]) if slot_row else str(uuid.uuid4())
        confirmation = {
            "revision_id": revision_id,
            "normalized_hash": revision["normalized_hash"],
            "preflight_report_hash": revision["preflight_report_hash"],
            "frozen_html_hash": revision["frozen_html_hash"],
            "asset_manifest_hash": revision["asset_manifest_hash"],
            "confirmed_by": confirmed_by,
            "confirmed_at": now,
        }
        with self.lock:
            if slot_row is None:
                self.connection.execute(
                    "INSERT INTO draft_slots (id, task_id, slot_key, successful_media_id, created_at) VALUES (?, ?, ?, NULL, ?)",
                    (slot_id, task_id, draft_slot, now),
                )
            self.connection.execute(
                """INSERT INTO draft_operations
                (id, task_id, revision_id, draft_slot_id, provider, idempotency_key, status,
                 version, simulation_mode, media_id, confirmation_json, last_error_json,
                 resolution_json, confirmed_by, confirmed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'wenyan', ?, 'running', 1, 'real', NULL, ?, NULL, NULL, ?, ?, ?, ?)""",
                (
                    operation_id,
                    task_id,
                    revision_id,
                    slot_id,
                    idempotency_key,
                    json.dumps(confirmation, ensure_ascii=False),
                    confirmed_by,
                    now,
                    now,
                    now,
                ),
            )
            for step_key, sequence_no, status in (
                ("validate_frozen_artifact", 1, "succeeded"),
                ("map_assets", 2, "succeeded"),
                ("create_draft", 3, "running"),
            ):
                self.connection.execute(
                    """INSERT INTO draft_operation_steps
                    (id, operation_id, step_key, sequence_no, status, version, attempt_count,
                     input_hash, output_json, last_error_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, NULL, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        operation_id,
                        step_key,
                        sequence_no,
                        status,
                        revision["frozen_html_hash"],
                        json.dumps({"provider": "wenyan"}, ensure_ascii=False) if status == "succeeded" else None,
                        now,
                        now,
                    ),
                )
            updated = self.connection.execute(
                """UPDATE tasks SET status = 'wechat_draft_syncing', version = version + 1, updated_at = ?
                WHERE id = ? AND version = ? AND active_publication_revision_id = ?""",
                (now, task_id, expected_task_version, revision_id),
            )
            if updated.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("任务已被更新，请刷新后重试")
            self._record_event_locked(
                task_id,
                "wenyan_draft_started",
                {"operation_id": operation_id, "revision_id": revision_id, "draft_slot": draft_slot},
                now,
            )
            self._record_idempotency_locked(
                scope="create_wenyan_draft",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_type="draft_operation",
                resource_id=operation_id,
                response=None,
                now=now,
            )
            self.connection.commit()
        return self.get_draft_operation(operation_id), self.get_task(task_id), False

    def finish_wenyan_draft_operation(
        self,
        *,
        operation_id: str,
        expected_task_version: int,
        status: str,
        media_id: str | None,
        error: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if status not in {"succeeded", "failed", "unknown"}:
            raise ValueError("不支持的 Wenyan 草稿结果")
        operation = self.get_draft_operation(operation_id)
        if operation["provider"] != "wenyan" or operation["status"] != "running":
            raise VersionConflictError("草稿操作当前不能完成")
        task = self.get_task(operation["task_id"])
        if task["version"] != expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后核对草稿状态")
        revision = self.get_publication_revision(operation["revision_id"])
        now = utc_now()
        task_status = {
            "succeeded": "wechat_draft_created",
            "failed": "wechat_draft_failed",
            "unknown": "wechat_draft_unknown",
        }[status]
        with self.lock:
            self.connection.execute(
                """UPDATE draft_operations SET status = ?, media_id = ?, last_error_json = ?,
                version = version + 1, updated_at = ? WHERE id = ? AND status = 'running'""",
                (
                    status,
                    media_id,
                    json.dumps(error, ensure_ascii=False) if error else None,
                    now,
                    operation_id,
                ),
            )
            self.connection.execute(
                """UPDATE draft_operation_steps SET status = ?, output_json = ?, last_error_json = ?,
                version = version + 1, updated_at = ?
                WHERE operation_id = ? AND step_key = 'create_draft'""",
                (
                    status,
                    json.dumps({"provider": "wenyan", "media_id": media_id}, ensure_ascii=False) if media_id else None,
                    json.dumps(error, ensure_ascii=False) if error else None,
                    now,
                    operation_id,
                ),
            )
            if media_id:
                self.connection.execute(
                    """UPDATE draft_slots SET successful_media_id = ?
                    WHERE id = (SELECT draft_slot_id FROM draft_operations WHERE id = ?)""",
                    (media_id, operation_id),
                )
            updated = self.connection.execute(
                "UPDATE tasks SET status = ?, version = version + 1, updated_at = ? WHERE id = ? AND version = ?",
                (task_status, now, task["id"], expected_task_version),
            )
            if updated.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("任务已被更新，请刷新后核对草稿状态")
            self._record_event_locked(
                task["id"],
                f"wenyan_draft_{status}",
                {"operation_id": operation_id, "revision_id": revision["id"], "media_id": media_id, "error": error},
                now,
            )
            self.connection.commit()
        return self.get_draft_operation(operation_id), self.get_task(task["id"])

    def retry_wenyan_draft_operation(
        self,
        *,
        operation_id: str,
        expected_task_version: int,
        expected_operation_version: int,
        idempotency_key: str,
        request_hash: str,
        operator_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        replay = self._idempotent_resource(
            scope="retry_wenyan_draft",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay:
            operation = self.get_draft_operation(replay[1])
            return operation, self.get_task(operation["task_id"]), True
        operation = self.get_draft_operation(operation_id)
        task = self.get_task(operation["task_id"])
        if operation["provider"] != "wenyan" or operation["status"] != "failed":
            raise VersionConflictError("只有明确失败的 Wenyan 草稿操作可以重试")
        if task["version"] != expected_task_version or operation["version"] != expected_operation_version:
            raise VersionConflictError("草稿操作已更新，请刷新后重试")
        if task.get("active_publication_revision_id") != operation["revision_id"]:
            raise VersionConflictError("草稿操作绑定的冻结版本已失效")
        now = utc_now()
        with self.lock:
            updated_op = self.connection.execute(
                """UPDATE draft_operations SET status = 'running', version = version + 1,
                last_error_json = NULL, updated_at = ? WHERE id = ? AND version = ? AND status = 'failed'""",
                (now, operation_id, expected_operation_version),
            )
            if updated_op.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("草稿操作已更新，请刷新后重试")
            self.connection.execute(
                """UPDATE draft_operation_steps SET status = 'running', version = version + 1,
                attempt_count = attempt_count + 1, output_json = NULL, last_error_json = NULL, updated_at = ?
                WHERE operation_id = ? AND step_key = 'create_draft'""",
                (now, operation_id),
            )
            updated_task = self.connection.execute(
                """UPDATE tasks SET status = 'wechat_draft_syncing', version = version + 1, updated_at = ?
                WHERE id = ? AND version = ?""",
                (now, task["id"], expected_task_version),
            )
            if updated_task.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("任务已被更新，请刷新后重试")
            self._record_event_locked(
                task["id"],
                "wenyan_draft_retry_started",
                {"operation_id": operation_id, "operator_id": operator_id},
                now,
            )
            self._record_idempotency_locked(
                scope="retry_wenyan_draft",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_type="draft_operation",
                resource_id=operation_id,
                response=None,
                now=now,
            )
            self.connection.commit()
        return self.get_draft_operation(operation_id), self.get_task(task["id"]), False

    def retry_mock_draft_operation(
        self,
        *,
        operation_id: str,
        expected_task_version: int,
        expected_operation_version: int,
        idempotency_key: str,
        request_hash: str,
        operator_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        replay = self._idempotent_resource(
            scope="retry_mock_draft",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay:
            operation = self.get_draft_operation(replay[1])
            return operation, self.get_task(operation["task_id"])
        operation = self.get_draft_operation(operation_id)
        task = self.get_task(operation["task_id"])
        revision = self.get_publication_revision(operation["revision_id"])
        if task["version"] != expected_task_version or operation["version"] != expected_operation_version:
            raise VersionConflictError("草稿操作已更新，请刷新后重试")
        if operation["status"] != "failed":
            raise VersionConflictError("当前草稿操作不可重试")
        if task.get("active_publication_revision_id") != operation["revision_id"]:
            raise VersionConflictError("草稿操作绑定的冻结版本已失效")
        now = utc_now()
        media_id = f"MOCK_MEDIA_{operation_id.replace('-', '')[:12].upper()}"
        with self.lock:
            updated_op = self.connection.execute(
                """UPDATE draft_operations SET status = 'succeeded', version = version + 1,
                media_id = ?, last_error_json = NULL, updated_at = ?
                WHERE id = ? AND version = ? AND status = 'failed'""",
                (media_id, now, operation_id, expected_operation_version),
            )
            if updated_op.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("草稿操作已更新，请刷新后重试")
            self.connection.execute(
                """UPDATE draft_operation_steps SET status = 'succeeded', version = version + 1,
                attempt_count = attempt_count + 1, output_json = ?, last_error_json = NULL, updated_at = ?
                WHERE operation_id = ? AND step_key = 'create_draft'""",
                (json.dumps({"is_mock": True, "media_id": media_id}, ensure_ascii=False), now, operation_id),
            )
            self.connection.execute(
                """UPDATE draft_slots SET successful_media_id = ?
                WHERE id = (SELECT draft_slot_id FROM draft_operations WHERE id = ?)""",
                (media_id, operation_id),
            )
            updated_task = self.connection.execute(
                """UPDATE tasks SET status = 'mock_draft_created', version = version + 1, updated_at = ?
                WHERE id = ? AND version = ?""",
                (now, task["id"], expected_task_version),
            )
            if updated_task.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("任务已被更新，请刷新后重试")
            self._record_event_locked(
                task["id"],
                "mock_draft_retry_succeeded",
                {"operation_id": operation_id, "media_id": media_id, "operator_id": operator_id},
                now,
            )
            self._record_idempotency_locked(
                scope="retry_mock_draft",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_type="draft_operation",
                resource_id=operation_id,
                response=None,
                now=now,
            )
            self.connection.commit()
        return self.get_draft_operation(operation_id), self.get_task(task["id"])

    def resolve_unknown_mock_draft_operation(
        self,
        *,
        operation_id: str,
        expected_task_version: int,
        expected_operation_version: int,
        outcome: str,
        evidence: str,
        idempotency_key: str,
        request_hash: str,
        operator_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        replay = self._idempotent_resource(
            scope="resolve_mock_unknown",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay:
            operation = self.get_draft_operation(replay[1])
            return operation, self.get_task(operation["task_id"])
        operation = self.get_draft_operation(operation_id)
        task = self.get_task(operation["task_id"])
        revision = self.get_publication_revision(operation["revision_id"])
        if task["version"] != expected_task_version or operation["version"] != expected_operation_version:
            raise VersionConflictError("草稿操作已更新，请刷新后重试")
        if operation["status"] != "unknown":
            raise VersionConflictError("当前草稿操作不是结果未知状态")
        if task.get("active_publication_revision_id") != operation["revision_id"]:
            raise VersionConflictError("草稿操作绑定的冻结版本已失效")
        now = utc_now()
        succeeded = outcome == "confirmed_succeeded"
        status = "succeeded" if succeeded else "failed"
        media_id = f"MOCK_MEDIA_{operation_id.replace('-', '')[:12].upper()}" if succeeded else None
        task_status = "mock_draft_created" if succeeded else "mock_draft_failed"
        resolution = {"outcome": outcome, "evidence": evidence, "resolved_by": operator_id, "resolved_at": now}
        with self.lock:
            updated_op = self.connection.execute(
                """UPDATE draft_operations SET status = ?, version = version + 1,
                simulation_mode = CASE WHEN ? = 'failed' THEN 'fail_once' ELSE simulation_mode END,
                media_id = ?, last_error_json = ?, resolution_json = ?, updated_at = ?
                WHERE id = ? AND version = ? AND status = 'unknown'""",
                (
                    status,
                    status,
                    media_id,
                    None if succeeded else json.dumps({"code": "confirmed_not_created", "message": "已确认未创建草稿", "retryable": True}, ensure_ascii=False),
                    json.dumps(resolution, ensure_ascii=False),
                    now,
                    operation_id,
                    expected_operation_version,
                ),
            )
            if updated_op.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("草稿操作已更新，请刷新后重试")
            self.connection.execute(
                """UPDATE draft_operation_steps SET status = ?, version = version + 1,
                output_json = ?, last_error_json = ?, updated_at = ?
                WHERE operation_id = ? AND step_key = 'create_draft'""",
                (
                    status,
                    json.dumps({"is_mock": True, "media_id": media_id}, ensure_ascii=False) if succeeded else None,
                    None if succeeded else json.dumps({"code": "confirmed_not_created", "message": "已确认未创建草稿", "retryable": True}, ensure_ascii=False),
                    now,
                    operation_id,
                ),
            )
            if succeeded:
                self.connection.execute(
                    """UPDATE draft_slots SET successful_media_id = ?
                    WHERE id = (SELECT draft_slot_id FROM draft_operations WHERE id = ?)""",
                    (media_id, operation_id),
                )
            updated_task = self.connection.execute(
                """UPDATE tasks SET status = ?, version = version + 1, updated_at = ?
                WHERE id = ? AND version = ?""",
                (task_status, now, task["id"], expected_task_version),
            )
            if updated_task.rowcount != 1:
                self.connection.rollback()
                raise VersionConflictError("任务已被更新，请刷新后重试")
            self._record_event_locked(
                task["id"],
                "mock_draft_unknown_resolved",
                {"operation_id": operation_id, **resolution, "media_id": media_id},
                now,
            )
            self._record_idempotency_locked(
                scope="resolve_mock_unknown",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_type="draft_operation",
                resource_id=operation_id,
                response=None,
                now=now,
            )
            self.connection.commit()
        return self.get_draft_operation(operation_id), self.get_task(task["id"])

    def list_blind_review_submissions(
        self, eval_set_id: str, reviewer_id: str | None = None
    ) -> list[dict[str, Any]]:
        if reviewer_id:
            rows = self.connection.execute(
                """SELECT * FROM blind_review_submissions
                WHERE eval_set_id = ? AND reviewer_id = ? ORDER BY created_at""",
                (eval_set_id, reviewer_id),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """SELECT * FROM blind_review_submissions
                WHERE eval_set_id = ? ORDER BY reviewer_id, created_at""",
                (eval_set_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "eval_set_id": row["eval_set_id"],
                "reviewer_id": row["reviewer_id"],
                "sample_id": row["sample_id"],
                "assignment_token": row["assignment_token"],
                "response": json.loads(row["response_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def create_blind_review_submission(
        self,
        *,
        eval_set_id: str,
        reviewer_id: str,
        sample_id: str,
        assignment_token: str,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        with self.lock:
            existing = self.connection.execute(
                """SELECT id FROM blind_review_submissions
                WHERE eval_set_id = ? AND reviewer_id = ? AND sample_id = ?""",
                (eval_set_id, reviewer_id, sample_id),
            ).fetchone()
            if existing is not None:
                raise VersionConflictError("该样本已经提交，盲评结果不可修改")
            self.connection.execute(
                "INSERT INTO blind_review_submissions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    eval_set_id,
                    reviewer_id,
                    sample_id,
                    assignment_token,
                    json.dumps(response, ensure_ascii=False),
                    now,
                ),
            )
            self.connection.commit()
        return next(
            item
            for item in self.list_blind_review_submissions(eval_set_id, reviewer_id)
            if item["sample_id"] == sample_id
        )
