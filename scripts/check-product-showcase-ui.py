"""Render the public gallery with local assets; no workbench or private data.

Requires Playwright and a Chromium browser. Example:
python scripts/check-product-showcase-ui.py --channel msedge --artifacts tmp/showcase
Use --url only to verify an already running/deployed public showcase.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
LOCAL_URL = "http://127.0.0.1:8765/"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default="msedge")
    parser.add_argument("--url")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--refresh-promotional-assets", action="store_true", help="Refresh the public hero and theme screenshots after checking the gallery")
    args = parser.parse_args()
    if args.artifacts:
        args.artifacts.mkdir(parents=True, exist_ok=True)
    url = args.url or LOCAL_URL
    results = {"viewports": [], "themes": 0, "phone_checks": 0, "articles": 0, "copy": False, "manual_copy": False, "retry": False}

    def local_asset(route):
        path = urlparse(route.request.url).path.lstrip("/") or "index.html"
        asset = (SITE / path).resolve()
        if asset.is_relative_to(SITE) and asset.is_file():
            route.fulfill(path=str(asset))
        else:
            route.fulfill(status=404, body="Not found")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel=args.channel)

        def new_context(**kwargs):
            context = browser.new_context(reduced_motion="reduce", **kwargs)
            if not args.url:
                context.route(LOCAL_URL + "**", local_asset)
            return context

        # Render source text and vectors at high density, rather than upscaling
        # a low-resolution crop when GitHub expands the README image.
        context = new_context(
            permissions=["clipboard-read", "clipboard-write"],
            device_scale_factor=3 if args.refresh_promotional_assets else 1,
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle")
        page.locator(".theme-button").nth(11).wait_for()
        assert page.locator("main#main > section").count() == 3
        assert page.locator(".edition").count() == 3
        assert page.locator("#faq .notes-content").is_visible()
        assert page.locator("#faq summary").count() == 0
        assert page.locator(".site-nav").get_by_role("link", name="看成稿", exact=True).count() == 0
        assert page.locator(".site-nav").get_by_role("link", name="换主题", exact=True).count() == 0
        assert page.evaluate("[...document.querySelectorAll('[id]')].map(e=>e.id).length === new Set([...document.querySelectorAll('[id]')].map(e=>e.id)).size")

        def check_phone():
            geometry = page.locator("#themePreview").evaluate("""el => {
                const footer = document.querySelector('.phone-actions');
                el.scrollTop = el.scrollHeight;
                const article = el.querySelector('main');
                const last = article.lastElementChild || article;
                return {
                    fits: el.scrollWidth <= el.clientWidth,
                    height: el.clientHeight,
                    separated: el.getBoundingClientRect().bottom <= footer.getBoundingClientRect().top + 1,
                    endVisible: last.getBoundingClientRect().bottom <= el.getBoundingClientRect().bottom + 1,
                    reachedEnd: Math.abs(el.scrollHeight - el.scrollTop - el.clientHeight) <= 1,
                };
            }""")
            assert geometry["fits"] and geometry["height"] > 300, geometry
            assert geometry["separated"] and geometry["endVisible"] and geometry["reachedEnd"], geometry
            page.locator("#themePreview").evaluate("el => el.scrollTop = 0")
            results["phone_checks"] += 1

        for width, height in ((360, 800), (390, 844), (768, 1024), (1024, 900), (1440, 1000), (1920, 1080)):
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("window.scrollTo(0, 0)")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Overflow at {width}px"
            page_height = page.evaluate("document.documentElement.scrollHeight")
            # The installation notes are now always visible, not a closed disclosure.
            assert page_height < (3700 if width < 1000 else 2900), (width, page_height)
            assert page.locator("#faq .notes-content").is_visible()
            check_phone()
            results["viewports"].append({"width": width, "height": page_height})
            if args.artifacts and width in (390, 1440):
                page.screenshot(path=str(args.artifacts / f"gallery-{width}.png"), full_page=True)
                page.screenshot(path=str(args.artifacts / f"hero-{width}.png"))
                page.locator("#start").screenshot(path=str(args.artifacts / f"installation-{width}.png"))

        page.set_viewport_size({"width": 1440, "height": 1000})
        if args.refresh_promotional_assets:
            page.evaluate("window.scrollTo(0,0)")
            page.locator(".hero").screenshot(path=str(ROOT / "docs/assets/readme/product-showcase-hero.png"))
            # Include the rotated cards' protruding edges, not just their parent box.
            gallery = page.locator(".edition-gallery").bounding_box()
            clip_x = max(0, gallery["x"] - 45)
            page.screenshot(path=str(ROOT / "docs/assets/readme/product-showcase-articles.png"), clip={
                "x": clip_x, "y": gallery["y"] - 12,
                "width": min(1440 - clip_x, gallery["width"] + 90), "height": gallery["height"] + 24,
            })
        for button in page.locator(".theme-button").all():
            button.click()
            assert button.get_attribute("aria-pressed") == "true"
            assert page.locator(".theme-button.active").count() == 1
            assert page.locator("#themePreview > main").count() == 1
            assert page.locator("#themePreview").evaluate("el => el.scrollTop === 0")
            assert button.locator("strong").inner_text() == page.locator("#themeLabel").inner_text()
            check_phone()
            results["themes"] += 1
        # All themes must also fit the narrow phone, not just the default theme.
        page.set_viewport_size({"width": 360, "height": 800})
        for button in page.locator(".theme-button").all():
            button.click()
            check_phone()
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator(".theme-button").last.press("Home")
        assert page.locator(".theme-button").first.get_attribute("aria-pressed") == "true"
        page.locator(".theme-button").first.press("ArrowRight")
        assert page.locator(".theme-button").nth(1).get_attribute("aria-pressed") == "true"
        page.locator('[data-theme-id="youth_campus"]').click()
        # Leave room for the sticky navigation above a full-height phone shot.
        theme_height = page.locator("#themes").bounding_box()["height"]
        page.set_viewport_size({"width": 1440, "height": max(1000, int(theme_height) + 120)})
        page.locator("#themes").evaluate("el => window.scrollTo(0, el.getBoundingClientRect().top + scrollY - 90)")
        if args.artifacts:
            page.locator("#themes").screenshot(path=str(args.artifacts / "themes.png"))
        if args.refresh_promotional_assets:
            page.locator("#themes").screenshot(path=str(ROOT / "docs/assets/readme/product-showcase-themes.png"))
        page.set_viewport_size({"width": 1440, "height": 1000})

        copy = page.locator("#heroCopyInstallPrompt")
        copy.scroll_into_view_if_needed()
        before = copy.bounding_box()
        scroll_before = page.evaluate("scrollY")
        copy.click()
        page.wait_for_function("document.querySelector('#heroCopyInstallPrompt').textContent.includes('已复制')")
        after = copy.bounding_box()
        assert before and after and abs(before["width"] - after["width"]) < 1
        assert abs(page.evaluate("scrollY") - scroll_before) < 1
        prompt = page.evaluate("navigator.clipboard.readText()")
        assert "main/INSTALL_FOR_AGENT.md" in prompt and "实际安装版本" in prompt
        assert "releases/download/v" not in prompt
        results["copy"] = True
        assert page.locator(".notes-content").is_visible()
        assert not errors, errors

        article_page = context.new_page()
        article_page.on("pageerror", lambda error: errors.append(str(error)))
        for link in page.locator(".edition[href]").all():
            href = link.get_attribute("href")
            article_page.goto(urljoin(url, href), wait_until="networkidle")
            assert "405PX WECHAT PREVIEW" in article_page.locator(".article-bar").inner_text()
            for width in (360, 390, 405, 430, 768, 1440):
                article_page.set_viewport_size({"width": width, "height": 950})
                geometry = article_page.locator(".article-stage").bounding_box()
                assert abs(geometry["width"] - min(405, width)) <= 1, (href, width, geometry)
                assert article_page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (href, width)
                assert article_page.locator(".wechat-document").evaluate("el => getComputedStyle(el).paddingLeft === '24px'")
                if args.artifacts and width == 1440:
                    article_page.screenshot(path=str(args.artifacts / f"article-{Path(href).stem}.png"))
            assert article_page.locator(".article-stage img").evaluate_all("els => els.every(el => el.complete && el.naturalWidth > 0)")
            article_page.evaluate("window.scrollTo(0,document.documentElement.scrollHeight)")
            assert article_page.locator(".wechat-document main > p").last.evaluate("el => el.getBoundingClientRect().bottom <= innerHeight + 1")
            results["articles"] += 1
        assert not errors, errors
        context.close()

        fallback = new_context(viewport={"width": 390, "height": 844})
        fallback.add_init_script("Object.defineProperty(navigator, 'clipboard', {value:{writeText:async()=>{throw Error('denied')}}}); document.execCommand=()=>false;")
        failure_page = fallback.new_page()
        failure_page.goto(url, wait_until="networkidle")
        failure_page.locator("#heroCopyInstallPrompt").click()
        failure_page.locator("#installDialog[open]").wait_for()
        assert "main/INSTALL_FOR_AGENT.md" in failure_page.locator("#installPromptText").input_value()
        assert failure_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        failure_page.keyboard.press("Escape")
        assert failure_page.locator("#installDialog").evaluate("el=>!el.open")
        results["manual_copy"] = True
        fallback.close()

        if not args.url:
            retry_context = new_context()
            attempts = 0
            def flaky_catalog(route):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    route.fulfill(status=503, body="Unavailable")
                else:
                    route.fulfill(path=str(SITE / "data/themes.json"))
            retry_context.route("**/data/themes.json", flaky_catalog)
            retry_page = retry_context.new_page()
            retry_page.goto(url, wait_until="networkidle")
            retry_page.locator(".theme-retry").click()
            retry_page.locator(".theme-button").nth(11).wait_for()
            results["retry"] = True
            retry_context.close()

        no_js = new_context(java_script_enabled=False)
        plain_page = no_js.new_page()
        plain_page.goto(url, wait_until="networkidle")
        assert plain_page.locator(".edition[href]").count() == 3
        assert plain_page.locator("a[href*='INSTALL_FOR_AGENT.md']").first.is_visible()
        assert plain_page.locator("#faq .notes-content").is_visible()
        no_js.close()
        browser.close()
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
