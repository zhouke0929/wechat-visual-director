#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIRECTORY="$ROOT/artifacts/release"
PYTHON_VERSION="3.11"
SKIP_WORKBENCH_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-directory) OUTPUT_DIRECTORY="$2"; shift 2 ;;
    --python-version) PYTHON_VERSION="$2"; shift 2 ;;
    --skip-workbench-build) SKIP_WORKBENCH_BUILD=1; shift ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

build_failure() {
  printf '{"ok":false,"schema_version":"macos_release_build.v0.1","error":{"code":"%s","message":"%s"}}\n' "$1" "$2"
  exit 2
}

[[ "$(uname -s)" == "Darwin" ]] || build_failure "macos_required" "The macOS package must be built on macOS."
command -v uv >/dev/null 2>&1 || build_failure "uv_missing" "uv is required while building the bundled Python runtime."

MACHINE="$(uname -m)"
case "$MACHINE" in
  arm64|aarch64) ARCHITECTURE="arm64" ;;
  x86_64|amd64) ARCHITECTURE="x64" ;;
  *) build_failure "macos_architecture_unsupported" "The current build architecture is unsupported." ;;
esac

VERSION="$(tr -d '\r\n' < "$ROOT/VERSION")"
[[ "$VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$ ]] || build_failure "version_invalid" "VERSION contains an unsupported value."
mkdir -p "$OUTPUT_DIRECTORY"
OUTPUT_DIRECTORY="$(cd "$OUTPUT_DIRECTORY" && pwd -P)"
BUILD_ROOT="$OUTPUT_DIRECTORY/.build-macos-$ARCHITECTURE-$VERSION"
PACKAGE_ROOT="$BUILD_ROOT/wechat-visual-director"
case "$BUILD_ROOT" in
  "$OUTPUT_DIRECTORY"/*) ;;
  *) build_failure "unsafe_build_path" "The build path escaped the output directory." ;;
esac
rm -rf "$BUILD_ROOT"
mkdir -p "$PACKAGE_ROOT"
trap 'rm -rf "$BUILD_ROOT"' EXIT

if [[ "$SKIP_WORKBENCH_BUILD" -eq 0 ]]; then
  command -v pnpm >/dev/null 2>&1 || build_failure "pnpm_missing" "pnpm is required only while building the release workbench."
  pnpm --dir "$ROOT/apps/web" install --frozen-lockfile
  pnpm --dir "$ROOT/apps/web" build
fi

copy_release_path() {
  local relative="$1"
  [[ -e "$ROOT/$relative" ]] || build_failure "release_input_missing" "A required release input is missing: $relative"
  mkdir -p "$PACKAGE_ROOT/$(dirname "$relative")"
  if [[ -d "$ROOT/$relative" ]]; then
    rsync -a "$ROOT/$relative/" "$PACKAGE_ROOT/$relative/"
  else
    cp "$ROOT/$relative" "$PACKAGE_ROOT/$relative"
  fi
}

REQUIRED_PATHS=(
  VERSION INSTALL_FOR_AGENT.md README.md LICENSE THIRD_PARTY_NOTICES.md .env.example
  docs/usage-guide.md
  scripts/bootstrap.sh scripts/install.sh scripts/persistent-launcher.sh scripts/visual-director.sh scripts/uninstall.sh
  apps/api/pyproject.toml apps/api/.env.example apps/web/dist
  skills/wechat-visual-director assets contracts samples/skill-alpha
)
for RELATIVE_PATH in "${REQUIRED_PATHS[@]}"; do
  copy_release_path "$RELATIVE_PATH"
done

UV_PYTHON_PREFERENCE=only-managed uv python install "$PYTHON_VERSION"
MANAGED_PYTHON="$(UV_PYTHON_PREFERENCE=only-managed uv python find "$PYTHON_VERSION")"
[[ -x "$MANAGED_PYTHON" ]] || build_failure "managed_python_missing" "uv did not return a usable managed Python runtime."
MANAGED_PYTHON="$("$MANAGED_PYTHON" -c 'import pathlib,sys; print(pathlib.Path(sys.executable).resolve())')"
MANAGED_PREFIX="$(cd "$(dirname "$MANAGED_PYTHON")/.." && pwd -P)"
mkdir -p "$PACKAGE_ROOT/runtime/python"
rsync -a "$MANAGED_PREFIX/" "$PACKAGE_ROOT/runtime/python/"
RUNTIME_PYTHON="$PACKAGE_ROOT/runtime/python/bin/python3"
[[ -x "$RUNTIME_PYTHON" ]] || build_failure "python_runtime_invalid" "The copied standalone Python runtime is incomplete."

# The uv-managed base interpreter intentionally carries PEP 668's
# EXTERNALLY-MANAGED marker. This is a private copied runtime inside the release
# payload, so installing the application into that copy is safe and explicit.
UV_NO_CACHE=1 uv pip install --python "$RUNTIME_PYTHON" --reinstall --break-system-packages "$ROOT/apps/api"
"$RUNTIME_PYTHON" -c 'import fastapi, PIL, uvicorn, visual_director, yaml; print("runtime-ok")' >/dev/null

find "$PACKAGE_ROOT/runtime/python" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$PACKAGE_ROOT/runtime/python" -type f \( -name '*.pyc' -o -name '*.log' \) -delete
chmod +x "$PACKAGE_ROOT/scripts/"*.sh "$PACKAGE_ROOT/runtime/python/bin/python3"

"$RUNTIME_PYTHON" - "$PACKAGE_ROOT" "$VERSION" "$ARCHITECTURE" <<'PY'
import importlib.metadata as md
import json
import pathlib
import platform
import sys

root = pathlib.Path(sys.argv[1])
rows = []
for dist in md.distributions():
    name = dist.metadata.get("Name")
    if name:
        rows.append({"name": name, "version": dist.version, "license": dist.metadata.get("License") or None})
(root / "runtime" / "THIRD_PARTY_PACKAGES.json").write_text(
    json.dumps(sorted(rows, key=lambda row: row["name"].lower()), ensure_ascii=False, indent=2),
    encoding="utf-8",
)
payload_bytes = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
manifest = {
    "schema_version": "release_package.v0.1",
    "application": "wechat-visual-director",
    "application_version": sys.argv[2],
    "platform": "macos",
    "architecture": sys.argv[3],
    "python_runtime": platform.python_version(),
    "runtime_mode": "bundled_python",
    "requires_git": False,
    "requires_system_python": False,
    "requires_node": False,
    "requires_homebrew": False,
    "requires_wenyan": False,
    "payload_bytes": payload_bytes,
}
(root / "release-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
PY

ASSET_NAME="wechat-visual-director-macos-$ARCHITECTURE-v$VERSION.tar.gz"
ASSET_PATH="$OUTPUT_DIRECTORY/$ASSET_NAME"
CHECKSUM_PATH="$ASSET_PATH.sha256"
rm -f "$ASSET_PATH" "$CHECKSUM_PATH"
tar -czf "$ASSET_PATH" -C "$BUILD_ROOT" wechat-visual-director
HASH="$(shasum -a 256 "$ASSET_PATH" | awk '{print tolower($1)}')"
printf '%s  %s\n' "$HASH" "$ASSET_NAME" > "$CHECKSUM_PATH"

"$RUNTIME_PYTHON" - "$VERSION" "$ARCHITECTURE" "$ASSET_PATH" "$CHECKSUM_PATH" "$HASH" <<'PY'
import json, os, platform, sys
version, architecture, asset, checksum, digest = sys.argv[1:]
print(json.dumps({
    "ok": True,
    "schema_version": "macos_release_build.v0.1",
    "version": version,
    "architecture": architecture,
    "asset": asset,
    "checksum_file": checksum,
    "sha256": digest,
    "asset_bytes": os.path.getsize(asset),
    "python_version": platform.python_version(),
}, separators=(",", ":")))
PY
