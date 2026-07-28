from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "theme-kit-v0.9"
THEMES = (
    "light_reading",
    "warm_humanist",
    "editorial_contrast",
    "structured_grid",
)


def inspect_page(page, theme: str, viewport: str) -> dict[str, object]:
    page.goto(f"http://127.0.0.1:3000/theme-gallery/{theme}", wait_until="networkidle")
    page.get_by_text("先判断主题，", exact=False).first.wait_for()
    article = page.locator("article").first
    article_metrics = article.evaluate(
        "(node) => ({clientWidth: node.clientWidth, scrollWidth: node.scrollWidth})"
    )
    page.screenshot(path=ARTIFACT_DIR / f"{theme}-{viewport}-article.png", full_page=False)
    if viewport == "desktop":
        article.screenshot(path=ARTIFACT_DIR / f"{theme}-article-full.png")

    page.get_by_role("button", name="02　主题部件库").click()
    page.get_by_text("RHYTHM PRIMITIVES / 01", exact=True).wait_for()
    primitive_count = page.locator('[class*="specimen"]').count()
    production_trigger_count = page.get_by_text("正式链路已接入", exact=False).count()
    canvas_metrics = page.locator('[class*="componentCanvas"]').evaluate_all(
        "(nodes) => nodes.map((node) => ({clientWidth: node.clientWidth, scrollWidth: node.scrollWidth}))"
    )
    document_metrics = page.locator("html").evaluate(
        "(node) => ({clientWidth: node.clientWidth, scrollWidth: node.scrollWidth})"
    )
    return {
        "theme": theme,
        "viewport": viewport,
        "article_metrics": article_metrics,
        "specimen_node_count": primitive_count,
        "production_trigger_count": production_trigger_count,
        "canvas_metrics": canvas_metrics,
        "document_metrics": document_metrics,
        "has_overflow": (
            article_metrics["scrollWidth"] > article_metrics["clientWidth"] + 1
            or document_metrics["scrollWidth"] > document_metrics["clientWidth"] + 1
            or any(item["scrollWidth"] > item["clientWidth"] + 1 for item in canvas_metrics)
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for viewport, size in (
            ("desktop", {"width": 1440, "height": 900}),
            ("mobile", {"width": 430, "height": 932}),
        ):
            page = browser.new_page(viewport=size)
            page.on("console", lambda message: print(f"browser:{message.type}:{message.text}") if message.type == "error" else None)
            for theme in THEMES:
                results.append(inspect_page(page, theme, viewport))
            page.close()
        browser.close()

    report = {
        "schema_version": "theme_kit_visual_acceptance.v0.3",
        "themes": list(THEMES),
        "results": results,
    }
    (ARTIFACT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(
        result["has_overflow"] or result["production_trigger_count"] != 6
        for result in results
    ):
        raise SystemExit("Theme gallery production parity or overflow check failed")


if __name__ == "__main__":
    main()
