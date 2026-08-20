from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
OUTPUT = ROOT / "site" / "data" / "themes.json"
STICKER_SOURCE = ROOT / "assets" / "theme-stickers"
STICKER_OUTPUT = ROOT / "site" / "assets" / "theme-stickers"
sys.path.insert(0, str(API_SRC))

from visual_director.theme_gallery import (  # noqa: E402
    THEME_GALLERY_SCHEMA_VERSION,
    build_theme_gallery,
)


def render_payload() -> str:
    payload = {
        "schema_version": THEME_GALLERY_SCHEMA_VERSION,
        "themes": build_theme_gallery(),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    rendered = rendered.replace(
        "/api/v1/theme-assets/",
        "assets/theme-stickers/",
    )
    return rendered + "\n"


def sticker_assets_are_current() -> bool:
    source_files = sorted(STICKER_SOURCE.glob("*.png"))
    output_files = sorted(STICKER_OUTPUT.glob("*.png")) if STICKER_OUTPUT.exists() else []
    if [path.name for path in source_files] != [path.name for path in output_files]:
        return False
    return all(
        source.read_bytes() == (STICKER_OUTPUT / source.name).read_bytes()
        for source in source_files
    )


def copy_sticker_assets() -> None:
    STICKER_OUTPUT.mkdir(parents=True, exist_ok=True)
    for stale in STICKER_OUTPUT.glob("*.png"):
        stale.unlink()
    for source in STICKER_SOURCE.glob("*.png"):
        shutil.copy2(source, STICKER_OUTPUT / source.name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the production theme gallery for the static product showcase.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed static gallery is out of sync.",
    )
    args = parser.parse_args()

    expected = render_payload()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != expected or not sticker_assets_are_current():
            print("site/data/themes.json is stale; run scripts/export_theme_gallery.py")
            return 1
        print("static theme gallery is in sync")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    copy_sticker_assets()
    print(f"exported {len(json.loads(expected)['themes'])} themes to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
