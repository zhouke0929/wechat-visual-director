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


def test_empty_target_with_independent_source_allows_install_without_import(tmp_path: Path) -> None:
    source = tmp_path / "source"
    install = tmp_path / "installed"
    make_dataset(source, ["old"])
    make_dataset(install / "data", [])
    before = dataset_snapshot(source)
    baseline = capture_upgrade_data(install, candidates=(source, source, install / "data"))
    assert baseline["before"]["task_count"] == 0
    assert len(baseline["migration_candidates"]) == 1
    assert baseline["migration_candidates"][0]["root"] == str(source.resolve())
    assert baseline["warnings"] == ["optional_data_migration_available"]
    report = verify_upgrade_data(baseline, install)
    assert report["preserved"] is True and report["after_task_count"] == 0
    assert report["migration_candidates"] == baseline["migration_candidates"]
    assert dataset_snapshot(source) == before
    assert dataset_snapshot(install / "data")["task_count"] == 0


@pytest.mark.parametrize("source_tasks", [[], ["old"]])
def test_foreign_runtime_is_a_service_conflict_not_required_migration(tmp_path: Path, source_tasks) -> None:
    source = tmp_path / "source"
    install = tmp_path / "installed"
    make_dataset(source, source_tasks)
    make_dataset(install / "data", ["other"])
    with pytest.raises(DataRecoveryError) as error:
        capture_upgrade_data(install, running={"root": str(source), "task_count": len(source_tasks)})
    assert error.value.code == "upgrade_runtime_conflict"
    assert error.value.details["action"] == "resolve_runtime_conflict"
    assert dataset_snapshot(install / "data")["task_ids"] == ["other"]


@pytest.mark.parametrize("with_manifest", [False, True])
def test_upgrade_or_reinstall_preserves_own_data_despite_independent_source(tmp_path, with_manifest):
    install = tmp_path / "installed"
    source = tmp_path / "developer-data"
    make_dataset(install / "data", ["own-task"])
    make_dataset(source, ["developer-task"])
    if with_manifest:
        (install / "install.json").write_text(json.dumps({"data_root": str(install / "data")}), encoding="utf-8")
    original = dataset_snapshot(install / "data")
    source_original = dataset_snapshot(source)
    baseline = backup_upgrade_data(capture_upgrade_data(install, running={"root": str(install / "data"), "task_count": 1}, candidates=(source,)))
    assert dataset_snapshot(Path(baseline["backup_root"]))["task_ids"] == ["own-task"]
    assert verify_upgrade_data(baseline, install)["preserved"] is True
    assert dataset_snapshot(install / "data") == original
    assert dataset_snapshot(source) == source_original


def test_unhealthy_optional_source_does_not_block_or_modify_fresh_install(tmp_path):
    source = tmp_path / "developer-data"
    source.mkdir()
    database = source / "visual-director.db"
    database.write_bytes(b"unrelated broken development database")
    baseline = capture_upgrade_data(tmp_path / "installed", candidates=(source,))
    assert baseline["migration_candidates"] == []
    assert database.read_bytes() == b"unrelated broken development database"


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
    install = tmp_path / "installed"
    install.mkdir()
    (install / "install.json").write_text(json.dumps({"data_root": str(source)}), encoding="utf-8")
    result = subprocess.run([sys.executable, "-S", str(REPO / "scripts/check-upgrade-data.py"),
                             "capture", "--install-root", str(install),
                             "--snapshot", str(tmp_path / "snapshot.json"), "--candidate", str(source),
                             "--api-base", "http://127.0.0.1:1/api/v1"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "upgrade_data_root_changed"
    assert not (tmp_path / "snapshot.json").exists()


@pytest.mark.parametrize("explicit_candidate", [False, True])
def test_helper_in_developer_working_directory_can_start_independently(tmp_path, explicit_candidate):
    source = tmp_path / "developer/apps/api/data"
    make_dataset(source, ["developer-task"])
    original = dataset_snapshot(source)
    install = tmp_path / "installed"
    snapshot = tmp_path / "snapshot.json"
    args = [sys.executable, "-S", str(REPO / "scripts/check-upgrade-data.py"), "capture",
            "--install-root", str(install), "--snapshot", str(snapshot), "--api-base", "http://127.0.0.1:1/api/v1"]
    if explicit_candidate:
        args.extend(["--candidate", str(source)])
    result = subprocess.run(args, cwd=source.parents[2], capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True and payload["data_continuity"]["captured"] is True
    assert len(payload["data_continuity"]["migration_candidates"]) == int(explicit_candidate)
    assert json.loads(snapshot.read_text(encoding="utf-8"))["before"]["task_count"] == 0
    assert dataset_snapshot(source) == original
    assert not (install / "data").exists()


def _bootstrap_fixture(tmp_path):
    source = tmp_path / "package"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    for name in ("bootstrap.ps1", "check-upgrade-data.py"):
        shutil.copy2(REPO / "scripts" / name, scripts / name)
    package = source / "apps/api/src/visual_director"
    package.mkdir(parents=True)
    for name in ("__init__.py", "data_recovery.py", "upgrade_data.py"):
        shutil.copy2(REPO / "apps/api/src/visual_director" / name, package / name)
    return source, scripts


@pytest.mark.skipif(os.name != "nt", reason="Windows bootstrap behavior")
def test_bootstrap_blocks_recorded_root_change_before_stop_or_install(tmp_path: Path) -> None:
    source, scripts = _bootstrap_fixture(tmp_path)
    (scripts / "install.ps1").write_text("throw 'Installer must not run'", encoding="utf-8")
    make_dataset(source / "apps/api/data", ["old"])
    install = tmp_path / "installed"
    install.mkdir()
    (install / "install.json").write_text(json.dumps({"data_root": str(source / "apps/api/data")}), encoding="utf-8")
    env = {**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                             str(scripts / "bootstrap.ps1"), "-InstallRoot", str(tmp_path / "installed"),
                             "-ApiBase", "http://127.0.0.1:1/api/v1"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "upgrade_data_root_changed"
    assert "Stopping the currently installed" not in result.stderr
    assert "Installing the repository" not in result.stderr
    assert not (install / "runtime").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows bootstrap behavior")
def test_bootstrap_reaches_installer_without_importing_independent_source(tmp_path):
    source, scripts = _bootstrap_fixture(tmp_path)
    (scripts / "install.ps1").write_text("Write-Output '{\"ok\":false,\"error\":{\"code\":\"test_boundary\"}}'; exit 2", encoding="utf-8")
    data = source / "apps/api/data"
    make_dataset(data, ["developer-task"])
    original = dataset_snapshot(data)
    env = {**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                             str(scripts / "bootstrap.ps1"), "-InstallRoot", str(tmp_path / "installed"),
                             "-ApiBase", "http://127.0.0.1:1/api/v1"],
                            cwd=source, env=env, capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert json.loads(result.stdout)["error"]["code"] == "install_failed"
    assert "Installing the repository" in result.stderr
    assert "Stopping the currently installed" not in result.stderr
    assert dataset_snapshot(data) == original
    assert not (tmp_path / "installed/data").exists()
