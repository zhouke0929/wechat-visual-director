from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


DATASET_DATABASE = "visual-director.db"
DATASET_DIRECTORIES = ("image-assets", "publication-assets")
HISTORY_FILENAME = "install-history.json"


class DataRecoveryError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class DatasetInventory:
    root: Path
    database: Path
    exists: bool
    healthy: bool
    task_count: int
    latest_task_at: str | None
    database_bytes: int
    database_sha256: str | None
    image_asset_count: int
    publication_asset_count: int
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "database": str(self.database),
            "exists": self.exists,
            "healthy": self.healthy,
            "task_count": self.task_count,
            "latest_task_at": self.latest_task_at,
            "database_bytes": self.database_bytes,
            "database_sha256": self.database_sha256,
            "image_asset_count": self.image_asset_count,
            "publication_asset_count": self.publication_asset_count,
            "error": self.error,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_count(root: Path) -> int:
    return sum(1 for path in root.rglob("*") if path.is_file()) if root.is_dir() else 0


def inspect_dataset(root: Path) -> DatasetInventory:
    root = root.expanduser().resolve()
    database = root / DATASET_DATABASE
    if not database.is_file():
        return DatasetInventory(
            root=root,
            database=database,
            exists=False,
            healthy=False,
            task_count=0,
            latest_task_at=None,
            database_bytes=0,
            database_sha256=None,
            image_asset_count=_file_count(root / "image-assets"),
            publication_asset_count=_file_count(root / "publication-assets"),
        )

    task_count = 0
    latest_task_at: str | None = None
    healthy = False
    error: str | None = None
    try:
        uri = f"file:{database.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        try:
            healthy = connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            table_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone()
            if table_exists:
                task_count, latest_task_at = connection.execute(
                    "SELECT COUNT(*), MAX(updated_at) FROM tasks"
                ).fetchone()
        finally:
            connection.close()
    except (sqlite3.Error, OSError) as exc:
        error = str(exc)

    return DatasetInventory(
        root=root,
        database=database,
        exists=True,
        healthy=healthy,
        task_count=int(task_count),
        latest_task_at=str(latest_task_at) if latest_task_at else None,
        database_bytes=database.stat().st_size,
        database_sha256=_sha256(database),
        image_asset_count=_file_count(root / "image-assets"),
        publication_asset_count=_file_count(root / "publication-assets"),
        error=error,
    )


def _read_history_candidates(history_file: Path | None) -> list[Path]:
    if history_file is None or not history_file.is_file():
        return []
    try:
        payload = json.loads(history_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    values: list[str] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("data_root"), str):
            values.append(payload["data_root"])
        for entry in payload.get("installations", []):
            if isinstance(entry, dict) and isinstance(entry.get("data_root"), str):
                values.append(entry["data_root"])
    return [Path(value).expanduser() for value in values]


def candidate_data_roots(
    *,
    active_root: Path,
    project_root: Path,
    history_file: Path | None = None,
    explicit: Iterable[Path] = (),
) -> list[Path]:
    home = Path.home()
    candidates = [
        active_root,
        project_root / "apps" / "api" / "data",
        home / "wechat-visual-director" / "apps" / "api" / "data",
        home / "Documents" / "wechat-visual-director" / "apps" / "api" / "data",
    ]
    candidates.extend(_read_history_candidates(history_file))
    candidates.extend(explicit)
    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        key = os.path.normcase(str(resolved))
        if key not in seen:
            seen.add(key)
            result.append(resolved)
    return result


def scan_datasets(
    *,
    active_root: Path,
    project_root: Path,
    history_file: Path | None = None,
    explicit: Iterable[Path] = (),
) -> list[DatasetInventory]:
    return [
        inspect_dataset(root)
        for root in candidate_data_roots(
            active_root=active_root,
            project_root=project_root,
            history_file=history_file,
            explicit=explicit,
        )
    ]


def _copy_dataset(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(f"file:{(source / DATASET_DATABASE).as_posix()}?mode=ro", uri=True)
    destination_connection = sqlite3.connect(destination / DATASET_DATABASE)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()
    for directory in DATASET_DIRECTORIES:
        source_dir = source / directory
        target_dir = destination / directory
        if target_dir.exists():
            shutil.rmtree(target_dir)
        if source_dir.is_dir():
            shutil.copytree(source_dir, target_dir)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)


def recover_dataset(
    *,
    source_root: Path,
    target_root: Path,
    backup_root: Path,
    activate: bool = False,
    confirmed: bool = False,
) -> dict[str, Any]:
    source = inspect_dataset(source_root)
    target = inspect_dataset(target_root)
    if not source.exists or not source.healthy:
        raise DataRecoveryError(
            "invalid_source_dataset",
            "来源数据不存在或未通过 SQLite 完整性检查",
            details={"source": source.as_dict()},
        )
    if source.root == target.root:
        raise DataRecoveryError("same_data_root", "来源与目标数据目录相同")
    if target.task_count > 0 and not activate:
        raise DataRecoveryError(
            "target_has_tasks",
            "目标数据中已有任务，拒绝静默覆盖；请先确认备份内容，再显式激活来源数据",
            details={"source": source.as_dict(), "target": target.as_dict(), "requires": ["--activate", "--yes"]},
        )
    if target.task_count > 0 and not confirmed:
        raise DataRecoveryError(
            "confirmation_required",
            "激活历史数据前必须显式确认",
            details={"requires": "--yes"},
        )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = backup_root.expanduser().resolve() / f"data-before-recovery-{stamp}"
    stage_dir = backup_root.expanduser().resolve() / f".stage-recovery-{stamp}"
    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    if target.exists or target.image_asset_count or target.publication_asset_count:
        _copy_dataset(target.root, backup_dir) if target.exists else shutil.copytree(target.root, backup_dir)

    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    _copy_dataset(source.root, stage_dir)
    staged = inspect_dataset(stage_dir)
    if (
        not staged.healthy
        or staged.task_count != source.task_count
        or staged.latest_task_at != source.latest_task_at
    ):
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise DataRecoveryError("staging_verification_failed", "恢复暂存数据校验失败")

    target.root.mkdir(parents=True, exist_ok=True)
    for name in (DATASET_DATABASE, *DATASET_DIRECTORIES):
        destination = target.root / name
        staged_path = stage_dir / name
        if destination.is_dir():
            shutil.rmtree(destination)
        elif destination.exists():
            destination.unlink()
        shutil.move(str(staged_path), str(destination))
    shutil.rmtree(stage_dir, ignore_errors=True)

    recovered = inspect_dataset(target.root)
    if not recovered.healthy or recovered.database_sha256 != staged.database_sha256:
        raise DataRecoveryError(
            "recovery_verification_failed",
            "数据已复制但最终校验失败，请使用备份恢复",
            details={"backup_root": str(backup_dir)},
        )
    return {
        "source": source.as_dict(),
        "previous_target": target.as_dict(),
        "recovered": recovered.as_dict(),
        "backup_root": str(backup_dir) if backup_dir.exists() else None,
        "mode": "activate" if target.task_count > 0 else "migrate",
    }
