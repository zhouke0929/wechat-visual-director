#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${HOME}/Library/Application Support/wechat-visual-director"
HOST_HOME="$HOME"
PURGE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --host-home) HOST_HOME="$2"; shift 2 ;;
    --purge) PURGE=1; shift ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

[[ -d "$INSTALL_ROOT" ]] || { printf '%s\n' '{"ok":false,"error":{"code":"install_root_missing"}}'; exit 2; }
INSTALL_ROOT="$(cd "$INSTALL_ROOT" && pwd -P)"
[[ "$INSTALL_ROOT" != "/" && "$INSTALL_ROOT" != "$HOME" ]] || { printf '%s\n' '{"ok":false,"error":{"code":"unsafe_install_root"}}'; exit 2; }
MANIFEST="$INSTALL_ROOT/install.json"
CURRENT_ROOT_FILE="$INSTALL_ROOT/current-root"
[[ -f "$MANIFEST" ]] || { printf '%s\n' '{"ok":false,"error":{"code":"install_manifest_missing"}}'; exit 2; }

CURRENT_ROOT=""
if [[ -f "$CURRENT_ROOT_FILE" ]]; then
  IFS= read -r CURRENT_ROOT < "$CURRENT_ROOT_FILE"
fi
if [[ -n "$CURRENT_ROOT" && -x "$CURRENT_ROOT/runtime/python/bin/python3" ]]; then
  TOOL_PYTHON="$CURRENT_ROOT/runtime/python/bin/python3"
elif [[ -n "$CURRENT_ROOT" && -x "$CURRENT_ROOT/apps/api/.venv/bin/python" ]]; then
  TOOL_PYTHON="$CURRENT_ROOT/apps/api/.venv/bin/python"
else
  TOOL_PYTHON="$(command -v python3 || true)"
fi
[[ -n "$TOOL_PYTHON" ]] || { printf '%s\n' '{"ok":false,"error":{"code":"installed_runtime_missing"}}'; exit 2; }

"$INSTALL_ROOT/visual-director" stop --json >/dev/null || {
  printf '%s\n' '{"ok":false,"error":{"code":"runtime_stop_refused"}}'
  exit 3
}

TEMP_RESULT="$(mktemp "${TMPDIR:-/tmp}/wechat-visual-director-uninstall.XXXXXX")"
trap 'rm -f "$TEMP_RESULT"' EXIT
"$TOOL_PYTHON" - "$MANIFEST" "$INSTALL_ROOT/config/install-history.json" "$INSTALL_ROOT" "$PURGE" "$TEMP_RESULT" <<'PY'
import datetime, json, sys
from pathlib import Path

manifest_path, history_path, install_root, purge, result_path = sys.argv[1:]
manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
if purge != "1":
    history = {
        "schema_version": "install_history.v0.1",
        "last_version": manifest.get("current_version"),
        "data_root": manifest.get("data_root"),
        "last_install_at": manifest.get("installed_at"),
        "last_uninstall_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    Path(history_path).parent.mkdir(parents=True, exist_ok=True)
    Path(history_path).write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
payload = {
    "ok": True,
    "schema_version": "uninstall_result.v0.1",
    "mode": "purge" if purge == "1" else "preserve_data",
    "install_root": install_root,
    "next_action": "installation_removed" if purge == "1" else "reinstall_to_restore_program",
}
Path(result_path).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
PY

rm -rf "$HOST_HOME/.agents/skills/wechat-visual-director" "$HOST_HOME/.config/opencode/skills/wechat-visual-director"
rm -f "$HOST_HOME/.config/opencode/commands/wechat-visual-director.md"
rm -rf "$INSTALL_ROOT/versions" "$INSTALL_ROOT/runtime"
rm -f "$INSTALL_ROOT/visual-director" "$INSTALL_ROOT/uninstall.sh" "$INSTALL_ROOT/install.json" "$CURRENT_ROOT_FILE"
if [[ "$PURGE" -eq 1 ]]; then
  rm -rf "$INSTALL_ROOT/data" "$INSTALL_ROOT/config" "$INSTALL_ROOT/backups"
  rmdir "$INSTALL_ROOT" 2>/dev/null || true
fi
cat "$TEMP_RESULT"
printf '\n'
