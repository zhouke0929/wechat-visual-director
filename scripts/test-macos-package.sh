#!/usr/bin/env bash
set -euo pipefail

ARCHIVE_PATH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive-path) ARCHIVE_PATH="$2"; shift 2 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done
[[ -f "$ARCHIVE_PATH" ]] || { printf 'Archive not found: %s\n' "$ARCHIVE_PATH" >&2; exit 2; }

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/wechat-visual-director-package-test.XXXXXX")"
INSTALL_ROOT="$TEMP_ROOT/installed"
HOST_HOME="$TEMP_ROOT/host-home"
EXTRACT_ROOT="$TEMP_ROOT/extracted"
mkdir -p "$EXTRACT_ROOT" "$HOST_HOME"

# Keep the runtime's host discovery aligned with the isolated registration
# target passed to the installer. Real users naturally have both values equal.
export HOME="$HOST_HOME"

cleanup() {
  if [[ -x "$INSTALL_ROOT/visual-director" ]]; then
    "$INSTALL_ROOT/visual-director" stop --json >/dev/null 2>&1 || true
  fi
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT

tar -xzf "$ARCHIVE_PATH" -C "$EXTRACT_ROOT"
PACKAGE_ROOT="$EXTRACT_ROOT/wechat-visual-director"
PACKAGE_PYTHON="$PACKAGE_ROOT/runtime/python/bin/python3"
[[ -x "$PACKAGE_PYTHON" ]] || { printf 'Bundled Python is missing.\n' >&2; exit 2; }

SHADOW_BIN="$TEMP_ROOT/shadow-bin"
mkdir -p "$SHADOW_BIN"
printf '%s\n' '#!/usr/bin/env bash' 'echo "system python must not be used" >&2' 'exit 91' > "$SHADOW_BIN/python3"
chmod +x "$SHADOW_BIN/python3"
export PATH="$SHADOW_BIN:/usr/bin:/bin:/usr/sbin:/sbin"

bash "$PACKAGE_ROOT/scripts/bootstrap.sh" --install-root "$INSTALL_ROOT" --host-home "$HOST_HOME" > "$TEMP_ROOT/bootstrap.json"
"$PACKAGE_PYTHON" - "$TEMP_ROOT/bootstrap.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["ok"] is True, payload
assert payload["runtime_mode"] == "bundled_python", payload
assert payload["bundled_runtime"] is True, payload
assert payload["installation"]["persistent"] is True, payload
assert payload["installation"]["version_match"] is True, payload
assert payload["installation"]["runtime_match"] is True, payload
assert payload["data_continuity"]["checked"] is True, payload
assert payload["data_continuity"]["preserved"] is True, payload
assert payload["capabilities"]["host_skill_registered"] is True, payload
assert payload["onboarding_pending"] is True, payload
assert len(payload["first_run_guide"]["lines"]) == 4, payload
PY

for SKILL_ROOT in "$HOST_HOME/.codex/skills/wechat-visual-director" "$HOST_HOME/.agents/skills/wechat-visual-director" "$HOST_HOME/.config/opencode/skills/wechat-visual-director"; do
  [[ -f "$SKILL_ROOT/SKILL.md" ]] || { printf 'Lightweight Skill registration is missing: %s\n' "$SKILL_ROOT" >&2; exit 2; }
  [[ ! -e "$SKILL_ROOT/apps" && ! -e "$SKILL_ROOT/docs" && ! -e "$SKILL_ROOT/.github" ]] || {
    printf 'Source directories leaked into lightweight Skill registration: %s\n' "$SKILL_ROOT" >&2
    exit 2
  }
done

"$INSTALL_ROOT/visual-director" doctor --json > "$TEMP_ROOT/doctor.json"
"$PACKAGE_PYTHON" - "$TEMP_ROOT/doctor.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["ok"] is True, payload
assert payload["installation"]["runtime_match"] is True, payload
assert payload["setup"]["onboarding_pending"] is True, payload
assert len(payload["setup"]["first_run_guide"]["lines"]) == 4, payload
PY

"$INSTALL_ROOT/visual-director" task create --file "$PACKAGE_ROOT/samples/skill-alpha/canonical-article.md" --no-plan --json > "$TEMP_ROOT/task.json"
bash "$PACKAGE_ROOT/scripts/bootstrap.sh" --install-root "$INSTALL_ROOT" --host-home "$HOST_HOME" > "$TEMP_ROOT/upgrade.json"
"$PACKAGE_PYTHON" - "$TEMP_ROOT/upgrade.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["ok"] is True, payload
assert payload["data_continuity"]["preserved"] is True, payload
assert payload["data_continuity"]["before_task_count"] == 1, payload
assert payload["installation"]["running_task_count"] == 1, payload
PY

printf 'preserve-me\n' > "$INSTALL_ROOT/data/package-test-marker.txt"
"$INSTALL_ROOT/visual-director" stop --json >/dev/null
bash "$INSTALL_ROOT/uninstall.sh" --install-root "$INSTALL_ROOT" --host-home "$HOST_HOME" > "$TEMP_ROOT/uninstall.json"
[[ ! -e "$HOST_HOME/.codex/skills/wechat-visual-director" ]] || { printf 'Codex Skill registration survived uninstall.\n' >&2; exit 2; }
"$PACKAGE_PYTHON" - "$TEMP_ROOT/uninstall.json" "$INSTALL_ROOT/data/package-test-marker.txt" <<'PY'
import json, pathlib, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["ok"] is True, payload
assert payload["mode"] == "preserve_data", payload
assert pathlib.Path(sys.argv[2]).is_file()
PY

printf '%s\n' '{"ok":true,"schema_version":"macos_release_smoke_test.v0.1"}'
