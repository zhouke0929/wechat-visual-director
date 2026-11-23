from copy import deepcopy

import pytest
from bs4 import BeautifulSoup

from visual_director.brief_compiler import visual_system_configuration, visual_system_variant
from visual_director.component_catalog import VISUAL_SYSTEM_ORDER
from visual_director import reading_rules
from visual_director.components import render_component
from visual_director.parser import parse_markdown
from visual_director.step_content import STEP_HIERARCHY_FORMAT


ARTICLE = parse_markdown(
        "# 检查流程\n\n"
        "1. **先看原图**\\\n   对照原稿，核对 **原来的位置**。\n"
        "2. 看完之后再保存。\n"
        "3. **注意：** 保留原有重点。\n"
        "4. **最后复查**\\\n   切到手机宽度再看一次。"
)
STEPS = next(block for block in ARTICLE.blocks if block.type == "ordered_list")
DETAIL_STYLE = "display:block;padding-top:2px;font-weight:400;"


def render(theme, configuration, *, selected=None, kind="logic_path", variant=None):
    slot = {
        "component_type": kind,
        "variant": variant or visual_system_variant(kind, theme),
        "content_bindings": {"items": [f"{STEPS.id}:item:{i}" for i in range(4)]},
    }
    return render_component(slot, ARTICLE, configuration["palette"], configuration, visual_system=selected)


@pytest.mark.parametrize("structure,reading", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("theme", VISUAL_SYSTEM_ORDER)
def test_official_theme_keeps_source_inline_emphasis_without_inventing_a_step_hierarchy(
    theme, structure, reading, monkeypatch
):
    monkeypatch.setenv("WVD_RENDERER_PILOT", str(int(structure)))
    monkeypatch.setenv("WVD_READING_RULES_PILOT", str(int(reading)))
    config = visual_system_configuration(theme)
    markup = render(theme, config, selected=theme)
    doc = BeautifulSoup(markup, "html.parser")
    assert DETAIL_STYLE not in markup
    assert doc.find("strong", string="先看原图").next_sibling.name == "br"
    assert doc.find("strong", string="最后复查").next_sibling.name == "br"
    assert doc.find("strong", string="原来的位置")
    assert [el.get_text() for el in doc.select("[data-editor-step-ref]")] or not structure


@pytest.mark.parametrize("kind", ["logic_path", "numbered_insight", "action_checklist"])
def test_pop_uses_the_released_list_artwork_without_new_theme_id_exceptions(kind):
    config = visual_system_configuration("pop_poster")
    markup = render("pop_poster", config, selected="pop_poster", kind=kind)
    doc = BeautifulSoup(markup, "html.parser")
    rows = doc.select(f'[data-list-role="{kind}"] section > p')
    markers = doc.select(f'[data-list-role="{kind}"] section > span')
    assert len(rows) == 4 and all("font-weight:700;line-height:1.68;" in row["style"] for row in rows)
    assert [marker.get_text() for marker in markers] == ["01", "02", "03", "04"]
    assert all("font-size:12px;font-weight:900;line-height:29px;" in marker["style"] for marker in markers)


def test_the_field_format_not_official_status_controls_custom_step_hierarchy():
    theme = "pixel_live"
    config = visual_system_configuration(theme)
    assert DETAIL_STYLE not in render(theme, config, selected="my_custom_theme")
    assert DETAIL_STYLE not in render(theme, config, selected=theme)
    config = deepcopy(config)
    row = config["generated_design_system"]["layouts"]["logic_path"]["children"][0]["children"]
    next(field for field in row if field["bind"] == "item")["format"] = STEP_HIERARCHY_FORMAT
    enabled = render(theme, config, selected="my_custom_theme")
    assert enabled.count(DETAIL_STYLE) == 2
    assert enabled == render(theme, config, selected=theme)


@pytest.mark.parametrize("theme", ["light_reading", "pop_poster", "pixel_live"])
def test_emphasis_only_does_not_trigger_a_step_hierarchy(theme, monkeypatch):
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")
    changes = {reading_rules.INLINE_EMPHASIS: {"weight": 833}}
    monkeypatch.setattr(reading_rules, "THEME_READING_OVERRIDES", {theme: changes})
    config = visual_system_configuration(theme)
    plain = BeautifulSoup(render(theme, config, selected=theme), "html.parser")
    title = plain.find("strong", string="先看原图")
    assert title.next_sibling.name == "br"
    assert "font-weight:833" in title["style"]
    if theme == "pixel_live":
        config = deepcopy(config)
        row = config["generated_design_system"]["layouts"]["logic_path"]["children"][0]["children"]
        next(field for field in row if field["bind"] == "item")["format"] = STEP_HIERARCHY_FORMAT
        opted_in = BeautifulSoup(render(theme, config, selected=theme), "html.parser")
        assert opted_in.find("strong", string="先看原图").find_next_sibling("span").strong["style"] == "font-weight:833;"
    changes[reading_rules.STEP_TITLE] = {"weight": 811}
    config = visual_system_configuration(theme)
    split = BeautifulSoup(render(theme, config, selected=theme), "html.parser")
    assert "font-weight:811" in split.find("strong", string="先看原图")["style"]


def test_one_bound_step_interpretation_reused_by_all_projectors_and_editor_modes(monkeypatch):
    from visual_director import logic_path_content, semantic_content
    from visual_director.components import render_bound_component

    count = []
    interpret = semantic_content.interpret_step

    def counted(source):
        count.append(source)
        return interpret(source)

    def reject_reparse(_):
        pytest.fail("An article field was converted back to raw text and interpreted by the layout")

    monkeypatch.setattr(semantic_content, "interpret_step", counted)
    monkeypatch.setattr(logic_path_content, "interpret_step", reject_reparse)
    refs = [f"{STEPS.id}:item:{i}" for i in range(4)]
    bound = semantic_content.SemanticSource.from_article(ARTICLE).bind(
        {"component_type": "logic_path", "content_bindings": {"items": refs}})
    assert count == STEPS.content
    assert [step.content.title for step in bound.steps] == ["先看原图", None, None, "最后复查"]
    assert bound.steps[0].content.detail == "对照原稿，核对 **原来的位置**。"
    assert [s.content is t.content for s, t in zip(bound.steps, bound.step_fields(editable=True))] == [True] * 4
    monkeypatch.setenv("WVD_LOGIC_PATH_PILOT", "0")
    for mode in ("0", "1"):
        monkeypatch.setenv("WVD_RENDERER_PILOT", mode)
        for theme in ("light_reading", "pop_poster", "pixel_live"):
            config = visual_system_configuration(theme)
            if theme == "pixel_live":  # same bound source, explicitly split in this drawing
                config = deepcopy(config)
                row = config["generated_design_system"]["layouts"]["logic_path"]["children"][0]["children"]
                next(node for node in row if node["bind"] == "item")["format"] = STEP_HIERARCHY_FORMAT
            markup = render_bound_component(bound, visual_system_variant("logic_path", theme),
                                            config["palette"], config, visual_system=theme)
            dom = BeautifulSoup(markup, "html.parser")
            assert [e["data-editor-step-ref"] for e in dom.select("[data-editor-step-ref]")] == (refs if mode == "1" else [])
            assert (DETAIL_STYLE in markup) == (theme == "pixel_live")
            assert "<strong>注意：</strong> 保留原有重点。" in markup
    assert count == STEPS.content


def test_legacy_token_fallback_scales_decorations_but_not_opted_in_step_roles(monkeypatch):
    theme = "pixel_live"
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")
    monkeypatch.setattr(reading_rules, "THEME_READING_OVERRIDES", {theme: {
        reading_rules.STEP_BODY: {"size_px": 17.5}, reading_rules.STEP_TITLE: {"size_px": 22},
        reading_rules.STEP_DETAIL: {"size_px": 13}, reading_rules.INLINE_EMPHASIS: {"weight": 812},
    }})
    config = deepcopy(visual_system_configuration(theme))
    config["generated_design_system"]["layouts"].pop("logic_path")
    config["generated_design_system"]["typography"]["body_scale"] = 1.2
    doc = BeautifulSoup(render(theme, config, selected=theme), "html.parser")
    steps = doc.select("[data-editor-step-ref]")
    assert len(steps) == 4 and all("font-size:17.5px;" in s["style"] for s in steps)
    assert "font-size:22px;" in steps[0].strong["style"]
    detail = steps[0].strong.find_next_sibling("span")
    assert "font-size:13px;" in detail["style"] and "font-weight:812;" in detail.strong["style"]
    assert not steps[1].strong and not steps[1].span
