from __future__ import annotations

import json
import re
from pathlib import Path
import base64
import io

import pytest
from bs4 import BeautifulSoup
from PIL import Image

from visual_director.component_catalog import VISUAL_SYSTEM_ORDER
from visual_director.theme_gallery import build_theme_gallery
from visual_director.theme_specimens import ARTICLE, BRAND, build_production_specimens
from visual_director.parser import parse_markdown
from visual_director.renderer import _opening_highlight, render_preview
from visual_director.planner import generate_plans
from visual_director.brief_compiler import visual_system_configuration
from visual_director.theme_packs import BUNDLED_THEME_IDS, configure_theme_packs, validate_theme_pack_manifest
from visual_director.component_catalog import CORE_THEME_COMPONENTS
from visual_director.theme_extensions import EXTENDED_THEME_IDS


def test_all_official_themes_expose_real_foundations_and_balanced_article():
    official = [theme for theme in build_theme_gallery() if theme["id"] in VISUAL_SYSTEM_ORDER]
    assert len(official) == len(VISUAL_SYSTEM_ORDER)
    for theme in official:
        foundations = theme["foundation_specimens"]
        lead_selector = ('[data-theme-layout="lead"]' if theme["id"] in BUNDLED_THEME_IDS
                         else '[data-content-role="lead"][data-lead-kind="本文导读"]')
        lead = BeautifulSoup(next(item["html"] for item in foundations if item["role"] == "lead"), "html.parser")
        assert lead.select_one(lead_selector)
        assert len(foundations) == 14
        roles = {item["role"] for item in foundations}
        assert {"hero", "lead", "quote", "paragraph", "ordered_list", "unordered_list", "table", "source", "reference_list", "image_caption", "closing_cta"} <= roles
        article = BeautifulSoup(theme["article_preview_html"], "html.parser")
        assert article.select_one('[data-gallery-production-article]')
        assert len(article.select(lead_selector)) == 1
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


def test_weekend_fieldnotes_renders_both_list_kinds_as_theme_layouts():
    samples, _ = build_production_specimens("weekend_fieldnotes")
    by_role = {item["role"]: item["html"] for item in samples}
    ordered = BeautifulSoup(by_role["ordered_list"], "html.parser").select_one('[data-theme-layout="list"]')
    unordered = BeautifulSoup(by_role["unordered_list"], "html.parser").select_one('[data-theme-layout="list"]')
    assert ordered and unordered

    badges = ordered.select("[data-theme-marker] [data-theme-list-index]")
    assert [badge.get_text() for badge in badges] == ["01", "02", "03"]
    assert all("background-color:#FFF8E7" in badge["style"] for badge in badges)
    assert not unordered.select("[data-theme-list-index]")
    assert len(unordered.select('[data-theme-marker] img[src^="data:image/png"]')) == 3

    parsed = parse_markdown(ARTICLE)
    for role, layout in (("ordered_list", ordered), ("unordered_list", unordered)):
        original = next(block.content for block in parsed.blocks if block.type == role)
        rendered = layout.select('[data-theme-marker-body] [data-theme-field="item"]')
        assert [item.get_text() for item in rendered] == original


@pytest.mark.parametrize("theme_id", ["retro_window", "folded_fan_detail", "color_paper_corners", "paper_fold",
                                     "candidate_light_blue_watercolor", "toy_storybook", "indigo_cloth",
                                     "night_walk_illustration"])
def test_themed_list_drawings_and_copyable_ordered_numbers(theme_id):
    samples, _ = build_production_specimens(theme_id)
    by_role = {item["role"]: BeautifulSoup(item["html"], "html.parser") for item in samples}
    ordered, unordered = by_role["ordered_list"], by_role["unordered_list"]
    assert [node.get_text() for node in ordered.select("[data-theme-marker] [data-theme-list-index]")] == ["01", "02", "03"]
    assert not ordered.select("[data-theme-list-fallback]")
    assert not unordered.select("[data-theme-list-index]")
    assert len(unordered.select('[data-theme-marker] img[src^="data:image/png"]')) == 3
    parsed = parse_markdown(ARTICLE)
    for role in ("ordered_list", "unordered_list"):
        original = next(block.content for block in parsed.blocks if block.type == role)
        assert [item.get_text() for item in by_role[role].select('[data-theme-marker-body] [data-theme-field="item"]')] == original


def test_after_screening_keeps_timeline_and_warning_fields_and_themes_both_lists():
    theme = build_theme_gallery(theme_id="after_screening")[0]
    foundations = {part["role"]: BeautifulSoup(part["html"], "html.parser")
                   for part in theme["foundation_specimens"]}
    assert foundations["subheading"].select_one('[data-theme-marker] img')
    assert len(foundations["unordered_list"].select('[data-theme-marker] img')) == 3
    ordered = foundations["ordered_list"]
    assert ordered.select_one('[data-theme-layout="list"]')
    assert [badge.get_text() for badge in ordered.select('[data-theme-marker] [data-theme-list-index]')] == ["01", "02", "03"]
    assert not ordered.select("[data-theme-list-fallback]")
    cards = {part["component_type"]: BeautifulSoup(part["html"], "html.parser") for part in theme["components"]}
    timeline = cards["before_after_timeline"].select_one('[data-theme-layout="before_after_timeline"]')
    (film_strip,) = timeline.find_all(recursive=False)
    first_frame, splice, second_frame = film_strip.find_all(recursive=False)
    for frame, label, binding in ((first_frame, "之前", "left"), (second_frame, "之后", "right")):
        assert frame.select_one('[data-theme-static]').get_text() == label
        assert frame.select_one(f'[data-theme-field="{binding}"]').get_text()
    assert splice["aria-hidden"] == "true"
    assert len(splice.select('img[data-theme-decoration][src^="data:image/png"]')) == 1
    warning = cards["warning_note"]
    assert [label.get_text() for label in warning.select('[data-theme-static]')] == ["留意"]
    assert len(warning.select('[data-theme-field="body"]')) == 1


def test_light_gallery_gallery_uses_authored_lists_and_keeps_photo_separate_from_mount():
    theme, = build_theme_gallery(theme_id="light_gallery")
    specimens = {sample["role"]: BeautifulSoup(sample["html"], "html.parser")
                 for sample in theme["foundation_specimens"]}
    ordered = specimens["ordered_list"].select_one('[data-theme-layout="list"]')
    unordered = specimens["unordered_list"].select_one('[data-theme-layout="list"]')
    assert [node.get_text() for node in ordered.select("[data-theme-list-index]")] == ["01", "02", "03"]
    assert not unordered.select("[data-theme-list-index]")
    assert [node.get_text() for node in unordered.select("[data-theme-marker]")] == ["•", "•", "•"]
    assert not ordered.select("[data-theme-list-fallback]")
    mounted = specimens["image_caption"].select_one('[data-theme-layout="image_caption"]')
    assert len(mounted.select("img[data-theme-media]")) == 1
    assert len(mounted.select("img[data-theme-decoration][alt='']")) >= 2
    assert mounted.select_one('[data-theme-field="caption"]').get_text()
    assert theme.get("wechat_acceptance") is None
    assert {part["status"] for part in theme["components"]} == {"wechat_candidate"}


def test_light_gallery_collection_layouts_keep_every_editable_item_in_source_order():
    from visual_director.theme_layouts import render_layout
    from visual_director.theme_packs import theme_pack

    pack = theme_pack("light_gallery")
    config = {"palette": pack["palette"], "generated_design_system": pack["design_system"]}
    items = [f"第 {i} 条：保留 **原文重点**，也保留大于号 >" for i in range(1, 13)]
    for role in ("list", "numbered_insight", "logic_path", "action_checklist", "section_summary"):
        markup = render_layout(role, {"items": items, "ordered": True}, config)
        layout = BeautifulSoup(markup, "html.parser").select_one(f'[data-theme-layout="{role}"]')
        fields = layout.select('[data-theme-field="item"]')
        assert [node.get_text() for node in fields] == [item.replace("**", "") for item in items]
        assert all(node.strong.get_text() == "原文重点" for node in fields)
        if role == "list":
            assert [node.get_text() for node in layout.select("[data-theme-list-index]")] == [
                f"{i:02d}" for i in range(1, 13)]


def test_pixel_live_places_evidence_label_first_and_keeps_timeline_fields_in_order():
    theme, = build_theme_gallery(theme_id="pixel_live")
    samples = {item["component_type"]: BeautifulSoup(item["html"], "html.parser")
               for item in theme["components"]}
    evidence = samples["evidence_callout"].select("[data-theme-static], [data-theme-field]")
    assert len(evidence) == 2
    assert evidence[0].get_text() == "依据"
    assert evidence[1]["data-theme-field"] == "body"
    timeline = samples["before_after_timeline"].select("[data-theme-static], [data-theme-field]")
    assert len(timeline) == 4
    assert [part.get("data-theme-field") or part.get_text() for part in timeline] == ["之前", "left", "之后", "right"]


def test_gallery_uses_distinct_copy_for_timeline_and_coexisting_options():
    from visual_director.theme_pair_samples import COMPARISON, TIMELINE

    theme, = build_theme_gallery(theme_id="pixel_live")
    specimens = {item["component_type"]: BeautifulSoup(item["html"], "html.parser")
                 for item in theme["components"]}
    timeline = specimens["before_after_timeline"]
    comparison = specimens["comparison_card"]
    for component, expected in ((timeline, TIMELINE), (comparison, COMPARISON)):
        fields = component.select('[data-theme-field="left"], [data-theme-field="right"]')
        assert [field.get_text() for field in fields] == list(expected)
    tabs = comparison.select("[data-theme-static]")
    assert [tab.get_text() for tab in tabs] == ["A", "B"]
    assert tabs[0]["style"] == tabs[1]["style"]
    assert len(comparison.select('section[style*="vertical-align:top;width:50%"]')) == 2


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
        for specimen_role, layout_role in (("hero", "hero"), ("lead", "lead"), ("quote", "quote"), ("unordered_list", "list"), ("divider", "divider")):
            markup = next(item["html"] for item in samples if item["role"] == specimen_role)
            assert f'data-theme-layout="{layout_role}"' in markup
        ordered = BeautifulSoup(next(item["html"] for item in samples if item["role"] == "ordered_list"), "html.parser")
        assert [node.get_text() for node in ordered.select("[data-theme-list-index]")] == ["01", "02", "03"]
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
