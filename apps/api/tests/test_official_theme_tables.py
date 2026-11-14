import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from visual_director.delivery import build_clipboard_payload
from visual_director.generated_theme import render_generated_table
from visual_director.brief_compiler import visual_system_configuration
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.publication import check_frozen_html, replace_asset_urls
from visual_director.theme_delivery import compiled_decoration_assets
from visual_director.theme_packs import ORIGINAL_BUNDLED_THEME_IDS, theme_pack
from visual_director.theme_review import build_foundation_preview
from visual_director.theme_specimens import build_production_specimens


TABLES = [
    ("weekend_fieldnotes", "weekend-fieldnotes-notebook-table", "border-top:2px solid"),
    ("after_screening", "after-screening-scene-ledger-table", "border-left:3px solid"),
    ("light_gallery", "light-gallery-index-table", "border-right:1px solid"),
    ("pixel_live", "pixel-live-stepped-table", "border-left:4px solid"),
    ("collage_fieldguide", "collage-fieldguide-label-table", "border-top:2px solid"),
    ("retro_window", "retro-window-directory-table", "border-top:2px solid"),
    ("folded_fan_detail", "folded-fan-paper-table", "border-top:3px solid"),
    ("indigo_cloth", "indigo-cloth-stitched-table", "border-top:3px solid"),
    ("night_walk_illustration", "night-walk-sign-table", "border-bottom:2px solid"),
    ("ink_traces", "ink-traces-landscape-table", "border-top:1px solid"),
]
ROWS = [["<name>", "A **label**", "Explanation"], ["01", "Line one\nLine two", "<img src=x>"]]


@pytest.fixture
def manifest():
    return json.loads((Path(__file__).resolve().parents[3]
                       / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))


def configuration(manifest, theme_id):
    return {"theme_id": theme_id, "palette": manifest["palette"], "generated_design_system": manifest["design_system"]}


@pytest.mark.parametrize(("theme_id", "grammar", "signature"), TABLES)
def test_official_table_uses_theme_signature_and_native_editable_cells(manifest, theme_id, grammar, signature):
    html = render_generated_table(ROWS, configuration(manifest, theme_id))
    artwork = compiled_decoration_assets(html)
    assets = [{**item, "id": item["asset_token"]} for item in artwork]
    frozen = replace_asset_urls(f"<main>{html}</main>", {a["source_url"]: a["asset_token"] for a in assets})
    assert check_frozen_html(frozen).status == "pass"
    clipboard = build_clipboard_payload(
        {"frozen_html": frozen, "metadata": {"title": "Table"}}, assets, lambda _: "",
        read_asset=lambda asset_id: (next(a["content"] for a in assets if a["id"] == asset_id), "image/png"),
    )
    has_ridge = theme_id == "ink_traces"
    assert len(artwork) == clipboard["image_count"] == int(has_ridge)
    for markup in (html, clipboard["html"]):
        root = BeautifulSoup(markup, "html.parser").select_one(f'[data-theme-grammar="{grammar}"]')
        assert [node.name for node in root.find_all(recursive=False)] == (["section", "table"] if has_ridge else ["table"])
        assert "width:100%" in root.table["style"] and "table-layout:fixed" in root.table["style"]
        assert all(th["scope"] == "col" for th in root.select("thead th"))
        assert signature in root.th["style"]
        assert [td.get_text(separator="\n") for td in root.select("tbody td")] == ROWS[1]
        assert [th.get_text() for th in root.select("thead th")] == ["<name>", "A label", "Explanation"]
        assert root.select_one("th strong").get_text() == "label"
        assert not root.table.select("img, [aria-hidden]")
        if has_ridge:
            ridge = root.select_one(':scope > section[aria-hidden="true"] img')
            assert ridge["alt"] == "" and ridge["src"].startswith("data:image/png;base64,")
            assert len(root.select("tr")) == len(ROWS)
        else:
            assert not root.select("img, [aria-hidden]")


@pytest.mark.parametrize(("theme_id", "grammar", "_signature"), TABLES)
def test_bundled_theme_and_offline_review_share_the_article_renderer(theme_id, grammar, _signature):
    manifest = theme_pack(theme_id)
    selector = f'[data-theme-grammar="{grammar}"] table'
    specimens, article = build_production_specimens(theme_id)
    assert BeautifulSoup(article, "html.parser").select_one(f'[data-editor-block-type="table"]{selector}')
    assert BeautifulSoup(next(sample["html"] for sample in specimens if sample["role"] == "table"),
                         "html.parser").select_one(selector)
    for document in build_foundation_preview(manifest).values():
        assert BeautifulSoup(document, "html.parser").select_one(f'[data-foundation-role="table"] {selector}')


def test_bundled_themes_do_not_shadow_or_delete_local_files(tmp_path, monkeypatch):
    from visual_director import theme_packs

    for key in ("_pack_dir", "_reserved_ids", "_core_components", "_installed", "_load_errors"):
        monkeypatch.setattr(theme_packs, key, getattr(theme_packs, key))
    assert set(ORIGINAL_BUNDLED_THEME_IDS) < {theme_id for theme_id, _, _ in TABLES}
    original = theme_pack("weekend_fieldnotes")
    local = {**original, "name": "旧本机试验版"}
    folder = tmp_path / local["id"]
    folder.mkdir()
    snapshot = folder / "theme.json"
    snapshot.write_text(json.dumps(local, ensure_ascii=False), encoding="utf-8")
    theme_packs.configure_theme_packs(tmp_path, reserved_ids=VISUAL_SYSTEM_ORDER,
                                     core_components=CORE_THEME_COMPONENTS)
    assert theme_pack(local["id"]) == original
    assert theme_packs.installed_theme_packs() == []
    assert theme_packs.theme_pack_load_errors() == []
    with pytest.raises(theme_packs.ThemePackError):
        theme_packs.delete_theme_pack(local["id"])
    with pytest.raises(theme_packs.ThemePackError):
        theme_packs.validate_theme_pack_manifest(local)
    assert json.loads(snapshot.read_text(encoding="utf-8")) == local


def test_local_palette_pack_can_inherit_a_bundled_theme_without_inheriting_its_id(manifest, monkeypatch):
    manifest.update(id="local_weekend_palette", base_theme="weekend_fieldnotes")
    manifest.pop("design_system")
    monkeypatch.setattr("visual_director.theme_packs._installed", {manifest["id"]: manifest})
    config = visual_system_configuration(manifest["id"])
    assert config["theme_id"] == manifest["id"]
    assert config["generated_design_system"] == theme_pack("weekend_fieldnotes")["design_system"]


@pytest.mark.parametrize("columns", [2, 3])
def test_weekend_header_fills_whole_cell_and_aligns_wrapped_labels(manifest, columns):
    config = configuration(manifest, "weekend_fieldnotes")
    rows = [["A", "A longer label\nthat wraps", "C"][:columns]]
    raw = render_generated_table(rows, config)
    clip = build_clipboard_payload({"frozen_html": f"<main>{raw}</main>", "metadata": {"title": "Table"}}, [], lambda _: "")
    palette = manifest["palette"]
    for markup in (raw, clip["html"]):
        soup = BeautifulSoup(markup, "html.parser")
        assert not soup.select("th > span")
        headers = soup.select("th")
        assert len(headers) == columns and headers[1].br is not None
        for i, node in enumerate(headers):
            style = node["style"]
            assert "vertical-align:top" in style and "border-top:2px" in style
            assert f'background-color:{palette["accent_pale" if columns == 2 and i == 0 else "pale"]};' in style
            if i < columns - 1:
                assert f'border-right:1px solid {palette["secondary"]};' in style


@pytest.mark.parametrize("columns", [3, 4])
@pytest.mark.parametrize("theme_id", [theme_id for theme_id, _, _ in TABLES])
def test_parallel_columns_use_equal_header_and_body_emphasis_with_row_stripes(manifest, theme_id, columns):
    headers = ["苹果", "梨", "桃", "橙"][:columns]
    body = [[str(value) for value in range(i, i + columns)] for i in (10, 20, 30)]
    raw = render_generated_table([headers, *body], configuration(manifest, theme_id))
    clipboard = build_clipboard_payload({"frozen_html": f"<main>{raw}</main>", "metadata": {"title": "Table"}},
                                        [], lambda _: "")

    def styles(cells, prop):
        return {
            dict(rule.split(":", 1) for rule in cell["style"].split(";") if rule).get(prop, "")
            for cell in cells
        }

    for markup in (raw, clipboard["html"]):
        table = BeautifulSoup(markup, "html.parser").table
        ths = table.select("thead th")
        assert [cell.get_text() for cell in ths] == headers
        for prop in ("background-color", "color", "font-weight"):
            assert len(styles(ths, prop)) == 1
        rows = [row.select("td") for row in table.select("tbody tr")]
        assert [[cell.get_text() for cell in row] for row in rows] == body
        assert all(len(styles(row, "background-color")) == 1 for row in rows)
        assert all(len(styles(row, "font-weight")) == 1 for row in rows)
        assert styles(rows[0], "background-color") == styles(rows[2], "background-color")
        assert styles(rows[0], "background-color") != styles(rows[1], "background-color")


@pytest.mark.parametrize("theme_id", ["indigo_cloth", "night_walk_illustration", "ink_traces"])
def test_two_column_table_does_not_imply_a_row_header(theme_id):
    config = visual_system_configuration(theme_id)
    raw = render_generated_table([["周六", "周日"], ["出发", "回程"], ["步行", "骑行"]], config)
    table = BeautifulSoup(raw, "html.parser").table
    assert len(table.select("tr")) == 3
    headers = table.select("th")
    assert len({th["style"].split("background-color:", 1)[1].split(";", 1)[0] for th in headers}) == 1
    rows = [row.select("td") for row in table.select("tbody tr")]
    for row in rows:
        assert len({td["style"].split("background-color:", 1)[1].split(";", 1)[0] for td in row}) == 1
        assert all("font-weight:" not in cell["style"] for cell in row)


def test_pixel_compacts_only_wide_tables_and_strengthens_column_rules(manifest):
    config = configuration(manifest, "pixel_live")
    short = BeautifulSoup(render_generated_table([row[:2] for row in ROWS], config), "html.parser")
    wide = BeautifulSoup(render_generated_table(ROWS, config), "html.parser")
    assert "font-size:15px" in short.td["style"]
    assert f'border-right:1px solid {manifest["palette"]["secondary_pale"]}' in short.td["style"]
    assert "font-size:14px" in wide.td["style"] and "padding:7px" in wide.td["style"]
    assert f'border-right:1px solid {manifest["palette"]["secondary"]}' in wide.select("td")[1]["style"]
    assert "border-right" not in wide.select("td")[-1]["style"]


def test_other_generated_themes_do_not_inherit_an_official_table(manifest):
    config = configuration(manifest, "custom_theme")
    baseline = render_generated_table(ROWS, config)
    config.update(base_theme="pixel_live")
    assert render_generated_table(ROWS, config) == baseline
    assert render_generated_table(ROWS, {"theme_id": "pixel_live"}) is None
