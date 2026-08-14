from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


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


RUNTIME_IDENTITY_SCHEMA_VERSION = "runtime_identity.v0.1"


def _resolved_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def runtime_identity(
    *,
    project_root: str | Path | None = None,
    database_path: str | Path | None = None,
) -> dict[str, Any]:
    """Describe the local runtime without exposing credentials.

    Version equality is not sufficient to identify a Visual Director process:
    a source checkout and a persistent install can run the same build while
    writing to different SQLite databases.  The fingerprint binds the process
    to its project root, install mode and actual database path.
    """

    resolved_project_root = _resolved_path(
        project_root
        or os.environ.get("VISUAL_DIRECTOR_PROJECT_ROOT")
        or Path(__file__).resolve().parents[4]
    )
    resolved_database_path = _resolved_path(
        database_path
        or os.environ.get("VISUAL_DIRECTOR_DB")
        or resolved_project_root / "apps" / "api" / "data" / "visual-director.db"
    )
    install_root_value = os.environ.get("VISUAL_DIRECTOR_INSTALL_ROOT")
    resolved_install_root = (
        _resolved_path(install_root_value) if install_root_value else None
    )
    mode = "persistent" if resolved_install_root else "source"
    identity_source = {
        "mode": mode,
        "project_root": os.path.normcase(str(resolved_project_root)),
        "database_path": os.path.normcase(str(resolved_database_path)),
        "install_root": (
            os.path.normcase(str(resolved_install_root))
            if resolved_install_root
            else None
        ),
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return {
        "schema_version": RUNTIME_IDENTITY_SCHEMA_VERSION,
        "mode": mode,
        "project_root": str(resolved_project_root),
        "data_root": str(resolved_database_path.parent),
        "database_path": str(resolved_database_path),
        "install_root": str(resolved_install_root) if resolved_install_root else None,
        "fingerprint": fingerprint,
    }
