"""Full component/whole-article renderer contract, not a planner test.

To reproduce the committed oracle: python apps/api/tests/test_renderer_catalog_parity.py.
That command renders ONLY the pinned Git archive; never the working tree. Normal
pytest uses the recorded plan and golden digests and does not need Git/history.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from contextlib import contextmanager
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[3]
ORACLE = Path(__file__).with_name("fixtures") / "catalog-v1.0.0.json"
# git rev-parse 'v1.0.0^{}' (annotated release tag, not the previous local trial).
REVISION = "10e5661afbe39e9999c7e8a3b5ca943f67c12ba5"
# "default" in the pinned v1 fixture means the historical no-switch rendering;
# do not relabel or recapture that oracle when promoting the compatible renderer.
MODES = {"default": {}, "legacy": {"WVD_RENDERER_PILOT": "0"},
         "structure": {"WVD_RENDERER_PILOT": "1"},
         "reading": {"WVD_RENDERER_PILOT": "1", "WVD_READING_RULES_PILOT": "1"}}
# Digests from the approved isolated poster/step trial, not a refresh of v1.
# The legacy rollback digests always remain pinned to v1.
APPROVED_POSTER_STEPS = {
    "pop_poster/logic_path": "62997dc102bccd620a23d626b35c392fac2a81b354a5e3a914c7223e566af251",
    "pop_poster/logic_path_stress": "1c04ab920d418bc4e2da29d8475f1cb587030053ad9b433e4ed1b6bd2192663f",
}
# Step typography and approved marker alignments: normal and stress cases.
STEP_WEIGHT_SAMPLES = {
    "youth_campus/logic_path": "9754db9e7474e171aa69c5a595e7bdca7f2296160c6867023a23f34631d6db7d",
    "youth_campus/logic_path_stress": "49e695dd914f8272bcba059249679b396f8776d3ba5d07b784aabb299b20ee2f",
    "editorial_contrast/logic_path": "7eda89cf28473c78a375f9f8a65c8d23f8fc676fd9adef14a4406d95b157c4de",
    "editorial_contrast/logic_path_stress": "8fb801ccf64ca338020001a96beb44916bd5308bff456470dd4bda33083586a9",
    "future_tech/logic_path": "de93d6c990a1853669df894099bde0f6413a739f9106c9ddb78e89e448345748",
    "future_tech/logic_path_stress": "141c75ba722dd1f80de87aa0dcdbcbdbad30a8f90e2275569c4036dfc65c7a6d",
    "business_review/logic_path": "6de469fa0e464bcbbb8d95ebb84a6d3c6b368cfd800566836a4177c66c9c0f72",
    "business_review/logic_path_stress": "09551f500cf14043912610d35c5f4d0ea499ea0aeaa56375c4ce012ed6bc9f35",
}
FOUNDATIONS = frozenset("hero lead paragraph section_heading subheading quote unordered_list "
                        "ordered_list image_caption table divider source reference_list closing_cta".split())
SEMANTIC = frozenset("question_hook numbered_insight evidence_callout before_after_timeline logic_path "
                     "concept_explainer case_card warning_note action_checklist faq_card comparison_card section_summary".split())

# Grid column sizing, plus the long-step and article probes.
GRID_REGISTER_SAMPLES = {
    "structured_grid/lead": "793152a15da59d5bb8461a7510d4af4ace515b23739e663e6c5845975e5155cd",
    "structured_grid/section_heading": "9b5923940b6fa6636b14ce731984733a32936fd25ee88721c074fb234543fd13",
    "structured_grid/unordered_list": "b82012ed23aaeab12c3342326f4df4295c2a9e9c6fd91fc9b4b6a7a71424c194",
    "structured_grid/ordered_list": "3518770e2aa15e7be779a73f3ccf46b3f0cf01d5bd87d5434d3b9b1c5ca90787",
    "structured_grid/action_checklist": "12662224aa2166567cb88eaa94696ab118e8281323bb6a2b14ee8499889578d2",
    "structured_grid/logic_path": "45107790fa5eb3bafdb219519956ecdba8b492a265002a9ff4495f39f41c7cc4",
    "structured_grid/warning_note": "2486d87dcab65a6b7619aaf86cc8166762c639c756d7bc9db4f2e68c796ab3d0",
    "structured_grid/quote": "2686b8d9a748efe6bd8aa89929244e88ae51cfc4be80bb5cd737a65f3393e56f",
    "structured_grid/evidence_callout": "df6990d73d15daed3b5d03b1ff1fe5cb54ad54d7cc73a39f2b947c08352d4fdc",
    "structured_grid/concept_explainer": "e372945daf50b026f1efd3d8da074904dc00297b2c3db315f499e18f51538dde",
    "structured_grid/case_card": "61815b16e7238bfbeff2848ed9c65e8abf3423636939d4ddcfa71245aff7d6ca",
    "structured_grid/whole_article": "4f3f7b6bc9a94b1c9cfb1b85b1d81c98c23746619c401584daf6f11e0884ba21",
    "structured_grid/logic_path_stress": "39a2e0bb3ac17dfd689055288a00a0b413522ea00baf2b41e237f6389f2a15d4",
}

_OPEN_TAG = re.compile(r"<[A-Za-z][^<>]*>")
_EDITOR_REF = re.compile(r"""(?:"[^"]*"|'[^']*'|(?P<ref> data-editor-(?:list|step)-ref="block-\d{3}(?::item:\d+)?"))""")


def _visible_markup(markup: str) -> str:
    # Do not parse/reserialize arbitrary HTML: that could hide changes to
    # wrappers, whitespace, style precedence, line breaks, or author text.
    return _OPEN_TAG.sub(lambda tag: _EDITOR_REF.sub(lambda m: "" if m["ref"] else m[0], tag[0]), markup)


def test_display_comparison_retains_markup_source_text_and_unrelated_hooks():
    for value in (' data-editor-list-ref="block-123:item:2"', ' data-editor-step-ref="block-123"'):
        quoted = "title='" + value + "'"
        unchanged = f'<p {quoted} data-editor-block-ids="block-123" style="font-weight:700;">{value}</p>'
        marked = unchanged.replace(" style=", value + " style=")
        assert _visible_markup(marked) == unchanged


def _stress_logic_path(theme: str) -> str:
    from visual_director import theme_gallery as gallery
    from visual_director.brief_compiler import visual_system_configuration
    from dataclasses import replace
    from visual_director.parser import ContentBlock, parse_markdown

    # Already-parsed source, just like a saved plan: do not test Markdown parser
    # differences here. Both duplicate items retain their independent references.
    rows = ["**核对图片位置**\n逐段确认图片放在它所说明的段落之后，观察引导语、图注和下一条说明的阅读节奏。"
            "这里还需确认**行内强调**和很长的说明不会变成另一层小标题。",
            "保存之前再检查。", "保存之前再检查。",
            "**注意**：这是一句普通说明，不是一个单独的小标题。"]
    parsed = replace(parse_markdown("# 固定复测"), blocks=[ContentBlock("block-001", "ordered_list", rows)])
    refs = {"logic_path": {"items": [f"block-001:item:{i}" for i in range(len(rows))]}}
    return gallery._component_specimen(parsed, "logic_path", theme, visual_system_configuration(theme)["palette"], refs)["html"]


def fixed_sample_plan(module, plan):
    # The historical oracle runs against the release archive, which pre-dates
    # the explicit fixture. Only this test adapter knows both interfaces.
    if hasattr(module, "sample_article_plan"):
        return patch.object(module, "sample_article_plan", return_value=plan)
    return patch.object(module, "generate_plans", return_value=[plan])


def _samples(root: Path, mode: str, plan: dict):
    from visual_director import theme_gallery as gallery, theme_specimens
    from visual_director.component_catalog import VISUAL_SYSTEM_ORDER
    from visual_director.parser import parse_markdown
    from visual_director.brief_compiler import visual_system_configuration
    assert len(VISUAL_SYSTEM_ORDER) == 26
    with patch.dict(os.environ, VISUAL_DIRECTOR_PROJECT_ROOT=str(root)), fixed_sample_plan(theme_specimens, plan):
        for name in ("WVD_RENDERER_PILOT", "WVD_LOGIC_PATH_PILOT", "WVD_READING_RULES_PILOT"):
            os.environ.pop(name, None)
        os.environ.update(MODES[mode])
        parsed = parse_markdown(gallery.THEME_FIXTURE)
        bindings = gallery._fixture_bindings(parsed)
        assert set(bindings) == SEMANTIC
        for theme in VISUAL_SYSTEM_ORDER:
            foundations, article = theme_specimens.build_production_specimens(theme)
            assert len(foundations) == 14 and {s["role"] for s in foundations} == FOUNDATIONS
            palette = visual_system_configuration(theme)["palette"]
            samples = [(s["role"], s["html"]) for s in foundations] + [
                (role, gallery._component_specimen(parsed, role, theme, palette, bindings)["html"])
                for role in sorted(SEMANTIC)
            ] + [("whole_article", article), ("logic_path_stress", _stress_logic_path(theme))]
            for role, markup in samples:
                assert markup.strip(), (theme, role)
                yield theme, role, markup


def _render(root: Path, mode: str, plan: dict) -> dict[str, str]:
    # The site's existing normalization checks PNG checksums, dimensions and
    # actual pixels; only platform-specific encoding can vary, never markup.
    with patch.object(sys, "path", [str(root / "scripts"), *sys.path]):
        from export_theme_gallery import comparable_gallery
    return {f"{theme}/{role}": hashlib.sha256(_visible_markup(comparable_gallery(markup)).encode()).hexdigest()
            for theme, role, markup in _samples(root, mode, plan)}


@pytest.fixture
def fixed_catalog(monkeypatch, tmp_path):
    from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
    from visual_director import theme_packs

    monkeypatch.setenv("VISUAL_DIRECTOR_THEME_PACK_DIR", str(tmp_path / "packs"))
    # configure_theme_packs replaces the process registry. Restore its actual
    # previous state (including a configured host or a never-initialized one).
    registry = {k: getattr(theme_packs, k) for k in ("_pack_dir", "_reserved_ids", "_core_components", "_installed", "_load_errors")}
    with patch.multiple(theme_packs, **registry):
        theme_packs.configure_theme_packs(tmp_path / "packs", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
        golden = json.loads(ORACLE.read_text(encoding="utf-8"))
        assert golden["revision"] == REVISION
        yield golden


@pytest.mark.parametrize("mode", MODES)
def test_complete_catalog_matches_pinned_renderer(mode, fixed_catalog):
    expected = {**fixed_catalog["default"], **fixed_catalog.get(mode, {})}
    # The WeChat-safe table border applies even with typography pilots off.
    expected["structured_grid/table"] = "938403058398ae80660e677c43e7918af7948074fbffc6f2daa593f7684288e9"
    if mode == "legacy":
        expected["structured_grid/whole_article"] = "b83d96f42095b5aaafa43d6e8cbb506b3deb653ccc5290715a26b9c3df90cb24"
    if mode != "legacy":
        expected.update(APPROVED_POSTER_STEPS)
        expected.update(STEP_WEIGHT_SAMPLES)
        expected.update(GRID_REGISTER_SAMPLES)
        # Campus evidence card: single-line radio sticker above the note.
        expected["youth_campus/evidence_callout"] = "03f24b1dd1b1298938bb827a87aa1be51f565b8857e02b5e1ccabf7d8075a826"
    observed = _render(ROOT, mode, fixed_catalog["fixed_plan"])
    differing = sorted(k for k in expected.keys() | observed.keys() if expected.get(k) != observed.get(k))
    assert not differing, f"{mode}: {len(differing)} changed theme/roles: {differing}"


def test_explicit_sizes_reach_every_authored_catalog_role(monkeypatch, fixed_catalog):
    # Differential probes use distinct values absent from ordinary themes. No
    # product config is changed. Do not couple expectations to renderer tables:
    # removing a field from the registry must not silently remove its test.
    from visual_director import reading_rules
    from visual_director.component_catalog import VISUAL_SYSTEM_ORDER

    fields = {
        "hero": ("article_title",), "lead": ("lead",), "paragraph": ("body",),
        "section_heading": ("section_title",), "subheading": ("subheading",), "quote": ("quote",),
        "unordered_list": ("list_body",), "ordered_list": ("list_body",), "image_caption": ("caption",),
        "table": ("table_header", "table_body"), "divider": (), "source": ("source",),
        "reference_list": ("reference",), "closing_cta": ("brand_footer",),
        "question_hook": ("component_title",), "numbered_insight": ("body",),
        "evidence_callout": ("quote",), "before_after_timeline": ("body",), "logic_path": ("step_body",),
        "concept_explainer": ("component_title", "body"), "case_card": ("component_title", "body"),
        "warning_note": ("body",), "action_checklist": ("body",), "faq_card": ("component_title", "body"),
        "comparison_card": ("body",), "section_summary": ("body",),
    }
    assert set(fields) == FOUNDATIONS | SEMANTIC
    role_names = sorted({name for names in fields.values() for name in names})
    overrides = {name: {"size_px": round(21.37 + i / 100, 2)} for i, name in enumerate(role_names)}
    monkeypatch.setattr(reading_rules, "THEME_READING_OVERRIDES", {t: overrides for t in VISUAL_SYSTEM_ORDER})
    missing = []
    for theme, role, markup in _samples(ROOT, "reading", fixed_catalog["fixed_plan"]):
        for field in fields.get(role, ()):
            if f'font-size:{overrides[field]["size_px"]:g}px;' not in markup:
                missing.append(f"{theme}/{role}/{field}")
    assert not missing, missing


def _print_archived(root: Path) -> None:
    from visual_director import theme_specimens as ts
    from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
    from visual_director.theme_packs import configure_theme_packs

    assert Path(ts.__file__).resolve().is_relative_to(root), "refusing to capture the working renderer"
    configure_theme_packs(root / "empty-packs", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    plan = ts.generate_plans(ts.parse_markdown(ts.ARTICLE), "tutorial_steps", 5)[0]
    # The public gallery materializes its own illustration and theme configuration.
    plan["image_slots"] = []
    plan["configuration"] = {}
    base = _render(root, "default", plan)
    result = {"revision": REVISION, "fixed_plan": plan, "default": base}
    for mode in ("structure", "reading"):
        trial = _render(root, mode, plan)
        assert trial.keys() == base.keys()
        result[mode] = {k: v for k, v in trial.items() if v != base[k]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


@contextmanager
def _pinned_source_tree(revision=REVISION):
    with tempfile.TemporaryDirectory(prefix="wvd-golden-catalog-") as name:
        root = Path(name).resolve()
        archive = subprocess.check_output(["git", "archive", "--format=zip", revision, "apps/api/src",
                                           "assets", "config", "contracts", "skills/wechat-visual-director/assets",
                                           "scripts/export_theme_gallery.py"], cwd=ROOT)
        with zipfile.ZipFile(io.BytesIO(archive)) as sources:
            sources.extractall(root)
        env = {**os.environ, "PYTHONPATH": str(root / "apps/api/src"), "PYTHONIOENCODING": "utf-8",
               "VISUAL_DIRECTOR_PROJECT_ROOT": str(root), "VISUAL_DIRECTOR_THEME_PACK_DIR": str(root / "empty-packs")}
        yield root, env


def _reproduce() -> None:
    with _pinned_source_tree() as (root, env):
        generated = subprocess.check_output([sys.executable, str(Path(__file__).resolve()), "--archived", str(root)],
                                            cwd=root, env=env, encoding="utf-8")
        ORACLE.parent.mkdir(exist_ok=True)
        ORACLE.write_text(generated, encoding="utf-8", newline="\n")


def _diagnose_revision(revision: str) -> None:
    # Optional: reconstruct a pre-fix candidate even if the working tree has
    # moved. Both sides always receive the one plan archived with the release.
    with _pinned_source_tree(revision) as (root, env):
        out = subprocess.check_output([sys.executable, str(Path(__file__).resolve()), "--inspect", str(root)],
                                      cwd=root, env=env, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--archived":
        _print_archived(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 3 and sys.argv[1] == "--diff-at":
        _diagnose_revision(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--inspect":
        from visual_director import theme_specimens as ts
        from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
        from visual_director.theme_packs import configure_theme_packs
        folder = Path(sys.argv[2]).resolve()
        assert Path(ts.__file__).resolve().is_relative_to(folder)
        configure_theme_packs(folder / "empty-packs", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
        golden = json.loads(ORACLE.read_text(encoding="utf-8"))
        for mode in MODES:
            old = {**golden["default"], **golden.get(mode, {})}
            new = _render(folder, mode, golden["fixed_plan"])
            assert old.keys() == new.keys()
            differences = [key for key in sorted(old) if old[key] != new[key]]
            print(json.dumps({"mode": mode, "differences": differences}))
    else:
        _reproduce()
