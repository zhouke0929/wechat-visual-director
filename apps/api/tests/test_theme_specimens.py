from __future__ import annotations

import json
import re
from pathlib import Path
import base64
import io

from bs4 import BeautifulSoup
from PIL import Image

from visual_director.component_catalog import VISUAL_SYSTEM_ORDER
from visual_director.theme_gallery import build_theme_gallery
from visual_director.theme_specimens import ARTICLE, BRAND, build_production_specimens
from visual_director.parser import parse_markdown
from visual_director.renderer import _opening_highlight, render_preview
from visual_director.planner import generate_plans
from visual_director.brief_compiler import visual_system_configuration
from visual_director.theme_packs import configure_theme_packs, validate_theme_pack_manifest
from visual_director.component_catalog import CORE_THEME_COMPONENTS
from visual_director.theme_extensions import EXTENDED_THEME_IDS


def test_all_official_themes_expose_real_foundations_and_balanced_article():
    for theme in build_theme_gallery():
        foundations = theme["foundation_specimens"]
        lead = BeautifulSoup(next(item["html"] for item in foundations if item["role"] == "lead"), "html.parser")
        assert lead.select_one('[data-content-role="lead"][data-lead-kind="本文导读"]')
        assert len(foundations) == 14
        roles = {item["role"] for item in foundations}
        assert {"hero", "lead", "quote", "paragraph", "ordered_list", "unordered_list", "table", "source", "reference_list", "image_caption", "closing_cta"} <= roles
        article = BeautifulSoup(theme["article_preview_html"], "html.parser")
        assert article.select_one('[data-gallery-production-article]')
        assert len(article.select('[data-content-role="lead"]')) == 1
        assert article.select_one('[data-editor-block-type="quote"]')
        assert article.select_one('[data-editor-block-type="table"]')
        assert article.select_one('img[src^="data:image/png"]')
        assert not article.select_one("script")
        assert 0 < len(article.select(".component-anchor")) <= 6
        assert len(theme["components"]) == 12


def test_foundation_quotes_and_lists_are_exact_production_nodes():
    parsed = parse_markdown(ARTICLE)
    for theme_id in VISUAL_SYSTEM_ORDER:
        samples, _ = build_production_specimens(theme_id)
        plan = generate_plans(parsed, "tutorial_steps", 5)[0]
        plan.update(configuration=visual_system_configuration(theme_id), slots=[], image_slots=[])
        production = render_preview(parsed, plan, brand_profile=BRAND)
        for role in ("quote", "ordered_list", "unordered_list", "table", "source", "reference_list"):
            sample = next(item for item in samples if item["role"] == role)
            assert sample["html"] in production


def test_gallery_does_not_read_user_brand_configuration(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("gallery must not read private branding")
    monkeypatch.setattr("visual_director.renderer.load_brand_profile", forbidden)
    build_production_specimens("youth_campus")


def test_gallery_uses_assets_in_the_configured_installation_root(monkeypatch, tmp_path):
    assets = tmp_path / "assets/theme-stickers"
    assets.mkdir(parents=True)
    Image.new("RGBA", (11, 7), (14, 52, 31, 255)).save(assets / "atlas-leaf.png")
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(tmp_path))
    samples, _ = build_production_specimens("light_reading")
    markup = next(item["html"] for item in samples if item["role"] == "image_caption")
    source = BeautifulSoup(markup, "html.parser").select_one('img[src^="data:image/png"]')["src"]
    with Image.open(io.BytesIO(base64.b64decode(source.split(",", 1)[1]))) as image:
        assert image.size == (11, 7)


def test_authored_theme_foundations_preserve_custom_hero_quote_list_and_divider(tmp_path):
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))
    pack = tmp_path / "packs" / manifest["id"]
    pack.mkdir(parents=True)
    normalized = validate_theme_pack_manifest(manifest, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    (pack / "theme.json").write_text(json.dumps(normalized), encoding="utf-8")
    configure_theme_packs(pack.parent, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    try:
        samples, article = build_production_specimens(manifest["id"])
        for specimen_role, layout_role in (("hero", "hero"), ("lead", "lead"), ("quote", "quote"), ("ordered_list", "list"), ("divider", "divider")):
            markup = next(item["html"] for item in samples if item["role"] == specimen_role)
            assert f'data-theme-layout="{layout_role}"' in markup
        assert 'data-theme-layout="hero"' in article
        assert 'data-theme-layout="image_caption"' in article
    finally:
        configure_theme_packs(tmp_path / "clean", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)


def test_lead_specimen_matches_the_actual_production_selection():
    parsed = parse_markdown(ARTICLE)
    lead_id, label = _opening_highlight(parsed)
    assert lead_id is not None and label == "本文导读"
    samples, article = build_production_specimens("light_reading")
    lead = next(item["html"] for item in samples if item["role"] == "lead")
    assert f'data-editor-block-ids="{lead_id}"' in lead
    assert lead in article
    # No arbitrary scene setter or post-heading paragraph should become a lead.
    ordinary = parse_markdown("# 周末散步\n\n窗外的阳光落在桌面，街角的小店刚刚打开门，路上有几个行人慢慢走过。\n\n## 出门之后\n\n本文记录几个日常片刻，也谈谈怎样在忙碌中留下一点自己的空间。")
    assert _opening_highlight(ordinary) == (None, None)


def test_gallery_rejects_a_mislabeled_plain_paragraph(monkeypatch):
    import pytest
    monkeypatch.setattr("visual_director.theme_specimens.ARTICLE", "# 样本\n\n导读：用清楚的结构，让读者看见重点，也愿意继续读下去。\n\n## 正文\n\n普通解释。")
    with pytest.raises(ValueError, match="不能用普通正文代替"):
        build_production_specimens("light_reading")


def test_extended_theme_leads_do_not_share_the_generic_card():
    structures = []
    for theme_id in EXTENDED_THEME_IDS:
        samples, article = build_production_specimens(theme_id)
        lead = next(item["html"] for item in samples if item["role"] == "lead")
        assert lead in article
        assert 'data-theme-grammar=' in lead
        assert '#EDF7F4' not in lead and '#17312D' not in lead
        # Ignore bookkeeping and palette: ensure this is not just a recolored fallback.
        neutral = re.sub(r'\sdata-[\w-]+="[^"]*"', '', lead)
        structures.append(re.sub(r'#[A-Fa-f0-9]{6}', '#COLOR', neutral))
    assert len(set(structures)) == len(EXTENDED_THEME_IDS)
