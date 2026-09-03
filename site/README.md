# Static product showcase

This directory is the public, backend-free GitHub Pages surface for WeChat Visual Director.

- `index.html`, `styles.css`, `app.js`: product landing page and interactive theme browser;
- `data/themes.json`: generated from the production theme catalog by `python scripts/export_theme_gallery.py`;
- `articles/`: curated static 390px article previews with local image assets;
- `assets/generated/`: compressed showcase images approved for public display.

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
