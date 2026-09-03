#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$HOME/Library/Application Support/wechat-visual-director"
HOST_HOME=""
UPGRADE=0
NO_OPEN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --host-home) HOST_HOME="$2"; shift 2 ;;
    --upgrade) UPGRADE=1; shift ;;
    --no-open) NO_OPEN=1; shift ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

failure() {
  printf '{"ok":false,"schema_version":"workbench_ready.v0.1","workbench_ready":false,"next_action":"retry_workbench_setup","error":{"code":"%s","message":"Workbench setup did not complete; report this step and retry when resolved."}}\n' "$1"
  exit 2
}
[[ "$(uname -s)" == "Darwin" ]] || failure "macos_required"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/wechat-workbench.XXXXXX")"
trap 'rm -rf "$TEMP_ROOT"' EXIT
LAUNCHER="$INSTALL_ROOT/visual-director"
MODE=existing
if [[ -n "$HOST_HOME" ]]; then export VISUAL_DIRECTOR_HOST_HOME="$HOST_HOME"; fi

if [[ "$UPGRADE" -eq 1 || ! -x "$LAUNCHER" ]]; then
  MODE=installed
  printf '[wechat-visual-director] Preparing the local workbench for first use or upgrade.\n' >&2
  curl -fsSL --retry 2 --connect-timeout 20 --max-time 60 "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/scripts/install-release.sh" -o "$TEMP_ROOT/install-release.sh" || failure "installer_download_failed"
  INSTALL_ARGS=(--install-root "$INSTALL_ROOT")
  if [[ -n "$HOST_HOME" ]]; then INSTALL_ARGS+=(--host-home "$HOST_HOME"); fi
  bash "$TEMP_ROOT/install-release.sh" "${INSTALL_ARGS[@]}" > "$TEMP_ROOT/install.json" || failure "release_install_failed"
else
  printf '[wechat-visual-director] Starting and checking the existing workbench.\n' >&2
  "$LAUNCHER" serve --json > "$TEMP_ROOT/serve.json" || failure "serve_failed"
  "$LAUNCHER" doctor --json > "$TEMP_ROOT/doctor.json" || failure "doctor_failed"
fi

[[ -x "$LAUNCHER" && -f "$INSTALL_ROOT/current-root" ]] || failure "installed_launcher_missing"
IFS= read -r VERSION_ROOT < "$INSTALL_ROOT/current-root"
RUNTIME_PYTHON="$VERSION_ROOT/runtime/python/bin/python3"
[[ -x "$RUNTIME_PYTHON" ]] || failure "bundled_runtime_missing"

# Parse JSON using the installed private runtime, never requiring system Python.
"$RUNTIME_PYTHON" - "$MODE" "$TEMP_ROOT" "$LAUNCHER" "$NO_OPEN" <<'PY'
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

mode, temporary, launcher, no_open = sys.argv[1:]
root = Path(temporary)

def read_result(name):
    value = json.loads((root / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} did not return a JSON object.")
    return value

try:
    if mode == "installed":
        result = read_result("install.json")
        if result.get("runtime_mode") != "bundled_python" or result.get("bundled_runtime") is not True:
            raise ValueError("The release did not provide its bundled runtime.")
    else:
        serve = read_result("serve.json")
        doctor = read_result("doctor.json")
        if serve.get("ok") is not True or doctor.get("ok") is not True:
            raise ValueError("The workbench did not pass its health check.")
        result = {
            "ok": True,
            "version": doctor.get("installation", {}).get("version"),
            "workbench_url": serve.get("web_base"),
            "settings_url": doctor.get("setup", {}).get("settings_url"),
            "next_action": doctor.get("setup", {}).get("next_action"),
            "installation": doctor.get("installation", {}),
            "capabilities": doctor.get("capabilities", {}),
            "first_install": False,
            "onboarding_pending": bool(doctor.get("setup", {}).get("onboarding_pending")),
            "first_run_guide": doctor.get("setup", {}).get("first_run_guide"),
        }
    installation = result.get("installation", {})
    if result.get("ok") is not True or not all(installation.get(key) is True for key in ("persistent", "version_match", "runtime_match")) or result.get("capabilities", {}).get("host_skill_registered") is not True:
        raise ValueError("Workbench identity or Skill registration could not be verified.")
    url = result["workbench_url"]
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("The workbench did not return a local HTTP URL.")
    opened = False
    if no_open != "1":
        try:
            opened = subprocess.run(["open", url], capture_output=True, timeout=10).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    result.update(schema_version="workbench_ready.v0.1", launcher=launcher, workbench_ready=True, browser_opened=opened, command_completed=True)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
    print(json.dumps({"ok": False, "schema_version": "workbench_ready.v0.1", "workbench_ready": False, "next_action": "retry_workbench_setup", "error": {"code": "workbench_setup_failed", "message": str(exc)}}, separators=(",", ":")))
    raise SystemExit(2)
PY
