import hashlib
import json
from collections import Counter
from importlib.resources import files
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from PIL import Image

from visual_director.brief_compiler import (
    ARTICLE_TYPE_THEME_AFFINITY, EditorialBriefCompileError, apply_visual_system,
    recommend_visual_system, visual_system_configuration,
)
from visual_director.component_catalog import (
    AUTO_RECOMMENDABLE_VISUAL_SYSTEMS, CORE_THEME_COMPONENTS,
    OFFICIAL_THEME_GROUPS, VISUAL_SYSTEM_ORDER, theme_group_metadata,
)
from visual_director.generated_theme import render_generated_table
from visual_director.image_provider import SURFACE_LABELS, build_cover_prompt, build_theme_fallback_cover
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director.renderer import render_preview
from visual_director.theme_packs import BUNDLED_THEME_IDS, REVIEWED_BUNDLED_THEME_IDS, bundled_theme_acceptance, theme_pack
from visual_director.theme_gallery import build_theme_gallery
from visual_director.visual_dna import (
    IMAGE_STYLE_MANIFESTS, IMAGE_STYLE_VARIANTS, OFFICIAL_PACK_SURFACES,
    image_style_recipe, resolve_article_image_direction,
)


@pytest.fixture(scope="module")
def gallery():
    return {entry["id"]: entry for entry in build_theme_gallery()}


def test_reviewed_official_files_preserve_accepted_artwork_and_have_real_sample_book(gallery):
    assert len(VISUAL_SYSTEM_ORDER) == 26 and len(BUNDLED_THEME_IDS) == 14
    assert "diagonal_type" not in gallery and "02-diagonal-type" not in gallery
    pkg = files("visual_director")
    evidence = json.loads(pkg.joinpath("bundled_theme_acceptance.json").read_text(encoding="utf-8"))
    assert list(evidence["themes"]) == list(REVIEWED_BUNDLED_THEME_IDS)
    for theme_id in REVIEWED_BUNDLED_THEME_IDS:
        record = evidence["themes"][theme_id]
        raw = pkg.joinpath("bundled_themes", f"{theme_id}.json").read_bytes()
        entry = gallery[theme_id]
        checksum = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        assert entry["source"] == "official"
        assert entry["delivery_report"]["wechat_saved_roundtrip"] == "not_verified"  # local preflight has no live authority
        assert entry["delivery_report"]["rehearsal"]["production"]["status"] == "pass"
        assert entry["layout_coverage"]["covered_count"] == 21
        assert len(entry["foundation_specimens"]) == 14 and len(entry["components"]) == len(CORE_THEME_COMPONENTS)
        if theme_id in {"retro_window", "folded_fan_detail", "color_paper_corners", "paper_fold",
                        "candidate_light_blue_watercolor", "toy_storybook", "indigo_cloth", "night_walk_illustration",
                        "ink_traces"}:
            assert checksum != record["manifest_lf_sha256"] and entry["pack_version"] != record["version"]
            assert bundled_theme_acceptance(theme_id) is None and "wechat_acceptance" not in entry
            assert all(c["status"] != "wechat_verified" for c in entry["components"])
        else:
            assert checksum == record["manifest_lf_sha256"] and entry["pack_version"] == record["version"]
            assert entry["wechat_acceptance"]["paths"] == ["clipboard", "api_draft"]
            assert {c["status"] for c in entry["components"]} == {"wechat_verified"}
    assert gallery["folded_fan_detail"]["pack_version"] == "1.3.3"


def test_gallery_summary_skips_official_artwork_and_detail_renders_only_requested_theme(monkeypatch):
    from visual_director import theme_gallery
    rendered = []
    build = theme_gallery._gallery_item

    def record(parsed, bindings, theme_id, metadata):
        rendered.append(theme_id)
        return build(parsed, bindings, theme_id, metadata)

    monkeypatch.setattr(theme_gallery, "_gallery_item", record)
    items = theme_gallery.build_theme_gallery(summary=True)
    assert len(items) == 26 and not rendered
    assert all(i["foundation_count"] == 14 and "article_preview_html" not in i for i in items)
    detail, = theme_gallery.build_theme_gallery(theme_id="color_paper_corners")
    assert detail["article_preview_html"] and rendered == ["color_paper_corners"]
    assert theme_gallery.build_theme_gallery(theme_id="does_not_exist") == []


@pytest.mark.parametrize(("retired", "table_grammar"), [
    ("round_table_bistro", "round-table-bistro-table"),
    ("city_wayfinding", None),
    ("soft_emboss", None),
    ("ticket_and_stub", "ticket-and-stub-perforated-table"),
])
def test_retired_theme_is_unselectable_but_saved_render_configuration_remains_usable(retired, table_grammar):
    assert retired not in VISUAL_SYSTEM_ORDER and retired not in AUTO_RECOMMENDABLE_VISUAL_SYSTEMS
    assert all(retired not in order for order in ARTICLE_TYPE_THEME_AFFINITY.values())
    assert theme_pack(retired) is None and build_theme_gallery(theme_id=retired) == []
    parsed = parse_markdown("# 旧稿\n\n原稿正文。\n\n| 项目 | 状态 |\n| --- | --- |\n| 草稿 | 保留 |")
    plan = apply_visual_system(generate_plans(parsed, "tutorial_steps", 5)[0], "light_reading")
    with pytest.raises(EditorialBriefCompileError):
        apply_visual_system(plan, retired)
    plan["visual_system"] = retired
    plan["configuration"]["theme_id"] = retired
    plan["configuration"]["generated_design_system"] = theme_pack("retro_window")["design_system"]
    soup = BeautifulSoup(render_preview(parsed, plan, brand_profile={}), "html.parser")
    old_table = soup.select_one(f'[data-theme-grammar="{table_grammar}"] table' if table_grammar else "table")
    assert "原稿正文。" in soup.get_text() and old_table.td.get_text() == "草稿"


def test_official_style_groups_cover_all_themes_once_independent_of_introduction_batch(gallery):
    grouped_ids = [theme_id for members in OFFICIAL_THEME_GROUPS.values() for theme_id in members]
    assert Counter(grouped_ids) == Counter(VISUAL_SYSTEM_ORDER)
    for order, (label, members) in enumerate(OFFICIAL_THEME_GROUPS.items()):
        for theme_id in members:
            assert gallery[theme_id]["theme_group"] == label
            assert gallery[theme_id]["theme_group_order"] == order
    assert theme_group_metadata("cinematic_story") == theme_group_metadata("after_screening")
    assert theme_group_metadata("structured_grid") == theme_group_metadata("retro_window")
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
    table, = root.find_all("table", recursive=False)
    assert [n.name for n in table.find_all(recursive=False)] == ["thead", "tbody"]
    assert len(table.select("tr")) == 2
    assert len(table.select("th")) == 3 and len(table.select("td")) == 3
    assert not table.select("img")
