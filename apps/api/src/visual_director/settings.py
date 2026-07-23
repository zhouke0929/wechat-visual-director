from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


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
