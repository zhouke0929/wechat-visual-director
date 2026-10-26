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
                         candidates: tuple[Path, ...] = (), target_data_root: Path | None = None) -> dict[str, Any]:
    install_root = install_root.resolve()
    target = target_data_root.resolve() if target_data_root else install_root / "data"
    manifest = install_root / "install.json"
    if manifest.is_file():
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8-sig"))
            previous_root = metadata["data_root"]
            # Legacy Windows manifests stored a virtual path. The manifest we
            # actually opened owns its standard adjacent data directory, even
            # when that recorded prefix resolves differently in another host.
            # Never rebase an external/custom data directory.
            recorded_install = metadata.get("install_root")
            if recorded_install and os.path.normcase(os.path.abspath(previous_root)) == os.path.normcase(
                os.path.abspath(Path(recorded_install) / "data")
            ):
                previous_root = str(install_root / "data")
            pinned_root = metadata.get("physical_install_root")
            if pinned_root and os.path.normcase(os.path.abspath(pinned_root)) != os.path.normcase(str(install_root)):
                raise DataRecoveryError("install_location_changed", "安装实际位置与记录不一致，请确认原安装后再升级",
                                        details={"expected_root": pinned_root, "actual_root": str(install_root)})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise DataRecoveryError("upgrade_manifest_invalid", "无法确认升级前的数据目录") from exc
        if not _same_path(previous_root, target) and target_data_root is None:
            raise DataRecoveryError("upgrade_data_root_changed", "安装器将切换既有数据目录，必须先确认迁移",
                                    details={"previous_data_root": previous_root, "target_data_root": str(target)})
    before = dataset_snapshot(target)
    if running and not _same_path(running["root"], target):
        # A foreign service is a port/runtime conflict, not consent to migrate it.
        raise DataRecoveryError("upgrade_runtime_conflict", "安装地址正由另一套工作台使用；请关闭该服务或使用独立端口，无需迁移其数据",
                                details={"running_data_root": running["root"], "target_data_root": str(target),
                                         "action": "resolve_runtime_conflict"})
    optional_sources = []
    seen = set()
    for root in candidates:
        key = os.path.normcase(str(root.resolve()))
        if key in seen or _same_path(root, target):
            continue
        seen.add(key)
        source = inspect_dataset(root)
        if source.exists and source.healthy and source.task_count > 0:
            optional_sources.append(source.as_dict())
    # Finding another dataset does not establish ownership by this installation.
    # Preserve the target; importing any optional source remains an explicit action.
    return {"schema_version": "upgrade_data_snapshot.v0.1", "install_root": str(install_root), "before": before,
            "target_data_root": str(target),
            "migration_candidates": optional_sources,
            "warnings": ["optional_data_migration_available"] if optional_sources else []}


def verify_upgrade_data(baseline: dict[str, Any], install_root: Path) -> dict[str, Any]:
    if baseline.get("schema_version") != "upgrade_data_snapshot.v0.1" or not _same_path(baseline["install_root"], install_root):
        raise DataRecoveryError("upgrade_snapshot_invalid", "数据延续检查快照不属于当前安装")
    before = baseline["before"]
    target = install_root / "data"
    manifest = install_root / "install.json"
    if manifest.is_file():
        metadata = json.loads(manifest.read_text(encoding="utf-8-sig"))
        target = Path(metadata["data_root"])
        if metadata.get("install_root") and os.path.normcase(os.path.abspath(target)) == os.path.normcase(
            os.path.abspath(Path(metadata["install_root"]) / "data")
        ):
            target = install_root / "data"
    current = dataset_snapshot(target)
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
            "backup_root": baseline.get("backup_root"),
            "migration_candidates": baseline.get("migration_candidates", []),
            "warnings": baseline.get("warnings", [])}


def backup_upgrade_data(baseline: dict[str, Any]) -> dict[str, Any]:
    """Back up a validated active dataset, never a guessed migration candidate."""
    before = baseline["before"]
    if not (before["task_count"] or before["assets"]):
        return baseline
    root = Path(baseline["install_root"]).resolve()
    source = Path(baseline.get("target_data_root", str(root / "data"))).resolve()
    if not _same_path(before["root"], source):
        raise DataRecoveryError("upgrade_snapshot_invalid", "备份快照的数据目录不属于当前安装")
    owner = root if _same_path(source, root / "data") else source.parent
    parent = owner / "backups"
    if parent.is_symlink() or not parent.resolve().is_relative_to(owner):
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
