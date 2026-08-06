#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="${HOME}/Library/Application Support/wechat-visual-director"
HOST_HOME="$HOME"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --host-home) HOST_HOME="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
if [[ -x "$INSTALL_ROOT/visual-director" ]]; then "$INSTALL_ROOT/visual-director" stop --json >/dev/null || true; fi
"$ROOT/scripts/install.sh" --install-root "$INSTALL_ROOT" --host-home "$HOST_HOME" >/dev/null
"$INSTALL_ROOT/visual-director" serve --json >/dev/null
"$INSTALL_ROOT/visual-director" doctor --json
