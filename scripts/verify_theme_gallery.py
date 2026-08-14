from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "theme-kit-v0.13-candidates"
THEMES = (
    "light_reading",
    "warm_humanist",
    "youth_campus",
    "editorial_contrast",
    "structured_grid",
    "future_tech",
    "oriental_archive",
    "vintage_press",
    "pop_poster",
    "natural_atlas",
    "business_review",
    "cinematic_story",
)


def inspect_page(page, theme: str, viewport: str) -> dict[str, object]:
    page.goto(f"http://127.0.0.1:8000/theme-gallery/{theme}", wait_until="networkidle")
    page.locator("article").first.wait_for()
    article = page.locator("article").first
    article_metrics = article.evaluate(
        "(node) => ({clientWidth: node.clientWidth, scrollWidth: node.scrollWidth})"
    )
    spacing_metrics = page.evaluate(
        """() => {
          const root = document.querySelector('article > main');
          const children = root ? Array.from(root.children) : [];
          const rects = children.map((node) => node.getBoundingClientRect());
          const rootRect = root ? root.getBoundingClientRect() : null;
          const directChildGaps = rects.slice(1).map(
            (rect, index) => Math.max(0, Math.round(rect.top - rects[index].bottom))
          );
          const edgeViolations = root && rootRect
            ? Array.from(root.querySelectorAll('*'))
                .map((node) => {
                  const rect = node.getBoundingClientRect();
                  return {
                    tag: node.tagName.toLowerCase(),
                    heading_level: node.getAttribute('data-heading-level'),
                    theme_grammar: node.getAttribute('data-theme-grammar'),
                    decoration: node.getAttribute('data-theme-decoration'),
                    left_escape: Math.max(0, Math.round(rootRect.left - rect.left)),
                    right_escape: Math.max(0, Math.round(rect.right - rootRect.right)),
                    text: (node.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 52),
                  };
                })
                .filter((item) => item.left_escape > 1 || item.right_escape > 1)
            : [];
          const originalPadding = root ? root.style.padding : '';
          if (root) root.style.padding = '0px';
          const publisherRootRect = root ? root.getBoundingClientRect() : null;
          const publisherEdgeViolations = root && publisherRootRect
            ? Array.from(root.querySelectorAll('*'))
                .map((node) => {
                  const rect = node.getBoundingClientRect();
                  return {
                    tag: node.tagName.toLowerCase(),
                    heading_level: node.getAttribute('data-heading-level'),
                    theme_grammar: node.getAttribute('data-theme-grammar'),
                    decoration: node.getAttribute('data-theme-decoration'),
                    left_escape: Math.max(0, Math.round(publisherRootRect.left - rect.left)),
                    right_escape: Math.max(0, Math.round(rect.right - publisherRootRect.right)),
                    text: (node.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 52),
                  };
                })
                .filter((item) => item.left_escape > 1 || item.right_escape > 1)
            : [];
          if (root) root.style.padding = originalPadding;
          const decorations = Array.from(document.querySelectorAll('[data-theme-decoration]')).map(
            (node) => {
              const overlay = node.querySelector('[data-decoration-layer="overlay"]');
              const directImage = Array.from(node.children).some((child) => child.tagName === 'IMG');
              return {
                kind: node.getAttribute('data-theme-decoration'),
                has_overlay: Boolean(overlay),
                overlay_height: overlay ? Math.round(overlay.getBoundingClientRect().height) : null,
                direct_image: directImage,
              };
            }
          );
          return {
            max_direct_child_gap: Math.max(0, ...directChildGaps),
            edge_violation_count: edgeViolations.length,
            edge_violations: edgeViolations.slice(0, 20),
            publisher_edge_violation_count: publisherEdgeViolations.length,
            publisher_edge_violations: publisherEdgeViolations.slice(0, 20),
            decorations,
            decoration_flow_intrusion: decorations.some(
              (item) => item.direct_image || !item.has_overlay || item.overlay_height > 1
            ),
          };
        }"""
    )
    page.screenshot(path=ARTIFACT_DIR / f"{theme}-{viewport}-article.png", full_page=False)
    if viewport == "desktop":
        article.screenshot(path=ARTIFACT_DIR / f"{theme}-article-full.png")

    page.locator("nav button").nth(1).click()
    page.get_by_text("RHYTHM PRIMITIVES / 01", exact=True).wait_for()
    specimen_count = page.locator('[class*="specimen"]').count()
    production_trigger_count = page.evaluate(
        """async (themeId) => {
          const response = await fetch('/api/v1/theme-gallery');
          const payload = await response.json();
          const theme = payload.themes.find((item) => item.id === themeId);
          return (theme?.rhythm_primitives ?? []).filter(
            (item) => item.production_status === 'production' && item.production_trigger
          ).length;
        }""",
        theme,
    )
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
        "specimen_node_count": specimen_count,
        "production_trigger_count": production_trigger_count,
        "canvas_metrics": canvas_metrics,
        "document_metrics": document_metrics,
        "spacing_metrics": spacing_metrics,
        "has_overflow": (
            article_metrics["scrollWidth"] > article_metrics["clientWidth"] + 1
            or document_metrics["scrollWidth"] > document_metrics["clientWidth"] + 1
            or any(item["scrollWidth"] > item["clientWidth"] + 1 for item in canvas_metrics)
        ),
        "has_spacing_regression": (
            spacing_metrics["decoration_flow_intrusion"]
            or spacing_metrics["max_direct_child_gap"] > 52
            or spacing_metrics["publisher_edge_violation_count"] > 0
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
            page.on(
                "console",
                lambda message: (
                    print(f"browser:{message.type}:{message.text}")
                    if message.type == "error"
                    else None
                ),
            )
            for theme in THEMES:
                results.append(inspect_page(page, theme, viewport))
            page.close()
        browser.close()

    report = {
        "schema_version": "theme_kit_visual_acceptance.v0.5",
        "themes": list(THEMES),
        "results": results,
    }
    (ARTIFACT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(
        result["has_overflow"]
        or result["has_spacing_regression"]
        or result["production_trigger_count"] != 6
        for result in results
    ):
        raise SystemExit("Theme gallery production parity, overflow, or spacing check failed")


if __name__ == "__main__":
    main()
