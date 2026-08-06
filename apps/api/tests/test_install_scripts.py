from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
UNINSTALLER = REPOSITORY_ROOT / "scripts" / "uninstall.ps1"


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


@pytest.mark.skipif(os.name != "nt", reason="Windows installer contract")
def test_uninstall_preserves_data_and_removes_host_registration(tmp_path: Path) -> None:
    install_root = tmp_path / "installed"
    host_home = tmp_path / "host"
    registration = host_home / ".agents" / "skills" / "wechat-visual-director"
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
    assert not (install_root / "versions").exists()
    assert not registration.exists()
    assert REPOSITORY_ROOT.joinpath("SKILL.md").is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows installer contract")
def test_installed_uninstaller_detects_adjacent_root_and_purges(tmp_path: Path) -> None:
    install_root = tmp_path / "custom-install"
    host_home = tmp_path / "host"
    _manifest(install_root)
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
    assert REPOSITORY_ROOT.joinpath("SKILL.md").is_file()
