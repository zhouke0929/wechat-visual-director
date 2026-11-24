"""A real maintenance change to one component, never an official visual change."""
import copy

import pytest
from bs4 import BeautifulSoup

from visual_director import official_component_recipes as catalog
from visual_director import theme_gallery
from visual_director.brief_compiler import visual_system_configuration, visual_system_variant
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.component_presentation import resolve_component_recipe, validate_component_recipes
from visual_director.components import render_bound_component
from visual_director.parser import parse_markdown
from visual_director.semantic_content import SemanticSource
from visual_director.theme_specimens import build_production_specimens


FAN, TIMELINE = "folded_fan_detail", "before_after_timeline"
LOCAL = {"outer_before_px": 13, "outer_after_px": 31, "field_sizes_px": {"left": 19.5}}


def samples(theme):
    parsed = parse_markdown(theme_gallery.THEME_FIXTURE)
    source, bindings = SemanticSource.from_article(parsed), theme_gallery._fixture_bindings(parsed)
    config = visual_system_configuration(theme)
    foundation, _ = build_production_specimens(theme)
    roles = {row["role"]: row["html"] for row in foundation}
    for role in CORE_THEME_COMPONENTS:
        content = source.bind({"component_type": role, "content_bindings": bindings[role]})
        roles[role] = render_bound_component(content, visual_system_variant(role, theme), config["palette"],
                                             config, visual_system=theme)
    return roles


def test_one_theme_one_component_one_text_field_and_real_outer_edges(monkeypatch):
    # These are the actual official registry, snapshot, content binding and HTML
    # projection, not a hand-built layout shown only on a standalone test page.
    original = {theme: samples(theme) for theme in VISUAL_SYSTEM_ORDER}
    monkeypatch.setattr(catalog, "OFFICIAL_COMPONENT_RECIPES", {
        **catalog.OFFICIAL_COMPONENT_RECIPES,
        FAN: {**catalog.OFFICIAL_COMPONENT_RECIPES.get(FAN, {}), TIMELINE: LOCAL},
    })
    changed = {theme: samples(theme) for theme in VISUAL_SYSTEM_ORDER}
    altered = [(theme, role) for theme in original for role in original[theme]
               if original[theme][role] != changed[theme][role]]
    assert altered == [(FAN, TIMELINE)]
    old, new = [BeautifulSoup(matrix[FAN][TIMELINE], "html.parser") for matrix in (original, changed)]
    selector = '[data-theme-layout="before_after_timeline"]'
    edge, old_edge = new.select_one(selector), old.select_one(selector)
    left, old_left = edge.select_one('[data-theme-field="left"]'), old_edge.select_one('[data-theme-field="left"]')
    assert edge["style"] == old_edge["style"].replace(";", ";margin-top:13px;margin-bottom:31px;", 1)
    assert left["style"] == old_left["style"] + "font-size:19.5px;"
    # Restore just these two owned styles; all padding, line height, sibling
    # text, column arrangement, labels, drawings and actual data are identical.
    edge["style"], left["style"] = old_edge["style"], old_left["style"]
    assert str(old) == str(new)


@pytest.mark.parametrize("bad", [
    {"outer_before_px": True}, {"outer_before_px": -1}, {"outer_after_px": float("nan")},
    {"field_sizes_px": {"right": "12px"}}, {"field_sizes_px": {"right": 9}},
    {"field_sizes_px": {"index": 17}}, {"field_sizes_px": {}}, {"line_height": 1.6},
    {"outer_before_px": 1, "css": "padding:7px"}, {"default_variant": "paired_current"},
    {"layout": "split_page_flip"}, {"layout": "invalid", "default_variant": "paired_current"},
    {"layout": "split_page_flip", "default_variant": "not_a_timeline_variant"},
])
def test_recipe_rejects_unreachable_or_unbounded_configuration(bad):
    with pytest.raises(ValueError):
        validate_component_recipes({"version": 1, "roles": {TIMELINE: bad}})


def test_zero_is_explicit_and_preserves_horizontal_and_unselected_field_styles():
    cfg = {"component_recipes": {"version": 1, "roles": {TIMELINE: {
        "outer_after_px": 0, "field_sizes_px": {"right": 17},
    }}}}
    before = copy.deepcopy(cfg)
    recipe = resolve_component_recipe(cfg, TIMELINE)
    assert recipe.box_css("margin:11px 9px 18px 5px;") == "margin:11px 9px 18px 5px;margin-bottom:0px;"
    assert recipe.field_css("line-height:1.6;", "right") == "line-height:1.6;font-size:17px;"
    assert recipe.field_css("line-height:1.6;", "left") == "line-height:1.6;"
    assert recipe.box_css("padding:2px") == "padding:2px;margin-bottom:0px;"
    assert recipe.field_css("line-height:1.6", "right") == "line-height:1.6;font-size:17px;"
    assert resolve_component_recipe(cfg, "comparison_card").margin_css(15) == "margin:15px 0;"
    assert cfg == before


def test_generated_token_fallback_honors_same_margin_and_absolute_field_size(monkeypatch):
    monkeypatch.setattr(catalog, "OFFICIAL_COMPONENT_RECIPES", {FAN: {TIMELINE: LOCAL}})
    config = visual_system_configuration(FAN)
    # Old generated plans and partial authored layouts reach the token fallback.
    design = copy.deepcopy(config["generated_design_system"])
    del design["layouts"][TIMELINE]
    design["typography"]["body_scale"] = 1.1
    config = {**config, "generated_design_system": design}
    article = parse_markdown("# Pair\n\nBefore text.\n\nAfter text.")
    fields = {"before": article.blocks[1].id, "after": article.blocks[2].id}
    bound = SemanticSource.from_article(article).bind({"component_type": TIMELINE, "content_bindings": fields})
    doc = BeautifulSoup(render_bound_component(bound, visual_system_variant(TIMELINE, FAN),
                        config["palette"], config, visual_system=FAN), "html.parser")
    box = doc.select_one('[data-component-type="before_after_timeline"]')
    assert "margin-top:13px;margin-bottom:31px;" in box["style"]
    before = doc.find(string="Before text.").parent
    assert "font-size:19.5px;" in before["style"]
    assert "font-size:19.5px;" not in doc.find(string="After text.").parent["style"]


@pytest.mark.parametrize("theme", VISUAL_SYSTEM_ORDER)
def test_geometry_only_recipe_reaches_existing_timeline_without_selecting_another_shape(monkeypatch, theme):
    article = parse_markdown("# Pair\n\nBefore text.\n\nAfter text.")
    fields = {"before": article.blocks[1].id, "after": article.blocks[2].id}
    bound = SemanticSource.from_article(article).bind({"component_type": TIMELINE, "content_bindings": fields})
    variant = visual_system_variant(TIMELINE, theme)

    def actual():
        cfg = visual_system_configuration(theme)
        return BeautifulSoup(render_bound_component(bound, variant, cfg["palette"], cfg, visual_system=theme),
                             "html.parser")

    old = actual()
    monkeypatch.setattr(catalog, "OFFICIAL_COMPONENT_RECIPES", {theme: {TIMELINE: LOCAL}})
    new = actual()
    assert old.get_text() == new.get_text()
    style_of = lambda node: node.get("style", "")
    frame = [node for node in new.find_all(style=True) if "margin-top:13px;margin-bottom:31px;" in style_of(node)]
    before, after = (new.find(string=t) for t in ("Before text.", "After text."))
    assert len(frame) == 1 and frame[0] in before.parents and frame[0] in after.parents
    assert any("font-size:19.5px;" in style_of(n) for n in before.parents)
    assert not any("font-size:19.5px;" in style_of(n) for n in after.parents)
    assert [(n.name, n.get("data-theme-grammar")) for n in new.select("[data-theme-grammar]")] == [
        (n.name, n.get("data-theme-grammar")) for n in old.select("[data-theme-grammar]")]
