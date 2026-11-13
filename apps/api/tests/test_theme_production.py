import copy
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from visual_director.delivery import build_clipboard_payload
from visual_director.generated_theme import render_generated_table
from visual_director.theme_delivery import theme_delivery_report
from visual_director.theme_production import check_theme_production
from visual_director.theme_layouts import ROLE_FIELDS


def manifest():
    return json.loads((Path(__file__).resolve().parents[3] / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))


def test_all_declared_roles_hit_their_actual_production_entry_points():
    report = check_theme_production(manifest())
    assert report["status"] == "pass"
    assert set(report["checked_roles"]) == set(ROLE_FIELDS)
    assert report["undeclared_roles"] == []
    assert len(report["cases"]) == 42
    assert {(case["role"], case["length"]) for case in report["cases"]} == {(role, length) for role in ROLE_FIELDS for length in ("short", "long")}
    assert report["visual_review"] == report["wechat_saved_roundtrip"] == "not_verified"
    assert len(report["foundation_checks"]) == 10
    assert {case["role"] for case in report["foundation_checks"]} == {
        "inline_emphasis", "ordered_list", "table", "source", "reference_list",
    }
    assert all(case["status"] == "pass" for case in report["foundation_checks"])


def test_ordered_list_requires_real_numbers_not_only_a_layout_hit(monkeypatch):
    from visual_director import renderer

    original = renderer.render_generated_list
    monkeypatch.setattr(renderer, "render_generated_list",
                        lambda items, ordered, config, role: original(items, False, config, role))
    report = check_theme_production(manifest())
    assert report["status"] == "blocking"
    assert all(case["status"] == "pass" for case in report["cases"])
    assert {case["role"] for case in report["foundation_checks"] if case["status"] == "blocking"} == {"ordered_list"}


@pytest.mark.parametrize(("motifs", "density", "has_ornament"), [
    (["none"], 0.6, False),
    (["paper_cut"], 0, False),
    (["paper_cut"], 0.6, True),
])
def test_generated_table_does_not_reserve_a_row_for_absent_decoration(motifs, density, has_ornament):
    value = manifest()
    design, palette = value["design_system"], value["palette"]
    design["motifs"] = motifs
    design["ornament"]["density"] = density
    config = {"generated_design_system": design, "palette": palette}
    raw = render_generated_table([["Item", "Meaning"], ["Example", "Demo"]], config)
    clip = build_clipboard_payload({"frozen_html": f"<main>{raw}</main>", "metadata": {"title": "Example"}},
                                   [], lambda _: "")["html"]
    for markup in (raw, clip):
        root = BeautifulSoup(markup, "html.parser").select_one("[data-theme-grammar]")
        assert [node.name for node in root.find_all(recursive=False)] == (
            ["section", "table"] if has_ornament else ["table"]
        )
        assert "padding-top" not in root["style"]
        assert bool(root.select_one('[aria-hidden="true"] [data-theme-motif]')) == has_ornament
        assert [th.text for th in root.select("th")] == ["Item", "Meaning"]
        assert [td.text for td in root.select("td")] == ["Example", "Demo"]
        assert f'border-top:{design["ornament"]["border_width"] + 2}px solid {palette["accent"]}' in root.th["style"]


def test_authored_list_can_style_ordered_indexes_and_unordered_markers():
    from visual_director.generated_theme import render_generated_list

    value = manifest()
    design = value["design_system"]
    marker = design["layouts"]["list"]["children"][0]["children"][0]
    marker.update(type="field", bind="index")
    marker.pop("text")
    config = {"generated_design_system": design, "palette": value["palette"]}
    items = ["First", "Second", "Third"]
    ordered = BeautifulSoup(render_generated_list(items, True, config, "key_points"), "html.parser")
    unordered = BeautifulSoup(render_generated_list(items, False, config, "key_points"), "html.parser")
    assert [node.get_text() for node in ordered.select("[data-theme-list-index]")] == ["01", "02", "03"]
    assert [node.get_text() for node in unordered.select("[data-theme-marker]")] == ["•", "•", "•"]
    assert not unordered.select("[data-theme-list-index]")


def test_renderable_layout_is_blocking_when_production_silently_ignores_it(monkeypatch):
    from visual_director import renderer
    original = renderer.render_generated_paragraph
    monkeypatch.setattr(renderer, "render_generated_paragraph", lambda content, config, lead=False: original(content, config, lead=False))
    report = theme_delivery_report(manifest())
    assert report["coverage"]["status"] == "complete"
    assert all(role["status"] == "pass" for role in report["rehearsal"]["roles"])
    assert report["rehearsal"]["status"] == "blocking"
    assert report["local_delivery"] == "blocking" and report["next_action"] == "fix_delivery"
    failed = [case for case in report["rehearsal"]["production"]["cases"] if case["status"] == "blocking"]
    assert {case["role"] for case in failed} == {"lead"}
    assert {case["length"] for case in failed} == {"short", "long"}


def test_missing_lead_is_not_reported_as_a_successful_authored_lead():
    value = manifest()
    del value["design_system"]["layouts"]["lead"]
    report = theme_delivery_report(value)
    assert report["coverage"]["status"] == "partial"
    assert "lead" in report["coverage"]["missing_roles"]
    assert "lead" in report["rehearsal"]["production"]["undeclared_roles"]
    assert "lead" not in report["rehearsal"]["production"]["checked_roles"]


def test_exact_template_layouts_require_visual_review_not_automatic_rejection():
    value = manifest()
    original = copy.deepcopy(value)
    report = theme_delivery_report(value)
    assert set(report["design_review"]["unchanged_template_roles"]) == set(ROLE_FIELDS)
    assert report["design_review"]["status"] == "review_required"
    assert report["local_delivery"] != "blocking"
    assert report["visual_review"] == "not_verified"
    assert value == original
    value["design_system"]["layouts"]["lead"] = {"type": "field", "bind": "body"}
    changed = theme_delivery_report(value)
    assert "lead" not in changed["design_review"]["unchanged_template_roles"]
    assert changed["visual_review"] == "not_verified"  # A change is not an aesthetic pass.


def test_template_comparison_uses_the_configured_installation_root(monkeypatch, tmp_path):
    template = tmp_path / "skills/wechat-visual-director/assets/theme-pack-template.json"
    template.parent.mkdir(parents=True)
    value = manifest()
    adjusted = copy.deepcopy(value)
    adjusted["design_system"]["layouts"]["lead"] = {"type": "field", "bind": "body"}
    template.write_text(json.dumps(adjusted), encoding="utf-8")
    monkeypatch.setenv("VISUAL_DIRECTOR_PROJECT_ROOT", str(tmp_path))
    result = theme_delivery_report(value)["design_review"]
    assert result["status"] == "review_required"
    assert "lead" not in result["unchanged_template_roles"]
    assert len(result["unchanged_template_roles"]) == len(ROLE_FIELDS) - 1


def test_cli_review_does_not_report_success_after_production_check_blocks(monkeypatch, capsys, tmp_path):
    from visual_director import cli
    monkeypatch.setattr("visual_director.theme_review.build_theme_review", lambda *args: {
        "ok": False, "production_check": {"status": "blocking"}, "review_file": str(tmp_path / "review/index.html")})
    code = cli.run(["theme", "review", "--file", "sample.json", "--output", str(tmp_path / "review"), "--image", "sample.png", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code != 0 and result["ok"] is False
    assert result["error"]["code"] == "theme_production_check_failed"
    assert result["error"]["details"]["production_check"]["status"] == "blocking"
