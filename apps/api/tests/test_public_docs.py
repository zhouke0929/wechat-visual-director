from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
PUBLIC_ENTRIES = (
    "README.md",
    "INSTALL_FOR_AGENT.md",
    "docs/usage-guide.md",
    "site/index.html",
    "site/app.js",
    "site/llms.txt",
    "skills/wechat-visual-director/references/install.md",
)
SITE_URL = "https://zhouke0929.github.io/wechat-visual-director/"


def _prose_links(text: str) -> list[str]:
    # Code examples such as ![caption](path-or-url) are not live document links.
    prose = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)
    prose = re.sub(r"`[^`\n]+`", "", prose)
    return re.findall(r"\]\(([^)\s]+)\)", prose) + re.findall(r'(?:src|href)="([^"]+)"', prose)


def test_document_link_scanner_keeps_prose_but_ignores_literal_examples() -> None:
    text = (
        "[Mode](references/mode.md)\n"
        "```markdown\n![caption](path-or-url)\n```\n"
        "Inline `![caption](placeholder)` and [Next](next.md).\n"
    )
    assert _prose_links(text) == ["references/mode.md", "next.md"]


@pytest.mark.parametrize("relative_path", PUBLIC_ENTRIES)
def test_public_install_entries_do_not_pin_a_historical_release(relative_path: str) -> None:
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    # Historical, reproducible commands belong in docs/releases/, not the
    # current product and installation entry points. Do not forbid tool versions.
    assert not re.search(r"(?:v)?\d+\.\d+\.\d+-alpha\.\d+", text)
    assert not re.search(r"releases/(?:download|tag)/v\d", text)
    assert not re.search(r"install[^\s\"']*alpha\d+", text)
    assert "releases/latest" not in text or relative_path == "INSTALL_FOR_AGENT.md"


def test_manual_install_docs_use_current_installers_for_both_platforms() -> None:
    base = "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/"
    for name in ("INSTALL_FOR_AGENT.md", "docs/usage-guide.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert base + "scripts/install-release.ps1" in text
        assert base + "scripts/install-release.sh" in text
        assert "main/VERSION" in text
    windows = (ROOT / "scripts/install-release.ps1").read_text(encoding="utf-8")
    macos = (ROOT / "scripts/install-release.sh").read_text(encoding="utf-8")
    assert '[string]$Version = ""' in windows
    assert 'VERSION=""' in macos
    assert "main/VERSION" in windows and "main/VERSION" in macos


def test_user_guide_is_public_and_included_in_release_packages() -> None:
    assert "!docs/usage-guide.md" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    for relative_path in ("scripts/build-windows-package.ps1", "scripts/build-macos-package.sh"):
        text = (ROOT / relative_path).read_text(encoding="utf-8").replace("\\", "/")
        assert "docs/usage-guide.md" in text


@pytest.mark.parametrize("relative_path", (
    "README.md", "docs/usage-guide.md", "INSTALL_FOR_AGENT.md",
    "skills/wechat-visual-director/SKILL.md",
    *(str(path.relative_to(ROOT)).replace("\\", "/") for path in
      sorted(ROOT.joinpath("skills/wechat-visual-director/references").glob("*.md"))),
))
def test_document_local_links_and_images_exist(relative_path: str) -> None:
    source = ROOT / relative_path
    text = source.read_text(encoding="utf-8")
    for link in _prose_links(text):
        if link.startswith(("https://", "http://", "#")):
            continue
        target = link.split("#", 1)[0]
        assert (source.parent / target).exists(), (relative_path, link)


def test_skill_mode_references_are_reachable_from_entrypoint() -> None:
    """Relocation must not strand instructions outside the installed router."""
    skill = ROOT / "skills/wechat-visual-director"
    pending = [skill / "SKILL.md"]
    seen: set[Path] = set()
    while pending:
        source = pending.pop().resolve()
        if source in seen:
            continue
        seen.add(source)
        for link in _prose_links(source.read_text(encoding="utf-8")):
            if link.startswith(("https://", "http://", "#")):
                continue
            target = (source.parent / link.split("#", 1)[0]).resolve()
            if target.suffix == ".md" and target.is_relative_to(skill.resolve()):
                pending.append(target)
    references = {path.resolve() for path in skill.joinpath("references").glob("*.md")}
    assert references <= seen, sorted(str(path) for path in references - seen)


class _PageHead(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.json_chunks: list[str] = []
        self.title = ""
        self.h1_count = 0
        self.in_json = False
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "meta":
            self.meta[attributes.get("name") or attributes.get("property") or ""] = attributes.get("content") or ""
        if tag == "link" and attributes.get("rel") == "canonical":
            self.canonical = attributes.get("href") or ""
        if tag == "script":
            self.in_json = attributes.get("type") == "application/ld+json"
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.h1_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_json = False
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_json:
            self.json_chunks.append(data)
        if self.in_title:
            self.title += data


def test_product_search_metadata_matches_visible_product_facts() -> None:
    text = (ROOT / "site/index.html").read_text(encoding="utf-8")
    head = _PageHead()
    head.feed(text)
    assert head.canonical == SITE_URL
    assert head.meta["og:url"] == SITE_URL
    assert head.h1_count == 1
    assert "微信公众号 AI 排版 Skill" in head.title
    assert "WeChat Visual Director" in head.title
    assert "noindex" not in head.meta["robots"]
    for key in ("description", "og:description", "twitter:description"):
        assert "编辑" in head.meta[key]
        assert "草稿" in head.meta[key]
    data = json.loads("".join(head.json_chunks))
    assert "SoftwareApplication" in data["@type"]
    assert data["url"] == SITE_URL
    assert "公众号视觉主编" in data["alternateName"]
    assert "Technical Preview" in data["operatingSystem"]
    assert "softwareVersion" not in data  # Do not duplicate the release pointer.
    body = text.split("<body>", 1)[1]
    for fact in ("600px", "405px", "12 类语义组件", "14 种基础样式"):
        assert fact in body
        assert fact in " ".join(data["featureList"])
        assert fact in (ROOT / "site/llms.txt").read_text(encoding="utf-8")
    assert 'id="faq"' in body


def test_public_sitemap_points_to_real_canonical_pages() -> None:
    sitemap = ET.parse(ROOT / "site/sitemap.xml")
    urls = [item.text for item in sitemap.findall(".//{*}loc")]
    assert SITE_URL in urls
    for url in urls:
        assert url and url.startswith(SITE_URL)
        path = url.removeprefix(SITE_URL) or "index.html"
        assert (ROOT / "site" / path).is_file()
    robots = (ROOT / "site/robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: " + SITE_URL + "sitemap.xml" in robots


def test_showcase_is_a_compact_gallery_with_real_article_links() -> None:
    text = (ROOT / "site/index.html").read_text(encoding="utf-8")
    assert len(re.findall(r"<section\b", text)) == 4
    assert '<aside class="product-notes" id="faq" aria-labelledby="notes-title">' in text
    assert '<summary' not in text
    header = text.split('<header class="site-nav">', 1)[1].split('</header>', 1)[0]
    assert '看成稿' not in header and '换主题' not in header
    assert text.count('class="edition edition-') == 3
    assert text.count("data-copy-install") == 3
    for attribute, link in re.findall(r'(src|href)="([^"]+)"', text):
        if link.startswith("./"):
            assert (ROOT / "site" / link.split("?", 1)[0]).exists(), (attribute, link)
        elif link.startswith("#"):
            assert f'id="{link[1:]}"' in text, link


def test_custom_theme_creation_is_discoverable_without_reading_developer_docs(tmp_path) -> None:
    page = (ROOT / "site/index.html").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'href="#custom-themes"' in page
    assert 'id="custom-themes"' in page and "data-copy-theme" in page
    assert 'id="specimenSelect"' in page
    assert "组件参考图" in readme and "`.vdtheme`" in readme
    assert "主题" in readme.split('<p align="center">', 1)[0]
    from visual_director.onboarding import read_workbench_onboarding
    guide = read_workbench_onboarding(tmp_path / "onboarding-state.json")["guide"]
    assert len(guide["lines"]) <= 5
    theme_line = next(line for line in guide["lines"] if "主题" in line and ("参考图" in line or "组件截图" in line))
    assert "描述风格" in theme_line
    assert "样本册" in theme_line and "真实文章" in theme_line
    assert any("候选" in line and "审核" in line for line in guide["lines"])
    assert any("不自动群发" in line for line in guide["lines"])


def test_showcase_article_width_matches_workbench_mobile_viewport() -> None:
    viewport = (ROOT / "apps/web/src/components/article-preview-viewport.tsx").read_text(encoding="utf-8")
    config = json.loads((ROOT / "apps/api/src/visual_director/preview_profiles.json").read_text(encoding="utf-8"))
    width = str(next(p['viewport_width'] for p in config['profiles'] if p['id'] == 'mobile'))
    assert "PREVIEW_PROFILES.mobile.viewport_width" in viewport
    stylesheet = (ROOT / "site/articles/article.css").read_text(encoding="utf-8")
    assert f"--article-preview-width: {width}px;" in stylesheet
    assert "width: var(--article-preview-width); max-width: 100%" in stylesheet
    for path in (ROOT / "site/articles").glob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert 'href="./article.css?' in text
        assert f"{width}PX WECHAT PREVIEW" in text
        assert "390PX" not in text and "width:390px" not in text
    gallery_css = (ROOT / "site/styles.css").read_text(encoding="utf-8")
    iframe_rule = re.search(r"\.edition-preview iframe\s*\{([^}]+)\}", gallery_css).group(1)
    assert f"width: {width}px;" in iframe_rule


def test_readme_article_presentation_has_clear_images_and_current_product_copy() -> None:
    from PIL import Image

    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "### 原文编辑与双端预览" in text
    for obsolete_copy in ("不用退回一个小窗口", "不需要在首页手动上传 Markdown", "不只是一个 `SKILL.md` 文件"):
        assert obsolete_copy not in text
    for image in ("campus-portfolio-steps.webp", "coffee-repeat-scene.webp", "pop-collaboration-memory.webp"):
        assert f'src="site/assets/generated/{image}"' in text
    with Image.open(ROOT / "docs/assets/readme/product-showcase-articles.png") as gallery:
        assert gallery.width >= 2400, "Render the gallery at high density for README display"
    assert "workbench-dual-preview.png" not in text
    for name in ("article-review.png", "article-mobile-review.png"):
        assert f"docs/assets/readme/{name}" in text
        with Image.open(ROOT / "docs/assets/readme" / name) as preview:
            assert preview.width >= 2400 and preview.width > preview.height
    assert text.index("docs/assets/readme/article-review.png") < text.index("docs/assets/readme/article-mobile-review.png")
