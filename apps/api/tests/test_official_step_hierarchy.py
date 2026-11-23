from copy import deepcopy

import pytest
from bs4 import BeautifulSoup

from visual_director.brief_compiler import visual_system_configuration, visual_system_variant
from visual_director.component_catalog import VISUAL_SYSTEM_ORDER
from visual_director import components
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


@pytest.mark.parametrize("theme", VISUAL_SYSTEM_ORDER)
def test_official_default_only_changes_two_explicit_steps(theme, monkeypatch):
    configuration = visual_system_configuration(theme)
    with monkeypatch.context() as baseline:
        baseline.setattr(components, "_step_inline", components._inline)
        before = render(theme, configuration, selected=theme)
    after = render(theme, configuration, selected=theme)

    doc = BeautifulSoup(after, "html.parser")
    assert doc.get_text(strip=True) == BeautifulSoup(before, "html.parser").get_text(strip=True)
    details = doc.select(f'span[style="{DETAIL_STYLE}"]')
    assert [el.find_previous_sibling("strong").get_text() for el in details] == ["先看原图", "最后复查"]
    assert details[0].strong.get_text() == "原来的位置"
    # Restore the original inline fragments; the rest of the component must be byte-identical.
    for el in details:
        title = el.find_previous_sibling("strong").get_text()
        after = after.replace(
            f'<strong style="font-weight:750;">{title}</strong>\n<span style="{DETAIL_STYLE}">{el.decode_contents()}</span>',
            f"<strong>{title}</strong><br>{el.decode_contents()}",
            1,
        )
    assert after == before
    assert render(theme, configuration, selected=theme, kind="numbered_insight") == render(
        theme, configuration, selected="non_official", kind="numbered_insight"
    )


def test_pop_logic_path_does_not_look_bold_outside_the_original_emphasis():
    theme = "pop_poster"
    config = visual_system_configuration(theme)
    markup = render(theme, config, selected=theme)
    doc = BeautifulSoup(markup, "html.parser")
    rows = doc.select('[data-list-role="logic_path"] section > p')
    assert len(rows) == 4
    assert all("font-weight:400;" in row["style"] for row in rows)
    assert [tag.get_text() for tag in rows[2].find_all("strong")] == ["注意："]
    assert [row.select_one("span strong").get_text() for row in rows if row.select_one("span strong")] == ["原来的位置"]
    legacy_custom = render(theme, config, selected="my_custom_theme")
    assert 'font-weight:700;line-height:1.68;' in legacy_custom


def test_pop_larger_step_markers_are_limited_to_the_official_logic_path():
    theme = "pop_poster"
    config = visual_system_configuration(theme)
    for selected, kind, expected_size in (
        (theme, "logic_path", 14),
        (theme, "numbered_insight", 12),
        (theme, "action_checklist", 12),
        ("my_custom_theme", "logic_path", 12),
    ):
        doc = BeautifulSoup(render(theme, config, selected=selected, kind=kind), "html.parser")
        markers = doc.select(f'[data-list-role="{kind}"] section > span')
        assert [marker.get_text() for marker in markers] == ["01", "02", "03", "04"]
        assert all(
            f"font-size:{expected_size}px;font-weight:900;line-height:29px;" in marker["style"] for marker in markers
        )


def test_custom_themes_keep_old_default_even_when_inheriting_an_official_layout():
    theme = "pixel_live"
    config = visual_system_configuration(theme)
    # The selected theme, not its copied configuration/master layout, controls the default.
    inherited = render(theme, config, selected="my_custom_theme")
    assert DETAIL_STYLE not in inherited
    assert "<strong>先看原图</strong><br>" in inherited

    config = deepcopy(config)
    row = config["generated_design_system"]["layouts"]["logic_path"]["children"][0]["children"]
    next(field for field in row if field["bind"] == "item")["format"] = STEP_HIERARCHY_FORMAT
    opted_in = render(theme, config, selected="my_custom_theme")
    assert opted_in == render(theme, visual_system_configuration(theme), selected=theme)
