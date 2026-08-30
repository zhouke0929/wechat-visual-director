#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="${HOME}/Library/Application Support/wechat-visual-director"
HOST_HOME="$HOME"
API_BASE="http://127.0.0.1:8000/api/v1"
WEB_BASE="http://127.0.0.1:8000"
SKIP_DEPENDENCIES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --host-home) HOST_HOME="$2"; shift 2 ;;
    --api-base) API_BASE="$2"; shift 2 ;;
    --web-base) WEB_BASE="$2"; shift 2 ;;
    --skip-dependencies) SKIP_DEPENDENCIES=1; shift ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

bootstrap_failure() {
  printf '{"ok":false,"schema_version":"bootstrap_result.v0.1","error":{"code":"%s","message":"%s","retryable":true}}\n' "$1" "$2"
  exit "${3:-2}"
}

progress() {
  printf '[wechat-visual-director] %s\n' "$1" >&2
}

FIRST_INSTALLATION=true
if [[ -x "$INSTALL_ROOT/visual-director" || -f "$INSTALL_ROOT/install.json" || -f "$INSTALL_ROOT/config/install-history.json" ]]; then
  FIRST_INSTALLATION=false
fi

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/wechat-visual-director-bootstrap.XXXXXX")"
trap 'rm -rf "$TEMP_ROOT"' EXIT

if [[ -x "$INSTALL_ROOT/visual-director" ]]; then
  progress "Stopping the currently installed runtime before upgrade."
  set +e
  "$INSTALL_ROOT/visual-director" stop --json > "$TEMP_ROOT/stop.json"
  STOP_EXIT=$?
  set -e
  [[ "$STOP_EXIT" -eq 0 ]] || bootstrap_failure "existing_runtime_stop_failed" "The previous runtime could not be stopped safely." 3
fi

progress "Installing the release into the persistent local application directory."
INSTALL_ARGS=(--install-root "$INSTALL_ROOT" --host-home "$HOST_HOME")
if [[ "$SKIP_DEPENDENCIES" -eq 1 ]]; then
  INSTALL_ARGS+=(--skip-dependencies)
fi
set +e
bash "$ROOT/scripts/install.sh" "${INSTALL_ARGS[@]}" > "$TEMP_ROOT/install.json"
INSTALL_EXIT=$?
set -e
[[ "$INSTALL_EXIT" -eq 0 ]] || bootstrap_failure "install_failed" "The persistent installation did not complete."

CURRENT_ROOT_FILE="$INSTALL_ROOT/current-root"
[[ -f "$CURRENT_ROOT_FILE" ]] || bootstrap_failure "current_root_missing" "The installed runtime pointer is missing."
IFS= read -r CURRENT_ROOT < "$CURRENT_ROOT_FILE"
if [[ -x "$CURRENT_ROOT/runtime/python/bin/python3" ]]; then
  ACTIVE_PYTHON="$CURRENT_ROOT/runtime/python/bin/python3"
else
  ACTIVE_PYTHON="$CURRENT_ROOT/apps/api/.venv/bin/python"
fi
[[ -x "$ACTIVE_PYTHON" ]] || bootstrap_failure "installed_runtime_missing" "The installed Python runtime is missing."

progress "Starting the installed production services."
set +e
"$INSTALL_ROOT/visual-director" serve --api-base "$API_BASE" --web-base "$WEB_BASE" --json > "$TEMP_ROOT/serve.json"
SERVE_EXIT=$?
set -e
[[ "$SERVE_EXIT" -eq 0 ]] || bootstrap_failure "serve_failed" "The installed services did not become ready." 3

progress "Checking the installed runtime contract."
set +e
"$INSTALL_ROOT/visual-director" doctor --api-base "$API_BASE" --web-base "$WEB_BASE" --json > "$TEMP_ROOT/doctor.json"
DOCTOR_EXIT=$?
set -e
[[ "$DOCTOR_EXIT" -eq 0 ]] || bootstrap_failure "doctor_failed" "The installed runtime failed its health check." 3

"$ACTIVE_PYTHON" - "$TEMP_ROOT/install.json" "$TEMP_ROOT/serve.json" "$TEMP_ROOT/doctor.json" "$FIRST_INSTALLATION" <<'PY'
import json, sys
from pathlib import Path

install = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
serve = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
doctor = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
first_install = sys.argv[4].lower() == "true"
next_action = doctor.get("setup", {}).get("next_action") or "create_article"
first_run_guide = None
if first_install:
    first_run_guide = {
        "schema_version": "first_run_guide.v0.1",
        "language": "respond_in_user_language",
        "title": "WeChat Visual Director is ready",
        "lines": [
            "Ask for a WeChat article by topic, or provide Markdown for typesetting.",
            "The Agent returns a local workbench link for theme, image, and cover review.",
            "If the current Agent supports native image generation, confirm the theme first and then ask it to generate and insert images for the current article.",
            "Enter image API and WeChat credentials only in Local Settings; the product creates drafts and never mass publishes automatically.",
        ],
    }
payload = {
    "ok": True,
    "schema_version": "bootstrap_result.v0.1",
    "install_mode": install.get("install_mode"),
    "platform": "macos",
    "version": install.get("version"),
    "launcher": install.get("launcher"),
    "uninstaller": install.get("uninstaller"),
    "api_base": serve.get("api_base"),
    "web_base": serve.get("web_base"),
    "workbench_url": serve.get("web_base"),
    "settings_url": doctor.get("setup", {}).get("settings_url"),
    "next_action": next_action,
    "first_install": first_install,
    "first_run_guide": first_run_guide,
    "background": True,
    "process_mode": "detached",
    "command_completed": True,
    "runtime_mode": install.get("runtime_mode"),
    "python_version": install.get("python_version"),
    "bundled_runtime": bool(install.get("bundled_runtime")),
    "installation": doctor.get("installation"),
    "capabilities": doctor.get("capabilities"),
    "setup": doctor.get("setup"),
    "warnings": list(install.get("warnings") or []) + list(doctor.get("warnings") or []),
}
print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
PY
