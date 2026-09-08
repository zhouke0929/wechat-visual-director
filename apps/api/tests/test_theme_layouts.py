from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from visual_director.brief_compiler import apply_visual_system, visual_system_configuration
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.generated_theme import render_generated_component, render_generated_paragraph, render_generated_quote
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director.renderer import render_preview
from visual_director.theme_gallery import _full_preview, build_theme_gallery
from visual_director.theme_layouts import render_layout, validate_layouts
from visual_director.theme_packs import ThemePackError, configure_theme_packs, validate_theme_pack_manifest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def manifest(tmp_path):
    configure_theme_packs(tmp_path / "packs", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    value = json.loads((ROOT / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))
    yield value
    configure_theme_packs(tmp_path / "clean", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)


def configuration(manifest):
    return {"visual_system": manifest["id"], "palette": manifest["palette"], "generated_design_system": manifest["design_system"]}


def evidence_layout():
    return {"type": "row", "widths": [25, 75], "children": [
        {"type": "text", "text": "档案摘录", "style": {"color": "accent", "font": "mono", "size": "label"}},
        {"type": "field", "bind": "body", "style": {"padding": [0, 0, 0, 12], "font": "serif", "border_left": {"width": 2, "color": "primary", "style": "solid"}}},
    ]}


def test_neutral_defaults_and_complete_authored_sample(manifest):
    from midnight_theme_fixture import midnight_manifest
    from visual_director.theme_layouts import ROLE_FIELDS
    assert manifest["design_system"]["motifs"] == ["none"]
    assert manifest["design_system"]["ornament"]["density"] == 0
    sample = midnight_manifest(manifest)
    assert set(sample["design_system"]["layouts"]) == set(ROLE_FIELDS)
    assert not validate_layouts(sample["design_system"]["layouts"])
    Draft202012Validator(json.loads((ROOT / "contracts/theme-pack-v1.schema.json").read_text(encoding="utf-8"))).validate(sample)
    validate_theme_pack_manifest(sample)


@pytest.mark.parametrize("theme_name", ["midnight", "postal"])
def test_media_is_core_owned_and_preserved_in_materialization(manifest, theme_name):
    from types import SimpleNamespace
    from visual_director.renderer import _render_image_placeholder, _render_source_image_placeholder, _render_fixed_footer
    from visual_director.publication import materialize_preview_document
    from midnight_theme_fixture import midnight_manifest
    from postal_theme_fixture import postal_manifest
    config = configuration((postal_manifest if theme_name == "postal" else midnight_manifest)(manifest))
    config["accent"] = config["palette"]["accent"]
    placeholder = _render_image_placeholder({"image_slot_id": "slot1", "purpose": "semantic_scene", "aspect_ratio": "4:3", "reason": "说明场景"}, config)
    source = _render_source_image_placeholder(SimpleNamespace(id="source1", content={"alt": "原图说明"}), config)
    repository = SimpleNamespace(
        get_artifact_record=lambda _: {"html": placeholder + source, "task_id": "task", "plan_id": "plan"},
        list_image_slot_states=lambda *_: [{"image_slot_id": "slot1", "status": "accepted", "selected_candidate_id": "image1", "candidates": [{"id": "image1", "width": 800, "height": 600, "content_url": "/api/v1/images/image1/content"}]}],
        list_preflight_asset_replacements=lambda *_: [{"asset_role": "body_image", "block_id": "source1", "width": 800, "height": 600, "content_url": "/api/v1/images/source1/content"}],
    )
    result = materialize_preview_document(repository, "artifact")
    soup = BeautifulSoup(result, "html.parser")
    assert len(soup.select('[data-theme-layout="image_caption"]')) == 2
    assert len(soup.select('img[data-theme-media]')) == 2
    assert soup.select_one('#source1 [data-theme-field="caption"]').get_text() == "原图说明"
    assert "data-theme-image-config" not in result and "IMAGE PLAN" not in result
    assert "data-theme-motif" not in result
    if theme_name == "postal":
        assert len(soup.select('[data-theme-cutout]')) == 2
        assert "radial-gradient" in result and "filter:drop-shadow" in result
    footer = _render_fixed_footer({"enabled": True, "text": "真实品牌说明", "asset_path": "core-owned"}, config)
    assert 'data-theme-layout="closing_cta"' in footer and "真实品牌说明" in footer
    assert len(BeautifulSoup(footer, "html.parser").select('img[data-theme-media]')) == 1
    with pytest.raises(ValueError, match="controlled asset"):
        render_layout("image_caption", {"caption": "x", "media": {"src": "javascript:alert(1)"}}, config)
    assert validate_layouts({"quote": {"type": "media"}})
    assert validate_layouts({"image_caption": {"type": "field", "bind": "caption"}})
    assert validate_layouts({"image_caption": {"type": "stack", "children": [{"type": "field", "bind": "caption"}, {"type": "media", "src": "https://untrusted.test"}]}})


@pytest.mark.parametrize("bad", [[], {}, None, 1, True])
def test_malformed_spacing_reports_field_error(manifest, bad):
    manifest["design_system"]["typography"]["letter_spacing"] = bad
    with pytest.raises(ThemePackError) as exc:
        validate_theme_pack_manifest(manifest)
    assert any(e["field"] == "design_system.typography.letter_spacing" for e in exc.value.field_errors)


@pytest.mark.parametrize("bad", [None, [], [1, {}], "color:red", {"position": "absolute"}, {"color": []}, {"border": {"width": 1, "color": [], "style": "solid"}}])
def test_layout_style_invalid_types_never_crash(bad):
    node = {"type": "field", "bind": "body", "style": bad}
    assert validate_layouts({"quote": node})


def test_structure_changes_without_changing_palette_or_preset(manifest):
    config = configuration(manifest)
    layouts = {"evidence_callout": evidence_layout()}
    config["generated_design_system"]["layouts"] = layouts
    article = parse_markdown("# 标题\n\n同一段**证据**，不能被删除。")
    slot = {"component_type": "evidence_callout", "content_bindings": {"evidence": article.blocks[-1].id}}
    side = BeautifulSoup(render_generated_component(slot, article, config), "html.parser")
    layouts["evidence_callout"] = {"type": "stack", "style": {"border_bottom": {"width": 3, "color": "primary", "style": "double"}}, "children": [
        {"type": "field", "bind": "body", "style": {"font": "serif", "align": "center"}},
        {"type": "text", "text": "档案摘录", "style": {"align": "right", "size": "label"}},
    ]}
    centered = BeautifulSoup(render_generated_component(slot, article, config), "html.parser")
    assert len(side.select('section[style*="display:inline-block"]')) == 2
    assert not centered.select('section[style*="display:inline-block"]')
    assert side.select_one('[data-theme-field="body"]').get_text() == centered.select_one('[data-theme-field="body"]').get_text()
    assert side.select_one('[data-theme-field="body"]').name == "p"
    assert not side.select_one('[data-theme-field="body"]').select('[data-theme-static]')


def test_required_content_must_appear_once():
    assert validate_layouts({"quote": {"type": "text", "text": "没有正文"}})
    assert validate_layouts({"quote": {"type": "stack", "children": [{"type": "field", "bind": "body"}] * 2}})
    assert validate_layouts({"list": {"type": "field", "bind": "item"}})
    assert not validate_layouts({"list": {"type": "repeat", "bind": "items", "children": [{"type": "field", "bind": "item"}]}})
    assert validate_layouts({"list": {"type": "repeat", "bind": "items", "children": [{"type": "repeat", "bind": "items", "children": [{"type": "field", "bind": "item"}]}]}})


def test_layout_bounds_and_no_executable_style():
    node = {"type": "field", "bind": "body"}
    for _ in range(10):
        node = {"type": "stack", "children": [node]}
    assert validate_layouts({"quote": node})
    node = evidence_layout()
    node["widths"] = [30, 90]
    assert validate_layouts({"evidence_callout": node})
    node = {"type": "field", "bind": "body", "style": {"background": "url(javascript:alert(1))"}}
    assert validate_layouts({"quote": node})


def test_body_metrics_apply_to_prose_quote_and_components(manifest):
    config = configuration(manifest)
    config["generated_design_system"].pop("layouts", None)
    config["generated_design_system"]["typography"]["body_scale"] = 1.1
    paragraph = render_generated_paragraph("长文正文", config)
    assert "font-size:17.6px" in paragraph
    assert f'color:{manifest["palette"]["ink"]}' in paragraph
    assert "font-size:18.7px" in render_generated_quote("证据原文", config)
    article = parse_markdown("# 标题\n\n证据原文")
    slot = {"component_type": "evidence_callout", "content_bindings": {"evidence": article.blocks[-1].id}}
    assert "font-size:17.6px" in render_generated_component(slot, article, config)


@pytest.mark.parametrize("base", ["warm_humanist", "youth_campus", "future_tech"])
def test_gallery_keeps_custom_hero(base, manifest):
    config = configuration(manifest)
    config["generated_design_system"]["layouts"] = {"hero": {"type": "stack", "children": [
        {"type": "field", "bind": "kicker"}, {"type": "field", "bind": "title", "style": {"size": "title"}},
    ]}}
    with patch("visual_director.theme_gallery.render_visual_system", return_value=base), patch("visual_director.theme_gallery.visual_system_configuration", return_value=config):
        preview = _full_preview(manifest["id"], {"english": manifest["english"]}, [], [], manifest["palette"])
    assert 'data-theme-layout="hero"' in preview
    assert "CAMPUS BULLETIN" not in preview and "FUTURE EDITION" not in preview


def test_layout_pack_schema_install_gallery_article_and_edit_markers(manifest, tmp_path):
    manifest["design_system"]["layouts"] = {
        "hero": {"type": "stack", "children": [{"type": "field", "bind": "kicker"}, {"type": "field", "bind": "title", "style": {"size": "title"}}]},
        "quote": {"type": "field", "bind": "body"},
        "evidence_callout": evidence_layout(),
    }
    schema = json.loads((ROOT / "contracts/theme-pack-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(manifest)
    normalized = validate_theme_pack_manifest(manifest)
    pack = tmp_path / "packs" / manifest["id"]
    pack.mkdir(parents=True)
    (pack / "theme.json").write_text(json.dumps(normalized), encoding="utf-8")
    configure_theme_packs(pack.parent, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    article = parse_markdown("# 新结构文章\n\n## 内容\n\n正文保持。\n\n> 证据保持。")
    plan = apply_visual_system(generate_plans(article, "tutorial_steps", 5)[0], manifest["id"], recent_summaries=[])
    soup = BeautifulSoup(render_preview(article, plan), "html.parser")
    assert soup.select_one('h1[data-editor-title="true"]').get_text() == "新结构文章"
    assert soup.select_one('[data-theme-field="body"]').find_parent(attrs={"data-editor-block-ids": True})
    assert not soup.select("script,[onclick]")
    gallery = next(t for t in build_theme_gallery() if t["id"] == manifest["id"])
    assert all(c["status"] == "wechat_candidate" for c in gallery["components"])
    assert 'data-theme-layout="hero"' in gallery["full_preview_html"]
    assert visual_system_configuration(manifest["id"])["generated_design_system"]["layouts"] == manifest["design_system"]["layouts"]


def test_literal_markup_is_text_and_all_repeated_content_survives(manifest):
    config = configuration(manifest)
    config["generated_design_system"]["layouts"] = {"list": {"type": "repeat", "bind": "items", "children": [{"type": "field", "bind": "item"}]}}
    items = ["<script>alert(1)</script>", "长内容" * 500, "最后一项"]
    soup = BeautifulSoup(render_layout("list", {"items": items}, config), "html.parser")
    assert not soup.select("script")
    assert [n.get_text() for n in soup.select('[data-theme-field="item"]')] == items


def test_custom_heading_uses_section_rhythm_and_preserves_style_cascade(manifest):
    config = configuration(manifest)
    design = config["generated_design_system"]
    design["rhythm"].update(section_gap=60, component_gap=20, density="airy")
    design["layouts"] = {"heading": {"type": "stack", "style": {"color": "accent"}, "children": [
        {"type": "field", "bind": "title", "style": {"size": "heading"}},
    ]}}
    document = render_layout("heading", {"title": "章节标题"}, config)
    assert "margin:72px 0" in document
    field = BeautifulSoup(document, "html.parser").select_one('[data-theme-field="title"]')
    assert "color:" not in field["style"]  # inherits the author's accent color


def test_generated_table_preserves_columns_after_the_fourth(manifest):
    from visual_director.generated_theme import render_generated_table

    soup = BeautifulSoup(render_generated_table([["A", "B", "C", "D", "E"], ["1", "2", "3", "4", "5"]], configuration(manifest)), "html.parser")
    assert [cell.get_text() for cell in soup.select("th")] == ["A", "B", "C", "D", "E"]
    assert [cell.get_text() for cell in soup.select("td")] == ["1", "2", "3", "4", "5"]
