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
MODES = {"default": ("0", "0"), "structure": ("1", "0"), "reading": ("1", "1")}
FOUNDATIONS = frozenset("hero lead paragraph section_heading subheading quote unordered_list "
                        "ordered_list image_caption table divider source reference_list closing_cta".split())
SEMANTIC = frozenset("question_hook numbered_insight evidence_callout before_after_timeline logic_path "
                     "concept_explainer case_card warning_note action_checklist faq_card comparison_card section_summary".split())

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


def _samples(root: Path, mode: str, plan: dict):
    from visual_director import theme_gallery as gallery, theme_specimens
    from visual_director.component_catalog import VISUAL_SYSTEM_ORDER
    from visual_director.parser import parse_markdown
    from visual_director.brief_compiler import visual_system_configuration
    renderer, reading = MODES[mode]
    flags = {"WVD_RENDERER_PILOT": renderer, "WVD_LOGIC_PATH_PILOT": "0",
             "WVD_READING_RULES_PILOT": reading, "VISUAL_DIRECTOR_PROJECT_ROOT": str(root)}
    assert len(VISUAL_SYSTEM_ORDER) == 26
    with patch.dict(os.environ, flags), patch.object(theme_specimens, "generate_plans", return_value=[plan]):
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
