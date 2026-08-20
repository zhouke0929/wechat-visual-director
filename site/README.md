# Static product showcase

This directory is the public, backend-free GitHub Pages surface for WeChat Visual Director.

- `index.html`, `styles.css`, `app.js`: product landing page and interactive theme browser;
- `data/themes.json`: generated from the production theme catalog by `python scripts/export_theme_gallery.py`;
- `articles/`: curated static 390px article previews with local image assets;
- `assets/generated/`: compressed showcase images approved for public display.

The site must not contain task databases, local settings, API keys, AppSecrets, access tokens, runtime logs, or unpublished company material. It intentionally cannot create tasks, generate images, or publish to WeChat.

Before committing a theme change, run:

```bash
python scripts/export_theme_gallery.py
python scripts/export_theme_gallery.py --check
```
