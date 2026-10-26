"""Real Windows handle/path checks in isolated folders; no user installs/network."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
HELPER = REPO / "skills/wechat-visual-director/scripts/windows-install-paths.ps1"
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows physical path/installer contracts")


def run_ps(tmp_path, body, *, local=None):
    script = tmp_path / "check.ps1"
    script.write_text(
        "$ErrorActionPreference='Stop'\n[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)\n"
        + f". '{str(HELPER).replace(chr(39), chr(39)*2)}'\n" + body,
        encoding="utf-8-sig",
    )
    env = {**os.environ, "LOCALAPPDATA": str(local or tmp_path / "local")}
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30, env=env)
    assert result.stdout.strip(), result.stderr
    return result, json.loads(result.stdout)


def lit(path):
    return "'" + str(path).replace("'", "''") + "'"


def mark(root):
    root.mkdir(parents=True)
    (root / "install.json").write_text('{"current_version":"test"}', encoding="utf-8")


@pytest.mark.parametrize("kind", ["normal", "cache", "retained"])
def test_only_existing_install_is_reused_across_host_paths(tmp_path, kind):
    local = tmp_path / "local"
    normal = local / "wechat-visual-director"
    cache = local / "Packages/OpenAI.Codex_test/LocalCache/Local/wechat-visual-director"
    selected = normal if kind == "normal" else cache
    if kind == "retained":
        (selected / "data").mkdir(parents=True)
        (selected / "data/visual-director.db").write_bytes(b"retained; do not open or alter")
    else:
        mark(selected)
    process, result = run_ps(tmp_path, "Resolve-WvdInstallLocation | ConvertTo-Json -Depth 5", local=local)
    assert process.returncode == 0, process.stderr
    assert Path(result["actual_root"]) == selected.resolve()
    assert result["existing_install"] is True
    if kind != "normal":
        assert not normal.exists()


def test_two_distinct_installs_block_without_selecting_newest_or_modifying(tmp_path):
    local = tmp_path / "local"
    roots = [local / "wechat-visual-director",
             local / "Packages/OpenAI.Codex_test/LocalCache/Local/wechat-visual-director"]
    for root in roots:
        mark(root)
    before = [(root / "install.json").read_bytes() for root in roots]
    process, result = run_ps(tmp_path, "try { Resolve-WvdInstallLocation } catch { Get-WvdPathFailure $_.Exception | ConvertTo-Json -Depth 5; exit 2 }", local=local)
    assert process.returncode == 2
    assert result["code"] == "install_location_ambiguous"
    assert set(result["details"]["candidates"]) == {str(p.resolve()) for p in roots}
    assert [(root / "install.json").read_bytes() for root in roots] == before


def test_explicit_selection_does_not_scan_or_modify_other_installs(tmp_path):
    local = tmp_path / "local"
    chosen = tmp_path / "chosen"
    mark(chosen)
    mark(local / "wechat-visual-director")
    mark(local / "Packages/OpenAI.Codex_test/LocalCache/Local/wechat-visual-director")
    process, result = run_ps(tmp_path, f"Resolve-WvdInstallLocation {lit(chosen)} | ConvertTo-Json -Depth 5", local=local)
    assert process.returncode == 0, process.stderr
    assert result["actual_root"] == str(chosen.resolve())
    assert result["explicit_selection"] is True


def test_fresh_resolution_does_not_create_an_empty_install(tmp_path):
    (tmp_path / "local").mkdir()
    process, result = run_ps(tmp_path, "Resolve-WvdInstallLocation | ConvertTo-Json -Depth 5")
    assert process.returncode == 0, process.stderr
    assert result["existing_install"] is False
    assert not Path(result["actual_root"]).exists()


def test_selection_checks_physical_pin_before_install_or_upgrade(tmp_path):
    root = tmp_path / "local/wechat-visual-director"
    mark(root)
    (root / "install.json").write_text(json.dumps({"physical_install_root": str(tmp_path / "elsewhere")}), encoding="utf-8")
    process, result = run_ps(tmp_path, "try { Resolve-WvdInstallLocation } catch { Get-WvdPathFailure $_.Exception | ConvertTo-Json -Depth 5; exit 2 }")
    assert process.returncode == 2
    assert result["code"] == "install_location_changed"
    assert not (root / "versions").exists()


def test_directory_aliases_are_one_install_not_a_conflict(tmp_path):
    local = tmp_path / "local"
    normal = local / "wechat-visual-director"
    cache = local / "Packages/OpenAI.Codex_test/LocalCache/Local/wechat-visual-director"
    mark(normal)
    cache.parent.mkdir(parents=True)
    body = (f"New-Item -ItemType Junction -Path {lit(cache)} -Target {lit(normal)} | Out-Null\n"
            "Resolve-WvdInstallLocation | ConvertTo-Json -Depth 5")
    process, result = run_ps(tmp_path, body, local=local)
    assert process.returncode == 0, process.stderr
    assert len(result["candidates"]) == 1
    assert Path(result["actual_root"]).resolve() == normal.resolve()


def launcher_fixture(tmp_path, *, pinned=False):
    actual = tmp_path / "actual"
    recorded = tmp_path / "virtual"
    version = actual / "versions/test"
    scripts = version / "scripts"
    scripts.mkdir(parents=True)
    helper = version / "skills/wechat-visual-director/scripts/windows-install-paths.ps1"
    helper.parent.mkdir(parents=True)
    shutil.copy2(HELPER, helper)
    shutil.copy2(REPO / "scripts/persistent-launcher.ps1", actual / "visual-director.ps1")
    (scripts / "visual-director.ps1").write_text(
        "@{data=$env:VISUAL_DIRECTOR_DATA_ROOT; app=$env:VISUAL_DIRECTOR_PROJECT_ROOT; "
        "config=$env:VISUAL_DIRECTOR_ENV_FILE; runtime=$env:VISUAL_DIRECTOR_HOME} | ConvertTo-Json; exit 0",
        encoding="utf-8",
    )
    manifest = {"install_root": str(recorded), "current_version": "test",
                "current_root": str(recorded / "versions/test"), "data_root": str(recorded / "data"),
                "config_file": str(recorded / "config/.env.local"), "runtime_root": str(recorded / "runtime")}
    if pinned:
        manifest["physical_install_root"] = str(recorded)
    (actual / "install.json").write_text(json.dumps(manifest), encoding="utf-8")
    return actual, recorded


def test_launcher_rebinds_old_virtual_prefix_without_reading_other_data(tmp_path):
    actual, recorded = launcher_fixture(tmp_path)
    (recorded / "data").mkdir(parents=True)
    marker = recorded / "data/do-not-touch.txt"
    marker.write_text("other installation", encoding="utf-8")
    process, result = run_ps(tmp_path, f"& {lit(actual / 'visual-director.ps1')} doctor --json\nexit $LASTEXITCODE")
    assert process.returncode == 0, process.stderr
    assert result == {"data": str(actual / "data"), "app": str(actual / "versions/test"),
                      "config": str(actual / "config/.env.local"), "runtime": str(actual / "runtime")}
    assert marker.read_text() == "other installation"


def test_launcher_refuses_pinned_location_change_before_start(tmp_path):
    actual, _ = launcher_fixture(tmp_path, pinned=True)
    process, result = run_ps(tmp_path, f"& {lit(actual / 'visual-director.ps1')} serve --json\nexit $LASTEXITCODE")
    assert process.returncode == 2
    assert result["error"]["code"] == "install_location_changed"


def test_old_launcher_needs_upgrade_if_its_recorded_root_points_elsewhere(tmp_path):
    actual, recorded = launcher_fixture(tmp_path)
    (actual / "versions/test/skills/wechat-visual-director/scripts/windows-install-paths.ps1").unlink()
    recorded.mkdir()
    process, result = run_ps(tmp_path, f"try {{ Assert-WvdLegacyLauncher {lit(actual)}; throw 'must not start' }} catch {{ Get-WvdPathFailure $_.Exception | ConvertTo-Json -Depth 5; exit 2 }}")
    assert process.returncode == 2
    assert result["code"] == "install_location_upgrade_required"


def test_upgrade_repairs_metadata_before_using_old_launcher_without_moving_data(tmp_path):
    actual, recorded = launcher_fixture(tmp_path)
    (actual / "data").mkdir()
    marker = actual / "data/task.bin"
    marker.write_bytes(b"owned data")
    process, result = run_ps(tmp_path, f"Update-WvdLegacyManifestPaths {lit(actual)}\nGet-Content -LiteralPath {lit(actual / 'install.json')} -Raw")
    assert process.returncode == 0, process.stderr
    assert result["install_root"] == result["physical_install_root"] == str(actual)
    assert result["current_root"] == str(actual / "versions/test")
    assert result["data_root"] == str(actual / "data")
    assert marker.read_bytes() == b"owned data"
    assert not recorded.exists()
