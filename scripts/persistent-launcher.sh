#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$INSTALL_ROOT/install.json"
CURRENT_ROOT_FILE="$INSTALL_ROOT/current-root"

launcher_failure() {
  printf '{"ok":false,"schema_version":"persistent_launcher.v0.1","error":{"code":"%s","message":"%s","retryable":true}}\n' "$1" "$2"
  exit 2
}

[[ -f "$MANIFEST" ]] || launcher_failure "install_manifest_missing" "Persistent install metadata was not found."

PROJECT_ROOT=""
if [[ -f "$CURRENT_ROOT_FILE" ]]; then
  IFS= read -r PROJECT_ROOT < "$CURRENT_ROOT_FILE"
fi

PARSER_PYTHON=""
if [[ -n "$PROJECT_ROOT" && -x "$PROJECT_ROOT/runtime/python/bin/python3" ]]; then
  PARSER_PYTHON="$PROJECT_ROOT/runtime/python/bin/python3"
elif [[ -n "$PROJECT_ROOT" && -x "$PROJECT_ROOT/apps/api/.venv/bin/python" ]]; then
  PARSER_PYTHON="$PROJECT_ROOT/apps/api/.venv/bin/python"
else
  PARSER_PYTHON="$(command -v python3 || true)"
fi
[[ -n "$PARSER_PYTHON" ]] || launcher_failure "installed_runtime_missing" "The active Visual Director runtime is missing."

eval "$("$PARSER_PYTHON" - "$MANIFEST" <<'PY'
import json, shlex, sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key, value in {
    "PROJECT_ROOT": payload["current_root"],
    "DATA_ROOT": payload["data_root"],
    "CONFIG_FILE": payload["config_file"],
    "RUNTIME_ROOT": payload["runtime_root"],
}.items():
    print(f"{key}={shlex.quote(str(value))}")
PY
)"

if [[ -x "$PROJECT_ROOT/runtime/python/bin/python3" ]]; then
  PYTHON="$PROJECT_ROOT/runtime/python/bin/python3"
else
  PYTHON="$PROJECT_ROOT/apps/api/.venv/bin/python"
fi
[[ -x "$PYTHON" ]] || launcher_failure "installed_version_missing" "The active Visual Director version is incomplete."

export VISUAL_DIRECTOR_INSTALL_ROOT="$INSTALL_ROOT"
export VISUAL_DIRECTOR_PROJECT_ROOT="$PROJECT_ROOT"
export VISUAL_DIRECTOR_DATA_ROOT="$DATA_ROOT"
export VISUAL_DIRECTOR_HOME="$RUNTIME_ROOT"
export VISUAL_DIRECTOR_DB="$DATA_ROOT/visual-director.db"
export VISUAL_DIRECTOR_ENV_FILE="$CONFIG_FILE"
export VISUAL_DIRECTOR_WECHAT_ENV_FILE="$CONFIG_FILE"
exec "$PYTHON" -m visual_director.cli "$@"
