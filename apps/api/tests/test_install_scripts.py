from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from test_data_recovery import make_dataset
from visual_director.upgrade_data import dataset_snapshot


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
INSTALLER = REPOSITORY_ROOT / "scripts" / "install.ps1"
UNINSTALLER = REPOSITORY_ROOT / "scripts" / "uninstall.ps1"
SKILL_SOURCE = REPOSITORY_ROOT / "skills" / "wechat-visual-director"


def _manifest(install_root: Path) -> None:
    version_root = install_root / "versions" / "0.1.0-test"
    version_root.mkdir(parents=True)
    (install_root / "data").mkdir()
    (install_root / "config").mkdir()
    (install_root / "runtime").mkdir()
    (install_root / "data" / "task.txt").write_text("keep", encoding="utf-8")
    (install_root / "config" / "private.txt").write_text("keep", encoding="utf-8")
    (install_root / "install.json").write_text(
        json.dumps(
            {
                "install_root": str(install_root),
                "current_root": str(version_root),
                "current_version": "0.1.0-test",
                "data_root": str(install_root / "data"),
                "installed_at": "2026-08-06T00:00:00Z",
            }
        ),
        encoding="utf-8-sig",
    )


def _run_uninstaller(script: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def _run_installer(*args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER),
            "-Isolated",
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    return completed, json.loads(completed.stdout)


@pytest.mark.skipif(os.name != "nt", reason="Windows installer contract")
@pytest.mark.parametrize("migrate_legacy", [False, True])
def test_independent_source_install_requires_explicit_data_and_config_import(tmp_path, monkeypatch, migrate_legacy):
    source = tmp_path / "source"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    for name in ("install.ps1", "persistent-launcher.ps1", "persistent-launcher.cmd", "uninstall.ps1"):
        shutil.copy2(REPOSITORY_ROOT / "scripts" / name, scripts / name)
    (source / "VERSION").write_text("0.1.0-isolation-test", encoding="utf-8")
    (source / ".env.example").write_text("INSTALL_TEST_MARKER=default\n", encoding="utf-8")
    (source / ".env.local").write_text("INSTALL_TEST_MARKER=source-only\n", encoding="utf-8")
    workbench = source / "apps/web/dist"
    workbench.mkdir(parents=True)
    (workbench / "index.html").write_text("<html>public test workbench</html>", encoding="utf-8")
    shutil.copytree(SKILL_SOURCE, source / "skills/wechat-visual-director")
    source_data = source / "apps/api/data"
    make_dataset(source_data, ["source-task"])
    original = dataset_snapshot(source_data)
    monkeypatch.setattr(f"{__name__}.INSTALLER", scripts / "install.ps1")
    install = tmp_path / "installed"
    args = ["-InstallRoot", str(install), "-HostHome", str(tmp_path / "host"), "-SkipDependencies"]
    if migrate_legacy:
        args.append("-MigrateLegacyData")
    completed, result = _run_installer(*args)
    assert completed.returncode == 0, completed.stderr
    assert result["ok"] is True
    assert result["migrated"]["database"] is migrate_legacy
    assert result["migrated"]["config"] is migrate_legacy
    config = install / "config/.env.local"
    assert config.read_text(encoding="utf-8") == ("INSTALL_TEST_MARKER=source-only\n" if migrate_legacy else "INSTALL_TEST_MARKER=default\n")
    assert (install / "data/visual-director.db").exists() is migrate_legacy
    assert dataset_snapshot(source_data) == original
    # A later reinstall must preserve the installation's own configuration.
    config.write_text("INSTALL_TEST_MARKER=installed-user-choice\n", encoding="utf-8")
    completed, second = _run_installer(*args)
    assert completed.returncode == 0, completed.stderr
    assert second["migrated"]["config"] is False
    assert config.read_text(encoding="utf-8") == "INSTALL_TEST_MARKER=installed-user-choice\n"
    assert dataset_snapshot(source_data) == original


@pytest.mark.skipif(os.name != "nt", reason="Windows installer contract")
def test_fresh_install_does_not_import_source_data_and_reinstall_is_clean(
    tmp_path: Path,
) -> None:
    install_root = tmp_path / "installed"
    host_home = tmp_path / "host"
    stale_codex_skill = host_home / ".codex" / "skills" / "wechat-visual-director"
    (stale_codex_skill / "apps").mkdir(parents=True)
    (stale_codex_skill / "apps" / "old-source.py").write_text("stale", encoding="utf-8")

    first_completed, first = _run_installer(
        "-InstallRoot",
        str(install_root),
        "-HostHome",
        str(host_home),
        "-SkipDependencies",
    )
    assert first_completed.returncode == 0, first_completed.stderr
    assert first["ok"] is True
    manifest = json.loads((install_root / "install.json").read_text(encoding="utf-8-sig"))
    assert manifest["physical_install_root"] == str(install_root.resolve())
    assert first["install_location"]["actual_root"] == str(install_root.resolve())
    assert first["legacy_data_migration_requested"] is False
    assert first["migrated"]["database"] is False
    assert first["host_registration"]["codex_skill_root"] == str(stale_codex_skill)
    assert not (install_root / "data" / "visual-director.db").exists()
    version_root = Path(first["app_root"])
    assert not (version_root / ".runtime").exists()

    stale_marker = version_root / ".runtime" / "stale-marker.txt"
    stale_marker.parent.mkdir()
    stale_marker.write_text("stale", encoding="utf-8")
    second_completed, second = _run_installer(
        "-InstallRoot",
        str(install_root),
        "-HostHome",
        str(host_home),
        "-SkipDependencies",
    )
    assert second_completed.returncode == 0, second_completed.stderr
    assert second["ok"] is True
    assert not stale_marker.exists()
    assert not (version_root / ".runtime").exists()

    expected_files = {
        path.relative_to(SKILL_SOURCE)
        for path in SKILL_SOURCE.rglob("*")
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'
    }
    assert expected_files
    for registration in (
        host_home / ".codex" / "skills" / "wechat-visual-director",
        host_home / ".agents" / "skills" / "wechat-visual-director",
        host_home / ".config" / "opencode" / "skills" / "wechat-visual-director",
    ):
        actual_files = {
            path.relative_to(registration)
            for path in registration.rglob("*")
            if path.is_file()
        }
        assert actual_files == expected_files
        assert not (registration / "apps").exists()
        assert not (registration / "docs").exists()
        assert not (registration / ".github").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows installer contract")
def test_uninstall_preserves_data_and_removes_host_registration(tmp_path: Path) -> None:
    install_root = tmp_path / "installed"
    host_home = tmp_path / "host"
    registrations = (
        host_home / ".codex" / "skills" / "wechat-visual-director",
        host_home / ".agents" / "skills" / "wechat-visual-director",
        host_home / ".config" / "opencode" / "skills" / "wechat-visual-director",
    )
    for registration in registrations:
        registration.mkdir(parents=True)
    _manifest(install_root)

    completed, payload = _run_uninstaller(
        UNINSTALLER,
        "-InstallRoot",
        str(install_root),
        "-HostHome",
        str(host_home),
    )

    assert completed.returncode == 0
    assert payload["ok"] is True
    assert payload["mode"] == "preserve_data"
    assert (install_root / "data" / "task.txt").is_file()
    assert (install_root / "config" / "private.txt").is_file()
    history = json.loads((install_root / "config" / "install-history.json").read_text(encoding="utf-8-sig"))
    assert history["last_version"] == "0.1.0-test"
    assert history["data_root"] == str(install_root / "data")
    assert not (install_root / "versions").exists()
    assert all(not registration.exists() for registration in registrations)
    assert SKILL_SOURCE.joinpath("SKILL.md").is_file()


def test_macos_scripts_are_present_and_do_not_depend_on_powershell() -> None:
    for name in (
        "install.sh",
        "install-release.sh",
        "uninstall.sh",
        "bootstrap.sh",
        "build-macos-package.sh",
        "test-macos-package.sh",
        "persistent-launcher.sh",
        "visual-director.sh",
    ):
        content = (REPOSITORY_ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert content.startswith("#!/usr/bin/env bash")
        assert "powershell" not in content.lower()


def test_user_installers_never_invoke_node_package_managers() -> None:
    for name in ("install.ps1", "install.sh", "install-release.sh"):
        content = (REPOSITORY_ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "corepack pnpm@" not in content
        assert "npm install" not in content


def test_macos_release_installer_is_agent_managed_and_self_contained() -> None:
    installer = (REPOSITORY_ROOT / "scripts" / "install-release.sh").read_text(encoding="utf-8")
    assert "uname -m" in installer
    assert "shasum -a 256" in installer
    assert "runtime/python/bin/python3" in installer
    assert "git clone" not in installer
    assert "brew install" not in installer

    persistent_installer = (REPOSITORY_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert "rsync " not in persistent_installer

    launcher = (REPOSITORY_ROOT / "scripts" / "persistent-launcher.sh").read_text(encoding="utf-8")
    assert "current-root" in launcher
    assert 'runtime/python/bin/python3' in launcher

    windows_installer = (REPOSITORY_ROOT / "scripts" / "install-release.ps1").read_text(encoding="utf-8")
    assert '[string]$Version = ""' in windows_installer
    assert "raw.githubusercontent.com/$Repository/main/VERSION" in windows_installer


def test_release_workflow_builds_both_macos_architectures() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "runner: macos-15" in workflow
    assert "runner: macos-15-intel" in workflow
    assert "architecture: arm64" in workflow
    assert "architecture: x64" in workflow
    assert "test-macos-package.sh" in workflow

    builder = (REPOSITORY_ROOT / "scripts" / "build-macos-package.sh").read_text(encoding="utf-8")
    assert "--break-system-packages" in builder


@pytest.mark.skipif(os.name != "nt", reason="Windows installer contract")
def test_installed_uninstaller_detects_adjacent_root_and_purges(tmp_path: Path) -> None:
    install_root = tmp_path / "custom-install"
    host_home = tmp_path / "host"
    _manifest(install_root)
    backup_root = install_root / "backups"
    backup_root.mkdir()
    (backup_root / "old-task.zip").write_text("delete", encoding="utf-8")
    installed_uninstaller = install_root / "uninstall.ps1"
    shutil.copy2(UNINSTALLER, installed_uninstaller)

    completed, payload = _run_uninstaller(
        installed_uninstaller,
        "-HostHome",
        str(host_home),
        "-Purge",
    )

    assert completed.returncode == 0
    assert payload["ok"] is True
    assert payload["mode"] == "purge"
    assert Path(payload["install_root"]) == install_root
    assert not install_root.exists()
    assert SKILL_SOURCE.joinpath("SKILL.md").is_file()


def test_lightweight_skill_is_not_the_repository_root() -> None:
    assert not REPOSITORY_ROOT.joinpath("SKILL.md").exists()
    assert SKILL_SOURCE.joinpath("SKILL.md").is_file()
    assert SKILL_SOURCE.joinpath("agents", "openai.yaml").is_file()
    assert SKILL_SOURCE.joinpath("references", "install.md").is_file()
    assert not SKILL_SOURCE.joinpath("apps").exists()
    assert not SKILL_SOURCE.joinpath("docs").exists()
    assert not SKILL_SOURCE.joinpath(".github").exists()
    total_bytes = sum(path.stat().st_size for path in SKILL_SOURCE.rglob("*") if path.is_file())
    assert total_bytes < 250_000
