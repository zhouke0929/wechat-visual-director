"""Local Chromium checks, not a substitute for WeChat backend verification."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from theme_layout_fixtures import example_layouts
from midnight_theme_fixture import midnight_manifest
from postal_theme_fixture import postal_manifest
from visual_director.brief_compiler import apply_visual_system
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director.renderer import render_preview
from visual_director.theme_gallery import THEME_FIXTURE, build_theme_gallery
from visual_director.theme_packs import configure_theme_packs, validate_theme_pack_manifest

ROOT = Path(__file__).resolve().parents[3]


def test_clipboard_checks_transformed_bounds_not_only_scroll_width():
    from visual_director.delivery import _clipboard_static_label_geometry
    playwright = pytest.importorskip("playwright.sync_api")
    original = '<main><p data-theme-static="true" style="margin:0;box-sizing:border-box;width:52px;padding:8px 0;border:3px double #873D4B;border-radius:64px;font-size:18.36px;line-height:1.5;transform:rotate(-6deg);">01</p></main>'
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except playwright.Error as exc:
            pytest.skip(f"Local Chromium not available: {exc}")
        try:
            page = browser.new_page()
            for width in (320, 375, 405, 677):
                page.set_viewport_size({"width":width,"height":900})
                page.set_content('<style>body{margin:0}</style>'+original)
                assert page.locator('p').evaluate('(e)=>e.getBoundingClientRect().left') < -2
                page.set_content('<style>body{margin:0}</style>'+_clipboard_static_label_geometry(original))
                assert page.locator('p').evaluate('(e)=>e.getBoundingClientRect().left') >= 0
                assert page.locator('p').inner_text() == '01'
        finally:
            browser.close()


def test_authored_layouts_at_phone_and_desktop_widths(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    pack_dir = tmp_path / "packs"
    configure_theme_packs(pack_dir, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    template = json.loads((ROOT / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))
    output = ROOT / ".visual-director-test-runtime/layout-acceptance"
    output.mkdir(parents=True, exist_ok=True)
    try:
        for direction in ("ledger", "herbarium", "signal"):
            manifest = json.loads(json.dumps(template))
            manifest.update(id=f"layout_{direction}", name={"ledger": "纸上来信", "herbarium": "草木手记", "signal": "信号档案"}[direction], english=direction.upper())
            manifest["description"] = {
                "ledger": "暖白纸面、朱红索引与细线分栏，以报刊式层级承载观点与现场记录。",
                "herbarium": "草木绿、柔和纸面与舒展的弧形留白，适合自然观察和人文叙事。",
                "signal": "蓝色坐标、非对称侧栏和清楚的编号，让知识、证据与行动形成可读的秩序。",
            }[direction]
            manifest["design_system"]["layouts"] = example_layouts(direction)
            manifest["design_system"]["typography"]["body_scale"] = 1.05
            if direction == "ledger":
                manifest["palette"].update(primary="#302A27", secondary="#B3A395", accent="#A13C32", ink="#302A27", surface="#FFFCF5", pale="#F3EBDF")
            elif direction == "herbarium":
                manifest["palette"].update(primary="#3D6247", secondary="#A1B59A", accent="#8A5935", ink="#293B2C", surface="#FFFEF7", pale="#F0F4E7")
                manifest["design_system"]["typography"]["heading_scale"] = .95
            else:
                manifest["palette"].update(primary="#214DBA", secondary="#9AB1D9", accent="#A34718", ink="#182841", surface="#FDFEFF", pale="#EDF3FC")
            manifest["palette"]["secondary_pale"] = manifest["palette"]["pale"]
            manifest = validate_theme_pack_manifest(manifest)
            destination = pack_dir / manifest["id"]
            destination.mkdir(parents=True)
            raw = json.dumps(manifest, ensure_ascii=False, indent=2)
            (destination / "theme.json").write_text(raw, encoding="utf-8")
            (output / f"{direction}.theme.json").write_text(raw, encoding="utf-8")
        midnight = validate_theme_pack_manifest(midnight_manifest(template))
        destination = pack_dir / midnight["id"]
        destination.mkdir(parents=True)
        raw = json.dumps(midnight, ensure_ascii=False, indent=2)
        (destination / "theme.json").write_text(raw, encoding="utf-8")
        (output / "midnight.theme.json").write_text(raw, encoding="utf-8")
        configure_theme_packs(pack_dir, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
        galleries = {g["id"]: g for g in build_theme_gallery()}
        # Long Chinese prose, unbroken Latin text, bold, multiple semantic structures.
        article = parse_markdown(THEME_FIXTURE + "\n\n## 补充验证\n\n" + "长文本不能溢出或丢失。" * 60 + "\n\n" + "LONGTOKEN" * 24)
        with playwright.sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except playwright.Error as exc:
                pytest.skip(f"Local Chromium not available: {exc}")
            try:
                for direction in ("ledger", "herbarium", "signal", "midnight"):
                    theme_id = "midnight_screening" if direction == "midnight" else f"layout_{direction}"
                    plan = apply_visual_system(generate_plans(article, "tutorial_steps", 5)[0], theme_id, recent_summaries=[])
                    document = render_preview(article, plan)
                    (output / f"{direction}.html").write_text(document, encoding="utf-8")
                    for width in (320, 390, 600):
                        page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
                        try:
                            for name, markup in (("article", document), ("gallery", galleries[theme_id]["full_preview_html"])):
                                page.set_content(markup, wait_until="load")
                                overflow = page.evaluate("""() => [...document.querySelectorAll('section,main,p,h1,blockquote,table')].filter(e => e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 2).map(e => ({tag:e.tagName,role:e.getAttribute('data-theme-layout'),width:e.clientWidth,scroll:e.scrollWidth,text:e.textContent.slice(0,40)}))""")
                                assert not overflow, (direction, width, name, overflow)
                                if name == "article":
                                    assert page.locator('h1[data-editor-title="true"]').count() == 1
                                    assert page.locator('[data-theme-field]').count() > 5
                                if width in (390, 600):
                                    page.screenshot(path=str(output / f"{direction}-{name}-{width}.png"), full_page=True)
                                if direction == "midnight" and width == 600 and name == "article":
                                    page.screenshot(path=str(output / "midnight-first-screen.png"))
                        finally:
                            page.close()
            finally:
                browser.close()
    finally:
        configure_theme_packs(tmp_path / "clean", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)


@pytest.mark.parametrize("theme_factory", [midnight_manifest, postal_manifest], ids=["midnight", "postal"])
def test_custom_layout_inline_save_and_mobile_preview(tmp_path, monkeypatch, theme_factory):
    from urllib.parse import urlsplit
    from fastapi.testclient import TestClient
    from test_api_workflow import _prepare_publication_ready_task
    from visual_director.image_provider import ManualImageProvider
    from visual_director.main import create_app
    from visual_director.text_planner import MockTextPlannerProvider

    playwright = pytest.importorskip("playwright.sync_api")
    if not (ROOT / "apps/web/dist/index.html").exists():
        pytest.skip("Build workbench before browser integration test")
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(tmp_path / "private.env"))
    monkeypatch.setenv("VISUAL_DIRECTOR_THEME_PACK_DIR", str(tmp_path / "packs"))
    monkeypatch.setenv("VISUAL_DIRECTOR_WEB_DIST", str(ROOT / "apps/web/dist"))
    app = create_app(str(tmp_path / "editor.db"), image_provider=ManualImageProvider(), text_planner_provider=MockTextPlannerProvider())
    with TestClient(app) as client:
        manifest = json.loads((ROOT / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))
        manifest = theme_factory(manifest)
        installed = client.post("/api/v1/theme-packs", headers={"X-Local-Intent": "local-operator"}, files={"theme_file": ("theme.json", json.dumps(manifest).encode(), "application/json")})
        assert installed.status_code == 200, installed.text
        task, plan = _prepare_publication_ready_task(client)
        changed = client.patch(f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/theme', json={"visual_system": manifest["id"], "expected_plan_revision": plan["revision"]})
        assert changed.status_code == 200, changed.text
        endpoint = f'/api/v1/article-tasks/{task["id"]}/content-editor'
        editor = client.get(endpoint).json()
        paragraph = next(b for b in editor["blocks"] if b["type"] == "paragraph")
        saved = client.patch(endpoint, json={"expected_revision": editor["revision"], "target": "block", "block_id": paragraph["block_id"], "content": "长文章中的编辑位置应该保持。" * 90})
        assert saved.status_code == 200, saved.text
        with playwright.sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except playwright.Error as exc:
                pytest.skip(f"Local Chromium not available: {exc}")
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1000})

                def handle(route):
                    request = route.request
                    url = urlsplit(request.url)
                    if url.hostname not in {"127.0.0.1", "localhost"}:
                        route.fulfill(status=204, body="")
                        return
                    response = client.request(request.method, url.path + ("?" + url.query if url.query else ""), content=request.post_data_buffer, headers={k: v for k, v in request.headers.items() if k not in {"host", "content-length"}})
                    route.fulfill(status=response.status_code, body=response.content, headers={k: v for k, v in response.headers.items() if k not in {"content-length", "content-encoding"}})

                page.route("**/*", handle)
                page.goto(f'http://127.0.0.1:8000/tasks/{task["id"]}', wait_until="networkidle")
                page.wait_for_selector("iframe")
                frame = next(f for f in page.frames if f != page.main_frame)
                frame.wait_for_selector('html[data-workbench-editor-contract="complete"]')
                assert frame.locator('[data-theme-static][contenteditable="true"]').count() == 0
                target = frame.locator('[data-theme-field="body"][contenteditable="true"]').last
                target.scroll_into_view_if_needed()
                old = target.inner_text()
                scroll_before = frame.evaluate("window.scrollY")
                assert scroll_before > 0
                updated = "修改后：" + old
                with page.expect_response(lambda r: r.request.method == "PATCH" and endpoint in r.url) as response:
                    target.fill(updated)
                    page.get_by_role("tab", name="内容校对", exact=True).click()
                assert response.value.status == 200
                frame.wait_for_function("document.documentElement.dataset.workbenchEditorContract === 'complete'")
                frame.wait_for_function("expected => Math.abs(window.scrollY - expected) < 5", arg=scroll_before, timeout=3000)
                assert abs(frame.evaluate("window.scrollY") - scroll_before) < 5
                latest = client.get(endpoint).json()
                assert any(b["content"] == updated for b in latest["blocks"])
                page.get_by_role("tab", name="手机预览", exact=True).click()
                mobile = next(f for f in page.frames if f != page.main_frame)
                mobile.wait_for_function("document.documentElement.dataset.workbenchEditable !== 'true'")
                mobile.get_by_text(updated, exact=True).wait_for()
                assert mobile.locator('[contenteditable="true"]').count() == 0
                assert not mobile.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
                page.screenshot(path=str(ROOT / ".visual-director-test-runtime/layout-acceptance/workbench-mobile.png"))
            finally:
                browser.close()
    configure_theme_packs(tmp_path / "clean", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
