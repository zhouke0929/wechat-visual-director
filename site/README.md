# Static product showcase

This directory is the public, backend-free GitHub Pages surface for WeChat Visual Director.

- `index.html`, `styles.css`, `editorial.css`, `app.js`: product landing page and interactive theme browser; `editorial.css` is the full-site editorial design layer;
- `brand.css`: shared colors, typography and page gutters for the homepage and article pages;
- `data/themes.json`: generated from the production theme catalog by `python scripts/export_theme_gallery.py`;
- `articles/`: curated static 405px article previews with local image assets;
- `assets/generated/`: compressed showcase images approved for public display.

## Brand and promotional media

The public brand uses ivory `#FFF8F4`, plum `#30223B` and coral `#F26078`,
with `#B83450` for small accent text. The approved comma mascot is used in
the navigation, footer and favicon. Full article contents and theme-catalog
HTML retain their own typography and palettes.

The hero shows an editorial paper composition beside a short product
introduction. Its play button opens the approved 48-second film in place, with native
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

The homepage has four chapters: the product film, the finished-article
walkthrough, the interactive theme library, and custom theme creation with
installation and delivery information. On desktop, crossing a chapter boundary
brings the next paper sheet up in a short animation. The previous sheet recedes
into the stack and leaves its top edge showing. Native scroll still drives the
article and theme sequences within their chapters. Narrow, short or zoomed-in
viewports use normal document flow. The last chapter links to setup, cost and
privacy details in a dialog.

The walkthrough shows three article excerpts side by side, using the original
components at the workbench's 405px mobile width and 24px inner gutters. The
papers scale in proportion to their columns. Scrolling reveals one excerpt
at a time on desktop. On narrow screens the finished excerpts form a
horizontal strip. Select any paper to open its complete article. Its link
also works without JavaScript.
The theme library shows six representative covers in a stack. On wide
screens, page scroll and the previous and next buttons draw each cover from
behind the stack and lay it on top. The phone updates the same article, stage
color and theme description with each selection. The catalog selector exposes every built-in
theme. Narrow screens use the existing horizontal specimen strip and short
phones use the catalog selector.
Use `?theme=<id>#themes` to preselect a theme.
Preserve the established
`#cases`, `#themes`, `#image-system`, `#workflow` and `#faq` link targets.
The three complete articles share `articles/article.css`: a 405px viewport with
24px inner gutters, matching the workbench's mobile source width (not its 600px
proofreading content width). Smaller screens fit their available width; larger
screens do not stretch the article. Keep source width and article labels in
sync with `ArticlePreviewViewport`. The walkthrough uses those same rendered examples.
The workbench theme album includes 14 foundation specimens and 12 semantic
components. The public theme phone shows a sample article.
At `#custom-themes`, three original reference images point to the cover,
chapter heading, and Q&A heading in the Spring Fold Notes edition of the coffee-corner
article. The samples use the actual static article export, including its
workbench illustrations, so this case also works without a running workbench.
On narrow screens, the selected reference controls which sample is shown.
The theme prompt and installer are available below the comparison.
The phone uses the original showcase's metal-rimmed shell and shrinks to fit
on narrow screens. Check that the final article block is reachable and that
selecting a new theme resets the screen scroll without moving the frame.
Installation copy feedback uses a fixed-position toast and a fixed-size button;
if both clipboard paths fail, show a selectable prompt in an accessible dialog.
The manual dialog must show the prompt associated with the clicked button,
whether installation or custom-theme creation.

Browser regression (Playwright + Microsoft Edge; no workbench or private data):

The editorial version is currently a local design review. The legacy showcase
harness below still assumes 26 individual theme buttons and homepage iframes;
update those assertions and the promotional capture path before publishing.
This version has been checked in the in-app browser at 320, 393, 768, 1024 and
1440 pixels, including all 26 selections, fixed phone geometry, specimen
switching, video playback and both copy actions.

```bash
python scripts/check-product-showcase-ui.py --artifacts tmp/showcase
python scripts/test_theme_gallery_browser.py
```

By default it routes public assets from this checkout inside the test browser,
so no server is required. Pass `--url http://127.0.0.1:<port>/` to test a running
preview or the deployed site. It checks all themes at five widths, six viewport
widths overall, keyboard selection, direct theme links, phone scroll boundaries
and narrow-screen fit, copy layout stability,
manual-copy fallback, catalog retry and no-JS
article links. Use `--refresh-theme-image` after a theme-gallery change to
refresh only the README gallery screenshot. `--refresh-promotional-assets` refreshes the hero,
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
`main/VERSION` and require matching published assets. Never pin a historical version
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

Windows is the canonical renderer for the public snapshot. The consistency
check compares layout and decoded decoration pixels, not PNG compression.
Before committing a theme change, run on Windows:

```bash
python scripts/export_theme_gallery.py
python scripts/export_theme_gallery.py --check
```
