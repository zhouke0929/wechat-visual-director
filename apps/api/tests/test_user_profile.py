from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pytest

from test_data_recovery import make_dataset
from visual_director.data_recovery import DataRecoveryError
from visual_director.upgrade_data import capture_upgrade_data, dataset_snapshot, verify_upgrade_data
from visual_director.user_profile import prepare_user_profile, profile_lock, read_user_profile, register_user_install

REPO = Path(__file__).resolve().parents[3]


def test_first_profile_copies_all_history_assets_themes_and_config_retaining_source(tmp_path):
    legacy, home = tmp_path / "legacy", tmp_path / "user-home"
    make_dataset(legacy / "data", ["historical-article"])
    theme = legacy / "data/theme-packs/original/theme.json"
    theme.parent.mkdir(parents=True)
    theme.write_text('{"name":"original theme"}', encoding="utf-8")
    (legacy / "config").mkdir()
    (legacy / "config/.env.local").write_bytes(b"TEST_ONLY_SETTING=keep\n")
    before = dataset_snapshot(legacy / "data")
    prepared = prepare_user_profile(home, legacy)
    copied = dataset_snapshot(home / "data")
    assert copied["task_ids"] == before["task_ids"]
    assert copied["assets"] == before["assets"]
    assert dataset_snapshot(legacy / "data") == before
    assert (home / "config/.env.local").read_bytes() == b"TEST_ONLY_SETTING=keep\n"
    assert prepared["copied_legacy"] is True
    assert "TEST_ONLY_SETTING" not in json.dumps(prepared)


def test_second_program_reuses_profile_and_does_not_import_another_database(tmp_path):
    a, b, home = tmp_path / "a", tmp_path / "b", tmp_path / "home"
    make_dataset(a / "data", ["a"])
    make_dataset(b / "data", ["b"])
    original_b = dataset_snapshot(b / "data")
    first = prepare_user_profile(home, a)
    with pytest.raises(DataRecoveryError) as error:
        prepare_user_profile(home, b)
    assert error.value.code == "shared_history_conflict"
    reused = prepare_user_profile(home, tmp_path / "fresh-program")
    assert first["profile"]["profile_id"] == reused["profile"]["profile_id"]
    assert reused["created"] is False
    assert dataset_snapshot(home / "data")["task_ids"] == ["a"]
    assert dataset_snapshot(b / "data") == original_b


def test_missing_registered_database_never_creates_empty_replacement(tmp_path):
    home = tmp_path / "home"
    prepare_user_profile(home, tmp_path / "install")
    (home / "data/visual-director.db").unlink()
    with pytest.raises(DataRecoveryError) as error:
        prepare_user_profile(home, tmp_path / "another")
    assert error.value.code == "shared_data_missing"
    assert not (home / "data/visual-director.db").exists()


def test_orphaned_data_without_registry_is_not_reinitialized(tmp_path):
    home = tmp_path / "home"
    make_dataset(home / "data", ["preserve"])
    with pytest.raises(DataRecoveryError) as error:
        prepare_user_profile(home, tmp_path / "install")
    assert error.value.code == "shared_data_unregistered"
    assert dataset_snapshot(home / "data")["task_ids"] == ["preserve"]


def test_profile_rejects_external_paths_and_registration_mismatch(tmp_path):
    home, install = tmp_path / "home", tmp_path / "install"
    prepare_user_profile(home, install)
    install.mkdir()
    (install / "install.json").write_text(json.dumps({"data_root": str(install / "data")}), encoding="utf-8")
    with pytest.raises(DataRecoveryError) as error:
        register_user_install(home, install)
    assert error.value.code == "shared_data_binding_mismatch"
    file = home / "profile.json"
    profile = json.loads(file.read_text())
    profile["data_root"] = str(tmp_path / "outside")
    file.write_text(json.dumps(profile))
    with pytest.raises(DataRecoveryError):
        read_user_profile(home)


def test_profile_lock_prevents_parallel_initialization(tmp_path):
    home = tmp_path / "home"
    with profile_lock(home):
        with pytest.raises(DataRecoveryError) as error:
            prepare_user_profile(home, tmp_path / "install")
    assert error.value.code == "user_profile_busy"
    assert not (home / "data").exists()


def test_old_source_changed_after_migration_requires_review_not_silent_loss(tmp_path):
    source, home = tmp_path / "legacy", tmp_path / "home"
    make_dataset(source / "data", ["old"])
    prepare_user_profile(home, source)
    with sqlite3.connect(source / "data/visual-director.db") as connection:
        connection.execute("INSERT INTO tasks VALUES ('written-by-old-version', '2026-10-26')")
    with pytest.raises(DataRecoveryError) as error:
        prepare_user_profile(home, source)
    assert error.value.code == "shared_history_conflict"
    assert dataset_snapshot(home / "data")["task_ids"] == ["old"]
    assert dataset_snapshot(source / "data")["task_ids"] == ["old", "written-by-old-version"]


def test_upgrade_checks_the_shared_dataset_not_an_empty_program_directory(tmp_path):
    install, home = tmp_path / "program", tmp_path / "home"
    make_dataset(install / "data", ["old"])
    before = capture_upgrade_data(install)
    result = prepare_user_profile(home, install)
    (install / "install.json").write_text(json.dumps({"data_root": result["profile"]["data_root"]}), encoding="utf-8")
    assert verify_upgrade_data(before, install)["after_task_count"] == 1
    second = tmp_path / "second"
    shared = capture_upgrade_data(second, target_data_root=home / "data")
    assert shared["before"]["task_ids"] == ["old"]


def test_real_workbench_api_reopens_history_and_uploaded_image_after_copy(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from PIL import Image
    from visual_director.main import create_app
    from visual_director.image_provider import MockImageProvider
    from visual_director.text_planner import MockTextPlannerProvider

    legacy, home = tmp_path / "program", tmp_path / "shared"
    (legacy / "config").mkdir(parents=True)
    (legacy / "config/.env.local").touch()
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(legacy / "config/.env.local"))
    app = create_app(str(legacy / "data/visual-director.db"), image_provider=MockImageProvider(), text_planner_provider=MockTextPlannerProvider())
    markdown = "# 历史文章\n\n保留这篇原文。\n\n## 行动\n\n1. 查看\n2. 记录\n3. 分享\n"
    image = BytesIO()
    Image.new("RGB", (640, 360), "#34796c").save(image, format="PNG")
    with TestClient(app) as client:
        response = client.post("/api/v1/article-tasks", files={"markdown_file": ("history.md", markdown.encode(), "text/markdown")})
        assert response.status_code == 201
        task = response.json()["task"]
        cover = client.post(f'/api/v1/article-tasks/{task["id"]}/preflight/findings/missing_cover/replace-asset',
                            data={"expected_task_version": task["version"]},
                            files={"image_file": ("cover.png", image.getvalue(), "image/png")})
        assert cover.status_code == 200
        asset = app.state.repository.list_preflight_asset_replacements(task["id"])[0]
        original_image = client.get(asset["content_url"]).content
    app.state.repository.connection.close()
    prepare_user_profile(home, legacy)
    # Old program files/data could disappear later; the migrated API cannot depend on them.
    shutil.move(str(legacy / "data"), str(tmp_path / "retained-legacy-backup"))
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(home / "config/.env.local"))
    reopened = create_app(str(home / "data/visual-director.db"), image_provider=MockImageProvider(), text_planner_provider=MockTextPlannerProvider())
    with TestClient(reopened) as client:
        items = client.get("/api/v1/article-tasks").json()["items"]
        assert any(item["id"] == task["id"] for item in items)
        loaded = client.get(f'/api/v1/article-tasks/{task["id"]}')
        assert loaded.status_code == 200
        assert loaded.json()["task"]["title"] == "历史文章"
        copied = client.get(asset["content_url"])
        assert copied.status_code == 200 and copied.content == original_image
    reopened.state.repository.connection.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows shared installation discovery")
def test_shared_registry_is_used_from_two_different_host_appdata_views(tmp_path):
    from test_windows_install_paths import lit, run_ps

    home, active = tmp_path / "shared-home", tmp_path / "active-program"
    prepare_user_profile(home, active)
    active.mkdir()
    (active / "install.json").write_text(json.dumps({"data_root": str(home / "data")}), encoding="utf-8")
    (active / "visual-director.ps1").write_text("throw 'must not start'", encoding="utf-8")
    register_user_install(home, active)
    for host in ("codex-view", "another-agent-view"):
        local = tmp_path / host
        for other in (local / "wechat-visual-director",
                      local / "Packages/OpenAI.Codex_old/LocalCache/Local/wechat-visual-director"):
            other.mkdir(parents=True)
            (other / "install.json").write_text("{}")
        process, result = run_ps(tmp_path, f"Resolve-WvdInstallLocation '' {lit(home)} | ConvertTo-Json -Depth 5", local=local)
        assert process.returncode == 0, process.stderr
        assert result["actual_root"] == str(active)
        assert result["shared_profile"] is True


@pytest.mark.skipif(os.name != "nt", reason="Windows shared data safety")
def test_shared_data_cannot_be_placed_in_removable_program_directory(tmp_path):
    from test_windows_install_paths import lit, run_ps
    program = tmp_path / "program"
    process, result = run_ps(tmp_path, f"try {{ Assert-WvdDataHomeSeparation {lit(program / 'versions/data')} {lit(program)}; throw 'not blocked' }} catch {{ @{{message=$_.Exception.Message}} | ConvertTo-Json; exit 2 }}")
    assert process.returncode == 2
    assert "outside the removable program" in result["message"]
    assert not program.exists()


def _package(tmp_path):
    source = tmp_path / "package"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    for name in ("install.ps1", "persistent-launcher.ps1", "persistent-launcher.cmd", "uninstall.ps1", "manage-user-profile.py"):
        shutil.copy2(REPO / "scripts" / name, scripts / name)
    shutil.copytree(REPO / "skills/wechat-visual-director", source / "skills/wechat-visual-director")
    api = source / "apps/api/src/visual_director"
    api.mkdir(parents=True)
    for name in ("__init__.py", "user_profile.py", "upgrade_data.py", "data_recovery.py"):
        shutil.copy2(REPO / "apps/api/src/visual_director" / name, api / name)
    (source / "VERSION").write_text("0.1.0-shared-test")
    (source / ".env.example").write_text("TEST_ONLY_CONFIG=default\n")
    (source / "apps/web/dist").mkdir(parents=True)
    (source / "apps/web/dist/index.html").write_text("<html>isolated</html>")
    (scripts / "mock-cli.py").write_text('''import json, os, sqlite3, sys
with sqlite3.connect(os.environ['VISUAL_DIRECTOR_DB']) as c:
    c.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL)')
    if sys.argv[1] == 'create': c.execute("INSERT INTO tasks VALUES (?, '2026-10-26')", (sys.argv[2],))
    ids = [r[0] for r in c.execute('SELECT id FROM tasks ORDER BY id')]
print(json.dumps(dict(ok=True, refused={}, ids=ids, data=os.environ['VISUAL_DIRECTOR_DATA_ROOT'], app=os.environ['VISUAL_DIRECTOR_PROJECT_ROOT'], api=os.environ.get('VISUAL_DIRECTOR_API_BASE'))))
''', encoding="utf-8")
    python = str(Path(sys.executable)).replace("'", "''")
    (scripts / "visual-director.ps1").write_text(
        f"& '{python}' (Join-Path $PSScriptRoot 'mock-cli.py') @args\nexit $LASTEXITCODE", encoding="utf-8-sig")
    return source


def _ps(script, *args):
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, args)],
                            env={**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]},
                            capture_output=True, text=True, encoding="utf-8", timeout=45)
    assert result.stdout.strip(), result.stderr
    return result, json.loads(result.stdout)


@pytest.mark.skipif(os.name != "nt", reason="Windows shared launcher integration")
def test_two_program_locations_and_hosts_reopen_the_same_history_and_survive_uninstall(tmp_path):
    source = _package(tmp_path)
    home, host = tmp_path / "shared-user", tmp_path / "host"
    a, b = tmp_path / "codex-program", tmp_path / "other-agent-program"
    make_dataset(a / "data", ["historical"])
    args = ("-UserDataHome", home, "-HostHome", host, "-SkipDependencies")
    first, installed = _ps(source / "scripts/install.ps1", "-InstallRoot", a, *args)
    assert first.returncode == 0, (first.stderr, installed)
    assert installed["data_root"] == str(home / "data")
    created, _ = _ps(a / "visual-director.ps1", "create", "from-codex")
    assert created.returncode == 0
    second, installed_b = _ps(source / "scripts/install.ps1", "-InstallRoot", b, *args)
    assert second.returncode == 0, (second.stderr, installed_b)
    register_user_install(home, b, api_base="http://127.0.0.1:18759/api/v1", web_base="http://127.0.0.1:18759")
    _, after_switch = _ps(b / "visual-director.ps1", "list")
    assert after_switch["ids"] == ["from-codex", "historical"]
    _ps(b / "visual-director.ps1", "create", "from-other-agent")
    _, after_return = _ps(a / "visual-director.ps1", "list")
    assert after_return["ids"] == ["from-codex", "from-other-agent", "historical"]
    assert Path(after_return["app"]) == b / "versions/0.1.0-shared-test"  # A delegates to the one active program.
    assert after_return["api"] == "http://127.0.0.1:18759/api/v1"
    # Removing an obsolete program must not stop/remove the active registration or shared history.
    removed, _ = _ps(a / "uninstall.ps1", "-HostHome", host)
    assert removed.returncode == 0, removed.stderr
    assert (host / ".agents/skills/wechat-visual-director/SKILL.md").is_file()
    _, retained = _ps(b / "visual-director.ps1", "list")
    assert retained["ids"] == after_return["ids"]
    # Default uninstall preserves history; a reinstall at a third program path sees it all.
    removed, _ = _ps(b / "uninstall.ps1", "-HostHome", host)
    assert removed.returncode == 0, removed.stderr
    c = tmp_path / "third-program"
    reinstalled, _ = _ps(source / "scripts/install.ps1", "-InstallRoot", c, *args)
    assert reinstalled.returncode == 0, reinstalled.stderr
    _, reopened = _ps(c / "visual-director.ps1", "list")
    assert reopened["ids"] == retained["ids"]
    assert dataset_snapshot(a / "data")["task_ids"] == ["historical"]  # Original source retained.
    (home / "data/visual-director.db").unlink()
    rejected, error = _ps(c / "visual-director.ps1", "list")
    assert rejected.returncode == 2
    assert error["ok"] is False
    assert not (home / "data/visual-director.db").exists()
