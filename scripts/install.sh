#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="${HOME}/Library/Application Support/wechat-visual-director"
HOST_HOME="$HOME"
SKIP_DEPENDENCIES=0
MIGRATE_LEGACY_DATA=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --host-home) HOST_HOME="$2"; shift 2 ;;
    --skip-dependencies) SKIP_DEPENDENCIES=1; shift ;;
    --migrate-legacy-data) MIGRATE_LEGACY_DATA=1; shift ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

SOURCE_BUNDLED_PYTHON="$SOURCE_ROOT/runtime/python/bin/python3"
SYSTEM_PYTHON="$(command -v python3 || true)"
if [[ -x "$SOURCE_BUNDLED_PYTHON" ]]; then
  UTILITY_PYTHON="$SOURCE_BUNDLED_PYTHON"
elif [[ -n "$SYSTEM_PYTHON" ]]; then
  UTILITY_PYTHON="$SYSTEM_PYTHON"
else
  printf '%s\n' '{"ok":false,"schema_version":"skill_install_result.v0.2","error":{"code":"python_not_found","message":"Python 3.11 or newer is required for a source install. Use the self-contained macOS Release installer for normal use.","retryable":true}}'
  exit 2
fi

INSTALL_ROOT="$("$UTILITY_PYTHON" -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$INSTALL_ROOT")"
HOST_HOME="$("$UTILITY_PYTHON" -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$HOST_HOME")"
VERSION="$(tr -d '\r\n' < "$SOURCE_ROOT/VERSION")"
[[ "$VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$ ]] || { printf '%s\n' '{"ok":false,"error":{"code":"version_invalid"}}'; exit 2; }
[[ "$INSTALL_ROOT" != "$SOURCE_ROOT" ]] || { printf '%s\n' '{"ok":false,"error":{"code":"install_root_is_source"}}'; exit 2; }
[[ "$INSTALL_ROOT" != "/" && "$INSTALL_ROOT" != "$HOME" ]] || { printf '%s\n' '{"ok":false,"error":{"code":"unsafe_install_root"}}'; exit 2; }

VERSIONS_ROOT="$INSTALL_ROOT/versions"
VERSION_ROOT="$VERSIONS_ROOT/$VERSION"
DATA_ROOT="$INSTALL_ROOT/data"
CONFIG_ROOT="$INSTALL_ROOT/config"
RUNTIME_ROOT="$INSTALL_ROOT/runtime"
CONFIG_FILE="$CONFIG_ROOT/.env.local"
MANIFEST="$INSTALL_ROOT/install.json"
HISTORY="$CONFIG_ROOT/install-history.json"
CURRENT_ROOT_FILE="$INSTALL_ROOT/current-root"
case "$VERSION_ROOT" in
  "$INSTALL_ROOT"/versions/*) ;;
  *) printf '%s\n' '{"ok":false,"error":{"code":"unsafe_version_root"}}'; exit 2 ;;
esac

if [[ -d "$VERSION_ROOT" ]]; then
  rm -rf "$VERSION_ROOT"
fi
mkdir -p "$VERSION_ROOT" "$DATA_ROOT" "$CONFIG_ROOT" "$RUNTIME_ROOT" "$INSTALL_ROOT/backups"

(
  cd "$SOURCE_ROOT"
  tar -cf - \
    --exclude='.git' --exclude='.tmp' --exclude='.pnpm-store' --exclude='artifacts' \
    --exclude='.runtime' \
    --exclude='apps/api/.venv' --exclude='apps/api/data' --exclude='apps/web/node_modules' \
    --exclude='apps/web/.next' --exclude='.env' --exclude='.env.local' --exclude='*.pyc' --exclude='*.log' \
    .
) | tar -xf - -C "$VERSION_ROOT"

MIGRATED_DB=false
MIGRATED_IMAGES=false
MIGRATED_PUBLICATION=false
MIGRATED_CONFIG=false
if [[ "$MIGRATE_LEGACY_DATA" -eq 1 && ! -f "$DATA_ROOT/visual-director.db" && -f "$SOURCE_ROOT/apps/api/data/visual-director.db" ]]; then
  cp "$SOURCE_ROOT/apps/api/data/visual-director.db" "$DATA_ROOT/visual-director.db"
  MIGRATED_DB=true
fi
if [[ "$MIGRATE_LEGACY_DATA" -eq 1 && ! -d "$DATA_ROOT/image-assets" && -d "$SOURCE_ROOT/apps/api/data/image-assets" ]]; then
  cp -R "$SOURCE_ROOT/apps/api/data/image-assets" "$DATA_ROOT/image-assets"
  MIGRATED_IMAGES=true
fi
if [[ "$MIGRATE_LEGACY_DATA" -eq 1 && ! -d "$DATA_ROOT/publication-assets" && -d "$SOURCE_ROOT/apps/api/data/publication-assets" ]]; then
  cp -R "$SOURCE_ROOT/apps/api/data/publication-assets" "$DATA_ROOT/publication-assets"
  MIGRATED_PUBLICATION=true
fi
if [[ "$MIGRATE_LEGACY_DATA" -eq 1 && ! -f "$CONFIG_FILE" && -f "$SOURCE_ROOT/.env.local" ]]; then
  cp "$SOURCE_ROOT/.env.local" "$CONFIG_FILE"
  MIGRATED_CONFIG=true
elif [[ ! -f "$CONFIG_FILE" ]]; then
  cp "$VERSION_ROOT/.env.example" "$CONFIG_FILE"
fi

API_DIR="$VERSION_ROOT/apps/api"
WEB_DIR="$VERSION_ROOT/apps/web"
BUNDLED_PYTHON="$VERSION_ROOT/runtime/python/bin/python3"
VENV_PYTHON="$API_DIR/.venv/bin/python"
RUNTIME_MODE="unresolved"
DEPENDENCIES_INSTALLED=false

if [[ -x "$BUNDLED_PYTHON" ]]; then
  ACTIVE_PYTHON="$BUNDLED_PYTHON"
  "$ACTIVE_PYTHON" -c 'import fastapi, PIL, uvicorn, visual_director, yaml' || {
    printf '%s\n' '{"ok":false,"error":{"code":"bundled_runtime_invalid","message":"The bundled Python runtime is incomplete."}}'
    exit 2
  }
  RUNTIME_MODE="bundled_python"
  DEPENDENCIES_INSTALLED=true
elif [[ "$SKIP_DEPENDENCIES" -eq 0 ]]; then
  [[ -n "$SYSTEM_PYTHON" ]] || { printf '%s\n' '{"ok":false,"error":{"code":"python_not_found"}}'; exit 2; }
  "$SYSTEM_PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)' || {
    printf '%s\n' '{"ok":false,"error":{"code":"python_version_unsupported","message":"Python 3.11 or newer is required."}}'
    exit 2
  }
  [[ -x "$VENV_PYTHON" ]] || "$SYSTEM_PYTHON" -m venv "$API_DIR/.venv"
  "$VENV_PYTHON" -m pip install --quiet --disable-pip-version-check -e "$API_DIR"
  ACTIVE_PYTHON="$VENV_PYTHON"
  RUNTIME_MODE="system_python_venv"
  DEPENDENCIES_INSTALLED=true
else
  ACTIVE_PYTHON="$UTILITY_PYTHON"
  RUNTIME_MODE="dependencies_skipped"
fi

[[ -f "$WEB_DIR/dist/index.html" ]] || {
  printf '%s\n' '{"ok":false,"error":{"code":"prebuilt_workbench_missing","message":"Release package is incomplete: prebuilt workbench is missing. Normal installation never invokes npm or pnpm."}}'
  exit 2
}

PREVIOUS_VERSION=""
if [[ -f "$MANIFEST" ]]; then
  PREVIOUS_VERSION="$("$ACTIVE_PYTHON" - "$MANIFEST" "$VERSION" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
current = str(payload.get("current_version") or "")
print((payload.get("previous_version") or "") if current == sys.argv[2] else current)
PY
)"
elif [[ -f "$HISTORY" ]]; then
  PREVIOUS_VERSION="$("$ACTIVE_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("last_version", ""))' "$HISTORY")"
fi

cp "$VERSION_ROOT/scripts/persistent-launcher.sh" "$INSTALL_ROOT/visual-director"
cp "$VERSION_ROOT/scripts/uninstall.sh" "$INSTALL_ROOT/uninstall.sh"
chmod +x "$INSTALL_ROOT/visual-director" "$INSTALL_ROOT/uninstall.sh" "$VERSION_ROOT/scripts/visual-director.sh"
printf '%s\n' "$VERSION_ROOT" > "$CURRENT_ROOT_FILE"

SKILL_SOURCE="$VERSION_ROOT/skills/wechat-visual-director"
[[ -f "$SKILL_SOURCE/SKILL.md" ]] || { printf '%s\n' '{"ok":false,"error":{"code":"skill_file_missing"}}'; exit 2; }
for SKILL_ROOT in "$HOST_HOME/.codex/skills/wechat-visual-director" "$HOST_HOME/.agents/skills/wechat-visual-director" "$HOST_HOME/.config/opencode/skills/wechat-visual-director"; do
  rm -rf "$SKILL_ROOT"
  mkdir -p "$SKILL_ROOT"
  cp -R "$SKILL_SOURCE/." "$SKILL_ROOT/"
done
mkdir -p "$HOST_HOME/.config/opencode/commands"
printf '%s\n' '---' 'description: 创建、排版或继续处理微信公众号视觉主编任务' '---' '' '加载并使用 `wechat-visual-director` Skill 处理下面的请求。严格遵守 Skill 的人工确认与密钥安全门禁。' '' '$ARGUMENTS' > "$HOST_HOME/.config/opencode/commands/wechat-visual-director.md"

INSTALLED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
"$ACTIVE_PYTHON" - "$MANIFEST" "$HISTORY" "$VERSION" "$PREVIOUS_VERSION" "$INSTALL_ROOT" "$VERSION_ROOT" "$DATA_ROOT" "$CONFIG_FILE" "$RUNTIME_ROOT" "$INSTALLED_AT" "$HOST_HOME" "$RUNTIME_MODE" <<'PY'
import json, sys
(
    manifest_path, history_path, version, previous_version, install_root,
    version_root, data_root, config_file, runtime_root, installed_at,
    host_home, runtime_mode,
) = sys.argv[1:]
manifest = {
    "schema_version": "persistent_install.v0.2",
    "current_version": version,
    "previous_version": previous_version or None,
    "install_root": install_root,
    "current_root": version_root,
    "data_root": data_root,
    "config_file": config_file,
    "runtime_root": runtime_root,
    "launcher": f"{install_root}/visual-director",
    "uninstaller": f"{install_root}/uninstall.sh",
    "runtime_mode": runtime_mode,
    "host_registration": {
        "codex_skill_root": f"{host_home}/.codex/skills/wechat-visual-director",
        "generic_skill_root": f"{host_home}/.agents/skills/wechat-visual-director",
        "opencode_skill_root": f"{host_home}/.config/opencode/skills/wechat-visual-director",
        "opencode_command": f"{host_home}/.config/opencode/commands/wechat-visual-director.md",
    },
    "installed_at": installed_at,
}
with open(manifest_path, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2)
history = {
    "schema_version": "install_history.v0.1",
    "last_version": version,
    "data_root": data_root,
    "last_install_at": installed_at,
    "last_uninstall_at": None,
}
with open(history_path, "w", encoding="utf-8") as handle:
    json.dump(history, handle, ensure_ascii=False, indent=2)
PY

PYTHON_VERSION="$("$ACTIVE_PYTHON" -c 'import platform; print(platform.python_version())')"
"$ACTIVE_PYTHON" - "$VERSION" "$PREVIOUS_VERSION" "$INSTALL_ROOT" "$VERSION_ROOT" "$DATA_ROOT" "$CONFIG_FILE" "$RUNTIME_ROOT" "$HOST_HOME" "$RUNTIME_MODE" "$PYTHON_VERSION" "$DEPENDENCIES_INSTALLED" "$MIGRATED_DB" "$MIGRATED_IMAGES" "$MIGRATED_PUBLICATION" "$MIGRATED_CONFIG" "$MIGRATE_LEGACY_DATA" <<'PY'
import json, sys
(
    version, previous_version, install_root, version_root, data_root,
    config_file, runtime_root, host_home, runtime_mode, python_version,
    dependencies_installed, migrated_db, migrated_images,
    migrated_publication, migrated_config, migration_requested,
) = sys.argv[1:]
as_bool = lambda value: value.lower() in {"1", "true", "yes"}
payload = {
    "ok": True,
    "schema_version": "skill_install_result.v0.2",
    "install_mode": "persistent",
    "platform": "macos",
    "version": version,
    "previous_version": previous_version or None,
    "install_root": install_root,
    "app_root": version_root,
    "data_root": data_root,
    "config_file": config_file,
    "runtime_root": runtime_root,
    "launcher": f"{install_root}/visual-director",
    "uninstaller": f"{install_root}/uninstall.sh",
    "skill_root": f"{host_home}/.agents/skills/wechat-visual-director",
    "host_registration": {
        "codex_skill_root": f"{host_home}/.codex/skills/wechat-visual-director",
        "generic_skill_root": f"{host_home}/.agents/skills/wechat-visual-director",
        "opencode_skill_root": f"{host_home}/.config/opencode/skills/wechat-visual-director",
        "opencode_command": f"{host_home}/.config/opencode/commands/wechat-visual-director.md",
    },
    "dependencies_installed": as_bool(dependencies_installed),
    "runtime_mode": runtime_mode,
    "python_version": python_version,
    "bundled_runtime": runtime_mode == "bundled_python",
    "production_workbench_built": True,
    "warnings": [],
    "migrated": {
        "database": as_bool(migrated_db),
        "image_assets": as_bool(migrated_images),
        "publication_assets": as_bool(migrated_publication),
        "config": as_bool(migrated_config),
    },
    "legacy_data_migration_requested": as_bool(migration_requested),
    "next_action": "run_doctor",
}
print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
PY
