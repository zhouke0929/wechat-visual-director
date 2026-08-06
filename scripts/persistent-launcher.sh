#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$INSTALL_ROOT/install.json"
if [[ ! -f "$MANIFEST" ]]; then
  printf '%s\n' '{"ok":false,"schema_version":"persistent_launcher.v0.1","error":{"code":"install_manifest_missing","message":"Persistent install metadata was not found.","retryable":true}}'
  exit 2
fi

eval "$(python3 - "$MANIFEST" <<'PY'
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

PYTHON="$PROJECT_ROOT/apps/api/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  printf '%s\n' '{"ok":false,"schema_version":"persistent_launcher.v0.1","error":{"code":"installed_version_missing","message":"The active Visual Director version is incomplete.","retryable":true}}'
  exit 2
fi
export VISUAL_DIRECTOR_INSTALL_ROOT="$INSTALL_ROOT"
export VISUAL_DIRECTOR_PROJECT_ROOT="$PROJECT_ROOT"
export VISUAL_DIRECTOR_DATA_ROOT="$DATA_ROOT"
export VISUAL_DIRECTOR_HOME="$RUNTIME_ROOT"
export VISUAL_DIRECTOR_DB="$DATA_ROOT/visual-director.db"
export VISUAL_DIRECTOR_ENV_FILE="$CONFIG_FILE"
export VISUAL_DIRECTOR_WECHAT_ENV_FILE="$CONFIG_FILE"
exec "$PYTHON" -m visual_director.cli "$@"
