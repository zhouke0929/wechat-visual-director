"""Browser regression for the autosave/freeze boundary; never calls WeChat."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from test_api_workflow import _prepare_publication_ready_task
from visual_director.image_provider import ManualImageProvider
from visual_director.main import create_app



def test_freeze_flushes_latest_edit_and_stops_if_autosave_fails(tmp_path, monkeypatch):
    playwright = pytest.importorskip("playwright.sync_api")
    root = Path(__file__).resolve().parents[3]
    if not (root / "apps/web/dist/index.html").is_file():
        pytest.skip("Build workbench before browser integration test")
    for key in ("WECHAT_APP_ID", "WECHAT_APP_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(tmp_path / "synthetic.env"))
    monkeypatch.setenv("VISUAL_DIRECTOR_WEB_DIST", str(root / "apps/web/dist"))
    app = create_app(str(tmp_path / "freeze-browser.db"), image_provider=ManualImageProvider())
    with TestClient(app) as client:
        task, _ = _prepare_publication_ready_task(client)
    task_id = task["id"]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 12
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline
            time.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        with playwright.sync_playwright() as runner:
            try:
                browser = runner.chromium.launch(headless=True)
            except playwright.Error as exc:
                pytest.skip(f"Chromium unavailable: {exc}")
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 960})
                page.goto(f"http://127.0.0.1:{port}/tasks/{task_id}", wait_until="networkidle")
                timeline = []
                induced_failure = True

                def save_gate(route):
                    if route.request.method != "PATCH":
                        route.continue_()
                        return
                    timeline.append("start-autosave")
                    if induced_failure:
                        route.fulfill(status=503, json={"error": {"message": "合成自动保存失败"}})
                    else:
                        time.sleep(0.30)
                        response = route.fetch()
                        timeline.append("autosave-complete")
                        route.fulfill(response=response)

                def freeze_gate(route):
                    if route.request.method == "POST":
                        timeline.append("freeze")
                    route.continue_()

                page.route("**/content-editor", save_gate)
                page.route("**/publication-revisions", freeze_gate)
                frame = page.frame_locator('iframe[title$="公众号移动端预览"]')
                paragraph = frame.locator('p[data-workbench-inline-block-id][contenteditable="true"]').first
                save = page.get_by_role("button", name="保存最终版本", exact=True)
                playwright.expect(save).to_be_enabled()
                paragraph.fill("这句必须和最终版本一起保存。", timeout=8000)
                save.click()
                playwright.expect(page.get_by_text("正文还未保存，请先重试保存正文，再交付最终版本。")).to_be_visible()
                assert "freeze" not in timeline
                induced_failure = False
                with page.expect_response(lambda item: item.url.endswith("/publication-revisions") and item.request.method == "POST") as event:
                    save.click()
                response = event.value
                assert response.status == 201, response.text()
                assert timeline[-3:] == ["start-autosave", "autosave-complete", "freeze"]
                assert response.request.post_data_json["expected_content_revision"] == 1
                revision_id = response.json()["revision"]["id"]
                frozen = page.request.get(f"http://127.0.0.1:{port}/api/v1/publication-revisions/{revision_id}/content")
                assert "这句必须和最终版本一起保存。" in frozen.text()
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.state.repository.connection.close()
