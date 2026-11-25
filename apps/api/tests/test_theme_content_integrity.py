"""Theme switches can change decoration, never the number or order of source fields."""
from dataclasses import replace

import pytest
from bs4 import BeautifulSoup

from visual_director import theme_gallery
from visual_director.brief_compiler import visual_system_configuration
from visual_director.component_catalog import VISUAL_SYSTEM_ORDER
from visual_director.content_editor import validate_content_for_block
from visual_director.foundation_structure import _render_table
from visual_director.parser import parse_markdown
from visual_director.renderer import render_preview
from visual_director.theme_specimens import ARTICLE, BRAND, _specimen_plan


@pytest.mark.parametrize("theme", VISUAL_SYSTEM_ORDER)
def test_native_tables_keep_authored_columns_and_empty_cells(theme):
    config = visual_system_configuration(theme)
    for width in (2, 3, 4, 5, 7):
        header = [f"字段{i}" for i in range(width)]
        row = [f"第{i}项需要核对较长的说明和截止日期。" for i in range(width)]
        if width > 4:
            row[-1] = "REF-" + "1234567890" * 5
        empty_edges = [""] + ["待确认"] * (width - 2) + [""]
        values = [header, row, empty_edges]
        md = "\n".join("|" + "|".join(cells) + "|" for cells in [header, ["---"] * width, row, empty_edges])
        table = parse_markdown("# 核对\n\n" + md).blocks[-1]
        assert table.content == values
        assert validate_content_for_block(table, values) == values
        html = BeautifulSoup(_render_table(table.content, config), "html.parser")
        assert [[c.get_text() for c in tr.find_all(["th", "td"], recursive=False)]
                for tr in html.select("table tr")] == values
        if width > 4:
            cell = html.select("tbody tr")[0].find_all("td")[-1]
            assert any("overflow-wrap:anywhere" in node.get("style", "").replace(" ", "")
                       for node in (cell, *cell.parents))


@pytest.mark.parametrize("theme", VISUAL_SYSTEM_ORDER)
def test_each_semantic_component_keeps_its_long_bound_fields_in_order(theme):
    parsed = parse_markdown(theme_gallery.THEME_FIXTURE)
    refs_to_text = {}
    blocks = []
    def author(ref):
        text = f"核对{ref}：" + "请依据原始记录逐一核对时间、地点以及具体要求。" * 3 + f"尾注{ref}。"
        refs_to_text[ref] = text
        return text
    for block in parsed.blocks:
        if block.type in ("unordered_list", "ordered_list"):
            block = replace(block, content=[author(f"{block.id}:item:{i}") for i in range(5)])
        elif block.type in ("paragraph", "heading", "quote"):
            block = replace(block, content=author(block.id))
        blocks.append(block)
    parsed = replace(parsed, blocks=blocks)
    bindings = theme_gallery._fixture_bindings(parsed)
    palette = visual_system_configuration(theme)["palette"]
    for role, fields in bindings.items():
        markup = theme_gallery._component_specimen(parsed, role, theme, palette, bindings)["html"]
        text = BeautifulSoup(markup, "html.parser").get_text()
        refs = [ref for value in fields.values() for ref in (value if isinstance(value, list) else [value])]
        cursor = 0
        for ref in refs:
            expected = refs_to_text[ref]
            position = text.find(expected, cursor)
            assert position >= 0, (theme, role, ref)
            cursor = position + len(expected)


@pytest.mark.parametrize("theme", VISUAL_SYSTEM_ORDER)
def test_long_foundation_texts_and_both_lists_survive_full_article(theme):
    article = parse_markdown(ARTICLE)
    plan = {**_specimen_plan(article, theme), "slots": []}
    expected, blocks = [], []
    for b in article.blocks:
        def line(index):
            return f"起始{b.id}-{index}。" + "阅读较长的核对说明，依次检查地点和时间。" * 4 + f"终点{b.id}-{index}。"
        if b.type in ("ordered_list", "unordered_list"):
            items = [line(i) for i in range(7)]
            expected.extend(items)
            b = replace(b, content=items)
        elif b.type in ("paragraph", "quote") or (b.type == "heading" and b.level != 1):
            expected.append(line(0))
            b = replace(b, content=expected[-1])
        blocks.append(b)
    markup = render_preview(replace(article, blocks=blocks), plan, brand_profile=BRAND)
    text = BeautifulSoup(markup, "html.parser").get_text()
    for field in expected:
        before, sep, text = text.partition(field)
        assert sep, (theme, field)
