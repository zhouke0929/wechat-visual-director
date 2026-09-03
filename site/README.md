# Static product showcase

This directory is the public, backend-free GitHub Pages surface for WeChat Visual Director.

- `index.html`, `styles.css`, `app.js`: product landing page and interactive theme browser;
- `data/themes.json`: generated from the production theme catalog by `python scripts/export_theme_gallery.py`;
- `articles/`: curated static 405px article previews with local image assets;
- `assets/generated/`: compressed showcase images approved for public display.

## A gallery, not a long-form manual

The homepage has three main sections: a first-screen gallery of three real
article editions, the interactive 12-theme atelier, and a compact installation
CTA. Image examples are integrated into the article gallery rather than repeated
in separate feature, comparison and workflow modules. Keep supporting setup,
cost and privacy details in a compact, always-visible two-column note (stacked
on small screens) and linked documentation. Do not hide these notes behind a
disclosure. The header contains the brand, GitHub and installation action only;
the hero retains its theme-gallery link.
Do not turn search optimization into another wall of feature cards.

The article cards open complete static articles. Theme changes use the real
exported catalog, not hand-drawn approximations. Preserve the established
`#cases`, `#themes`, `#image-system`, `#workflow` and `#faq` link targets.
The three complete articles share `articles/article.css`: a 405px viewport with
24px inner gutters, matching the workbench's mobile source width (not its 600px
proofreading content width). Smaller screens fit their available width; larger
screens do not stretch the article. Card iframes use the same 405px source width
with a visual scale, so card dimensions stay unchanged. Keep the source width and
article labels in sync with `ArticlePreviewViewport`; regression tests check it.
The theme preview uses a lightweight phone shell matching the workbench's visual
language: status bar, camera island, article navigation, account actions and home
indicator. Only the article scrolls. Keep the bottom chrome in separate grid rows,
check the final article block is reachable, and prevent horizontal overflow for
every theme. Phone icons are decorative, not working WeChat controls; the sample
label makes clear that this is a static public demonstration, not a live session.
Installation copy feedback uses a fixed-position toast and a fixed-size button;
if both clipboard paths fail, show a selectable prompt in an accessible dialog.

Browser regression (Playwright + Microsoft Edge; no workbench or private data):

```bash
python scripts/check-product-showcase-ui.py --artifacts tmp/showcase
```

By default it routes public assets from this checkout inside the test browser,
so no server is required. Pass `--url http://127.0.0.1:<port>/` to test a running
preview or the deployed site. It checks six viewport widths, 12 themes, keyboard
selection, phone scroll boundaries and narrow-screen fit, copy layout stability,
manual-copy fallback, catalog retry and no-JS
article links. `--refresh-promotional-assets` explicitly refreshes the hero,
article-card gallery and theme screenshots used in README/social sharing; do not
overwrite approved art. README keeps three visual groups: finished editions,
theme switching and the real editing workbench. Avoid repeating the same image
examples in another large feature panel; the three article links retain compact
image thumbnails. Promotional screenshots render at 3x device pixel density so
GitHub can display them clearly across large and high-density screens.

Product-facing prose describes capabilities and user outcomes. Do not import
internal iteration history or compare the product against its own old interface
(for example, a removed editing popup or Markdown-upload entry). Keep necessary
installation, cost and permission boundaries, expressed as current behavior.

`python scripts/capture_readme_workbench.py` refreshes `article-review.png` from
the real built workbench. It uses only the public campus sample and curated local
images, a fresh test database and a loopback service that stops after capture.
It never uses saved credentials, existing tasks or model/publishing requests.
API dependencies, Playwright and Edge must be available in the chosen Python.

## Search and AI-retrieval maintenance

Keep the product entity consistent across the repository README, the visible
homepage, title/description/social metadata, SoftwareApplication JSON-LD and
`llms.txt`: WeChat Visual Director / 公众号视觉主编 / 微信公众号 AI 排版 Skill.
Use natural descriptions of Markdown-to-WeChat rendering, in-place editing,
themes, image generation and draft delivery; do not replace the product name
with slogans or add keyword stuffing, hidden search text or invented reviews.

Important facts and FAQs must be visible in the static HTML, not only in images,
JavaScript or structured data. Keep structured data consistent with visible copy.
`llms.txt` is an optional concise source map for readers and agents, not an
indexing requirement or a promise of AI citations. Google's guidance states that
AI search uses the same SEO fundamentals and needs no special AI markup:
https://developers.google.com/search/docs/appearance/ai-features

The canonical page URL is the published GitHub Pages URL. Keep `sitemap.xml`
limited to real public pages; change `lastmod` only when that page materially
changes, not on every package release. A robots.txt policy must be served at the
origin root to control crawlers; this project site's nested robots.txt is not a
substitute for control of the account-level root. Do not block the product pages.

Default install prompts link to `main/INSTALL_FOR_AGENT.md`, and manual commands
use current `main/scripts/install-release.*` entry points. Installers resolve
`main/VERSION` and require matching published assets. Never pin an Alpha version
in current entry points or assume `/releases/latest` includes prereleases.
Historical release notes can retain their own version-specific commands.

Run the documentation regressions before publishing:

```bash
python -m pytest apps/api/tests/test_public_docs.py -q
```

After deployment, check live HTTP status, canonical URLs and the installed-version
receipt. Search Console indexing and actual search / AI referral data require the
site owner's access; local tests cannot prove rankings, indexing or citations.

The site must not contain task databases, local settings, API keys, AppSecrets, access tokens, runtime logs, or unpublished company material. It intentionally cannot create tasks, generate images, or publish to WeChat.

Before committing a theme change, run:

```bash
python scripts/export_theme_gallery.py
python scripts/export_theme_gallery.py --check
```
