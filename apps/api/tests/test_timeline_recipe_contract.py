"""Opt-in reuse of two existing timelines across all three theme sources."""
import json

import pytest
from bs4 import BeautifulSoup

from visual_director.brief_compiler import visual_system_configuration, visual_system_variant
from visual_director.component_catalog import COMPONENT_CATALOG
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director.renderer import render_preview


ROLE = "before_after_timeline"
THEMES = ("warm_humanist", "pop_poster", "folded_fan_detail")
BEFORE = "旧版先发清单。大家需要逐项复核报名时间、入口和图片是否都在同一个地方。" * 3
AFTER = "新版先确认**日期**，再去同一页查看领取方式、原稿与原图之间的对应关系。" * 4


def _render(theme, recipe=None, *, variant=None):
    parsed = parse_markdown(f"# 同一篇稿件\n\n{BEFORE}\n\n{AFTER}")
    before, after = [b.id for b in parsed.blocks if b.type == "paragraph"]
    config = visual_system_configuration(theme)
    default = visual_system_variant(ROLE, theme)
    if recipe is not None:
        entry = dict(recipe)
        if "layout" in entry:
            entry.update(default_variant=default)
        config = {**config, "component_recipes": {"version": 1, "roles": {ROLE: entry}}}
    slot = {"slot_id": "slot-001", "component_type": ROLE, "semantic_role": ROLE,
            "anchor_block_id": before, "consume_block_ids": [before, after],
            "variant": variant or default, "fallback_variant": COMPONENT_CATALOG[ROLE]["fallback_variant"],
            "emphasis": "primary", "content_bindings": {"before": before, "after": after},
            "selection_reason": "原文明确前后变化"}
    plan = generate_plans(parsed, "tutorial_steps", 5)[0]
    plan.update(configuration=config, visual_system=theme, slots=[slot], image_slots=[])
    # Public render path after an ordinary JSON snapshot round trip.
    document = render_preview(parsed, json.loads(json.dumps(plan)), brand_profile={})
    return BeautifulSoup(document, "html.parser").find(id="slot-001")


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("layout", ("stacked_before_after", "split_page_flip"))
def test_same_existing_layout_is_reusable_with_either_geometry_and_preserves_text(theme, layout):
    default = _render(theme)
    candidate = _render(theme, {"layout": layout})
    assert candidate != default
    assert candidate["data-editor-block-ids"] == default["data-editor-block-ids"]
    assert candidate["data-editor-block-type"] == "component:before_after_timeline"
    assert candidate.get_text().count(BEFORE) == 1
    assert candidate.get_text().count(AFTER.replace("**", "")) == 1
    assert candidate.get_text().index(BEFORE) < candidate.get_text().index(AFTER[:5])
    assert len(candidate.find_all("strong", string="日期")) == 4
    box = candidate.find("section", recursive=False)
    boxes = box.find_all(recursive=False)
    if layout == "stacked_before_after":
        assert [node.name for node in boxes] == ["p", "p"]
        assert [node.strong.get_text() for node in boxes] == ["之前：", "之后："]
    else:
        assert [node.name for node in boxes] == ["section", "span", "section"]
        assert [node.span.get_text() for node in (boxes[0], boxes[2])] == ["BEFORE PAGE", "NEXT PAGE"]
        assert boxes[1].get_text() == "›"
        assert all("display:inline-block;width:47%" in n["style"] for n in (boxes[0], boxes[2]))
        assert "transform:rotate(-1deg)" in boxes[0]["style"] and "transform:rotate(1deg)" in boxes[2]["style"]


@pytest.mark.parametrize("theme", THEMES)
def test_layout_default_does_not_mask_manual_slot_variant(theme):
    # Respect the historical backend's behavior for that exact variant, even
    # when an older generated theme draws its own layout rather than a variant.
    manual = "shift_axis"
    assert _render(theme, {"layout": "split_page_flip"}, variant=manual) == _render(theme, variant=manual)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("with_layout", (False, True))
def test_geometry_only_changes_real_stored_pair_and_its_one_selected_text_field(theme, with_layout):
    base = {"layout": "split_page_flip"} if with_layout else {}
    original = _render(theme, base or None)
    styled = _render(theme, {**base, "outer_before_px": 0, "outer_after_px": 41, "field_sizes_px": {"left": 23.5}})
    assert styled.get_text() == original.get_text()
    sized = styled.find_all(style=lambda css: css and "font-size:23.5px;" in css)
    assert len(sized) == 1 and sized[0].get_text() == BEFORE
    boxes = styled.find_all(style=lambda css: css and "margin-top:0px;margin-bottom:41px;" in css)
    assert len(boxes) == 1 and boxes[0] in sized[0].parents
    assert AFTER.replace("**", "") in boxes[0].get_text()
    assert [img.get("src") for img in styled.find_all("img")] == [img.get("src") for img in original.find_all("img")]


if __name__ == "__main__":
    # Optional browser check: PYTHONPATH=apps/api/src python path/to/this_file.
    # Compare computed geometry rather than treating CSS string matches as a
    # substitute for a long source paragraph wrapping on real mobile widths.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            for width in (320, 390):
                page = browser.new_page(viewport={"width": width, "height": 800})
                for theme in THEMES:
                    for layout in ("stacked_before_after", "split_page_flip"):
                        markup = _render(theme, {"layout": layout})
                        page.set_content('<!doctype html><meta charset="utf-8"><body style="margin:0;padding:0 12px">'
                                         + str(markup) + '</body>')
                        geometry = page.locator("#slot-001 > section").evaluate("""box => {
                            const a = box.firstElementChild.getBoundingClientRect();
                            const b = box.lastElementChild.getBoundingClientRect();
                            return {width: document.documentElement.scrollWidth, stacked: b.top >= a.bottom,
                                    sideBySide: b.left > a.left && b.top < a.bottom};
                        }""")
                        assert geometry["width"] == width, (width, theme, layout, geometry)
                        assert geometry["stacked" if layout == "stacked_before_after" else "sideBySide"], geometry
                page.close()
        finally:
            browser.close()
    print("12 long-article mobile layouts verified (3 theme sources x 2 layouts x 320/390px).")
