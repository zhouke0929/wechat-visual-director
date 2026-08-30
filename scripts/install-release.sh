#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="zhouke0929/wechat-visual-director"
VERSION=""
INSTALL_ROOT=""
HOST_HOME=""
KEEP_DOWNLOAD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --host-home) HOST_HOME="$2"; shift 2 ;;
    --keep-download) KEEP_DOWNLOAD=1; shift ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

install_failure() {
  printf '{"ok":false,"schema_version":"release_install_result.v0.1","error":{"code":"%s","message":"%s","retryable":true}}\n' "$1" "$2"
  exit "${3:-2}"
}

[[ "$(uname -s)" == "Darwin" ]] || install_failure "macos_required" "This installer supports macOS only."
command -v curl >/dev/null 2>&1 || install_failure "curl_missing" "curl is required to download the release package."
command -v tar >/dev/null 2>&1 || install_failure "tar_missing" "tar is required to extract the release package."
command -v shasum >/dev/null 2>&1 || install_failure "shasum_missing" "shasum is required to verify the release package."

if [[ -z "$VERSION" ]]; then
  VERSION="$(curl -fsSL "https://raw.githubusercontent.com/$REPOSITORY/main/VERSION" | tr -d '\r\n')" || install_failure "release_version_unavailable" "The current release version could not be resolved."
fi
[[ "$VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$ ]] || install_failure "version_invalid" "The requested release version is invalid."

MACHINE="$(uname -m)"
case "$MACHINE" in
  arm64|aarch64) ARCHITECTURE="arm64" ;;
  x86_64|amd64) ARCHITECTURE="x64" ;;
  *) install_failure "macos_architecture_unsupported" "This Mac architecture is not supported by the current release." ;;
esac

ASSET_NAME="wechat-visual-director-macos-$ARCHITECTURE-v$VERSION.tar.gz"
RELEASE_BASE="https://github.com/$REPOSITORY/releases/download/v$VERSION"
DOWNLOAD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/wechat-visual-director-release.XXXXXX")"
ARCHIVE_PATH="$DOWNLOAD_ROOT/$ASSET_NAME"
CHECKSUM_PATH="$ARCHIVE_PATH.sha256"
EXTRACT_ROOT="$DOWNLOAD_ROOT/extracted"
mkdir -p "$EXTRACT_ROOT"

cleanup() {
  if [[ "$KEEP_DOWNLOAD" -eq 0 ]]; then
    rm -rf "$DOWNLOAD_ROOT"
  fi
}
trap cleanup EXIT

printf '[wechat-visual-director] Downloading the verified macOS %s release package.\n' "$ARCHITECTURE" >&2
curl -fL --retry 3 --connect-timeout 20 -sS "$RELEASE_BASE/$ASSET_NAME" -o "$ARCHIVE_PATH" || install_failure "release_download_failed" "The macOS release package could not be downloaded."
curl -fL --retry 3 --connect-timeout 20 -sS "$RELEASE_BASE/$ASSET_NAME.sha256" -o "$CHECKSUM_PATH" || install_failure "release_checksum_download_failed" "The release checksum could not be downloaded."

EXPECTED_HASH="$(awk 'NR==1 {print tolower($1)}' "$CHECKSUM_PATH")"
ACTUAL_HASH="$(shasum -a 256 "$ARCHIVE_PATH" | awk '{print tolower($1)}')"
[[ -n "$EXPECTED_HASH" && "$EXPECTED_HASH" == "$ACTUAL_HASH" ]] || install_failure "release_checksum_mismatch" "The downloaded release package failed SHA-256 verification."

tar -xzf "$ARCHIVE_PATH" -C "$EXTRACT_ROOT" || install_failure "release_extract_failed" "The macOS release package could not be extracted."
PACKAGE_ROOT="$EXTRACT_ROOT/wechat-visual-director"
BOOTSTRAP="$PACKAGE_ROOT/scripts/bootstrap.sh"
PACKAGE_PYTHON="$PACKAGE_ROOT/runtime/python/bin/python3"
[[ -f "$BOOTSTRAP" && -x "$PACKAGE_PYTHON" ]] || install_failure "release_package_invalid" "The release package does not contain the expected bootstrap and runtime."
"$PACKAGE_PYTHON" - "$PACKAGE_ROOT/release-manifest.json" "$VERSION" "$ARCHITECTURE" <<'PY' || install_failure "release_manifest_mismatch" "The release package metadata does not match this Mac."
import json, sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
valid = (
    payload.get("application") == "wechat-visual-director"
    and payload.get("application_version") == sys.argv[2]
    and payload.get("platform") == "macos"
    and payload.get("architecture") == sys.argv[3]
    and payload.get("runtime_mode") == "bundled_python"
    and payload.get("requires_system_python") is False
)
raise SystemExit(0 if valid else 2)
PY

BOOTSTRAP_ARGS=()
if [[ -n "$INSTALL_ROOT" ]]; then BOOTSTRAP_ARGS+=(--install-root "$INSTALL_ROOT"); fi
if [[ -n "$HOST_HOME" ]]; then BOOTSTRAP_ARGS+=(--host-home "$HOST_HOME"); fi
set +e
bash "$BOOTSTRAP" "${BOOTSTRAP_ARGS[@]}" > "$DOWNLOAD_ROOT/bootstrap.json"
BOOTSTRAP_EXIT=$?
set -e
if [[ "$BOOTSTRAP_EXIT" -ne 0 ]]; then
  install_failure "bootstrap_failed" "The packaged macOS installation did not complete." "$BOOTSTRAP_EXIT"
fi

"$PACKAGE_PYTHON" - "$DOWNLOAD_ROOT/bootstrap.json" "$ASSET_NAME" "$ACTUAL_HASH" <<'PY'
import json, sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
payload["install_source"] = "github_release"
payload["release_asset"] = sys.argv[2]
payload["archive_sha256"] = sys.argv[3]
print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
PY
