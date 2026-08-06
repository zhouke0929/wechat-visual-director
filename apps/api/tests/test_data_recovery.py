from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from visual_director.data_recovery import DataRecoveryError, inspect_dataset, recover_dataset


def make_dataset(root: Path, task_ids: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(root / "visual-director.db")
    connection.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL)")
    connection.executemany(
        "INSERT INTO tasks (id, updated_at) VALUES (?, ?)",
        [(task_id, f"2026-08-{index + 1:02d}T00:00:00+00:00") for index, task_id in enumerate(task_ids)],
    )
    connection.commit()
    connection.close()
    (root / "image-assets").mkdir()
    (root / "publication-assets").mkdir()
    (root / "image-assets" / "image.png").write_bytes(b"image")
    (root / "publication-assets" / "article.html").write_text("ok", encoding="utf-8")


def test_inspect_dataset_reports_database_and_assets(tmp_path: Path) -> None:
    root = tmp_path / "source"
    make_dataset(root, ["task-a", "task-b"])
    result = inspect_dataset(root)
    assert result.healthy is True
    assert result.task_count == 2
    assert result.image_asset_count == 1
    assert result.publication_asset_count == 1


def test_recover_into_empty_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    make_dataset(source, ["task-a"])
    result = recover_dataset(source_root=source, target_root=target, backup_root=tmp_path / "backups")
    assert result["mode"] == "migrate"
    assert inspect_dataset(target).task_count == 1
    assert (target / "image-assets" / "image.png").is_file()


def test_nonempty_target_requires_explicit_activation_and_keeps_backup(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    make_dataset(source, ["old-task"])
    make_dataset(target, ["new-task"])
    with pytest.raises(DataRecoveryError) as error:
        recover_dataset(source_root=source, target_root=target, backup_root=tmp_path / "backups")
    assert error.value.code == "target_has_tasks"

    result = recover_dataset(
        source_root=source,
        target_root=target,
        backup_root=tmp_path / "backups",
        activate=True,
        confirmed=True,
    )
    assert result["mode"] == "activate"
    assert inspect_dataset(target).task_count == 1
    backup = Path(result["backup_root"])
    connection = sqlite3.connect(backup / "visual-director.db")
    try:
        assert connection.execute("SELECT id FROM tasks").fetchone()[0] == "new-task"
    finally:
        connection.close()
