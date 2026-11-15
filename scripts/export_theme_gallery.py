from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import sys
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from PIL import Image

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

DECORATION = re.compile(
    r'(<img data-theme-decoration=")([a-f0-9]{64})'
    r'(" data-decoration-compiler="[^"]+" src="data:image/png;base64,)([A-Za-z0-9+/=]+)(")'
)


@lru_cache(maxsize=512)
def decoration_pixel_digest(encoded: str, file_digest: str) -> str:
    data = base64.b64decode(encoded, validate=True)
    if hashlib.sha256(data).hexdigest() != file_digest:
        raise ValueError("Static theme decoration checksum mismatch")
    with Image.open(io.BytesIO(data)) as image:
        if (image.format, image.mode) != ("PNG", "RGBA") or not (
            1 <= image.width <= 640 and 1 <= image.height <= 640
        ):
            raise ValueError("Static theme decoration must be a bounded RGBA PNG")
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        pixels = image.tobytes()
        # The PNG encoder may change its filters or compression per platform.
        size = f"{image.width}x{image.height}:".encode("ascii")
        return hashlib.sha256(size + pixels).hexdigest()


def comparable_gallery(value, path: tuple[str | int, ...] = ()):
    """Compare layout and pixels exactly, ignoring only derived PNG storage sizes."""
    if isinstance(value, dict):
        return {key: comparable_gallery(item, (*path, key)) for key, item in value.items()}
    if isinstance(value, list):
        return [comparable_gallery(item, (*path, index)) for index, item in enumerate(value)]
    if isinstance(value, str):
        def canonical_decoration(match: re.Match[str]) -> str:
            pixel_digest = decoration_pixel_digest(match[4], match[2])
            return f"{match[1]}{pixel_digest}{match[3]}{pixel_digest}{match[5]}"

        return DECORATION.sub(canonical_decoration, value)
    if (
        len(path) == 7
        and path[0] == "themes"
        and path[2:5] == ("delivery_report", "rehearsal", "roles")
        and isinstance(path[5], int)
        and path[-1] == "decoration_bytes"
        and type(value) is int
        and value >= 0
    ):
        return None
    return value


def gallery_contents_match(current: str, expected: str) -> bool:
    return not next(gallery_differences(current, expected), None)


def gallery_differences(current: str, expected: str) -> Iterator[str]:
    try:
        left = comparable_gallery(json.loads(current))
        right = comparable_gallery(json.loads(expected))
    except (ValueError, OSError, SyntaxError) as error:
        yield f"Invalid gallery data: {error}"
        return

    def fields(old, new, field: str) -> Iterator[str]:
        if old == new:
            return
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(old.keys() | new.keys()):
                child = f"{field}.{key}"
                if key not in old or key not in new:
                    yield child
                else:
                    yield from fields(old[key], new[key], child)
        elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
            for index, (first, second) in enumerate(zip(old, new)):
                label = second.get("id", index) if isinstance(second, dict) else index
                yield from fields(first, second, f"{field}[{label}]")
        else:
            yield field

    yield from fields(left, right, "gallery")


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
    parser.add_argument("--diagnostic-output", type=Path, help="Write generated JSON here only when --check fails.")
    args = parser.parse_args()

    expected = render_payload()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        differences = list(gallery_differences(current, expected))
        if not sticker_assets_are_current():
            differences.append("site/assets/theme-stickers")
        if differences:
            print("Static gallery does not match the renderer:")
            print("\n".join(differences[:20]))
            if args.diagnostic_output:
                args.diagnostic_output.write_text(expected, encoding="utf-8")
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
