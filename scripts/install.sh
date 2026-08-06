#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="${HOME}/Library/Application Support/wechat-visual-director"
HOST_HOME="$HOME"
SKIP_DEPENDENCIES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --host-home) HOST_HOME="$2"; shift 2 ;;
    --skip-dependencies) SKIP_DEPENDENCIES=1; shift ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done
INSTALL_ROOT="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$INSTALL_ROOT")"
VERSION="$(tr -d '\r\n' < "$SOURCE_ROOT/VERSION")"
[[ "$VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$ ]] || { echo 'Invalid VERSION' >&2; exit 2; }
[[ "$INSTALL_ROOT" != "$SOURCE_ROOT" ]] || { echo 'Install root cannot be the source repository.' >&2; exit 2; }

VERSIONS_ROOT="$INSTALL_ROOT/versions"
VERSION_ROOT="$VERSIONS_ROOT/$VERSION"
DATA_ROOT="$INSTALL_ROOT/data"
CONFIG_ROOT="$INSTALL_ROOT/config"
RUNTIME_ROOT="$INSTALL_ROOT/runtime"
CONFIG_FILE="$CONFIG_ROOT/.env.local"
MANIFEST="$INSTALL_ROOT/install.json"
HISTORY="$CONFIG_ROOT/install-history.json"
mkdir -p "$VERSION_ROOT" "$DATA_ROOT" "$CONFIG_ROOT" "$RUNTIME_ROOT" "$INSTALL_ROOT/backups"

rsync -a --delete \
  --exclude '.git' --exclude '.tmp' --exclude '.pnpm-store' --exclude 'artifacts' \
  --exclude 'apps/api/.venv' --exclude 'apps/api/data' --exclude 'apps/web/node_modules' \
  --exclude 'apps/web/.next' --exclude '.env' --exclude '.env.local' --exclude '*.pyc' --exclude '*.log' \
  "$SOURCE_ROOT/" "$VERSION_ROOT/"

MIGRATED_DB=false; MIGRATED_IMAGES=false; MIGRATED_PUBLICATION=false; MIGRATED_CONFIG=false
if [[ ! -f "$DATA_ROOT/visual-director.db" && -f "$SOURCE_ROOT/apps/api/data/visual-director.db" ]]; then
  cp "$SOURCE_ROOT/apps/api/data/visual-director.db" "$DATA_ROOT/visual-director.db"; MIGRATED_DB=true
fi
if [[ ! -d "$DATA_ROOT/image-assets" && -d "$SOURCE_ROOT/apps/api/data/image-assets" ]]; then
  cp -R "$SOURCE_ROOT/apps/api/data/image-assets" "$DATA_ROOT/image-assets"; MIGRATED_IMAGES=true
fi
if [[ ! -d "$DATA_ROOT/publication-assets" && -d "$SOURCE_ROOT/apps/api/data/publication-assets" ]]; then
  cp -R "$SOURCE_ROOT/apps/api/data/publication-assets" "$DATA_ROOT/publication-assets"; MIGRATED_PUBLICATION=true
fi
if [[ ! -f "$CONFIG_FILE" && -f "$SOURCE_ROOT/.env.local" ]]; then
  cp "$SOURCE_ROOT/.env.local" "$CONFIG_FILE"; MIGRATED_CONFIG=true
elif [[ ! -f "$CONFIG_FILE" ]]; then
  cp "$VERSION_ROOT/.env.example" "$CONFIG_FILE"
fi

API_DIR="$VERSION_ROOT/apps/api"
WEB_DIR="$VERSION_ROOT/apps/web"
if [[ "$SKIP_DEPENDENCIES" -eq 0 ]]; then
  PYTHON="$(command -v python3 || true)"
  [[ -n "$PYTHON" ]] || { echo 'Python 3.11 or newer is required.' >&2; exit 2; }
  "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)' || { echo 'Python 3.11 or newer is required.' >&2; exit 2; }
  [[ -x "$API_DIR/.venv/bin/python" ]] || "$PYTHON" -m venv "$API_DIR/.venv"
  "$API_DIR/.venv/bin/python" -m pip install --quiet --disable-pip-version-check -e "$API_DIR"
  if [[ ! -f "$WEB_DIR/dist/index.html" ]]; then
    command -v corepack >/dev/null 2>&1 || { echo 'Prebuilt workbench missing; Node.js with Corepack is required for source builds.' >&2; exit 2; }
    corepack pnpm@11.7.0 --dir "$WEB_DIR" install --frozen-lockfile --reporter=silent
    corepack pnpm@11.7.0 --dir "$WEB_DIR" build
  fi
fi
[[ -f "$WEB_DIR/dist/index.html" ]] || { echo 'Static workbench build is missing.' >&2; exit 2; }

PREVIOUS_VERSION=""
if [[ -f "$MANIFEST" ]]; then
  PREVIOUS_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("current_version", ""))' "$MANIFEST")"
elif [[ -f "$HISTORY" ]]; then
  PREVIOUS_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("last_version", ""))' "$HISTORY")"
fi

cp "$VERSION_ROOT/scripts/persistent-launcher.sh" "$INSTALL_ROOT/visual-director"
cp "$VERSION_ROOT/scripts/uninstall.sh" "$INSTALL_ROOT/uninstall.sh"
chmod +x "$INSTALL_ROOT/visual-director" "$INSTALL_ROOT/uninstall.sh" "$VERSION_ROOT/scripts/visual-director.sh"

for SKILL_ROOT in "$HOST_HOME/.agents/skills/wechat-visual-director" "$HOST_HOME/.config/opencode/skills/wechat-visual-director"; do
  mkdir -p "$SKILL_ROOT"
  cp "$VERSION_ROOT/SKILL.md" "$SKILL_ROOT/SKILL.md"
  rm -rf "$SKILL_ROOT/references" "$SKILL_ROOT/agents"
  [[ -d "$VERSION_ROOT/references" ]] && cp -R "$VERSION_ROOT/references" "$SKILL_ROOT/references"
  [[ -d "$VERSION_ROOT/agents" ]] && cp -R "$VERSION_ROOT/agents" "$SKILL_ROOT/agents"
  [[ -f "$VERSION_ROOT/INSTALL_FOR_AGENT.md" ]] && cp "$VERSION_ROOT/INSTALL_FOR_AGENT.md" "$SKILL_ROOT/INSTALL_FOR_AGENT.md"
done
mkdir -p "$HOST_HOME/.config/opencode/commands"
printf '%s\n' '---' 'description: 创建、排版或继续处理微信公众号视觉主编任务' '---' '' '加载并使用 `wechat-visual-director` Skill 处理下面的请求。严格遵守 Skill 的人工确认与密钥安全门禁。' '' '$ARGUMENTS' > "$HOST_HOME/.config/opencode/commands/wechat-visual-director.md"

INSTALLED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$MANIFEST" "$HISTORY" <<PY
import json, sys
manifest = {
  "schema_version": "persistent_install.v0.2", "current_version": "$VERSION",
  "previous_version": "$PREVIOUS_VERSION" or None, "install_root": "$INSTALL_ROOT",
  "current_root": "$VERSION_ROOT", "data_root": "$DATA_ROOT", "config_file": "$CONFIG_FILE",
  "runtime_root": "$RUNTIME_ROOT", "launcher": "$INSTALL_ROOT/visual-director",
  "uninstaller": "$INSTALL_ROOT/uninstall.sh", "installed_at": "$INSTALLED_AT"
}
with open(sys.argv[1], "w", encoding="utf-8") as f: json.dump(manifest, f, ensure_ascii=False, indent=2)
history = {"schema_version":"install_history.v0.1", "last_version":"$VERSION", "data_root":"$DATA_ROOT", "last_install_at":"$INSTALLED_AT", "last_uninstall_at":None}
with open(sys.argv[2], "w", encoding="utf-8") as f: json.dump(history, f, ensure_ascii=False, indent=2)
PY

python3 - <<PY
import json
print(json.dumps({"ok":True,"schema_version":"skill_install_result.v0.2","install_mode":"persistent","platform":"macos_technical_preview","version":"$VERSION","previous_version":"$PREVIOUS_VERSION" or None,"install_root":"$INSTALL_ROOT","app_root":"$VERSION_ROOT","data_root":"$DATA_ROOT","config_file":"$CONFIG_FILE","launcher":"$INSTALL_ROOT/visual-director","uninstaller":"$INSTALL_ROOT/uninstall.sh","dependencies_installed":bool(1-$SKIP_DEPENDENCIES),"production_workbench_built":True,"migrated":{"database":"$MIGRATED_DB" == "true","image_assets":"$MIGRATED_IMAGES" == "true","publication_assets":"$MIGRATED_PUBLICATION" == "true","config":"$MIGRATED_CONFIG" == "true"},"next_action":"run_doctor"}, ensure_ascii=False, separators=(",",":")))
PY
