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
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
INSTALL_ROOT="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$INSTALL_ROOT")"
MANIFEST="$INSTALL_ROOT/install.json"
[[ -f "$MANIFEST" ]] || { echo '{"ok":false,"error":{"code":"install_manifest_missing"}}'; exit 2; }
"$INSTALL_ROOT/visual-director" stop --json >/dev/null || { echo '{"ok":false,"error":{"code":"runtime_stop_refused"}}'; exit 3; }

if [[ "$PURGE" -eq 0 ]]; then
  mkdir -p "$INSTALL_ROOT/config"
  python3 - "$MANIFEST" "$INSTALL_ROOT/config/install-history.json" <<'PY'
import datetime, json, sys
manifest=json.load(open(sys.argv[1], encoding="utf-8"))
history={"schema_version":"install_history.v0.1","last_version":manifest.get("current_version"),"data_root":manifest.get("data_root"),"last_install_at":manifest.get("installed_at"),"last_uninstall_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
json.dump(history, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
fi
rm -rf "$HOST_HOME/.agents/skills/wechat-visual-director" "$HOST_HOME/.config/opencode/skills/wechat-visual-director"
rm -f "$HOST_HOME/.config/opencode/commands/wechat-visual-director.md"
rm -rf "$INSTALL_ROOT/versions" "$INSTALL_ROOT/runtime"
rm -f "$INSTALL_ROOT/visual-director" "$INSTALL_ROOT/install.json"
if [[ "$PURGE" -eq 1 ]]; then rm -rf "$INSTALL_ROOT/data" "$INSTALL_ROOT/config" "$INSTALL_ROOT/backups"; fi
python3 - <<PY
import json
print(json.dumps({"ok":True,"schema_version":"uninstall_result.v0.1","mode":"purge" if $PURGE else "preserve_data","install_root":"$INSTALL_ROOT","next_action":"installation_removed" if $PURGE else "reinstall_to_restore_program"}, ensure_ascii=False, separators=(",",":")))
PY
