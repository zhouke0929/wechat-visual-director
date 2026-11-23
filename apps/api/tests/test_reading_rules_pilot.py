"""Check opt-in reading roles without silently changing structure or old themes."""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from test_logic_path_pilot import _WechatTransportFixture
from test_plain_lists_pilot import (
    CUSTOM_THEMES,
    MARKDOWN,
    REF,
    ROOT,
    STEP_SWITCH,
    SWITCH,
    _configure_registry,
    _install_custom_theme,
    _list_blocks,
    _prepare_task,
)
from visual_director.brief_compiler import apply_visual_system
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.image_provider import ManualImageProvider
from visual_director.main import create_app
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director import reading_rules, reading_theme_overrides
from visual_director.renderer import render_preview
from visual_director.text_planner import MockTextPlannerProvider
from visual_director.theme_specimens import build_production_specimens
from visual_director.wechat_publisher import WechatDraftPublisher


READING_SWITCH = "WVD_READING_RULES_PILOT"
STEP_REF = "data-editor-step-ref"
TEXT_STYLE_KEYS = {"font-size", "font-weight", "line-height", "letter-spacing", "overflow-wrap"}
TEXT_BOX_KEYS = {"margin-top", "margin-bottom", "padding-top", "padding-bottom"}
STEP_TITLE_TEXT = "先核对原稿"
STEP_DETAIL_TEXT = "然后记录内容所在的原始位置。"
STEP_UNTITLED_TEXT = "检查交付素材。"


@pytest.fixture(autouse=True)
def _isolated_switches(tmp_path, monkeypatch):
    for name in (READING_SWITCH, SWITCH, STEP_SWITCH, "WECHAT_APP_ID", "WECHAT_APP_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(tmp_path / "isolated.env"))
    monkeypatch.setenv("VISUAL_DIRECTOR_THEME_PACK_DIR", str(tmp_path / "packs"))
    _configure_registry(tmp_path / "packs")
    yield
    _configure_registry(tmp_path / "clean")


def _fixed_inputs(theme: str):
    if theme in CUSTOM_THEMES:
        _install_custom_theme(theme)
    article = parse_markdown(MARKDOWN)
    step = _list_blocks(article)[0]
    plan = apply_visual_system(generate_plans(article, "tutorial_steps", 5)[0], theme)
    plan["slots"] = [slot for slot in plan["slots"] if slot["component_type"] == "logic_path"
                     and slot["anchor_block_id"] == step.id]
    assert len(plan["slots"]) == 1
    return article, plan


def _style(node) -> dict[str, str]:
    return dict((key.strip(), value.strip()) for part in node.get("style", "").split(";")
                if part.strip() for key, value in [part.split(":", 1)])


def _strip_style_keys(node, keys: set[str]) -> None:
    style = [pair for pair in node.get("style", "").split(";") if pair.strip() and pair.split(":", 1)[0].strip() not in keys]
    if style:
        node["style"] = ";".join(style) + ";"
    else:
        node.attrs.pop("style", None)


def _without_reading_differences(markup: str) -> str:
    """Only text-host styles and the step title/detail gap can change."""
    dom = BeautifulSoup(markup, "html.parser")
    for node in dom.select(f"[{REF}], [{STEP_REF}]"):
        _strip_style_keys(node, TEXT_STYLE_KEYS | TEXT_BOX_KEYS)
        for emphasis in node.find_all("strong"):
            if "data-editor-step-prefix" not in emphasis.attrs:
                _strip_style_keys(emphasis, TEXT_STYLE_KEYS)
        if STEP_REF in node.attrs:
            for detail in node.find_all("span", recursive=False):
                if detail.get_text(strip=True) == STEP_DETAIL_TEXT and _style(detail).get("display") == "block":
                    _strip_style_keys(detail, TEXT_STYLE_KEYS | TEXT_BOX_KEYS)
    return str(dom)


def _by_text(elements, text):
    matches = [node for node in elements if node.get_text(strip=True) == text]
    assert len(matches) == 1, (text, [node.get_text(strip=True) for node in elements])
    return matches[0]


def _em(value: str) -> float:
    if value == "normal":
        return 0.0
    assert value.endswith("em"), value
    return float(value[:-2])


def _trial_on(monkeypatch) -> None:
    monkeypatch.setenv(SWITCH, "1")
    monkeypatch.setenv(READING_SWITCH, "1")


def _replace_theme_overrides(monkeypatch, overrides) -> None:
    # Patch the data module and, if the resolver imports the name directly,
    # its alias too. Both methods use the same private data contract.
    monkeypatch.setattr(reading_theme_overrides, "THEME_READING_OVERRIDES", overrides)
    if hasattr(reading_rules, "THEME_READING_OVERRIDES"):
        monkeypatch.setattr(reading_rules, "THEME_READING_OVERRIDES", overrides)


def test_reading_role_inventory_covers_all_displayed_foundations_and_semantic_components(monkeypatch):
    foundations, _ = build_production_specimens("light_reading")
    assert set(reading_rules.FOUNDATION_READING_ROLES) == {specimen["role"] for specimen in foundations}
    assert set(reading_rules.SEMANTIC_READING_ROLES) == set(CORE_THEME_COMPONENTS)
    monkeypatch.setenv(SWITCH, "1")
    monkeypatch.setenv(READING_SWITCH, "1")
    profile = reading_rules.resolve_reading_profile({}, official=True)
    assert profile is not None
    for inventory in (reading_rules.FOUNDATION_READING_ROLES, reading_rules.SEMANTIC_READING_ROLES):
        assert {role for roles in inventory.values() for role in roles} <= set(profile.rules)


def test_editing_one_body_token_updates_all_prose_roles_without_touching_emphasis(monkeypatch):
    monkeypatch.setenv(SWITCH, "1")
    monkeypatch.setenv(READING_SWITCH, "1")
    rule_set = dict(reading_rules.DEFAULT_READING_RULES)
    rule_set[reading_rules.BODY] = replace(rule_set[reading_rules.BODY], size_px=17, weight=450,
                                           line_height=1.7, letter_spacing_em=0.025)
    monkeypatch.setattr(reading_rules, "DEFAULT_READING_RULES", rule_set)
    profile = reading_rules.resolve_reading_profile({}, official=True)
    assert profile is not None
    for role in (reading_rules.LIST_BODY, reading_rules.STEP_BODY, reading_rules.STEP_DETAIL, reading_rules.TABLE_BODY):
        assert profile.rules[role].size_px == 17
        assert profile.rules[role].weight == 450
        assert profile.rules[role].line_height == 1.7
        assert profile.rules[role].letter_spacing_em == 0.025
        assert profile.rules[role].wrap == "anywhere"
    assert profile.rules[reading_rules.STEP_TITLE] == rule_set[reading_rules.STEP_TITLE]
    assert profile.rules[reading_rules.INLINE_EMPHASIS] == rule_set[reading_rules.INLINE_EMPHASIS]


@pytest.mark.parametrize(("tracking", "expected"), (("tight", -0.02), ("normal", 0.0), ("relaxed", 0.04)))
def test_existing_declared_tracking_is_kept_by_the_shared_resolver(monkeypatch, tracking, expected):
    _trial_on(monkeypatch)
    config = {"generated_design_system": {"typography": {"body_scale": 1.05, "letter_spacing": tracking}}}
    profile = reading_rules.resolve_reading_profile(config, official=True, theme_id="folded_fan_detail")
    assert profile is not None
    for role in (reading_rules.LIST_BODY, reading_rules.STEP_BODY, reading_rules.STEP_DETAIL):
        assert profile.rules[role].letter_spacing_em == expected
        assert profile.rules[role].size_px == 16.8
        sources = profile.field_sources[role]
        assert (sources["letter_spacing_em"] == sources["weight"]) == (tracking == "normal")


def test_normal_tracking_inherits_but_an_explicit_zero_role_override_wins(monkeypatch):
    _trial_on(monkeypatch)
    rules = dict(reading_rules.DEFAULT_READING_RULES)
    rules[reading_rules.BODY] = replace(rules[reading_rules.BODY], letter_spacing_em=0.015)
    monkeypatch.setattr(reading_rules, "DEFAULT_READING_RULES", rules)
    theme = "folded_fan_detail"
    normal = {"generated_design_system": {"typography": {"letter_spacing": "normal"}}}
    profile = reading_rules.resolve_reading_profile(normal, official=True, theme_id=theme)
    assert profile is not None and profile.rules[reading_rules.LIST_BODY].letter_spacing_em == 0.015
    _replace_theme_overrides(monkeypatch, {theme: {reading_rules.LIST_BODY: {"letter_spacing_em": 0}}})
    tight = {"generated_design_system": {"typography": {"letter_spacing": "tight"}}}
    profile = reading_rules.resolve_reading_profile(tight, official=True, theme_id=theme)
    assert profile is not None
    assert profile.rules[reading_rules.LIST_BODY].letter_spacing_em == 0
    assert profile.rules[reading_rules.STEP_BODY].letter_spacing_em == -0.02
    assert (profile.field_sources[reading_rules.LIST_BODY]["letter_spacing_em"]
            != profile.field_sources[reading_rules.STEP_BODY]["letter_spacing_em"])


def test_pop_checked_in_override_changes_list_only(monkeypatch):
    article, plan = _fixed_inputs("pop_poster")
    _trial_on(monkeypatch)
    profile = reading_rules.resolve_reading_profile(plan["configuration"], official=True, theme_id="pop_poster")
    assert profile is not None
    list_rule = profile.rules[reading_rules.LIST_BODY]
    assert (list_rule.size_px, list_rule.line_height, list_rule.weight) == (15, 1.75, 400)
    assert (profile.rules[reading_rules.STEP_BODY].size_px, profile.rules[reading_rules.STEP_BODY].line_height) == (16, 1.8)
    list_origin = profile.field_sources[reading_rules.LIST_BODY]
    assert list_origin["size_px"] == list_origin["line_height"] and list_origin["size_px"] != list_origin["weight"]
    doc = BeautifulSoup(render_preview(article, plan, brand_profile={}), "html.parser")
    assert all((_style(node)["font-size"], _style(node)["line-height"]) == ("15px", "1.75")
               for node in doc.select(f"[{REF}]"))
    assert all((_style(node)["font-size"], _style(node)["line-height"]) == ("16px", "1.8")
               for node in doc.select(f"[{STEP_REF}]"))


@pytest.mark.parametrize("selector_theme", ("light_reading", "pop_poster", "folded_fan_detail"))
def test_one_private_role_override_updates_only_one_theme_and_role_in_real_renderer(monkeypatch, selector_theme):
    unaffected_theme = "warm_humanist"
    article, plan = _fixed_inputs(selector_theme)
    other_article, other_plan = _fixed_inputs(unaffected_theme)
    _trial_on(monkeypatch)
    before = render_preview(article, plan, brand_profile={})
    unrelated_before = render_preview(other_article, other_plan, brand_profile={})
    overrides = dict(reading_theme_overrides.THEME_READING_OVERRIDES)
    overrides[selector_theme] = {
        reading_rules.LIST_BODY: {"size_px": 15.25, "weight": 425, "line_height": 1.72,
                                  "letter_spacing_em": 0.025, "before_px": 2, "after_px": 4,
                                  "inset_before_px": 3, "inset_after_px": 5},
    }
    _replace_theme_overrides(monkeypatch, overrides)
    changed = render_preview(article, plan, brand_profile={})
    after_doc = BeautifulSoup(changed, "html.parser")
    before_doc = BeautifulSoup(before, "html.parser")
    assert after_doc.select(f"[{STEP_REF}]") == before_doc.select(f"[{STEP_REF}]")
    assert render_preview(other_article, other_plan, brand_profile={}) == unrelated_before
    assert _without_reading_differences(changed) == _without_reading_differences(before)
    fields = after_doc.select(f"[{REF}]")
    assert fields
    properties = {"font-size": "15.25px", "font-weight": "425", "line-height": "1.72", "letter-spacing": "0.025em",
                  "margin-top": "2px", "margin-bottom": "4px", "padding-top": "3px", "padding-bottom": "5px"}
    for field in fields:
        assert properties.items() <= _style(field).items()
    profile = reading_rules.resolve_reading_profile(plan["configuration"], official=True, theme_id=selector_theme)
    assert profile is not None
    list_source = profile.field_sources[reading_rules.LIST_BODY]
    origin = list_source["size_px"]
    assert all(list_source[field] == origin for field in overrides[selector_theme][reading_rules.LIST_BODY])
    assert list_source["wrap"] != origin


@pytest.mark.parametrize(("inset", "expected"), ((0, "7px"), (4, "11px")))
def test_step_title_gap_is_projected_once_and_combines_with_the_detail_inset(monkeypatch, inset, expected):
    _trial_on(monkeypatch)
    article, plan = _fixed_inputs("light_reading")
    _replace_theme_overrides(monkeypatch, {"light_reading": {
        reading_rules.STEP_TITLE: {"after_px": 7},
        reading_rules.STEP_DETAIL: {"inset_before_px": inset},
    }})
    dom = BeautifulSoup(render_preview(article, plan, brand_profile={}), "html.parser")
    title = _by_text(dom.find_all("strong"), STEP_TITLE_TEXT)
    detail = _by_text(dom.find_all("span"), STEP_DETAIL_TEXT)
    assert "margin-bottom" not in _style(title)
    assert _style(detail)["padding-top"] == expected


def test_optional_step_title_insets_use_a_box_but_default_title_stays_inline(monkeypatch):
    _trial_on(monkeypatch)
    article, plan = _fixed_inputs("light_reading")
    base = BeautifulSoup(render_preview(article, plan, brand_profile={}), "html.parser")
    assert "display" not in _style(_by_text(base.find_all("strong"), STEP_TITLE_TEXT))
    _replace_theme_overrides(monkeypatch, {"light_reading": {
        reading_rules.STEP_TITLE: {"before_px": 2, "inset_before_px": 1, "inset_after_px": 4},
    }})
    doc = BeautifulSoup(render_preview(article, plan, brand_profile={}), "html.parser")
    title = _style(_by_text(doc.find_all("strong"), STEP_TITLE_TEXT))
    assert {"display": "inline-block", "margin-top": "2px", "padding-top": "1px",
            "padding-bottom": "4px"}.items() <= title.items()
    assert "margin-bottom" not in title
    assert _style(_by_text(doc.find_all("span"), STEP_DETAIL_TEXT))["padding-top"] == "3px"


def test_default_plain_steps_keep_existing_row_gap_but_explicit_zero_can_override_it(monkeypatch):
    _trial_on(monkeypatch)
    article, plan = _fixed_inputs("light_reading")
    plan["slots"][0]["variant"] = "plain_steps"
    before = BeautifulSoup(render_preview(article, plan, brand_profile={}), "html.parser")
    orig = _style(before.select(f"[{STEP_REF}]")[1])
    assert orig["margin"] == "0 0 12px"
    assert "margin-bottom" not in orig
    _replace_theme_overrides(monkeypatch, {"light_reading": {reading_rules.STEP_BODY: {"after_px": 0}}})
    after = BeautifulSoup(render_preview(article, plan, brand_profile={}), "html.parser")
    adjusted = _style(after.select(f"[{STEP_REF}]")[1])
    assert adjusted["margin"] == orig["margin"]  # Leave the shorthand's other edges in place.
    assert adjusted["margin-bottom"] == "0px"


@pytest.mark.parametrize("metric", ({"letter_spacing_em": "calc(1em)"}, {"before_px": -2}, {"weight": 400.5}))
def test_private_override_does_not_accept_css_strings_or_invalid_metrics(monkeypatch, metric):
    _trial_on(monkeypatch)
    theme = "light_reading"
    _replace_theme_overrides(monkeypatch, {theme: {reading_rules.LIST_BODY: metric}})
    assert reading_rules.resolve_reading_profile({}, official=False, theme_id=theme) is None
    with pytest.raises(ValueError, match="Invalid official reading metric"):
        reading_rules.resolve_reading_profile({}, official=True, theme_id=theme)


@pytest.mark.parametrize("theme", ("light_reading", "pop_poster", "folded_fan_detail"))
def test_one_body_token_reaches_each_renderer_without_overriding_step_hierarchy(monkeypatch, theme):
    article, plan = _fixed_inputs(theme)
    monkeypatch.setenv(SWITCH, "1")
    monkeypatch.setenv(READING_SWITCH, "1")
    original = dict(reading_rules.DEFAULT_READING_RULES)
    revised = {**original, reading_rules.BODY: replace(original[reading_rules.BODY], weight=450)}
    monkeypatch.setattr(reading_rules, "DEFAULT_READING_RULES", revised)
    dom = BeautifulSoup(render_preview(article, plan, brand_profile={}), "html.parser")
    rows = dom.select(f"[{REF}], [{STEP_REF}]")
    assert rows and all(_style(row)["font-weight"] == "450" for row in rows)
    title = _by_text(dom.find_all("strong"), STEP_TITLE_TEXT)
    detail = _by_text(dom.find_all("span"), STEP_DETAIL_TEXT)
    assert int(_style(title)["font-weight"]) == original[reading_rules.STEP_TITLE].weight
    assert _style(detail)["font-weight"] == "450"


@pytest.mark.parametrize("theme", VISUAL_SYSTEM_ORDER)
def test_official_list_and_step_fields_use_reading_roles_without_other_markup_changes(monkeypatch, theme):
    article, plan = _fixed_inputs(theme)
    monkeypatch.setenv(SWITCH, "1")
    baseline = render_preview(article, plan, brand_profile={})
    monkeypatch.setenv(READING_SWITCH, "1")
    trial = render_preview(article, plan, brand_profile={})
    assert _without_reading_differences(trial) == _without_reading_differences(baseline)
    profile = reading_rules.resolve_reading_profile(plan["configuration"], official=True, theme_id=theme)
    assert profile is not None

    dom = BeautifulSoup(trial, "html.parser")
    step, *lists = _list_blocks(article)
    ordinary_rows = dom.select(f"[{REF}]")
    assert [row[REF] for row in ordinary_rows] == [f"{block.id}:item:{i}" for block in lists for i in range(len(block.content))]
    for row in ordinary_rows:
        style = _style(row)
        assert style["font-weight"] == "400"
        assert re.fullmatch(r"\d+(?:\.\d+)?px", style["font-size"])
        assert float(style["font-size"][:-2]) == profile.rules[reading_rules.LIST_BODY].size_px
        assert float(style["line-height"]) == profile.rules[reading_rules.LIST_BODY].line_height
        assert _em(style["letter-spacing"]) == profile.rules[reading_rules.LIST_BODY].letter_spacing_em
    emphasis = [node for row in ordinary_rows for node in row.find_all("strong")]
    assert emphasis and all(_style(word)["font-weight"] == "700" for word in emphasis)

    step_rows = dom.select(f"[{STEP_REF}]")
    assert [row[STEP_REF] for row in step_rows] == [f"{step.id}:item:{i}" for i in range(len(step.content))]
    assert all(_style(row)["font-weight"] == "400" for row in step_rows)
    assert all(float(_style(row)["font-size"][:-2]) == profile.rules[reading_rules.STEP_BODY].size_px for row in step_rows)
    first = step_rows[0]
    title = _by_text(first.find_all("strong"), STEP_TITLE_TEXT)
    detail = _by_text(first.find_all("span", recursive=False), STEP_DETAIL_TEXT)
    assert int(_style(title)["font-weight"]) > 400
    assert _style(detail)["font-weight"] == "400"
    assert _style(detail)["display"] == "block"
    assert float(_style(detail)["padding-top"][:-2]) == profile.rules[reading_rules.STEP_TITLE].after_px
    assert step_rows[1].get_text(strip=True) == STEP_UNTITLED_TEXT
    assert not step_rows[1].find("strong")  # Plain steps never become inferred titles.


@pytest.mark.parametrize("theme", CUSTOM_THEMES)
def test_reading_trial_is_byte_exact_for_v1_custom_themes(monkeypatch, theme):
    article, plan = _fixed_inputs(theme)
    monkeypatch.setenv(SWITCH, "1")
    before = render_preview(article, plan, brand_profile={})
    monkeypatch.setenv(READING_SWITCH, "1")
    assert render_preview(article, plan, brand_profile={}) == before


@pytest.mark.parametrize("theme", ("light_reading", "pop_poster", "folded_fan_detail"))
@pytest.mark.parametrize("step_pilot", (False, True))
def test_reading_flag_cannot_change_default_or_step_only_visual_output(monkeypatch, theme, step_pilot):
    article, plan = _fixed_inputs(theme)
    if step_pilot:
        monkeypatch.setenv(STEP_SWITCH, "1")
    before = render_preview(article, plan, brand_profile={})
    monkeypatch.setenv(READING_SWITCH, "1")
    assert render_preview(article, plan, brand_profile={}) == before


def _assert_pop_body_styles_in_delivered_html(markup: str, texts: list[str]) -> None:
    assert not any(marker in markup for marker in (REF, STEP_REF, "data-editor-block-ids"))
    dom = BeautifulSoup(markup, "html.parser")
    for text in texts:
        matching = [node for node in dom.find_all("p") if node.get_text(strip=True) == text]
        assert matching, text
        assert all(_style(node).get("font-weight") == "400" for node in matching)
        expected = ("16px", "1.8") if text == STEP_UNTITLED_TEXT else ("15px", "1.75")
        assert all((_style(node).get("font-size"), _style(node).get("line-height")) == expected for node in matching)
        if text != STEP_UNTITLED_TEXT:
            properties = {"letter-spacing": "0.02em", "margin-top": "2px", "margin-bottom": "5px",
                          "padding-top": "3px", "padding-bottom": "4px"}
            assert all(properties.items() <= _style(node).items() for node in matching)
    title = _by_text(dom.find_all("strong"), STEP_TITLE_TEXT)
    detail = _by_text(dom.find_all("span"), STEP_DETAIL_TEXT)
    assert int(_style(title)["font-weight"]) > 400
    assert _style(detail)["font-weight"] == "400"


def test_enabling_reading_pilot_does_not_rewrite_an_old_frozen_revision(tmp_path, monkeypatch):
    monkeypatch.setenv(SWITCH, "1")
    app = create_app(str(tmp_path / "frozen-baseline.db"), image_provider=ManualImageProvider(),
                     text_planner_provider=MockTextPlannerProvider())
    try:
        with TestClient(app) as client:
            task_url, _, (_, bullets, *_other) = _prepare_task(client, "pop_poster")
            task = client.get(task_url).json()["task"]
            frozen = client.post(f"{task_url}/publication-revisions", headers={"Idempotency-Key": "pre-reading-freeze"}, json={
                "expected_task_version": task["version"],
            })
            assert frozen.status_code == 201, frozen.text[:500]
            preview_url = frozen.json()["revision"]["preview_url"]
            before = client.get(preview_url)
            assert before.status_code == 200, before.text[:500]
            rows = [node for node in BeautifulSoup(before.text, "html.parser").find_all("p")
                    if node.get_text(strip=True) == bullets.content[1]]
            assert rows and all(_style(row)["font-weight"] == "700" for row in rows)
            monkeypatch.setenv(READING_SWITCH, "1")
            assert client.get(preview_url).content == before.content
    finally:
        app.state.repository.connection.close()


def test_edited_reading_trial_survives_copy_freeze_and_mock_wechat(tmp_path, monkeypatch):
    monkeypatch.setenv(SWITCH, "1")
    monkeypatch.setenv(READING_SWITCH, "1")
    overrides = dict(reading_theme_overrides.THEME_READING_OVERRIDES)
    pop = dict(overrides["pop_poster"])
    pop[reading_rules.LIST_BODY] = {**pop[reading_rules.LIST_BODY], "letter_spacing_em": 0.02,
                                   "before_px": 2, "after_px": 5, "inset_before_px": 3, "inset_after_px": 4}
    overrides["pop_poster"] = pop
    _replace_theme_overrides(monkeypatch, overrides)
    remote = _WechatTransportFixture()
    publisher = WechatDraftPublisher(ROOT, token_endpoint="https://wechat-pilot.invalid/token",
                                     api_base="https://wechat-pilot.invalid", requester=remote)
    app = create_app(str(tmp_path / "reading.db"), image_provider=ManualImageProvider(),
                     text_planner_provider=MockTextPlannerProvider(), wechat_publisher=publisher)
    try:
        with TestClient(app) as client:
            task_url, plan, (ordered, bullets, *_other) = _prepare_task(client, "pop_poster")
            editor = client.get(f"{task_url}/content-editor").json()
            new_text = "新编辑的第三条仍使用常规字重。"
            values = list(bullets.content)
            values[2] = new_text
            edited = client.patch(f"{task_url}/content-editor", json={
                "expected_revision": editor["revision"], "target": "block", "block_id": bullets.id, "content": values,
            })
            assert edited.status_code == 200, edited.text
            saved = client.get(f"{task_url}/content-editor").json()
            assert next(block["content"] for block in saved["blocks"] if block["block_id"] == bullets.id) == values
            plan = client.get(f'{task_url}/plans/{plan["id"]}').json()["plan"]
            work = client.get(f"{task_url}/clipboard", headers={"X-Local-Intent": "local-operator"}, params={
                "plan_id": plan["id"], "plan_revision": plan["revision"], "content_revision": saved["revision"],
            })
            assert work.status_code == 200, work.text[:500]
            texts = [ordered.content[1], bullets.content[1], STEP_UNTITLED_TEXT, new_text]
            _assert_pop_body_styles_in_delivered_html(work.json()["html"], texts)

            task = client.get(task_url).json()["task"]
            frozen = client.post(f"{task_url}/publication-revisions", headers={"Idempotency-Key": "reading-trial-freeze"}, json={
                "expected_task_version": task["version"], "expected_content_revision": saved["revision"],
            })
            assert frozen.status_code == 201, frozen.text[:500]
            revision = frozen.json()["revision"]
            revision_url = f'/api/v1/publication-revisions/{revision["id"]}'
            before = client.get(f"{revision_url}/content")
            assert before.status_code == 200
            _assert_pop_body_styles_in_delivered_html(before.text, texts)
            monkeypatch.delenv(READING_SWITCH)
            monkeypatch.delenv(SWITCH)
            assert client.get(f"{revision_url}/content").content == before.content
            _assert_pop_body_styles_in_delivered_html(client.get(f"{revision_url}/clipboard").json()["html"], texts)

            monkeypatch.setenv("WECHAT_APP_ID", "offline-app-id")
            monkeypatch.setenv("WECHAT_APP_SECRET", "offline-placeholder")
            draft = client.post(f"{revision_url}/wechat-draft", headers={"Idempotency-Key": "reading-trial-mock-draft"}, json={
                "expected_task_version": frozen.json()["task"]["version"], "draft_slot": revision["suggested_draft_slot"],
            })
            assert draft.status_code == 200 and draft.json()["operation"]["status"] == "succeeded", draft.text
            assert remote.paths.count("/draft/add") == len(remote.articles) == 1
            _assert_pop_body_styles_in_delivered_html(remote.articles[0]["content"], texts)
    finally:
        app.state.repository.connection.close()
