"""Guard the separation of source advice, host compilation and authored gallery samples."""
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

import pytest

from visual_director import component_opportunities, planner, theme_specimens
from visual_director.brief_compiler import apply_visual_system, compile_editorial_brief_recommended, structure_fingerprint
from visual_director.component_catalog import COMPONENT_CATALOG, VISUAL_SYSTEM_ORDER
from visual_director.editorial_brief import normalize_editorial_brief_for_article
from visual_director.parser import parse_markdown
from visual_director.renderer import render_preview
from visual_director.theme_production import check_theme_production

ROOT = Path(__file__).resolve().parents[3]


def test_public_app_can_load_without_historical_planner():
    # A separate interpreter avoids the test runner's own imports of legacy fixtures.
    subprocess.run([
        sys.executable, "-c",
        "import sys; from visual_director.main import create_app; "
        "assert not {'visual_director.planner', 'visual_director.rule_baseline'}.intersection(sys.modules)",
    ], cwd=ROOT / "apps/api/src", check=True)


@pytest.fixture
def no_rule_planning(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A host brief or authored specimen must not scan for extra plans or slots")
    for module, name in (
        (planner, "_build_candidates"), (planner, "_image_candidates"),
        (component_opportunities, "_build_candidates"),
    ):
        monkeypatch.setattr(module, name, forbidden)


@pytest.mark.parametrize("article, fingerprint", [
    ("01-campus-project-portfolio", "ed9a52d00376e4adfdc08558c9a4be2abb78cac2de1d9c29e2d6628e4239d400"),
    ("02-neighborhood-coffee-repeat-visits", "815e2bb8060cf9a5b5692373206739e1ce18f89e0fdfd37288899a6613ac8640"),
    ("03-pop-collaboration-memory", "f75bd7949937eaec6db0f0ef515ac6a832def67f6da2f8c1aafc6b7ea5dbb6a4"),
])
def test_approved_brief_structure_survives_compilation_and_theme_switch(no_rule_planning, article, fingerprint):
    samples = ROOT / "samples/showcase"
    parsed = parse_markdown((samples / f"{article}.md").read_text(encoding="utf-8"))
    raw = json.loads((samples / f"brief-{article}.json").read_text(encoding="utf-8"))
    brief, _ = normalize_editorial_brief_for_article(raw, parsed)
    plan = compile_editorial_brief_recommended(parsed, brief, history_window=5)
    assert plan["structure_fingerprint"] == fingerprint
    actual = Counter(slot["component_type"] for slot in plan["slots"])
    assert {key: value for key, value in plan["component_usage"].items() if key in COMPONENT_CATALOG} == actual
    switched = apply_visual_system(plan, "warm_humanist" if plan["visual_system"] != "warm_humanist" else "pop_poster")
    assert structure_fingerprint(switched) == fingerprint
    assert parsed.title in render_preview(parsed, switched)


def test_theme_picker_full_specimens_and_theme_validation_are_planner_free(no_rule_planning):
    cards = theme_specimens.build_theme_card_specimens()
    assert set(VISUAL_SYSTEM_ORDER) <= cards.keys()
    samples, article = theme_specimens.build_production_specimens("pop_poster")
    assert samples and "给好内容留一点呼吸的空间" in article
    template = ROOT / "skills/wechat-visual-director/assets/theme-pack-template.json"
    assert check_theme_production(json.loads(template.read_text(encoding="utf-8")))["status"] == "pass"
