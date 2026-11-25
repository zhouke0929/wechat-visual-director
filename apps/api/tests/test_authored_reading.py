"""Authored fields preserve theme CSS unless a specific internal override exists."""
import pytest
from bs4 import BeautifulSoup

from visual_director import reading_rules as rules
from visual_director.brief_compiler import visual_system_configuration
from visual_director.image_caption_render import caption_metrics_attribute, stored_caption_profile
from visual_director.publication import _materialized_image_markup


def _override(monkeypatch, value):
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")
    monkeypatch.setattr(rules, "THEME_READING_OVERRIDES", {"light_reading": value})
    return rules.resolve_reading_profile(visual_system_configuration("light_reading"), official=True, theme_id="light_reading")


def test_authored_type_retains_theme_recipe_and_styles_only_source_emphasis(monkeypatch):
    markup = '普通文字与 <strong style="color:#456;">明确重点</strong>，以及 &lt;strong&gt;'
    original = _override(monkeypatch, {})
    assert rules.render_authored_text(markup, rules.BODY, original) == markup
    assert rules.authored_host_css("font:15px/1.7 Georgia;", rules.BODY, original) == "font:15px/1.7 Georgia;"
    trial = _override(monkeypatch, {rules.BODY: {"before_px": 2, "size_px": 17},
                                   rules.INLINE_EMPHASIS: {"weight": 800}})
    rendered = rules.render_authored_text(markup, rules.BODY, trial)
    assert rendered == '<span style="font-size:17px;">' + markup.replace("color:#456;", "color:#456;font-weight:800;") + "</span>"
    assert rules.authored_host_css("color:#345;", rules.BODY, trial) == "color:#345;font-size:17px;margin-top:2px;"


@pytest.mark.parametrize("role", [rules.LIST_BODY, rules.STEP_BODY])
def test_registration_does_not_apply_reference_metrics_to_published_styles(monkeypatch, role):
    css = "font-size:14px;font-weight:650;line-height:1.67;padding:2px 9px;"
    original = _override(monkeypatch, {})
    assert rules.apply_reading_css(css, role, original) == css
    assert rules.apply_reading_emphasis("<strong>原来的重点</strong>", original) == "<strong>原来的重点</strong>"
    assert rules.reading_gap(rules.STEP_TITLE, original, 9) == 9
    custom = _override(monkeypatch, {role: {"line_height": 1.91}})
    assert rules.apply_reading_css(css, role, custom) == css.replace("line-height:1.67;", "") + "line-height:1.91;"


@pytest.mark.parametrize("theme", ("light_reading", "folded_fan_detail"))
def test_source_caption_uses_captured_not_current_metrics(monkeypatch, theme):
    trial = _override(monkeypatch, {rules.CAPTION: {"weight": 600, "size_px": 15, "before_px": 0}})
    attr = caption_metrics_attribute(trial)
    assert caption_metrics_attribute(None) == "" and stored_caption_profile("<section>") is None
    monkeypatch.delenv("WVD_READING_RULES_PILOT")
    kwargs = dict(element_id="img", anchor_class="source-image-anchor", content_url="/api/v1/image-assets/sample",
                  width=200, height=100, alt="A < B", frame_variant="neutral", caption_html="A &lt; B",
                  theme_config=visual_system_configuration(theme))
    unchanged = _materialized_image_markup(**kwargs)
    styled = _materialized_image_markup(**kwargs, reading=stored_caption_profile("<section"+attr+">"))
    a, b = [BeautifulSoup(html, "html.parser") for html in (unchanged, styled)]
    assert a.img == b.img
    assert a.get_text(strip=True) == b.get_text(strip=True) == "A < B"
    assert "font-size:15px;font-weight:600;margin-top:0px;" in b.find(string="A < B").parent["style"]
    assert _materialized_image_markup(**kwargs) == unchanged


@pytest.mark.parametrize("value", ('[]', '{"size_px":1000}', '{"color":"red"}', '{"weight":"bold;display:none"}'))
def test_bad_image_snapshot_cannot_inject_theme_css(value):
    with pytest.raises(ValueError):
        stored_caption_profile('<section data-image-caption-metrics="' + value.replace('"', '&quot;') + '">')
