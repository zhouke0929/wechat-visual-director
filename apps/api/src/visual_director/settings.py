from __future__ import annotations

import os
import re
import uuid
from collections.abc import Mapping
from pathlib import Path


ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


def read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized_key = key.strip()
        if normalized_key:
            values[normalized_key] = value.strip().strip('"').strip("'")
    return values


def load_runtime_settings(
    root: Path,
    environ: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], Path | None]:
    process_values = dict(environ if environ is not None else os.environ)
    configured_path = process_values.get("VISUAL_DIRECTOR_ENV_FILE")
    env_path = (
        Path(configured_path).expanduser().resolve()
        if configured_path
        else root / ".env.local"
    )
    file_values = read_env_file(env_path)
    # Explicit process variables win over the local file without mutating os.environ.
    return {**file_values, **process_values}, env_path if env_path.is_file() else None


def update_env_file(path: Path, updates: Mapping[str, str]) -> None:
    normalized_updates: dict[str, str] = {}
    for key, value in updates.items():
        if not ENV_KEY_RE.fullmatch(key):
            raise ValueError(f"Unsupported environment key: {key}")
        normalized_value = str(value)
        if "\n" in normalized_value or "\r" in normalized_value or "\0" in normalized_value:
            raise ValueError(f"Environment value for {key} contains a forbidden character")
        normalized_updates[key] = normalized_value

    existing_lines = (
        path.read_text(encoding="utf-8-sig").splitlines()
        if path.is_file()
        else []
    )
    written: set[str] = set()
    output_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in normalized_updates:
                output_lines.append(f"{key}={normalized_updates[key]}")
                written.add(key)
                continue
        output_lines.append(line)
    for key, value in normalized_updates.items():
        if key not in written:
            output_lines.append(f"{key}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
        if os.name != "nt":
            temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
