"""Isolate catalogue selection from replaying an article's stored configuration."""
import json

import pytest
from bs4 import BeautifulSoup

from visual_director import brief_compiler as compiler, official_component_recipes as catalogue
from visual_director import reading_rules
from visual_director.component_catalog import COMPONENT_CATALOG, VISUAL_SYSTEM_ORDER
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director.renderer import render_preview


FAN = "folded_fan_detail"
ROLE = "before_after_timeline"


def _sample():
    article = parse_markdown("# 两次校对\n\n过去分开发送。\n\n现在合并发送。")
    before, after = [b for b in article.blocks if b.type == "paragraph"]
    plan = generate_plans(article, "tutorial_steps", 5)[0]
    plan["slots"] = [{
        "slot_id": "slot-001", "component_type": ROLE, "semantic_role": ROLE,
        "variant": compiler.visual_system_variant(ROLE, FAN),
        "fallback_variant": COMPONENT_CATALOG[ROLE]["fallback_variant"],
        "anchor_block_id": before.id, "consume_block_ids": [before.id, after.id],
        "content_bindings": {"before": before.id, "after": after.id},
        "emphasis": "primary", "selection_reason": "前后对照", "facts_locked": True,
    }]
    plan["image_slots"] = []
    return article, plan


def test_selected_recipe_survives_replay_but_does_not_follow_a_theme_switch(monkeypatch):
    article, seed = _sample()
    def render(plan):
        return render_preview(article, plan, brand_profile={})
    old = compiler.apply_visual_system(seed, FAN)
    assert "component_recipes" not in old["configuration"]
    old_html = render(old)
    declaration = {"layout": "split_page_flip", "outer_after_px": 19, "field_sizes_px": {"left": 21}}
    monkeypatch.setattr(catalogue, "OFFICIAL_COMPONENT_RECIPES", {FAN: {ROLE: declaration}})
    selected = compiler.apply_visual_system(seed, FAN)
    assert selected["slots"] == old["slots"]  # style does not re-plan or change the source
    chosen_html = render(selected)
    assert chosen_html != old_html and "font-size:21px;" in chosen_html
    assert "margin-bottom:19px;" in chosen_html
    text = BeautifulSoup(chosen_html, "html.parser").get_text()
    assert text.count("过去分开发送。") == text.count("现在合并发送。") == 1
    assert text.index("过去分开发送。") < text.index("现在合并发送。")

    declaration["field_sizes_px"]["left"] = 22
    assert "font-size:22px;" in render(compiler.apply_visual_system(seed, FAN))
    assert render(json.loads(json.dumps(selected))) == chosen_html
    assert render(old) == old_html
    switched = compiler.apply_visual_system(selected, "pop_poster")
    assert "component_recipes" not in switched["configuration"]
    assert render(switched) == render(compiler.apply_visual_system(seed, "pop_poster"))


def test_v1_inheritance_and_unconfigured_themes_do_not_import_official_overrides(monkeypatch):
    monkeypatch.setattr(catalogue, "OFFICIAL_COMPONENT_RECIPES", {FAN: {ROLE: {"outer_before_px": 11}}})
    monkeypatch.setattr(reading_rules, "THEME_READING_OVERRIDES", {FAN: {reading_rules.LIST_BODY: {"size_px": 19}}})
    for theme in VISUAL_SYSTEM_ORDER:
        assert ("component_recipes" in compiler.visual_system_configuration(theme)) == (theme == FAN)
    original = compiler.theme_pack
    monkeypatch.setattr(compiler, "theme_pack", lambda key: {
        "base_theme": FAN, "palette": compiler.base_visual_system_configuration(FAN)["palette"], "version": "1.0.0",
    } if key == "local-user-test" else original(key))
    assert {"component_recipes", "reading_overrides"}.isdisjoint(compiler.visual_system_configuration("local-user-test"))


def test_reading_configuration_replays_the_selected_value_after_catalogue_changes(monkeypatch):
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")
    theme_rules = {reading_rules.LIST_BODY: {"size_px": 18}}
    old = compiler.visual_system_configuration(FAN)
    monkeypatch.setattr(reading_rules, "THEME_READING_OVERRIDES", {FAN: theme_rules})
    saved = compiler.visual_system_configuration(FAN)
    theme_rules[reading_rules.LIST_BODY]["size_px"] = 20
    fresh = compiler.visual_system_configuration(FAN)
    assert "reading_overrides" not in old
    for cfg, expected in ((json.loads(json.dumps(saved)), 18), (fresh, 20)):
        profile = reading_rules.resolve_reading_profile(cfg, official=True, theme_id=FAN)
        assert profile.rules[reading_rules.LIST_BODY].size_px == expected


def test_unregistered_component_with_layout_is_rejected(monkeypatch):
    monkeypatch.setattr(catalogue, "OFFICIAL_COMPONENT_RECIPES", {FAN: {"unknown-role": {"layout": "split_page_flip"}}})
    with pytest.raises(ValueError, match="Unknown official component"):
        compiler.visual_system_configuration(FAN)


def test_maintainer_cannot_pin_an_arbitrary_variant_as_the_default(monkeypatch):
    monkeypatch.setattr(catalogue, "OFFICIAL_COMPONENT_RECIPES", {FAN: {ROLE: {
        "layout": "split_page_flip", "default_variant": "made_up",
    }}})
    with pytest.raises(ValueError, match="Invalid official component recipe"):
        compiler.visual_system_configuration(FAN)
