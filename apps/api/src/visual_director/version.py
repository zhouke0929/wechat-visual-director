from __future__ import annotations

import os
from pathlib import Path


def application_version() -> str:
    configured_root = os.environ.get("VISUAL_DIRECTOR_PROJECT_ROOT")
    project_root = (
        Path(configured_root).expanduser().resolve()
        if configured_root
        else Path(__file__).resolve().parents[4]
    )
    version_file = project_root / "VERSION"
    if not version_file.is_file():
        return "0.1.0-dev"
    try:
        value = version_file.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return "0.1.0-dev"
    return value or "0.1.0-dev"
