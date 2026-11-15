from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "export_theme_gallery.py"
SPEC = importlib.util.spec_from_file_location("export_theme_gallery", SCRIPT)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def gallery(compression: int, *, color=(26, 37, 48, 255), style="width:20px", status="pass", bad_hash=False):
    output = io.BytesIO()
    Image.new("RGBA", (20, 20), color).save(output, format="PNG", compress_level=compression)
    content = output.getvalue()
    digest = "0" * 64 if bad_hash else hashlib.sha256(content).hexdigest()
    encoded = base64.b64encode(content).decode("ascii")
    html = (f'<img data-theme-decoration="{digest}" data-decoration-compiler="drawing_png.v1" '
            f'src="data:image/png;base64,{encoded}" style="{style}" />')
    return json.dumps({"themes": [{
        "article_preview_html": html,
        "delivery_report": {"rehearsal": {"roles": [{"status": status, "decoration_bytes": len(content)}]}},
    }]})


def test_gallery_allows_different_png_encoding_with_same_pixels():
    stored = gallery(0)
    current = gallery(9)
    assert stored != current
    assert exporter.gallery_contents_match(stored, current)


def test_gallery_detects_layout_pixels_delivery_status_and_bad_hash():
    expected = gallery(0)
    assert not exporter.gallery_contents_match(expected, gallery(9, color=(26, 37, 49, 255)))
    assert not exporter.gallery_contents_match(expected, gallery(9, style="width:18px"))
    assert not exporter.gallery_contents_match(expected, gallery(9, status="blocking"))
    assert not exporter.gallery_contents_match(expected, gallery(9, bad_hash=True))
