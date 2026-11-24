"""Offline local review; run: python apps/api/tests/render_catalog_review.py."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

from test_renderer_catalog_parity import ORACLE, ROOT, fixed_sample_plan

OUT = ROOT / "artifacts/render-component-contracts-review"
CSS = """
:root{color-scheme:light;background:#eeece2;color:#21352e;font:16px/1.5 "Microsoft YaHei",sans-serif}
body{margin:0}.review{width:min(1120px,calc(100% - 28px));margin:20px auto 56px}.mast{padding:12px 0 16px;border-top:3px solid #256359;border-bottom:1px solid #b9c2b6;display:flex;gap:16px;justify-content:space-between;align-items:end;flex-wrap:wrap}
.kicker{font:700 11px/1.6 Georgia,serif;color:#934f39;letter-spacing:.16em}.mast h1{margin:1px 0 0;font:600 clamp(25px,4vw,40px)/1.2 Georgia,SimSun,serif}
.review-nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.review-nav a,.theme-link{padding:6px 12px;color:#224c43;border:1px solid #bdc4ba;text-decoration:none;background:#fcfbf5;font-size:14px}
.review-nav a[aria-current],.theme-link[aria-current]{background:#1e584c;color:white;border-color:#1e584c}.review-nav a:hover,.theme-link:hover{border-color:#a44931}
.theme-list{padding:10px 0;border-bottom:1px solid #c4c6ba}.theme-list summary{cursor:pointer;font-weight:650}.theme-links{display:flex;gap:6px;flex-wrap:wrap;padding:9px 0}
.sample-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(320px,100%),1fr));gap:12px;margin-top:16px;align-items:start}
.sample{min-width:0;background:white}.sample-label{margin:0;padding:8px 13px;border-bottom:1px solid #ebe7dc;font-size:14px;color:#253930}
.sample-label b{color:#904b35;font:600 12px Georgia,serif;letter-spacing:.12em;margin-right:8px}.isolate{display:block;width:100%;border:0;height:270px;background:white}
.article-frame{width:min(390px,100%);margin:24px auto;background:white;border-top:2px solid #246052}
"""
IFRAME_HEAD = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" '
               'content="width=device-width,initial-scale=1"><body style="margin:0;padding:0 14px;'
               'font-family:\'Noto Sans SC\',\'Microsoft YaHei\',Arial,sans-serif">')
RESIZE = """<script>function fit(f){let b=f.contentDocument?.body;if(!b)return;let resize=()=>{f.style.height=Math.ceil(b.getBoundingClientRect().height)+1+'px'};new ResizeObserver(resize).observe(b);resize()}</script>"""


def srcdoc(markup):
    return html.escape(IFRAME_HEAD + '<div style="display:flow-root">' + markup + '</div></body></html>', quote=True)


def generate() -> None:
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from visual_director import theme_gallery as gallery, theme_specimens as ts
    from visual_director.component_catalog import registered_visual_system_catalog, VISUAL_SYSTEM_ORDER, CORE_THEME_COMPONENTS
    from visual_director.brief_compiler import visual_system_configuration
    from visual_director.theme_packs import configure_theme_packs
    from visual_director.parser import parse_markdown

    OUT.mkdir(parents=True, exist_ok=True)
    # Off-directory review is portable; only copy the bundled, explicitly referenced
    # decorations. No network, user files, custom theme HTML, API or database.
    assets = OUT / "stickers"
    assets.mkdir(exist_ok=True)
    def offline(markup):
        def copy(m):
            name = m[1]
            (assets / name).write_bytes((ROOT / "assets/theme-stickers" / name).read_bytes())
            return "stickers/" + name
        return re.sub(r"/api/v1/theme-assets/([a-z0-9-]+\.png)", copy, markup)

    plan = json.loads(ORACLE.read_text(encoding="utf-8"))["fixed_plan"]
    with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
        "WVD_RENDERER_PILOT": "1", "WVD_READING_RULES_PILOT": "1", "WVD_LOGIC_PATH_PILOT": "0",
        "VISUAL_DIRECTOR_PROJECT_ROOT": str(ROOT), "VISUAL_DIRECTOR_THEME_PACK_DIR": temp,
    }), fixed_sample_plan(ts, plan):
        configure_theme_packs(Path(temp), reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
        parsed = parse_markdown(gallery.THEME_FIXTURE)
        bindings = gallery._fixture_bindings(parsed)
        catalog = registered_visual_system_catalog()
        for i, theme in enumerate(VISUAL_SYSTEM_ORDER, 1):
            label = html.escape(catalog[theme]["label"])
            foundation, article = ts.build_production_specimens(theme)
            palette = visual_system_configuration(theme)["palette"]
            cards = list(foundation) + [gallery._component_specimen(parsed, role, theme, palette, bindings)
                                        for role in CORE_THEME_COMPONENTS]
            assert len(cards) == 26
            for entire in (False, True):
                suffix = "-article.html" if entire else ".html"
                nav = ''.join(f'<a class="theme-link" href="{t}{suffix}"' + (' aria-current="page"' if t == theme else '')
                              + '>' + html.escape(catalog[t]["label"]) + '</a>' for t in VISUAL_SYSTEM_ORDER)
                tabs = "".join(f'<a href="{theme}{suf}"' + (' aria-current="page"' if suf == suffix else '') + '>' + text + '</a>'
                               for suf, text in ((".html", "全部组件 · 26"), ("-article.html", "整篇样稿")))
                if entire:
                    content = '<div class="article-frame">' + offline(article) + '</div>'
                else:
                    content = '<div class="sample-grid">' + ''.join(
                        f'<section class="sample"><h2 class="sample-label"><b>{n:02}</b>{html.escape(c["label"])}</h2>'
                        f'<iframe class="isolate" title="{html.escape(c["label"], quote=True)}" sandbox="allow-same-origin" onload="fit(this)" '
                        f'srcdoc="{srcdoc(offline(c["html"]))}"></iframe></section>'
                        for n, c in enumerate(cards, 1)) + '</div>'
                page = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                        f'<title>{label} · 组件评审</title><style>{CSS}</style>{RESIZE}<div class="review">'
                        f'<header class="mast"><div><span class="kicker">组件评审 / {i:02} OF 26</span><h1>{label}</h1></div>'
                        f'<nav class="review-nav" aria-label="样稿">{tabs}</nav></header><details class="theme-list"><summary>选择主题 · 26 套</summary>'
                        f'<nav class="theme-links" aria-label="主题">{nav}</nav></details>{content}</div></html>')
                (OUT / (theme + suffix)).write_text(page, encoding="utf-8")
                if i == 1 and not entire:
                    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"26 themes · 676 components · 26 articles: {OUT / 'index.html'}")


if __name__ == "__main__":
    generate()
