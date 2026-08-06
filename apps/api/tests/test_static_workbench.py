from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from visual_director.main import create_app


def test_fastapi_serves_static_workbench_and_spa_routes(tmp_path: Path, monkeypatch) -> None:
    web_dist = tmp_path / "dist"
    (web_dist / "assets").mkdir(parents=True)
    (web_dist / "index.html").write_text(
        '<!doctype html><div id="root">single-process-workbench</div>', encoding="utf-8"
    )
    (web_dist / "assets" / "app.js").write_text("window.ready=true", encoding="utf-8")
    monkeypatch.setenv("VISUAL_DIRECTOR_WEB_DIST", str(web_dist))
    client = TestClient(create_app(database_path=str(tmp_path / "visual-director.db")))

    assert "single-process-workbench" in client.get("/").text
    assert "single-process-workbench" in client.get("/tasks/task-123").text
    assert client.get("/assets/app.js").text == "window.ready=true"
    health = client.get("/api/health").json()
    assert health["application"] == "wechat_visual_director_workbench"
    assert client.get("/api/v1/does-not-exist").status_code == 404
