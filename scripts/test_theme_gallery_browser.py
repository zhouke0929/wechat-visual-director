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
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class PublicFixtureHandler(QuietHandler):

    def do_GET(self):
        if self.path == "/health":
            content = json.dumps({"status": "ok", "application_version": (ROOT / "VERSION").read_text().strip()}).encode()
        elif urlsplit(self.path).path == "/api/v1/theme-gallery":
            payload = json.loads((ROOT / "site/data/themes.json").read_text(encoding="utf-8"))
            if getattr(self.server, "with_unavailable_fixture", False):
                payload["themes"].append({"id": "broken_fixture", "label": "公开故障试样", "source": "custom",
                                         "availability": "unavailable", "diagnostic": {"code": "theme_pack_load_failed", "message": "主题文件无法加载，原文件未删除。"}})
            query = parse_qs(urlsplit(self.path).query)
            if query.get("theme_id"):
                payload["themes"] = [theme for theme in payload["themes"] if theme["id"] == query["theme_id"][0]]
            if query.get("summary") == ["true"]:
                for theme in payload["themes"]:
                    theme["foundation_count"] = len(theme.get("foundation_specimens", []))
                    for key in ("components", "rhythm_primitives", "foundation_specimens", "article_preview_html", "full_preview_html"):
                        theme.pop(key, None)
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
                choices = page.locator("#themeChoices button")
                choices.first.wait_for()
                assert choices.count() == 26
                assert page.get_by_role("button", name="浅浮雕按钮", exact=True).count() == 0
                assert page.get_by_role("button", name="票面与副联", exact=True).count() == 0
                for button in choices.all():
                    button.click()
                    live = page.locator("#themeLive")
                    assert live.get_attribute("data-theme") == button.get_attribute("data-theme")
                    assert live.locator("[data-gallery-production-article] > main").count() == 1
                    assert live.locator('[data-editor-block-type="quote"]').count() >= 1
                    assert live.locator("img").evaluate_all(
                        "imgs => Promise.all(imgs.map(img => img.decode())).then(() => true)"
                    )
                page.locator("#custom-themes").scroll_into_view_if_needed()
                page.screenshot(path=str(output / f"site-{width}.png"))
                page.locator("[data-copy-theme]").click()
                assert "一整套新的主题" in page.evaluate("navigator.clipboard.readText()")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "site horizontal overflow"
                checks.append(f"site {width}: 26 themes, complete articles, loaded images, theme prompt")

                gallery = f"http://127.0.0.1:{args.web_port}/theme-gallery"
                page.goto(gallery, wait_until="networkidle")
                nav = page.get_by_role("navigation", name="工作台导航")
                assert nav.locator('[aria-current="page"]').inner_text() == "主题样本册"
                brand = page.get_by_role("link", name="视觉主编首页")
                gallery_brand = brand.bounding_box()
                cards = page.get_by_role("region", name="官方视觉主题").get_by_role("article")
                assert cards.count() == 30
                # The optional diagnostic fixture adds a visible warning before the grid.
                diagnostic = page.get_by_role("status", name="暂不可用的主题")
                diagnostic_height = diagnostic.bounding_box()["height"] + 24 if diagnostic.count() else 0
                assert cards.first.bounding_box()["y"] - diagnostic_height < 380, "theme cards should start near the top"
                first_two = [cards.nth(i).bounding_box() for i in (0, 1)]
                assert first_two[0]["y"] == first_two[1]["y"], "compact multi-column catalog"
                group_counts = {"清新自然": 4, "生活手帐": 4, "手作绘本": 6, "东方意境": 3,
                                "杂志与海报": 4, "光影叙事": 3, "数字与导视": 6}
                group_filters = page.get_by_role("group", name="按主题分组筛选")
                assert group_filters.get_by_role("button").all_text_contents() == ["全部", *group_counts]
                filtered_links = []
                for group, count in group_counts.items():
                    group_filters.get_by_role("button", name=group, exact=True).click()
                    assert cards.count() == count
                    filtered_links.extend(cards.get_by_role("link").evaluate_all("(links) => links.map(link => link.href)"))
                assert len(set(filtered_links)) == len(filtered_links) == 30
                page.get_by_role("button", name="全部", exact=True).click()
                assert cards.count() == 30
                page.get_by_role("button", name="我的主题", exact=False).click()
                assert page.get_by_role("button", name="导入第一套主题").is_visible()
                page.get_by_role("button", name="官方主题", exact=False).click()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(output / f"gallery-index-{width}.png"))
                cards.last.get_by_role("link").click()
                page.locator('[data-gallery-production-article]').wait_for()
                assert page.evaluate("window.scrollY") <= 1, "opening a lower card should show the detail from its start"

                page.goto(f"{gallery}/light_reading", wait_until="networkidle")
                preview = page.locator('[data-gallery-production-article]')
                assert preview.bounding_box()["y"] < 400, "article preview should start near the top"
                page.screenshot(path=str(output / f"gallery-detail-{width}.png"))
                page.get_by_role("button", name="02　主题部件库").click()
                assert page.locator('[id^="foundation-"]').count() == 14
                assert page.locator('[id^="component-"]').count() == 12
                page.get_by_text("部件索引 · 26 个", exact=True).click()
                index = page.get_by_role("navigation", name="全部部件索引")
                assert index.is_visible() and index.locator("a").count() == 26
                assert page.locator('#foundation-lead [data-content-role="lead"]').count() == 1
                page.locator('#foundation-lead').screenshot(path=str(output / f"gallery-lead-{width}.png"))
                page.locator('#foundation-quote').scroll_into_view_if_needed()
                page.screenshot(path=str(output / f"gallery-quote-{width}.png"))
                page.locator('#foundation-ordered_list').scroll_into_view_if_needed()
                page.screenshot(path=str(output / f"gallery-list-{width}.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "gallery horizontal overflow"
                page.get_by_role("button", name="01　整篇样张").click()
                assert page.locator('[data-gallery-production-article]').count() == 1
                assert preview.bounding_box()["y"] >= 0, "switching modes from lower down should show the start"
                assert page.locator('[data-gallery-production-article] [data-editor-block-type="quote"]').count() == 1
                page.goto(f"http://127.0.0.1:{args.web_port}/theme-gallery/city_wayfinding", wait_until="networkidle")
                page.get_by_role("heading", name="城市导视", exact=True).wait_for()
                assert page.locator('[data-gallery-production-article] [data-theme-layout="heading"]').count() > 0
                page.locator("#theme-delivery summary").click()
                assert page.get_by_text("该版验收稿已通过复制粘贴和 API 保存实测。", exact=False).is_visible()
                page.get_by_role("button", name="02　主题部件库").click()
                assert page.locator('[id^="foundation-"]').count() == 14
                assert page.locator('[id^="component-"]').count() == 12
                component_cards = page.locator('[id^="component-"]')
                assert component_cards.locator('[class*="specimenInfo"] > p').count() == 0, "omit variant names"
                assert component_cards.locator('[class*="specimenInfo"] > span').count() == 12, "keep only component index labels"
                assert component_cards.locator('[class*="componentCanvas"]').count() == 12, "retain all previews"
                page.goto(f"http://127.0.0.1:{args.web_port}", wait_until="networkidle")
                assert brand.bounding_box() == gallery_brand, "homepage and catalog share the same brand header"
                assert nav.locator("[aria-current]").count() == 0
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
                checks.append(f"workbench {width}: compact catalog, filters, first-screen preview, all components, home prompt")
                if args.with_unavailable_fixture:
                    page.goto(f"http://127.0.0.1:{args.web_port}/theme-gallery", wait_until="networkidle")
                    diagnostic = page.get_by_role("status", name="暂不可用的主题")
                    assert diagnostic.is_visible() and "公开故障试样" in diagnostic.inner_text()
                    assert page.locator('a[href^="/theme-gallery/"]').count() >= 30
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
