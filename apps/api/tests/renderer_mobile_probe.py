"""On-demand mobile acceptance: compare actual pixels on THIS browser, not across hosts.

Run: python apps/api/tests/renderer_mobile_probe.py
No accounts, network, database, running workbench or real WeChat required.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch

from test_renderer_catalog_parity import ORACLE, ROOT, _pinned_source_tree


def _stage(root: Path, destination: Path) -> None:
    from visual_director import theme_specimens as ts
    from visual_director.component_catalog import VISUAL_SYSTEM_ORDER, CORE_THEME_COMPONENTS
    from visual_director.theme_packs import configure_theme_packs
    import base64

    assert Path(ts.__file__).resolve().is_relative_to(root)
    configure_theme_packs(destination / "empty-packs", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    plan = json.loads(ORACLE.read_text(encoding="utf-8"))["fixed_plan"]

    @functools.lru_cache(maxsize=128)
    def sticker(name: str) -> str:
        data = (root / "assets" / "theme-stickers" / name).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")

    with patch.object(ts, "generate_plans", return_value=[plan]):
        for theme in VISUAL_SYSTEM_ORDER:
            _, article = ts.build_production_specimens(theme)
            article = re.sub(r"/api/v1/theme-assets/([a-z0-9-]+\.png)", lambda m: sticker(m[1]), article)
            (destination / f"{theme}.html").write_text(
                '<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" '
                'content="width=device-width, initial-scale=1"><body style="margin:0">' + article + "</body></html>",
                encoding="utf-8",
            )


def _capture(page, path: Path):
    page.set_content(path.read_text(encoding="utf-8"), wait_until="load")
    metrics = page.evaluate("""async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map(image => image.decode()));
      return {width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight,
              images: document.images.length};
    }""")
    assert metrics["images"] > 0 and metrics["height"] > 800, (path.name, metrics)
    pixels = hashlib.sha256(page.screenshot(full_page=True, animations="disabled")).hexdigest()
    return metrics, pixels


def compare_mobile() -> None:
    from playwright.sync_api import sync_playwright

    with _pinned_source_tree() as (base, _), tempfile.TemporaryDirectory(prefix="wvd-compare-mobile-") as tmp:
        paths = []
        for src, slug in ((base, "base"), (ROOT, "candidate")):
            out = Path(tmp) / slug
            out.mkdir()
            env = {**os.environ, "PYTHONPATH": str(src / "apps/api/src"), "VISUAL_DIRECTOR_PROJECT_ROOT": str(src),
                   "VISUAL_DIRECTOR_THEME_PACK_DIR": str(out / "empty-packs"),
                   "WVD_RENDERER_PILOT": "1", "WVD_READING_RULES_PILOT": "1", "WVD_LOGIC_PATH_PILOT": "0"}
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--stage", str(src), str(out)],
                           cwd=src, env=env, check=True)
            paths.append(out)
        names = sorted(p.name for p in paths[0].glob("*.html"))
        assert len(names) == 26 and names == sorted(p.name for p in paths[1].glob("*.html"))
        issues = []
        verified = 0
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                for width in (320, 390):
                    page = browser.new_page(viewport={"width": width, "height": 800}, device_scale_factor=1)
                    page.route("**/*", lambda route: route.abort())
                    for name in names:
                        a, b = (_capture(page, folder / name) for folder in paths)
                        if a != b or b[0]["width"] > max(width, a[0]["width"]):
                            issues.append((width, name, a, b))
                        verified += 1
                    page.close()
            finally:
                browser.close()
        assert not issues, issues
        print(f"{verified} full article screenshot pairs identical (26 themes x 320/390px).")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--stage":
        _stage(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
    else:
        compare_mobile()
