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


@pytest.mark.parametrize("relative_path", ("README.md", "docs/usage-guide.md", "INSTALL_FOR_AGENT.md"))
def test_document_local_links_and_images_exist(relative_path: str) -> None:
    source = ROOT / relative_path
    text = source.read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)\s]+)\)", text)
    links += re.findall(r'(?:src|href)="([^"]+)"', text)
    for link in links:
        if link.startswith(("https://", "http://", "#")):
            continue
        target = link.split("#", 1)[0]
        assert (source.parent / target).exists(), (relative_path, link)


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
    for fact in ("600px", "405px", "12 类语义组件", "6 类文章骨架"):
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
