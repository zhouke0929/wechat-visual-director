from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from visual_director.data_recovery import DataRecoveryError
from visual_director.upgrade_data import backup_upgrade_data, capture_upgrade_data, dataset_snapshot, verify_upgrade_data
from test_data_recovery import make_dataset


REPO = Path(__file__).resolve().parents[3]


def test_upgrade_preserves_ids_and_assets_not_just_counts(tmp_path: Path) -> None:
    install = tmp_path / "installed"
    make_dataset(install / "data", ["old-task"])
    before = capture_upgrade_data(install)
    result = verify_upgrade_data(before, install)
    assert result["preserved"] is True
    assert result["before_task_count"] == result["after_task_count"] == 1
    with sqlite3.connect(install / "data/visual-director.db") as connection:
        connection.execute("UPDATE tasks SET id = 'different-task'")
    with pytest.raises(DataRecoveryError, match="不完整") as error:
        verify_upgrade_data(before, install)
    assert error.value.code == "upgrade_data_continuity_failed"
    assert error.value.details["missing_task_count"] == 1


@pytest.mark.parametrize("asset", ["image-assets/image.png", "publication-assets/article.html"])
def test_missing_or_changed_assets_block_success(tmp_path: Path, asset: str) -> None:
    install = tmp_path / "installed"
    make_dataset(install / "data", ["task"])
    before = capture_upgrade_data(install)
    (install / "data" / asset).write_bytes(b"changed but same file count")
    with pytest.raises(DataRecoveryError) as error:
        verify_upgrade_data(before, install)
    assert error.value.details["changed_asset_count"] == 1
    (install / "data" / asset).unlink()
    with pytest.raises(DataRecoveryError):
        verify_upgrade_data(before, install)


def test_empty_target_with_old_source_blocks_without_mutating_either(tmp_path: Path) -> None:
    source = tmp_path / "source"
    install = tmp_path / "installed"
    make_dataset(source, ["old"])
    make_dataset(install / "data", [])
    before = dataset_snapshot(source)
    with pytest.raises(DataRecoveryError) as error:
        capture_upgrade_data(install, candidates=(source,))
    assert error.value.code == "upgrade_data_migration_required"
    assert dataset_snapshot(source) == before
    assert dataset_snapshot(install / "data")["task_count"] == 0


def test_live_foreign_data_blocks_even_when_target_also_has_tasks(tmp_path: Path) -> None:
    source = tmp_path / "source"
    install = tmp_path / "installed"
    make_dataset(source, ["old"])
    make_dataset(install / "data", ["other"])
    with pytest.raises(DataRecoveryError) as error:
        capture_upgrade_data(install, running={"root": str(source), "task_count": 1})
    assert error.value.code == "upgrade_data_migration_required"


def test_genuine_first_install_with_no_history_is_allowed(tmp_path: Path) -> None:
    install = tmp_path / "installed"
    before = capture_upgrade_data(install, candidates=(tmp_path / "absent",))
    make_dataset(install / "data", [])
    assert verify_upgrade_data(before, install)["preserved"] is True


def test_changed_manifest_data_root_is_not_silently_reset(tmp_path: Path) -> None:
    install = tmp_path / "installed"
    install.mkdir()
    (install / "install.json").write_text(json.dumps({"data_root": str(tmp_path / "custom-data")}), encoding="utf-8")
    with pytest.raises(DataRecoveryError) as error:
        capture_upgrade_data(install)
    assert error.value.code == "upgrade_data_root_changed"


def test_upgrade_backup_includes_database_and_both_asset_families(tmp_path: Path) -> None:
    install = tmp_path / "installed"
    make_dataset(install / "data", ["old"])
    before = backup_upgrade_data(capture_upgrade_data(install))
    copied = dataset_snapshot(Path(before["backup_root"]))
    assert copied["task_ids"] == before["before"]["task_ids"]
    assert copied["assets"] == before["before"]["assets"]
    assert verify_upgrade_data(before, install)["backup_root"] == before["backup_root"]


def test_first_install_does_not_create_an_empty_backup(tmp_path: Path) -> None:
    install = tmp_path / "installed"
    assert "backup_root" not in backup_upgrade_data(capture_upgrade_data(install))
    assert not (install / "backups").exists()


def test_unhealthy_or_missing_original_database_blocks(tmp_path: Path) -> None:
    install = tmp_path / "installed"
    make_dataset(install / "data", ["task"])
    before = capture_upgrade_data(install)
    (install / "data/visual-director.db").write_bytes(b"not a database")
    with pytest.raises(DataRecoveryError) as error:
        verify_upgrade_data(before, install)
    assert error.value.code == "upgrade_dataset_unhealthy"
    (install / "data/visual-director.db").unlink()
    with pytest.raises(DataRecoveryError):
        verify_upgrade_data(before, install)


def test_snapshot_cannot_be_used_for_another_install(tmp_path: Path) -> None:
    before = capture_upgrade_data(tmp_path / "first")
    with pytest.raises(DataRecoveryError) as error:
        verify_upgrade_data(before, tmp_path / "other")
    assert error.value.code == "upgrade_snapshot_invalid"


def test_helper_uses_only_stdlib_and_emits_structured_failure(tmp_path: Path) -> None:
    source = tmp_path / "old-data"
    make_dataset(source, ["old"])
    result = subprocess.run([sys.executable, "-S", str(REPO / "scripts/check-upgrade-data.py"),
                             "capture", "--install-root", str(tmp_path / "installed"),
                             "--snapshot", str(tmp_path / "snapshot.json"), "--candidate", str(source),
                             "--api-base", "http://127.0.0.1:1/api/v1"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "upgrade_data_migration_required"
    assert not (tmp_path / "snapshot.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows bootstrap behavior")
def test_bootstrap_blocks_before_stop_or_install(tmp_path: Path) -> None:
    source = tmp_path / "package"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    for name in ("bootstrap.ps1", "check-upgrade-data.py"):
        shutil.copy2(REPO / "scripts" / name, scripts / name)
    package = source / "apps/api/src/visual_director"
    package.mkdir(parents=True)
    for name in ("__init__.py", "data_recovery.py", "upgrade_data.py"):
        shutil.copy2(REPO / "apps/api/src/visual_director" / name, package / name)
    (scripts / "install.ps1").write_text("throw 'Installer must not run'", encoding="utf-8")
    make_dataset(source / "apps/api/data", ["old"])
    env = {**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                             str(scripts / "bootstrap.ps1"), "-InstallRoot", str(tmp_path / "installed"),
                             "-ApiBase", "http://127.0.0.1:1/api/v1"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "upgrade_data_migration_required"
    assert "Stopping the currently installed" not in result.stderr
    assert "Installing the repository" not in result.stderr
    assert not (tmp_path / "installed").exists()
