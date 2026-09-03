"""First-use orchestration contracts; no network, real services or user installs."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from visual_director.onboarding import read_workbench_onboarding


REPOSITORY = Path(__file__).resolve().parents[3]
SKILL = REPOSITORY / "skills" / "wechat-visual-director"
WINDOWS = os.name == "nt"
SUPPORTED = WINDOWS or sys.platform == "darwin"


class WorkbenchFixture:
    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch):
        self.root = root
        self.install = root / "installed workbench"
        self.host = root / "isolated host"
        self.launcher = self.install / ("visual-director.ps1" if WINDOWS else "visual-director")
        self.suffix = "ps1" if WINDOWS else "sh"
        self.helper = SKILL / "scripts" / f"ensure-workbench.{self.suffix}"
        monkeypatch.setenv("WVD_FIXTURE_ROOT", str(root))
        monkeypatch.setenv("WVD_FIXTURE_PYTHON", sys.executable)
        guide = read_workbench_onboarding(root / "onboarding.json")["guide"]
        self.doctor = {
            "ok": True,
            "installation": {"persistent": True, "version_match": True, "runtime_match": True, "version": "test"},
            "capabilities": {"host_skill_registered": True, "image_generation": False, "wechat_draft": False},
            "setup": {"settings_url": "http://127.0.0.1:8000/settings", "next_action": "create_article",
                      "onboarding_pending": True, "first_run_guide": guide},
        }
        self.write_json("doctor.json", self.doctor)
        self.write_json("serve.json", {"ok": True, "web_base": "http://127.0.0.1:8000"})
        self.write_json("install.json", {
            **self.doctor,
            "runtime_mode": "bundled_python", "bundled_runtime": True,
            "workbench_url": "http://127.0.0.1:8000", "first_install": True,
            "onboarding_pending": True, "first_run_guide": guide,
        })
        if WINDOWS:
            self._windows_fixtures()
        else:
            self._macos_fixtures(monkeypatch)

    def write_json(self, name: str, payload: dict) -> None:
        (self.root / name).write_text(json.dumps(payload), encoding="utf-8")

    def _windows_fixtures(self) -> None:
        (self.root / "launcher.ps1").write_text('''
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Content -LiteralPath (Join-Path $env:WVD_FIXTURE_ROOT 'calls.log') -Value $args[0]
Get-Content -Raw -LiteralPath (Join-Path $env:WVD_FIXTURE_ROOT ($args[0] + '.json'))
exit 0
''', encoding="utf-8")
        (self.root / "installer.ps1").write_text('''
param([string]$InstallRoot, [string]$HostHome)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $env:WVD_FIXTURE_ROOT 'launcher.ps1') -Destination (Join-Path $InstallRoot 'visual-director.ps1')
@{install_root=$InstallRoot; host_home=$HostHome} | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $env:WVD_FIXTURE_ROOT 'install-args.json')
Get-Content -Raw -LiteralPath (Join-Path $env:WVD_FIXTURE_ROOT 'install.json')
exit 0
''', encoding="utf-8")
        helper_literal = str(self.helper).replace("'", "''")
        (self.root / "run.ps1").write_text(f'''
function Invoke-WebRequest {{
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile, [int]$TimeoutSec)
    Add-Content -LiteralPath (Join-Path $env:WVD_FIXTURE_ROOT 'downloads.log') -Value $Uri
    if ($env:WVD_FIXTURE_DOWNLOAD_FAIL -eq '1') {{ throw 'Simulated offline download' }}
    Copy-Item -LiteralPath (Join-Path $env:WVD_FIXTURE_ROOT 'installer.ps1') -Destination $OutFile
}}
& '{helper_literal}' @args
exit $LASTEXITCODE
''', encoding="utf-8-sig")

    def _macos_fixtures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        (self.root / "launcher.sh").write_text('''#!/usr/bin/env bash
set -eu
printf '%s\\n' "$1" >> "$WVD_FIXTURE_ROOT/calls.log"
cat "$WVD_FIXTURE_ROOT/$1.json"
''', encoding="utf-8")
        (self.root / "installer.sh").write_text('''#!/usr/bin/env bash
set -eu
install_root=''; host_home=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) install_root="$2"; shift 2 ;;
    --host-home) host_home="$2"; shift 2 ;;
    *) exit 2 ;;
  esac
done
mkdir -p "$install_root/versions/test/runtime/python/bin"
cp "$WVD_FIXTURE_ROOT/launcher.sh" "$install_root/visual-director"
chmod +x "$install_root/visual-director"
ln -sf "$WVD_FIXTURE_PYTHON" "$install_root/versions/test/runtime/python/bin/python3"
printf '%s\\n' "$install_root/versions/test" > "$install_root/current-root"
"$WVD_FIXTURE_PYTHON" -c 'import json, sys; print(json.dumps(dict(install_root=sys.argv[1], host_home=sys.argv[2])))' "$install_root" "$host_home" > "$WVD_FIXTURE_ROOT/install-args.json"
cat "$WVD_FIXTURE_ROOT/install.json"
''', encoding="utf-8")
        bin_root = self.root / "bin"
        bin_root.mkdir()
        curl = bin_root / "curl"
        curl.write_text('''#!/usr/bin/env bash
set -eu
printf 'download\\n' >> "$WVD_FIXTURE_ROOT/downloads.log"
if [[ "${WVD_FIXTURE_DOWNLOAD_FAIL:-0}" == '1' ]]; then exit 22; fi
while [[ $# -gt 0 ]]; do
  if [[ "$1" == '-o' ]]; then cp "$WVD_FIXTURE_ROOT/installer.sh" "$2"; exit 0; fi
  shift
done
exit 2
''', encoding="utf-8")
        curl.chmod(0o755)
        monkeypatch.setenv("PATH", str(bin_root) + os.pathsep + os.environ["PATH"])

    def existing(self) -> None:
        self.install.mkdir()
        shutil.copyfile(self.root / f"launcher.{self.suffix}", self.launcher)
        if not WINDOWS:
            self.launcher.chmod(0o755)
            version_root = self.install / "versions" / "test"
            runtime = version_root / "runtime" / "python" / "bin"
            runtime.mkdir(parents=True)
            (runtime / "python3").symlink_to(sys.executable)
            (self.install / "current-root").write_text(str(version_root) + "\n", encoding="utf-8")

    def run(self, *, upgrade: bool = False) -> tuple[subprocess.CompletedProcess[str], dict]:
        if WINDOWS:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.root / "run.ps1"),
                   "-InstallRoot", str(self.install), "-HostHome", str(self.host), "-NoOpen"]
            if upgrade:
                cmd.append("-Upgrade")
        else:
            cmd = ["bash", str(self.helper), "--install-root", str(self.install), "--host-home", str(self.host), "--no-open"]
            if upgrade:
                cmd.append("--upgrade")
        process = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=45, check=False)
        assert process.stdout.strip(), process.stderr
        return process, json.loads(process.stdout)


@pytest.fixture
def workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WorkbenchFixture:
    if not SUPPORTED:
        pytest.skip("Windows/macOS first-use helper")
    return WorkbenchFixture(tmp_path, monkeypatch)


def test_first_use_installs_then_reuses_without_consuming_onboarding(workbench: WorkbenchFixture) -> None:
    process, result = workbench.run()
    assert process.returncode == 0, process.stderr
    assert result["ok"] is True and result["workbench_ready"] is True
    assert result["first_install"] is True and result["first_run_guide"]["lines"]
    assert result["browser_opened"] is False
    assert result["launcher"] == str(workbench.launcher)
    args = json.loads((workbench.root / "install-args.json").read_text(encoding="utf-8-sig"))
    assert args == {"install_root": str(workbench.install), "host_home": str(workbench.host)}
    second, payload = workbench.run()
    assert second.returncode == 0, second.stderr
    assert payload["first_install"] is False
    assert payload["onboarding_pending"] is True
    assert payload["first_run_guide"] == result["first_run_guide"]
    assert payload["command_completed"] is True and payload["workbench_ready"] is True
    assert len((workbench.root / "downloads.log").read_text().splitlines()) == 1
    assert (workbench.root / "calls.log").read_text().splitlines() == ["serve", "doctor"]


def test_acknowledged_guide_is_not_repeated_by_existing_helper(workbench: WorkbenchFixture) -> None:
    workbench.existing()
    workbench.doctor["setup"].update(onboarding_pending=False, first_run_guide=None)
    workbench.write_json("doctor.json", workbench.doctor)
    process, result = workbench.run()
    assert process.returncode == 0, process.stderr
    assert result["onboarding_pending"] is False
    assert result["first_run_guide"] is None
    assert not (workbench.root / "downloads.log").exists()


def test_helper_remains_compatible_with_old_core_without_onboarding(workbench: WorkbenchFixture) -> None:
    workbench.existing()
    workbench.doctor["setup"].pop("onboarding_pending")
    workbench.doctor["setup"].pop("first_run_guide")
    workbench.write_json("doctor.json", workbench.doctor)
    process, result = workbench.run()
    assert process.returncode == 0, process.stderr
    assert result["workbench_ready"] is True and result["first_run_guide"] is None


def test_existing_install_starts_without_network_or_optional_keys(workbench: WorkbenchFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    workbench.existing()
    monkeypatch.setenv("WVD_FIXTURE_DOWNLOAD_FAIL", "1")
    process, result = workbench.run()
    assert process.returncode == 0, process.stderr
    assert result["workbench_ready"] is True
    assert result["capabilities"]["image_generation"] is False
    assert not (workbench.root / "downloads.log").exists()


@pytest.mark.parametrize("key", ["runtime_match", "version_match", "persistent", "host_skill_registered"])
def test_identity_failure_never_reports_ready(workbench: WorkbenchFixture, key: str) -> None:
    workbench.existing()
    section = "capabilities" if key == "host_skill_registered" else "installation"
    workbench.doctor[section][key] = False
    workbench.write_json("doctor.json", workbench.doctor)
    process, result = workbench.run()
    assert process.returncode == 2
    assert result["ok"] is False and result["workbench_ready"] is False
    assert result["next_action"] == "retry_workbench_setup"
    assert not (workbench.root / "downloads.log").exists()


def test_explicit_upgrade_downloads_even_when_launcher_exists(workbench: WorkbenchFixture) -> None:
    workbench.existing()
    process, result = workbench.run(upgrade=True)
    assert process.returncode == 0, process.stderr
    assert result["workbench_ready"] is True
    assert (workbench.root / "downloads.log").exists()


@pytest.mark.parametrize("field", ["ok", "bundled_runtime"])
def test_incomplete_release_install_never_reports_ready(workbench: WorkbenchFixture, field: str) -> None:
    result = json.loads((workbench.root / "install.json").read_text())
    result[field] = False
    workbench.write_json("install.json", result)
    process, payload = workbench.run()
    assert process.returncode == 2
    assert payload["ok"] is False and payload["workbench_ready"] is False


@pytest.mark.parametrize("failure", ["download", "invalid_json", "remote_url"])
def test_setup_failure_has_honest_retry_receipt(workbench: WorkbenchFixture, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    if failure == "download":
        monkeypatch.setenv("WVD_FIXTURE_DOWNLOAD_FAIL", "1")
    else:
        workbench.existing()
        if failure == "invalid_json":
            (workbench.root / "doctor.json").write_text("not json", encoding="utf-8")
        else:
            workbench.write_json("serve.json", {"ok": True, "web_base": "https://example.com"})
    process, result = workbench.run()
    assert process.returncode == 2
    assert result["ok"] is False and result["workbench_ready"] is False
    assert result["next_action"] == "retry_workbench_setup"


def test_onboarding_is_on_the_first_screen_and_helpers_ship_with_skill() -> None:
    opening = "\n".join((SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()[:12])
    assert "打开公众号工作台" in opening
    assert "第一次使用" in opening
    assert "支持生图" in opening
    assert not (REPOSITORY / "SKILL.md").exists()
    for suffix in ("ps1", "sh"):
        assert (SKILL / "scripts" / f"ensure-workbench.{suffix}").is_file()
