"""Data continuity checks and backups; never automatically choose a migration."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

from .data_recovery import DATASET_DIRECTORIES, DataRecoveryError, _copy_dataset, _sha256, inspect_dataset


def _same_path(first: str | Path, second: str | Path) -> bool:
    return os.path.normcase(str(Path(first).resolve())) == os.path.normcase(str(Path(second).resolve()))


def dataset_snapshot(root: Path) -> dict[str, Any]:
    inventory = inspect_dataset(root)
    if inventory.exists and not inventory.healthy:
        raise DataRecoveryError("upgrade_dataset_unhealthy", "升级前后数据未通过完整性检查",
                                details={"dataset": inventory.as_dict()})
    task_ids: list[str] = []
    if inventory.exists:
        try:
            with closing(sqlite3.connect(inventory.database.as_uri() + "?mode=ro", uri=True)) as connection:
                if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tasks'").fetchone():
                    task_ids = sorted(row[0] for row in connection.execute("SELECT id FROM tasks"))
        except sqlite3.Error as exc:
            raise DataRecoveryError("upgrade_dataset_incompatible", "无法读取现有任务清单，停止升级") from exc
    assets = {
        str(path.relative_to(inventory.root).as_posix()): _sha256(path)
        for name in DATASET_DIRECTORIES
        for path in sorted((inventory.root / name).rglob("*"))
        if path.is_file()
    }
    return {**inventory.as_dict(), "task_ids": task_ids, "assets": assets}


def probe_running_data(api_base: str) -> dict[str, Any] | None:
    url = urlsplit(api_base)
    if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.username or url.password:
        raise DataRecoveryError("upgrade_api_not_local", "升级检查只允许本地工作台地址")
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    # No proxy, redirects or credentials: read only the local health response.
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(f"{url.scheme}://{url.netloc}/health", timeout=3) as response:
            value = json.loads(response.read(65536))
    except (OSError, URLError, ValueError):
        return None
    if not isinstance(value, dict) or value.get("application") != "wechat_visual_director_workbench":
        return None
    identity = value.get("runtime_identity")
    if isinstance(identity, dict) and isinstance(identity.get("data_root"), str):
        return {"root": identity["data_root"], "task_count": identity.get("task_count", 0)}
    raise DataRecoveryError("upgrade_running_data_unknown", "无法确认当前工作台的数据来源；请先盘点旧数据")


def capture_upgrade_data(install_root: Path, *, running: dict[str, Any] | None = None,
                         candidates: tuple[Path, ...] = ()) -> dict[str, Any]:
    install_root = install_root.resolve()
    target = install_root / "data"
    manifest = install_root / "install.json"
    if manifest.is_file():
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8-sig"))
            previous_root = metadata["data_root"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise DataRecoveryError("upgrade_manifest_invalid", "无法确认升级前的数据目录") from exc
        if not _same_path(previous_root, target):
            raise DataRecoveryError("upgrade_data_root_changed", "安装器将切换既有数据目录，必须先确认迁移",
                                    details={"previous_data_root": previous_root, "target_data_root": str(target)})
    before = dataset_snapshot(target)
    known = list(candidates)
    if running and not _same_path(running["root"], target):
        source = dataset_snapshot(Path(running["root"]))
        if source["task_count"] or running.get("task_count", 0):
            raise DataRecoveryError("upgrade_data_migration_required", "正在使用另一套任务数据；确认迁移后才能升级",
                                    details={"source": inspect_dataset(Path(running["root"])).as_dict(),
                                             "target": inspect_dataset(target).as_dict(), "action": "review_data_migration"})
        known.append(Path(running["root"]))
    if before["task_count"] == 0:
        for root in known:
            if _same_path(root, target):
                continue
            source = inspect_dataset(root)
            if source.exists and source.task_count > 0:
                raise DataRecoveryError("upgrade_data_migration_required", "新工作台为空，但发现已有任务数据；请先确认迁移",
                                        details={"source": source.as_dict(), "target": inspect_dataset(target).as_dict(),
                                                 "action": "review_data_migration"})
    return {"schema_version": "upgrade_data_snapshot.v0.1", "install_root": str(install_root), "before": before}


def verify_upgrade_data(baseline: dict[str, Any], install_root: Path) -> dict[str, Any]:
    if baseline.get("schema_version") != "upgrade_data_snapshot.v0.1" or not _same_path(baseline["install_root"], install_root):
        raise DataRecoveryError("upgrade_snapshot_invalid", "数据延续检查快照不属于当前安装")
    before = baseline["before"]
    current = dataset_snapshot(install_root / "data")
    missing_tasks = sorted(set(before["task_ids"]) - set(current["task_ids"]))
    changed_assets = [name for name, digest in before["assets"].items() if current["assets"].get(name) != digest]
    if missing_tasks or changed_assets or (before["exists"] and not current["exists"]):
        raise DataRecoveryError("upgrade_data_continuity_failed", "升级后的任务或配套资产不完整；不能报告工作台已就绪",
                                details={"missing_task_count": len(missing_tasks),
                                         "changed_asset_count": len(changed_assets), "data_root": current["root"]})
    return {"checked": True, "preserved": True, "data_root": current["root"],
            "before_task_count": before["task_count"], "after_task_count": current["task_count"],
            "image_asset_count": current["image_asset_count"],
            "publication_asset_count": current["publication_asset_count"],
            "backup_root": baseline.get("backup_root")}


def backup_upgrade_data(baseline: dict[str, Any]) -> dict[str, Any]:
    """Back up a validated active dataset, never a guessed migration candidate."""
    before = baseline["before"]
    if not (before["task_count"] or before["assets"]):
        return baseline
    root = Path(baseline["install_root"]).resolve()
    source = root / "data"
    if not _same_path(before["root"], source):
        raise DataRecoveryError("upgrade_snapshot_invalid", "备份快照的数据目录不属于当前安装")
    parent = root / "backups"
    if parent.is_symlink() or not parent.resolve().is_relative_to(root):
        raise DataRecoveryError("upgrade_backup_path_unsafe", "升级备份目录不能重定向到安装目录之外")
    backup = parent / f"data-before-upgrade-{uuid.uuid4().hex}"
    try:
        _copy_dataset(source, backup)
        copied = dataset_snapshot(backup)
    except (OSError, sqlite3.Error) as exc:
        raise DataRecoveryError("upgrade_backup_failed", "升级前备份未完成，保留现有安装并停止升级") from exc
    if copied["task_ids"] != before["task_ids"] or copied["assets"] != before["assets"]:
        raise DataRecoveryError("upgrade_backup_verification_failed", "备份期间数据发生变化，请暂停编辑后重试升级")
    return {**baseline, "backup_root": str(backup)}
