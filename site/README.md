# Static product showcase

This directory is the public, backend-free GitHub Pages surface for WeChat Visual Director.

- `index.html`, `styles.css`, `app.js`: product landing page and interactive theme browser;
- `data/themes.json`: generated from the production theme catalog by `python scripts/export_theme_gallery.py`;
- `articles/`: curated static 405px article previews with local image assets;
- `assets/generated/`: compressed showcase images approved for public display.

## Brand and promotional media

The public brand uses ivory `#FFF8F4`, plum `#30223B` and coral `#F26078`,
with `#B83450` for small accent text. The approved comma mascot is used in
the navigation, footer and favicon. Article iframe contents and theme-catalog
HTML retain their own typography and palettes.

The hero shows the approved 48-second product film beside a short product
introduction. It starts in place when the play button is activated, with native
playback, volume and fullscreen controls. It does not autoplay or download the
MP4 on page load (`preload="none"`). Without JavaScript, native video controls
remain available. The finished-article gallery follows in its own section.

Run `python scripts/sync_public_brand_assets.py` after updating the approved
repository mascot, video or poster. It mirrors those exact files into the
self-contained `site/assets/` deployment and records hashes in
`assets/media/sources.json`; it does not publish anything. Video music has its
own third-party license and is not licensed as project source code.

After a website brand change, run the showcase check with
`--refresh-promotional-assets` to regenerate the README/social hero, article
montage and theme screenshot. The article montage imports brand tokens from
the live site while retaining each article's actual heading and text styles.

## A gallery, not a long-form manual

The homepage has five main sections: a first-screen product introduction and
film, three real article editions, the interactive 12-theme atelier, a
reference-to-custom-theme creation entry, and a compact installation CTA.
On phones the first screen presents the introduction, film and installation
action in that order. Image examples are integrated into the article gallery rather than repeated
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
with a visual scale. The excerpt ends after the complete first paragraph;
the remaining article is clipped before the curated image row. Cards appear
side by side on desktop and stack on phones. Keep the source width and
article labels in sync with `ArticlePreviewViewport`; regression tests check it.
The atelier exposes a production-rendered article plus 14 foundation specimens
and 12 semantic components. Keep ordinary quotes and lists visible, rather than
presenting every quoted passage as an evidence card. Its specimen picker must
preserve the selected role when switching themes. `#custom-themes` describes the
workflow with explicitly labeled illustrative elements, not an unverified claim
about a one-shot generation result; its copy button sends nothing automatically.
The theme preview uses a lightweight phone shell matching the workbench's visual
language: status bar, camera island, article navigation, account actions and home
indicator. Only the article scrolls. Keep the bottom chrome in separate grid rows,
check the final article block is reachable, and prevent horizontal overflow for
every theme. Phone icons are decorative, not working WeChat controls; the sample
label makes clear that this is a static public demonstration, not a live session.
Installation copy feedback uses a fixed-position toast and a fixed-size button;
if both clipboard paths fail, show a selectable prompt in an accessible dialog.
The manual dialog must show the prompt associated with the clicked button,
whether installation or custom-theme creation.

Browser regression (Playwright + Microsoft Edge; no workbench or private data):

```bash
python scripts/check-product-showcase-ui.py --artifacts tmp/showcase
python scripts/test_theme_gallery_browser.py
```

By default it routes public assets from this checkout inside the test browser,
so no server is required. Pass `--url http://127.0.0.1:<port>/` to test a running
preview or the deployed site. It checks six viewport widths, 12 themes, keyboard
selection, phone scroll boundaries and narrow-screen fit, copy layout stability,
manual-copy fallback, catalog retry and no-JS
article links. `--refresh-promotional-assets` explicitly refreshes the hero,
article excerpts and theme screenshots used in README/social sharing; do not
overwrite approved art. README keeps three visual groups: finished editions,
theme switching and the real editing workbench. Avoid repeating the same image
examples in another large feature panel; the three article links retain compact
image thumbnails. Promotional screenshots render at 3x device pixel density so
GitHub can display them clearly across large and high-density screens.
README uses a dedicated three-column composition from `scripts/readme-assets/editions.html`:
the actual article heading and complete first paragraph flow above the curated
image, with consistent gutters and aligned image rows. Do not splice artwork
onto a clipped live-iframe paragraph or reuse the tilted website crop here.

Product-facing prose describes capabilities and user outcomes. Do not import
internal iteration history or compare the product against its own old interface
(for example, a removed editing popup or Markdown-upload entry). Keep necessary
installation, cost and permission boundaries, expressed as current behavior.

`python scripts/capture_readme_workbench.py` refreshes `article-review.png` and
`article-mobile-review.png` from the real built workbench. README shows two full
screenshots vertically: editing first, mobile preview below. Both retain the
image-review workspace on the left and show the same article on the right;
do not crop out the phone or combine the views into a promotional board.
It uses only the public campus sample and curated local
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
