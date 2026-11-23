"""Source-to-layout boundaries for semantic components, independent of planner decisions."""
import re

import pytest

from visual_director import reading_rules, theme_gallery
from visual_director.brief_compiler import visual_system_configuration, visual_system_variant
from visual_director.component_catalog import CORE_THEME_COMPONENTS
from visual_director.components import render_bound_component
from visual_director.parser import parse_markdown
from visual_director.reading_rules import BODY, COMPONENT_TITLE, INLINE_EMPHASIS, QUOTE
from visual_director.semantic_content import SemanticSource


def test_every_component_projects_a_real_source_and_grouped_concepts_keep_identity():
    parsed = parse_markdown(theme_gallery.THEME_FIXTURE)
    source = SemanticSource.from_article(parsed)
    bindings = theme_gallery._fixture_bindings(parsed)
    assert set(bindings) == set(CORE_THEME_COMPONENTS)
    for component, refs in bindings.items():
        content = source.bind({"component_type": component, "content_bindings": refs})
        assert content.layout_payload()["kind"]
        for key, original in refs.items():
            if isinstance(original, str):
                assert content.one(key).reference == original
            else:
                assert [item.reference for item in content.many(key)] == original

    title, body = bindings["case_card"].values()
    refs = {**bindings["concept_explainer"], "related_titles": [title], "related_definitions": [body]}
    grouped = source.bind({"component_type": "concept_explainer", "content_bindings": refs})
    entries = grouped.layout_payload()["entries"]
    assert entries[0]["title"] is grouped.one("title")
    assert entries[1]["body"] is grouped.many("related_definitions")[0]
    assert (entries[1]["title"].role, entries[1]["body"].role) == (COMPONENT_TITLE, BODY)
    with pytest.raises(TypeError):
        grouped.fields["title"] = None


def test_list_bindings_preserve_duplicate_text_and_source_order():
    parsed = parse_markdown("# Title\n\n- Same\n- Same\n- Other")
    block = next(b for b in parsed.blocks if b.type == "unordered_list")
    references = [f"{block.id}:item:{i}" for i in (1, 0, 2)]
    source = SemanticSource.from_article(parsed)
    content = source.bind({"component_type": "numbered_insight", "content_bindings": {"items": references}})
    items = content.layout_payload()["items"]
    assert [(i.reference, i.text) for i in items] == list(zip(references, ("Same", "Same", "Other")))
    for bad in ("block-999", "not-a-reference", f"{block.id}:item:99"):
        with pytest.raises(ValueError):
            source.bind({"component_type": "warning_note", "content_bindings": {"body": bad}})


@pytest.mark.parametrize("theme", ["light_reading", "pop_poster", "folded_fan_detail"])
@pytest.mark.parametrize("extension", ["related_titles", "related_definitions", "five_pairs", "mismatched"])
def test_saved_concept_group_preserves_the_projector_contract(theme, extension):
    parsed = parse_markdown("# Article\n\n### PrimaryHeading\n\nPrimaryBody\n\n### ExtraHeading\n\nExtraBody")
    ids = {b.content: b.id for b in parsed.blocks}
    fields = {"title": ids["PrimaryHeading"], "definition": ids["PrimaryBody"]}
    if extension in {"related_titles", "five_pairs", "mismatched"}:
        fields["related_titles"] = [ids["ExtraHeading"]] * (4 if extension == "five_pairs" else 1)
    if extension in {"related_definitions", "five_pairs", "mismatched"}:
        fields["related_definitions"] = [ids["ExtraBody"]] * (4 if extension == "five_pairs" else 2)
    content = SemanticSource.from_article(parsed).bind({"component_type": "concept_explainer", "content_bindings": fields})
    config = visual_system_configuration(theme)

    def render():
        return render_bound_component(content, visual_system_variant("concept_explainer", theme),
                                      config["palette"], config, visual_system=theme)

    if extension == "mismatched" or theme == "light_reading":
        with pytest.raises(ValueError):
            render()
    else:
        document = render()
        assert document.count("PrimaryHeading") == document.count("PrimaryBody") == 1
        assert document.count("ExtraHeading") == document.count("ExtraBody") == (4 if extension == "five_pairs" else 0)


@pytest.mark.parametrize("theme", ["light_reading", "pop_poster", "pixel_live"])
def test_native_kit_and_json_receive_authored_roles_without_styling_their_furniture(theme, monkeypatch):
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")
    config = visual_system_configuration(theme)
    # Synthetic, non-published values distinguish actual typography from legacy artwork.
    monkeypatch.setattr(reading_rules, "THEME_READING_OVERRIDES",
                        {theme: {BODY: {"size_px": 23.1}, COMPONENT_TITLE: {"size_px": 22.2},
                                 QUOTE: {"size_px": 21.3}, INLINE_EMPHASIS: {"weight": 833}}})
    profile = reading_rules.resolve_reading_profile(config, official=True, theme_id=theme)
    parsed = parse_markdown("# Test\n\n### Original heading\n\nA **real focus** and <unchanged>.\n\n> Quote.")
    refs = {b.type: b.id for b in parsed.blocks}
    source = SemanticSource.from_article(parsed, profile)

    def render(component, bindings):
        bound = source.bind({"component_type": component, "content_bindings": bindings})
        return render_bound_component(bound, visual_system_variant(component, theme),
                                      config["palette"], config, visual_system=theme)

    case = render("case_card", {"title": refs["heading"], "body": refs["paragraph"]})
    evidence = render("evidence_callout", {"evidence": refs["quote"]})
    assert case.count("font-size:23.1px;") == case.count("font-size:22.2px;") == 1
    assert len(re.findall(r'<strong\b[^>]*font-weight:833;[^>]*>real focus</strong>', case)) == 1
    assert "Original heading" in case and "&lt;unchanged&gt;" in case
    assert evidence.count("font-size:21.3px;") == 1 and "Quote." in evidence
    assert "SemanticField(" not in case + evidence
