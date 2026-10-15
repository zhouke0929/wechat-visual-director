"""Evaluation harness checks only: no app, database, network or model imports."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "evals/theme-creation" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


EVAL = module("theme_creation_eval", "run.py")
RUNTIME = module("theme_creation_runtime", "runtime_cli.py")


@pytest.fixture
def corpus(tmp_path: Path):
    root = tmp_path / "repo"
    raw = root / "artifacts/raw"
    raw.mkdir(parents=True)
    article = raw / "article.md"
    article.write_text("# 原标题\n\n完整正文。", encoding="utf-8")
    image = raw / "sample.png"
    image.write_bytes(b"test-only-image-bytes")
    skill = root / "skills/wechat-visual-director"
    (skill / "evals").mkdir(parents=True)
    (skill / "SKILL.md").write_text("repository skill", encoding="utf-8")
    (skill / "evals/answers.json").write_text("hidden answer", encoding="utf-8")
    suite = {
        "schema_version": "theme_creation_eval.v1", "revision": "test",
        "cases": [{"id": "sample", "status": "regression_observed", "request": "制作完整主题。",
                   "inputs": [{"name": "article.md", "path": "artifacts/raw/article.md", "sha256": EVAL.digest(article)}]}],
        "anchors": [{"id": "private-anchor", "role": "faq_card", "title": "<not markup>",
                     "label": "待校准", "reason": "hidden answer", "boundary": "不是整套通过",
                     "path": "artifacts/raw/sample.png", "sha256": EVAL.digest(image)}],
    }
    return root, suite


def test_suite_has_two_regressions_and_an_unrun_description_case():
    suite = EVAL.read_json(ROOT / "evals/theme-creation/suite.json")
    EVAL.validate_suite(suite)
    assert [c["status"] for c in suite["cases"]].count("regression_observed") == 2
    assert [c["status"] for c in suite["cases"]].count("reserved_unrun") == 1
    assert suite["owner_calibration"] == "pending"
    for case in suite["cases"]:
        for item in case["inputs"]:
            if item["path"].startswith("evals/"):
                assert EVAL.digest(ROOT / item["path"]) == item["sha256"]


def test_prepare_freezes_only_raw_inputs_skill_and_isolated_runtime(corpus):
    root, suite = corpus
    out = root / "artifacts/run"
    result = EVAL.prepare(root, suite, "sample", out, 18589)
    assert result["model_calls"] == 0 and result["visual_result"] == "not_reviewed"
    assert EVAL.verify(out)["inputs_and_skill_unchanged"]
    assert not (out / "skill-snapshot/evals").exists()
    assert not list(out.rglob("*answers*"))
    assert "hidden answer" not in (out / "task-prompt.md").read_text(encoding="utf-8")
    assert not (out / "input/sample.png").exists()
    config = EVAL.read_json(out / "output/runtime-config.json")
    assert config == {"repository": str(root), "port": 18589}
    assessment = EVAL.read_json(out / "assessment.json")
    assert assessment["visual"]["delivery_judgment"] == "not_reviewed"
    assert assessment["execution"]["tokens"] is None


@pytest.mark.parametrize("kind", ["missing", "changed"])
def test_input_failure_does_not_create_output(corpus, kind):
    root, suite = corpus
    path = root / "artifacts/raw/article.md"
    if kind == "missing":
        path.unlink()
    else:
        path.write_text("changed", encoding="utf-8")
    out = root / "artifacts/run"
    with pytest.raises(ValueError):
        EVAL.prepare(root, suite, "sample", out, 18589)
    assert not out.exists()
    assert EVAL.inspect(root, suite)["cases"][0]["inputs_available"] is False


def test_existing_output_is_preserved(corpus):
    root, suite = corpus
    out = root / "artifacts/run"
    out.mkdir()
    (out / "keep.txt").write_text("user data", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        EVAL.prepare(root, suite, "sample", out, 18589)
    assert (out / "keep.txt").read_text(encoding="utf-8") == "user data"


def test_private_source_and_nonisolated_destination_are_rejected(corpus):
    root, suite = corpus
    with pytest.raises(ValueError, match="outside evaluation"):
        EVAL.source(root, "apps/api/data/private.db")
    with pytest.raises(ValueError, match="Output must"):
        EVAL.prepare(root, suite, "sample", root / "apps/new", 18589)
    assert not (root / "apps").exists()


@pytest.mark.parametrize("port", [8000, 80, 70000])
def test_production_or_invalid_port_does_not_prepare(corpus, port):
    root, suite = corpus
    with pytest.raises(ValueError, match="port"):
        EVAL.prepare(root, suite, "sample", root / "artifacts/run", port)


def test_verify_detects_changed_and_extra_inputs_without_claiming_visual_pass(corpus):
    root, suite = corpus
    out = root / "artifacts/run"
    EVAL.prepare(root, suite, "sample", out, 18589)
    (out / "input/article.md").write_text("changed", encoding="utf-8")
    (out / "skill-snapshot/extra.md").write_text("extra", encoding="utf-8")
    result = EVAL.verify(out)
    assert not result["inputs_and_skill_unchanged"]
    assert result["changed"] == ["input/article.md", "skill-snapshot/extra.md"]
    assert result["visual_result"] == "not_reviewed"


def test_run_lock_path_escape_is_rejected(corpus):
    root, suite = corpus
    out = root / "artifacts/run"
    EVAL.prepare(root, suite, "sample", out, 18589)
    lock = EVAL.read_json(out / "run-lock.json")
    lock["input_sha256"]["../../private.db"] = "0" * 64
    (out / "run-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe"):
        EVAL.verify(out)


def test_board_copies_original_bytes_escapes_text_and_stays_unconfirmed(corpus):
    root, suite = corpus
    out = root / "artifacts/board"
    result = EVAL.board(root, suite, out)
    assert result["owner_confirmation"] == "pending" and result["model_calls"] == 0
    assert (out / "assets/anchor-1.png").read_bytes() == (root / "artifacts/raw/sample.png").read_bytes()
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "&lt;not markup&gt;" in page and "<not markup>" not in page
    assert "fetch(" not in page and "XMLHttpRequest" not in page


def test_board_rejects_changed_anchor_before_writing(corpus):
    root, suite = corpus
    suite["anchors"][0]["sha256"] = "0" * 64
    out = root / "artifacts/board"
    with pytest.raises(ValueError, match="hash changed"):
        EVAL.board(root, suite, out)
    assert not out.exists()


def test_runtime_rejects_connection_override_before_cli_import(corpus, monkeypatch):
    root, _ = corpus
    monkeypatch.setattr(RUNTIME, "configure", lambda: (root, 18589))
    monkeypatch.setattr(sys, "argv", ["isolated_cli.py", "theme", "list", "--api-base=http://127.0.0.1:8000"])
    with pytest.raises(SystemExit, match="cannot be overridden"):
        RUNTIME.main()


def test_runtime_clears_inherited_business_configuration(corpus, monkeypatch):
    root, suite = corpus
    out = root / "artifacts/run"
    EVAL.prepare(root, suite, "sample", out, 18589)
    monkeypatch.setattr(RUNTIME, "__file__", str(out / "output/isolated_cli.py"))
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(sys, "dont_write_bytecode", sys.dont_write_bytecode)
    monkeypatch.setenv("SAMPLE_PRIVATE_KEY", "do-not-copy")
    monkeypatch.setenv("VISUAL_DIRECTOR_DB", "production.db")
    original = dict(RUNTIME.os.environ)
    try:
        repo, port = RUNTIME.configure()
        assert repo == root and port == 18589
        assert "SAMPLE_PRIVATE_KEY" not in RUNTIME.os.environ
        assert RUNTIME.os.environ["VISUAL_DIRECTOR_DB"] == str(out / "output/runtime/data/visual-director.db")
        assert RUNTIME.os.environ["VISUAL_DIRECTOR_API_BASE"] == "http://127.0.0.1:18589/api/v1"
    finally:
        RUNTIME.os.environ.clear()
        RUNTIME.os.environ.update(original)


def test_invalid_suite_does_not_accept_input_filename_traversal(corpus):
    _, suite = corpus
    invalid = copy.deepcopy(suite)
    invalid["cases"][0]["inputs"][0]["name"] = "../article.md"
    with pytest.raises(ValueError, match="unique input|filenames"):
        EVAL.validate_suite(invalid)
