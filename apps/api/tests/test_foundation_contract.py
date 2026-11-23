"""Exercise role dispatch and typed source fields through production article rendering."""
import pytest
from bs4 import BeautifulSoup

from visual_director import reading_rules as rules
from visual_director.brief_compiler import visual_system_configuration
from visual_director.component_catalog import VISUAL_SYSTEM_ORDER
from visual_director.foundation_renderer import BLOCK_PROJECTORS
from visual_director.generated_theme import render_generated_quote, render_generated_table
from visual_director.theme_specimens import build_production_specimens


def test_all_foundations_have_one_source_route():
    # The opening title and brand footer are document sources; inline emphasis
    # belongs to its authored text field, not to an independent block.
    assert set(BLOCK_PROJECTORS) | {"hero", "closing_cta"} == set(rules.FOUNDATION_READING_ROLES)


@pytest.mark.parametrize("theme", VISUAL_SYSTEM_ORDER)
def test_explicit_foundation_fields_reach_native_kit_and_pack(monkeypatch, theme):
    roles = {
        "hero": rules.ARTICLE_TITLE, "lead": rules.LEAD, "paragraph": rules.BODY,
        "section_heading": rules.SECTION_TITLE, "subheading": rules.SUBHEADING, "quote": rules.QUOTE,
        "source": rules.SOURCE, "reference_list": rules.REFERENCE, "closing_cta": rules.BRAND_FOOTER,
    }
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")
    overrides = {role: {"size_px": 31.5} for role in roles.values()}
    overrides.update({rules.TABLE_HEADER: {"size_px": 29.5}, rules.TABLE_BODY: {"size_px": 27.5}})
    monkeypatch.setattr(rules, "THEME_READING_OVERRIDES", {theme: overrides})
    samples, _ = build_production_specimens(theme)
    by_role = {sample["role"]: sample["html"] for sample in samples}
    for role in roles:
        assert "font-size:31.5px;" in by_role[role], (theme, role)
    table = BeautifulSoup(by_role["table"], "html.parser")
    for tag, size in (("th", 29.5), ("td", 27.5)):
        cells = [cell for cell in table.find_all(tag) if cell.get_text(strip=True)]
        assert cells and all(f"font-size:{size}px;" in str(cell) for cell in cells)


def test_generated_token_typography_never_scales_authored_text_twice(monkeypatch):
    theme = "folded_fan_detail"
    config = visual_system_configuration(theme)
    design = dict(config["generated_design_system"])
    design.pop("layouts", None)
    design["typography"] = {**design["typography"], "body_scale": 1.1}
    config = {**config, "generated_design_system": design}
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")
    monkeypatch.setattr(rules, "THEME_READING_OVERRIDES", {theme: {
        role: {"size_px": 19} for role in (rules.QUOTE, rules.TABLE_BODY, rules.TABLE_HEADER)
    }})
    profile = rules.resolve_reading_profile(config, official=True, theme_id=theme)
    source = "font-size:12px; <span> <!--wvd-type-field:0-->"
    for markup in (render_generated_quote(source, config, reading=profile),
                   render_generated_table([["表头"], [source]], config, reading=profile)):
        dom = BeautifulSoup(markup, "html.parser")
        assert source in dom.get_text() and "font-size:19px;" in str(dom)
        assert "font-size:20.9px;" not in str(dom)
