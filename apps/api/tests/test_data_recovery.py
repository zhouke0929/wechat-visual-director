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


def test_recovery_reads_chinese_path_with_hash_as_literal(tmp_path: Path) -> None:
    source = tmp_path / "旧稿#2026"
    target = tmp_path / "归档#本地"
    make_dataset(source, ["task-a"])
    assert inspect_dataset(source).task_count == 1
    result = recover_dataset(source_root=source, target_root=target, backup_root=tmp_path / "backups")
    assert result["recovered"]["task_count"] == 1
    assert (target / "image-assets" / "image.png").read_bytes() == b"image"
    assert not (tmp_path / "旧稿").exists()
    assert not (tmp_path / "归档").exists()


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


@pytest.mark.parametrize("with_database", [False, True])
def test_theme_only_target_requires_confirmation_and_keeps_theme_backup(tmp_path: Path, with_database: bool) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup_root = tmp_path / "backups"
    make_dataset(source, ["old-task"])
    if with_database:
        target.mkdir()
        connection = sqlite3.connect(target / "visual-director.db")
        connection.close()
    theme_file = target / "theme-packs" / "local-theme" / "manifest.json"
    theme_file.parent.mkdir(parents=True)
    theme_file.write_text("{}", encoding="utf-8")
    assert inspect_dataset(target).theme_pack_file_count == 1

    args = dict(source_root=source, target_root=target, backup_root=backup_root)
    with pytest.raises(DataRecoveryError) as error:
        recover_dataset(**args)
    assert error.value.code == "target_has_assets"
    with pytest.raises(DataRecoveryError) as error:
        recover_dataset(**args, activate=True)
    assert error.value.code == "confirmation_required"
    assert theme_file.is_file()

    result = recover_dataset(**args, activate=True, confirmed=True)
    assert result["mode"] == "activate"
    assert (Path(result["backup_root"]) / theme_file.relative_to(target)).read_text(encoding="utf-8") == "{}"
