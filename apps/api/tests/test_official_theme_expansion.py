import hashlib
import json
from collections import Counter
from importlib.resources import files
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from PIL import Image

from visual_director.brief_compiler import ARTICLE_TYPE_THEME_AFFINITY, recommend_visual_system, visual_system_configuration
from visual_director.component_catalog import (
    AUTO_RECOMMENDABLE_VISUAL_SYSTEMS, CORE_THEME_COMPONENTS,
    OFFICIAL_THEME_GROUPS, VISUAL_SYSTEM_ORDER, theme_group_metadata,
)
from visual_director.generated_theme import render_generated_table
from visual_director.image_provider import SURFACE_LABELS, build_cover_prompt, build_theme_fallback_cover
from visual_director.theme_packs import BUNDLED_THEME_IDS, REVIEWED_BUNDLED_THEME_IDS, theme_pack
from visual_director.theme_gallery import build_theme_gallery
from visual_director.visual_dna import (
    IMAGE_STYLE_MANIFESTS, IMAGE_STYLE_VARIANTS, OFFICIAL_PACK_SURFACES,
    image_style_recipe, resolve_article_image_direction,
)


@pytest.fixture(scope="module")
def gallery():
    return {entry["id"]: entry for entry in build_theme_gallery()}


def test_reviewed_official_files_preserve_accepted_artwork_and_have_real_sample_book(gallery):
    assert len(VISUAL_SYSTEM_ORDER) == 30 and len(BUNDLED_THEME_IDS) == 18
    assert "diagonal_type" not in gallery and "02-diagonal-type" not in gallery
    pkg = files("visual_director")
    evidence = json.loads(pkg.joinpath("bundled_theme_acceptance.json").read_text(encoding="utf-8"))
    assert list(evidence["themes"]) == list(REVIEWED_BUNDLED_THEME_IDS)
    for theme_id in REVIEWED_BUNDLED_THEME_IDS:
        record = evidence["themes"][theme_id]
        raw = pkg.joinpath("bundled_themes", f"{theme_id}.json").read_bytes()
        assert hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == record["manifest_lf_sha256"]
        entry = gallery[theme_id]
        assert entry["source"] == "official" and entry["pack_version"] == record["version"]
        assert entry["wechat_acceptance"]["paths"] == ["clipboard", "api_draft"]
        assert entry["delivery_report"]["wechat_saved_roundtrip"] == "not_verified"  # local preflight has no live authority
        assert entry["delivery_report"]["rehearsal"]["production"]["status"] == "pass"
        assert entry["layout_coverage"]["covered_count"] == 21
        assert len(entry["foundation_specimens"]) == 14 and len(entry["components"]) == len(CORE_THEME_COMPONENTS)
        assert {c["status"] for c in entry["components"]} == {"wechat_verified"}
    assert gallery["city_wayfinding"]["pack_version"] == "1.0.3"


def test_gallery_summary_skips_official_artwork_and_detail_renders_only_requested_theme(monkeypatch):
    from visual_director import theme_gallery
    rendered = []
    build = theme_gallery._gallery_item

    def record(parsed, bindings, theme_id, metadata):
        rendered.append(theme_id)
        return build(parsed, bindings, theme_id, metadata)

    monkeypatch.setattr(theme_gallery, "_gallery_item", record)
    items = theme_gallery.build_theme_gallery(summary=True)
    assert len(items) == 30 and not rendered
    assert all(i["foundation_count"] == 14 and "article_preview_html" not in i for i in items)
    detail, = theme_gallery.build_theme_gallery(theme_id="city_wayfinding")
    assert detail["article_preview_html"] and rendered == ["city_wayfinding"]
    assert theme_gallery.build_theme_gallery(theme_id="does_not_exist") == []


def test_official_style_groups_cover_all_themes_once_independent_of_introduction_batch(gallery):
    grouped_ids = [theme_id for members in OFFICIAL_THEME_GROUPS.values() for theme_id in members]
    assert Counter(grouped_ids) == Counter(VISUAL_SYSTEM_ORDER)
    for order, (label, members) in enumerate(OFFICIAL_THEME_GROUPS.items()):
        for theme_id in members:
            assert gallery[theme_id]["theme_group"] == label
            assert gallery[theme_id]["theme_group_order"] == order
    assert theme_group_metadata("cinematic_story") == theme_group_metadata("after_screening")
    assert theme_group_metadata("structured_grid") == theme_group_metadata("city_wayfinding")
    assert theme_group_metadata("local_theme")["theme_group"] == "我的主题"


@pytest.mark.parametrize("theme_id", REVIEWED_BUNDLED_THEME_IDS)
def test_recommendation_only_rotates_reviewed_themes_into_relevant_content(theme_id):
    eligible = [t for t, order in ARTICLE_TYPE_THEME_AFFINITY.items() if theme_id in order]
    assert eligible
    recent = [{"visual_system": t} for t in AUTO_RECOMMENDABLE_VISUAL_SYSTEMS if t != theme_id]
    for kind in eligible:
        picked, counts, previous = recommend_visual_system(kind, recent, len(recent))
        assert picked == theme_id and previous != picked and counts[picked] == 0
    for kind in set(ARTICLE_TYPE_THEME_AFFINITY).difference(eligible):
        assert recommend_visual_system(kind, recent, len(recent))[0] != theme_id


@pytest.mark.parametrize("theme_id", BUNDLED_THEME_IDS)
def test_image_families_use_official_theme_palette_and_publishable_fallback_cover(theme_id):
    manifest = theme_pack(theme_id)
    direction = resolve_article_image_direction(visual_system=theme_id, article_type="tutorial_steps")
    assert direction["style_family"] in IMAGE_STYLE_MANIFESTS
    assert direction["palette_family"] == f"official_pack:{theme_id}"
    variant = IMAGE_STYLE_VARIANTS.get(direction.get("style_variant"))
    recipe = image_style_recipe(direction["style_family"], direction.get("style_variant"))
    if recipe is None:
        assert direction["surface_treatment"] in OFFICIAL_PACK_SURFACES[theme_id]
    else:
        assert direction["surface_treatment"] == recipe.surface_id
    expected_palette = list(variant.palette_roles) if variant and variant.palette_roles else [
        manifest["palette"][role] for role in ("primary", "secondary", "accent", "surface")
    ]
    assert direction["palette_roles"] == expected_palette
    brief = {"title": "给社区开放日做一份指引", "article_type": "tutorial_steps", "visual_system": theme_id,
             "image_art_direction": direction}
    for profile in ("generic", "seedream"):
        if recipe is None:
            expected_surface = SURFACE_LABELS[direction["surface_treatment"]]
        else:
            expected_surface = recipe.surface_zh if profile == "seedream" else recipe.surface_en
        assert expected_surface in build_cover_prompt(brief, prompt_profile=profile)
    with Image.open(BytesIO(build_theme_fallback_cover(brief))) as cover:
        rgb = tuple(bytes.fromhex(manifest["palette"]["primary"][1:]))
        assert Counter(cover.convert("RGB").getdata())[rgb] > 0


@pytest.mark.parametrize("theme_id", REVIEWED_BUNDLED_THEME_IDS)
def test_promoted_themes_keep_tested_native_tables(theme_id):
    config = visual_system_configuration(theme_id)
    markup = render_generated_table([["A", "B", "C"], ["1", "2", "3"]], config)
    root = BeautifulSoup(markup, "html.parser").select_one("[data-theme-grammar]")
    assert [n.name for n in root.find_all(recursive=False)] == ["table"]
    assert len(root.select("th")) == 3 and len(root.select("td")) == 3
