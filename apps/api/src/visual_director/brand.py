from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_BRAND_PROFILE = "assets/brand/brand-profile-example-v0.1.json"


def load_brand_profile(root: Path) -> dict[str, Any]:
    configured = os.environ.get("VISUAL_DIRECTOR_BRAND_PROFILE", DEFAULT_BRAND_PROFILE)
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        raise FileNotFoundError(f"Brand profile was not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Brand profile must be a JSON object")
    payload["_profile_path"] = str(path.resolve())
    return payload


def public_brand_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in profile.items() if not key.startswith("_")}


def brand_asset_path(root: Path, profile: dict[str, Any]) -> Path | None:
    footer = profile.get("fixed_footer")
    if not isinstance(footer, dict) or not footer.get("enabled", False):
        return None
    raw_path = footer.get("asset_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else root / path
