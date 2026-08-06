#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/apps/api/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  printf '%s\n' '{"ok":false,"schema_version":"skill_launcher.v0.1","error":{"code":"core_not_installed","message":"Visual Director is not installed. Run scripts/install.sh first.","retryable":true}}'
  exit 2
fi
export VISUAL_DIRECTOR_PROJECT_ROOT="$ROOT"
exec "$PYTHON" -m visual_director.cli "$@"
