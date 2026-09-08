from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from postal_theme_fixture import postal_manifest, paper
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.theme_layouts import ROLE_FIELDS, render_layout, validate_layouts
from visual_director.theme_packs import configure_theme_packs, validate_theme_pack_manifest

ROOT = Path(__file__).resolve().parents[3]


def sample():
    template = json.loads((ROOT / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))
    return postal_manifest(template)


@pytest.mark.parametrize("style", [
    {"rotate": 90}, {"rotate": True}, {"shadow": "0 0 url(x)"},
    {"shadow": {"x": 0, "y": 0, "blur": 2, "color": []}},
    {"fit": "absolute"}, {"width": 9999}, {"margin": -25}, {"padding": -1},
])
def test_unsafe_geometry_is_rejected(style):
    assert validate_layouts({"quote": {"type": "field", "bind": "body", "style": style}})


def test_cutout_bounds_and_complete_content():
    node = paper([{"type": "field", "bind": "body"}])
    assert not validate_layouts({"quote": node})
    for change in ({"radius": 20}, {"fill": "url(x)"}, {"radius": 8, "pitch": 12}, {"style": {"background": "surface"}}):
        assert validate_layouts({"quote": {**node, **change}})
    assert validate_layouts({"quote": paper([{"type": "text", "text": "遗漏正文"}])})


def test_reference_theme_schema_and_editable_fields(tmp_path):
    configure_theme_packs(tmp_path, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    value = sample()
    assert set(value["design_system"]["layouts"]) == set(ROLE_FIELDS)
    assert not validate_layouts(value["design_system"]["layouts"])
    schema = json.loads((ROOT / "contracts/theme-pack-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(value)
    validate_theme_pack_manifest(value)
    config = {"palette": value["palette"], "generated_design_system": value["design_system"]}
    markup = render_layout("evidence_callout", {"body": "真实的**证据**与多行文字。"}, config)
    soup = BeautifulSoup(markup, "html.parser")
    assert soup.select_one('[data-theme-field="body"]').get_text() == "真实的证据与多行文字。"
    assert soup.select_one('[data-theme-field="body"]').name == "p"
    assert soup.select_one('[data-theme-drawing]')
    assert not soup.select_one('[data-theme-field="body"]').select('[data-theme-static]')
    assert value["palette"]["surface"] == "#FFFFFF"


def test_reference_component_and_theme_browser(tmp_path):
    from visual_director.brief_compiler import apply_visual_system
    from visual_director.parser import parse_markdown
    from visual_director.planner import generate_plans
    from visual_director.renderer import render_preview
    from visual_director.theme_gallery import THEME_FIXTURE, build_theme_gallery

    playwright = pytest.importorskip("playwright.sync_api")
    value = sample()
    output = ROOT / ".visual-director-test-runtime/layout-acceptance"
    output.mkdir(parents=True, exist_ok=True)
    pack_dir = tmp_path / "packs"
    (pack_dir / value["id"]).mkdir(parents=True)
    raw = json.dumps(value, ensure_ascii=False, indent=2)
    (pack_dir / value["id"] / "theme.json").write_text(raw, encoding="utf-8")
    configure_theme_packs(pack_dir, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    try:
        config = {"palette": value["palette"], "generated_design_system": value["design_system"]}
        prototype = render_layout("image_caption", {"caption": "把日常的片刻，寄给远方。", "media": {
            "src": "/api/v1/reference-review/sample-image", "alt": "项目自有的咖啡店示例配图",
        }}, config)
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 440, "height": 620}, device_scale_factor=2)
                page.route("**/api/v1/reference-review/sample-image", lambda route: route.fulfill(path=str(ROOT / "site/assets/generated/coffee-repeat-scene.webp"), content_type="image/webp"))
                page.set_content(f'<html><head><base href="http://127.0.0.1:8015"></head><body style="margin:0;padding:30px;background:#FFFFFF;">{prototype}</body></html>', wait_until="networkidle")
                box = page.locator('[data-theme-layout="image_caption"]').bounding_box()
                page.screenshot(path=str(output / "postal-component.png"), clip={"x": box["x"]-14, "y": box["y"]-14, "width": box["width"]+28, "height": box["height"]+28})
                page.close()
                # Six real role renderings, not a promotional mock-up.
                specimens = [
                    ("01 / 片头 · 远山邮票", "hero", {"title": "把路上的片刻，\n寄给远方的你", "kicker": "LETTERS FROM AFAR"}),
                    ("02 / 章节 · 邮戳波纹", "heading", {"title": "在日常里，找到值得留下的风景", "index": "01"}),
                    ("03 / 引用 · 展开的信笺", "quote", {"body": "不必等到走得很远，才开始记录。街角的一束光，也可以是寄给远方的一封信。"}),
                    ("04 / 图文 · 风景明信片", "image_caption", {"caption": "街角的午后，一次不赶时间的停留。", "media": {"src": "/api/v1/reference-review/sample-image", "alt": "咖啡店示例图"}}),
                    ("05 / 步骤 · 邮路站点", "logic_path", {"items": ["观察：找到真正触动你的片刻", "记录：留下声音、颜色与细节", "分享：把这份感受寄给想念的人"]}),
                    ("06 / 总结 · 收信小卡", "section_summary", {"items": ["给日常留一点空白", "记住具体的人与风景", "让一次分享成为新的连接"]}),
                ]
                cards = ''.join(f'<article><h2>{title}</h2>{render_layout(role, payload, config)}</article>' for title, role, payload in specimens)
                board = ('<html><head><base href="http://127.0.0.1:8015"><meta charset="utf-8"><style>'
                         'body{margin:0;background:#f0f1ef;color:#373936;font-family:"Microsoft YaHei",sans-serif;padding:32px;}'
                         'main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;max-width:1320px;margin:auto;}'
                         'article{background:white;padding:24px;min-width:0;}h2{font-size:12px;font-weight:400;color:#677d82;margin:0 0 24px;padding-bottom:12px;border-bottom:1px solid #eee;}'
                         '</style></head><body><main>' + cards + '</main></body></html>')
                (output / 'postal-six-components.html').write_text(board, encoding='utf-8')
                board_page = browser.new_page(viewport={"width": 1420, "height": 1180}, device_scale_factor=2)
                board_page.route("**/api/v1/reference-review/sample-image", lambda route: route.fulfill(path=str(ROOT / "site/assets/generated/coffee-repeat-scene.webp"), content_type="image/webp"))
                board_page.set_content(board, wait_until="networkidle")
                board_page.locator('main').screenshot(path=str(output / 'postal-six-components.png'))
                board_page.close()
                # Separate from the component prototype: complete article/role family.
                article = parse_markdown(THEME_FIXTURE + "\n\n## 长文本验证\n\n" + "正文不能被装饰遮挡。" * 70 + "\n\n" + "LONGTOKEN" * 24)
                plan = apply_visual_system(generate_plans(article, "tutorial_steps", 5)[0], value["id"], recent_summaries=[])
                document = render_preview(article, plan)
                gallery = next(t for t in build_theme_gallery() if t["id"] == value["id"])["full_preview_html"]
                (output / "postal.theme.json").write_text(raw, encoding="utf-8")
                (output / "postal.html").write_text(document, encoding="utf-8")
                for width in (320, 390, 600):
                    page = browser.new_page(viewport={"width": width, "height": 1100})
                    try:
                        for name, markup in (("article", document), ("gallery", gallery)):
                            page.set_content(markup, wait_until="load")
                            surface = page.locator('main').first if name == 'gallery' else page.locator('body')
                            assert surface.evaluate("e=>getComputedStyle(e).backgroundColor") == 'rgb(255, 255, 255)'
                            overflow = page.evaluate("""() => [...document.querySelectorAll('section,main,p,h1')].filter(e=>e.clientWidth>0 && e.scrollWidth>e.clientWidth+2).map(e=>({tag:e.tagName,text:e.textContent.slice(0,50),width:e.clientWidth,scroll:e.scrollWidth}))""")
                            assert not overflow, (width, name, overflow)
                            fields = page.locator('[data-theme-field]')
                            assert fields.count() > 10
                            if name == "gallery":
                                assert page.locator('[data-theme-cutout]').count() > 0
                            # Decorations must not intercept clicks at field centers.
                            covered = fields.evaluate_all("""es=>es.filter(e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1||r.top<0||r.bottom>innerHeight)return false; const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2); return hit && !e.contains(hit);}).map(e=>e.textContent.slice(0,30))""")
                            assert not covered, covered
                            if width in (390, 600):
                                page.screenshot(path=str(output / f"postal-{name}-{width}.png"), full_page=True)
                            if width == 600 and name == "gallery":
                                page.screenshot(path=str(output / "postal-first-screen.png"))
                                page.evaluate('window.scrollTo(0, 1100)')
                                page.screenshot(path=str(output / "postal-middle-screen.png"))
                                page.evaluate('window.scrollTo(0, 2350)')
                                page.screenshot(path=str(output / "postal-lower-screen.png"))
                    finally:
                        page.close()
            finally:
                browser.close()
    finally:
        configure_theme_packs(tmp_path / "clean", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)


def test_every_postal_role_preserves_long_content_in_browser():
    playwright = pytest.importorskip('playwright.sync_api')
    value = sample()
    config = {'palette': value['palette'], 'generated_design_system': value['design_system']}
    long_text = '需要完整保留的长文本与细节。' * 12 + 'LONGTOKEN' * 18
    fragments = []
    expected = 0
    for role, (fields, collection) in ROLE_FIELDS.items():
        payload = {key: long_text for key in fields}
        expected += len(fields)
        payload['index'] = '12'
        if collection:
            payload[collection] = ([long_text, long_text] if collection == 'items'
                                   else [{'title': long_text, 'body': long_text}] * 2)
            expected += 2 if collection == 'items' else 4
        if role in ('image_caption', 'closing_cta'):
            payload['media'] = {'specimen': True}
        fragments.append(render_layout(role, payload, config))
    markup = '<body style="margin:0;padding:24px;background:#fff">' + ''.join(fragments) + '</body>'
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in (320, 390, 600):
                page = browser.new_page(viewport={'width': width, 'height': 900})
                page.set_content(markup)
                fields = page.locator('[data-theme-field]')
                assert fields.count() == expected
                assert all(text == long_text for text in fields.all_text_contents())
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 2')
                assert not fields.evaluate_all('es => es.some(e => e.scrollWidth > e.clientWidth + 2 || e.scrollHeight > e.clientHeight + 2)')
                # Check centers across the whole document, not only its first screen.
                for field in fields.all():
                    field.evaluate('e => e.scrollIntoView({block:"center"})')
                    assert field.evaluate('e => { const r=e.getBoundingClientRect(); const y=Math.max(1,Math.min(innerHeight-1,r.top+r.height/2)); return e.contains(document.elementFromPoint(r.left+r.width/2,y)); }')
                page.close()
        finally:
            browser.close()
