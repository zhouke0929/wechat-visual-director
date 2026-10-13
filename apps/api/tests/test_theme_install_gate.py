from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from visual_director import cli, theme_gallery, theme_packs
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.main import create_app


ROOT = Path(__file__).resolve().parents[3]
HEADERS = {"X-Local-Intent": "local-operator"}


def manifest():
    return json.loads((ROOT / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))


def content(value=None):
    return json.dumps(value or manifest(), ensure_ascii=False).encode("utf-8")


@pytest.fixture
def pack_dir(tmp_path):
    path = tmp_path / "theme-packs"
    theme_packs.configure_theme_packs(path, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    return path


def test_delivery_warning_and_unverified_visual_state_do_not_block_install(pack_dir):
    result = theme_packs.install_theme_pack_bytes(content(), "theme.json", with_report=True)
    report = result["delivery_report"]
    assert report["rehearsal"]["status"] == "pass"
    assert report["design_review"]["status"] == "review_required"
    assert report["visual_review"] == report["wechat_saved_roundtrip"] == "not_verified"
    assert theme_packs.theme_pack(manifest()["id"]) == result["manifest"]


def test_partial_authored_prototype_is_not_confused_with_renderer_failure(pack_dir):
    value = manifest()
    del value["design_system"]["layouts"]["lead"]
    result = theme_packs.install_theme_pack_bytes(content(value), "theme.json", with_report=True)
    assert result["delivery_report"]["coverage"]["status"] == "partial"
    assert result["delivery_report"]["rehearsal"]["status"] == "pass"
    assert result["delivery_report"]["next_action"] == "complete_theme_layouts"


@pytest.mark.parametrize("install", [False, True])
def test_api_blocks_production_failure_before_creating_or_replacing_a_pack(tmp_path, monkeypatch, install):
    app = create_app(str(tmp_path / "gate.db"))
    old = theme_packs.install_theme_pack_bytes(content(), "theme.json")
    path = theme_packs.theme_pack_directory() / old["id"] / "theme.json"
    original = path.read_bytes()
    value = manifest()
    value["version"] = "2.0.0"
    from visual_director import renderer
    original_renderer = renderer.render_generated_paragraph
    monkeypatch.setattr(renderer, "render_generated_paragraph", lambda text, config, lead=False: original_renderer(text, config, lead=False))
    with TestClient(app) as client:
        endpoint = "/api/v1/theme-packs" + ("" if install else "/validate")
        response = client.post(endpoint, headers=HEADERS, files={"theme_file": ("theme.json", content(value), "application/json")})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "theme_pack_delivery_blocked"
    assert error["details"]["delivery_report"]["rehearsal"]["production"]["status"] == "blocking"
    assert path.read_bytes() == original
    assert theme_packs.theme_pack(old["id"]) == old
    assert sorted(item.name for item in path.parent.parent.iterdir()) == [old["id"]]


def test_fresh_direct_install_is_also_gated_and_writes_nothing(pack_dir, monkeypatch):
    monkeypatch.setattr("visual_director.theme_delivery.theme_delivery_report", lambda value: {"local_delivery": "blocking", "rehearsal": {"status": "blocking"}})
    with pytest.raises(theme_packs.ThemePackError) as error:
        theme_packs.install_theme_pack_bytes(content(), "theme.json")
    assert error.value.code == "theme_pack_delivery_blocked"
    assert list(pack_dir.iterdir()) == []
    assert theme_packs.installed_theme_packs() == []


def test_asset_or_renderer_exception_blocks_without_mutation(pack_dir, monkeypatch):
    def failure(value):
        raise OSError("simulated unavailable image compiler")
    monkeypatch.setattr("visual_director.theme_delivery.theme_delivery_report", failure)
    with pytest.raises(theme_packs.ThemePackError) as error:
        theme_packs.install_theme_pack_bytes(content(), "theme.json")
    assert error.value.code == "theme_pack_delivery_blocked"
    assert error.value.delivery_report["cause"] == "OSError"
    assert list(pack_dir.iterdir()) == []


def test_failed_filesystem_replacement_restores_old_file_and_registry(pack_dir, monkeypatch):
    old = theme_packs.install_theme_pack_bytes(content(), "theme.json")
    destination = pack_dir / old["id"]
    original = (destination / "theme.json").read_bytes()
    value = manifest()
    value["version"] = "2.0.0"
    real_replace = theme_packs.os.replace

    def fail_candidate(source, target):
        if Path(target) == destination and Path(source).name != f".{old['id']}.backup":
            raise OSError("simulated candidate replacement failure")
        return real_replace(source, target)

    monkeypatch.setattr(theme_packs.os, "replace", fail_candidate)
    with pytest.raises(theme_packs.ThemePackError) as error:
        theme_packs.install_theme_pack_bytes(content(value), "theme.json")
    assert error.value.code == "theme_pack_install_failed"
    assert (destination / "theme.json").read_bytes() == original
    assert theme_packs.theme_pack(old["id"]) == old
    assert sorted(item.name for item in pack_dir.iterdir()) == [old["id"]]


def test_backup_cleanup_failure_is_not_reported_as_failed_install(pack_dir, monkeypatch):
    theme_packs.install_theme_pack_bytes(content(), "theme.json")
    value = manifest()
    value["version"] = "2.0.0"
    real_remove = theme_packs.shutil.rmtree

    def keep_backup(path, *args, **kwargs):
        if Path(path).name.endswith(".backup"):
            raise OSError("simulated cleanup failure")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(theme_packs.shutil, "rmtree", keep_backup)
    result = theme_packs.install_theme_pack_bytes(content(value), "theme.json", with_report=True)
    assert result["manifest"]["version"] == "2.0.0"
    assert result["delivery_report"]["installation_warnings"] == ["old_theme_backup_retained"]
    theme_packs.configure_theme_packs(pack_dir, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    assert theme_packs.theme_pack(value["id"])["version"] == "2.0.0"


def test_bad_custom_preview_is_isolated_and_does_not_fake_fallback_artwork(pack_dir, monkeypatch):
    value = theme_packs.install_theme_pack_bytes(content(), "theme.json")
    original = theme_gallery.build_production_specimens

    def fail_only_custom(theme_id):
        if theme_id == value["id"]:
            raise ValueError("simulated old custom renderer failure")
        return original(theme_id)

    monkeypatch.setattr(theme_gallery, "build_production_specimens", fail_only_custom)
    items = theme_gallery.build_theme_gallery()
    assert len([item for item in items if item["source"] == "official"]) == 12
    bad = next(item for item in items if item["id"] == value["id"])
    assert bad["availability"] == "unavailable" and bad["diagnostic"]["code"] == "theme_preview_failed"
    assert bad["components"] == [] and bad["article_preview_html"] == ""
    assert (pack_dir / value["id"] / "theme.json").exists()


def test_corrupt_local_file_is_visible_and_reimport_clears_diagnostic(pack_dir):
    value = manifest()
    directory = pack_dir / value["id"]
    directory.mkdir()
    path = directory / "theme.json"
    path.write_bytes(b"\xff not UTF-8 or JSON")
    theme_packs.configure_theme_packs(pack_dir, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    items = theme_gallery.build_theme_gallery()
    bad = next(item for item in items if item.get("availability") == "unavailable")
    assert bad["diagnostic"]["code"] == "theme_pack_load_failed"
    assert path.read_bytes() == b"\xff not UTF-8 or JSON"
    theme_packs.install_theme_pack_bytes(content(), "theme.json")
    assert theme_packs.theme_pack_load_errors() == []
    assert not any(item.get("availability") == "unavailable" for item in theme_gallery.build_theme_gallery())


def test_explicit_deletion_clears_stale_corrupt_file_diagnostic(pack_dir):
    value = manifest()
    directory = pack_dir / value["id"]
    directory.mkdir()
    (directory / "theme.json").write_bytes(b"not JSON")
    theme_packs.configure_theme_packs(pack_dir, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    assert theme_packs.theme_pack_load_errors()
    assert theme_packs.delete_theme_pack(value["id"]) is True
    assert theme_packs.theme_pack_load_errors() == []


@pytest.mark.parametrize("install", [False, True])
def test_cli_never_claims_success_for_older_server_blocking_response(monkeypatch, capsys, install):
    monkeypatch.setattr(cli, "_request_json", lambda *args, **kwargs: {"manifest": manifest(), "valid": True, "installed": install,
                      "delivery_report": {"local_delivery": "blocking", "rehearsal": {"status": "blocking"}}})
    code = cli.run(["theme", "install" if install else "validate", "--no-start", "--file", str(ROOT / "skills/wechat-visual-director/assets/theme-pack-template.json"), "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code != 0 and result["ok"] is False
    assert result["error"]["code"] == "theme_pack_delivery_blocked"


def test_shared_official_renderer_failure_is_not_silently_hidden(pack_dir, monkeypatch):
    monkeypatch.setattr(theme_gallery, "build_production_specimens", lambda *args: (_ for _ in ()).throw(ValueError("shared failure")))
    with pytest.raises(ValueError, match="shared failure"):
        theme_gallery.build_theme_gallery()
