from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from .delivery_markup import DeliveryMarkup

THEME_ASSET_URL_PREFIX = "/api/v1/theme-assets/"
THEME_ASSET_NAME_RE = re.compile(r"^[a-z0-9-]+\.png$")


def theme_asset_root(project_root: Path) -> Path:
    return project_root / "assets" / "theme-stickers"


def theme_asset_path(project_root: Path, name: str) -> Path | None:
    if not THEME_ASSET_NAME_RE.fullmatch(name):
        return None
    path = theme_asset_root(project_root) / name
    return path if path.is_file() else None


def theme_asset_metadata(project_root: Path, name: str) -> tuple[Path, int, int, str] | None:
    path = theme_asset_path(project_root, name)
    if path is None:
        return None
    with Image.open(path) as image:
        width, height = image.size
        content_type = Image.MIME.get(image.format, "image/png")
    return path, width, height, content_type


def referenced_theme_assets(document: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for source_url in DeliveryMarkup(document).image_sources:
        if not source_url.startswith(THEME_ASSET_URL_PREFIX) or source_url in seen:
            continue
        name = source_url.removeprefix(THEME_ASSET_URL_PREFIX)
        if THEME_ASSET_NAME_RE.fullmatch(name):
            seen.add(source_url)
            found.append((source_url, name))
    return found
