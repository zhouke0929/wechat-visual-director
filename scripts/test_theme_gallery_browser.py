"""Read-only UI smoke test. Public fixtures only; never starts a user database.

Requires the optional Playwright test environment and built apps/web/dist.
Use --serve to keep the isolated public-fixture preview available after testing.
"""
from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class PublicFixtureHandler(QuietHandler):

    def do_GET(self):
        if self.path == "/health":
            content = json.dumps({"status": "ok", "application_version": (ROOT / "VERSION").read_text().strip()}).encode()
        elif self.path == "/api/v1/theme-gallery":
            payload = json.loads((ROOT / "site/data/themes.json").read_text(encoding="utf-8"))
            if getattr(self.server, "with_unavailable_fixture", False):
                payload["themes"].append({"id": "broken_fixture", "label": "公开故障试样", "source": "custom",
                                         "availability": "unavailable", "diagnostic": {"code": "theme_pack_load_failed", "message": "主题文件无法加载，原文件未删除。"}})
            content = json.dumps(payload, ensure_ascii=False).replace("assets/theme-stickers/", "/gallery-assets/").encode()
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def translate_path(self, path):
        if path.startswith("/gallery-assets/"):
            return str(ROOT / "site/assets/theme-stickers" / Path(path.split("?", 1)[0]).name)
        if path.startswith("/theme-gallery"):
            return str(ROOT / "apps/web/dist/index.html")
        return super().translate_path(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--web-port", type=int, default=18511)
    parser.add_argument("--site-port", type=int, default=18512)
    parser.add_argument("--with-unavailable-fixture", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp/theme-discovery-review")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    servers = [
        ThreadingHTTPServer(("127.0.0.1", args.web_port), partial(PublicFixtureHandler, directory=str(ROOT / "apps/web/dist"))),
        ThreadingHTTPServer(("127.0.0.1", args.site_port), partial(QuietHandler, directory=str(ROOT / "site"))),
    ]
    servers[0].with_unavailable_fixture = args.with_unavailable_fixture
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    errors = []
    checks = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            for width in (1440, 405):
                page.set_viewport_size({"width": width, "height": 1000})
                page.goto(f"http://127.0.0.1:{args.site_port}", wait_until="networkidle")
                page.screenshot(path=str(output / f"site-{width}-hero.png"))
                page.locator("#faq").scroll_into_view_if_needed()
                page.screenshot(path=str(output / f"site-{width}-faq.png"))
                assert page.locator(".theme-button").count() == 12
                assert page.locator("#specimenSelect option").count() == 27
                for button in page.locator(".theme-button").all():
                    button.click()
                    page.locator("#specimenSelect").select_option("lead")
                    assert page.locator('#themePreview [data-content-role="lead"]').count() == 1
                    page.locator("#specimenSelect").select_option("quote")
                    assert page.locator('#themePreview [data-editor-block-type="quote"]').count() == 1
                    page.locator("#specimenSelect").select_option("image_caption")
                    page.wait_for_function("[...document.querySelectorAll('#themePreview img')].every(i => i.complete && i.naturalWidth > 0)")
                page.locator("#custom-themes").scroll_into_view_if_needed()
                page.screenshot(path=str(output / f"site-{width}.png"))
                page.locator("[data-copy-theme]").click()
                assert "一整套新的主题" in page.evaluate("navigator.clipboard.readText()")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "site horizontal overflow"
                checks.append(f"site {width}: 12 themes, 26 specimens, loaded images, theme prompt")

                page.goto(f"http://127.0.0.1:{args.web_port}/theme-gallery/light_reading", wait_until="networkidle")
                page.get_by_role("button", name="02　主题部件库").click()
                assert page.locator('[id^="foundation-"]').count() == 14
                assert page.locator('[id^="component-"]').count() == 12
                assert page.get_by_role("navigation", name="全部部件索引").locator("a").count() == 26
                assert page.locator('#foundation-lead [data-content-role="lead"]').count() == 1
                page.locator('#foundation-lead').screenshot(path=str(output / f"gallery-lead-{width}.png"))
                page.locator('#foundation-quote').scroll_into_view_if_needed()
                page.screenshot(path=str(output / f"gallery-quote-{width}.png"))
                page.locator('#foundation-ordered_list').scroll_into_view_if_needed()
                page.screenshot(path=str(output / f"gallery-list-{width}.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "gallery horizontal overflow"
                page.get_by_role("button", name="01　整篇样张").click()
                assert page.locator('[data-gallery-production-article]').count() == 1
                assert page.locator('[data-gallery-production-article] [data-editor-block-type="quote"]').count() == 1
                page.goto(f"http://127.0.0.1:{args.web_port}", wait_until="networkidle")
                page.get_by_role("button", name="我想创作新主题").click()
                visible_prompt = page.locator("#agent-writing-prompt").input_value()
                assert "一整套新的主题" in visible_prompt
                page.get_by_role("button", name="复制给 Agent 的指令").click()
                copied_prompt = page.evaluate("navigator.clipboard.readText()")
                assert copied_prompt == visible_prompt, "clipboard differs from visible theme instructions"
                assert "组件参考图" in copied_prompt
                assert page.locator(".agent-start-next").is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "home prompt horizontal overflow"
                page.locator(".agent-start").screenshot(path=str(output / f"home-theme-{width}.png"))
                checks.append(f"workbench {width}: full foundation/semantic navigation and home prompt")
                if args.with_unavailable_fixture:
                    page.goto(f"http://127.0.0.1:{args.web_port}/theme-gallery", wait_until="networkidle")
                    diagnostic = page.get_by_role("status", name="暂不可用的主题")
                    assert diagnostic.is_visible() and "公开故障试样" in diagnostic.inner_text()
                    assert page.locator('a[href^="/theme-gallery/"]').count() >= 12
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    diagnostic.screenshot(path=str(output / f"unavailable-notice-{width}.png"))
                    page.goto(f"http://127.0.0.1:{args.web_port}/theme-gallery/broken_fixture", wait_until="networkidle")
                    assert "暂不可用" in page.locator("h1").inner_text()
                    assert page.get_by_role("link", name="返回主题样本册").is_visible()
                    checks.append(f"unavailable theme {width}: visible diagnostic, healthy themes retained, detail recovery")

            # Denied clipboard must offer the correct manual prompt, not install text.
            page.goto(f"http://127.0.0.1:{args.site_port}", wait_until="networkidle")
            page.evaluate("Object.defineProperty(navigator, 'clipboard', {value:{writeText:async()=>{throw Error('denied')}}, configurable:true}); document.execCommand=()=>false")
            page.locator('[data-copy-theme]').click()
            assert page.locator('#installDialog').is_visible()
            assert "一整套新的主题" in page.locator('#installPromptText').input_value()
            page.locator('.dialog-close').click()
            page.locator('[data-copy-install]').first.click()
            assert "安装或升级完整" in page.locator('#installPromptText').input_value()
            assert not errors, errors
            checks.append("clipboard denied: correct manual theme/install instructions; no JavaScript errors")
            browser.close()
        report = {"ok": True, "checks": checks, "screenshots": str(output), "database_access": False}
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if args.serve:
            print(f"Public-fixture gallery: http://127.0.0.1:{args.web_port}/theme-gallery/light_reading\nPublic site preview: http://127.0.0.1:{args.site_port}/#custom-themes", flush=True)
            threading.Event().wait()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
