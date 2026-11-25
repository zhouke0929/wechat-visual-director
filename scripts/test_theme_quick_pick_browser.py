"""Try on themes using an isolated local draft; no external services or real task data."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import threading
import time

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
import uvicorn


def run(out: Path, repo: Path) -> None:
    for key in list(os.environ):
        if key.startswith(("VISUAL_DIRECTOR_", "WECHAT_", "OPENAI_", "GEMINI_")):
            del os.environ[key]
    os.environ.update({
        "VISUAL_DIRECTOR_PROJECT_ROOT": str(repo),
        "VISUAL_DIRECTOR_HOME": str(out / "runtime"),
        "VISUAL_DIRECTOR_DB": str(out / "test.db"),
        "VISUAL_DIRECTOR_ENV_FILE": str(out / "empty.env"),
        "VISUAL_DIRECTOR_THEME_PACK_DIR": str(out / "theme-packs"),
        "VISUAL_DIRECTOR_IMAGE_PROVIDER": "manual",
    })
    sys.path.insert(0, str(repo / "apps/api/src"))
    sys.path.insert(0, str(repo / "apps/api/tests"))
    from host_fixture import submit_fixture
    from visual_director.main import app

    with TestClient(app) as client:
        markdown = "# 给街角留十分钟\n\n## 从门口出发\n\n今天试着在熟悉的街上慢慢走一段，把看到的东西记下来。\n\n> 一次停留，就是一段可分享的故事。\n"
        response = client.post("/api/v1/article-tasks", files={"markdown_file": ("article.md", markdown.encode(), "text/markdown")})
        assert response.status_code == 201, response.text
        task = response.json()["task"]
        api = f"/api/v1/article-tasks/{task['id']}"
        result = submit_fixture(client, api, task["version"])
        assert result.status_code == 202, result.text
        assert client.get(f"{api}/content-editor").status_code == 200
        specimens = client.get("/api/v1/theme-card-specimens").json()["specimens"]
        options = client.get(f"{api}/plans").json()["plans"][0]["visual_system_metadata"]["available_visual_systems"]
        assert set(specimens) == {item["value"] for item in options}
        assert all("给好内容留一点呼吸的空间" in html or "data-editor-title" in html for html in specimens.values())

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline, "Isolated server didn't start"
            time.sleep(.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}/tasks/{task['id']}"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 960})
                failures, writes, responses = [], [], []
                page.on("pageerror", lambda error: failures.append(str(error)))
                page.on("request", lambda request: writes.append(request.url) if request.method in ("PATCH", "POST") else None)
                page.on("response", lambda response: responses.append(response.url) if response.request.method in ("PATCH", "POST") else None)
                page.goto(url, wait_until="networkidle")
                tabs = page.get_by_role("tablist", name="切换编辑内容")
                assert tabs.get_by_role("tab").locator("strong").all_text_contents() == ["主题选择", "配图审核", "文章封面"]
                expect(tabs.get_by_role("tab", name="主题选择")).to_have_attribute("aria-selected", "true")
                expect(page.get_by_role("combobox", name="选择整篇文章主题")).to_have_count(0)
                picker = page.get_by_role("tabpanel", name="主题选择").locator("[data-current-theme]")
                original = picker.get_attribute("data-current-theme")
                cards = page.get_by_role("region", name="主题小卡")
                expect(cards.get_by_role("button")).to_have_count(len(options))
                expect(cards.locator("iframe")).to_have_count(len(options), timeout=20_000)
                filters = page.get_by_role("group", name="按风格筛选主题")
                filters.get_by_role("button", name="数字与导视").click()
                expect(cards.get_by_role("region")).to_have_count(1)
                card = cards.locator(f"button[data-theme='{'future_tech' if original != 'future_tech' else 'retro_window'}']")
                theme = card.get_attribute("data-theme")
                frame = page.frame_locator("iframe.preview-frame")
                original_src = page.locator("iframe.preview-frame").get_attribute("src")
                body = frame.get_by_role("textbox").filter(has_text="把看到的东西记下来")
                body.fill("换主题之前刚编辑的正文必须保留。")
                with page.expect_response(lambda r: r.url.endswith("/theme") and r.request.method == "PATCH") as switch:
                    card.click()
                assert switch.value.ok, switch.value.text()
                assert switch.value.json()["planner_called"] is False
                assert switch.value.json()["images_regenerated"] is False
                assert [url.rsplit("/", 1)[-1] for url in writes] == ["content-editor", "theme"], writes
                assert responses[0].endswith("/content-editor"), responses
                expect(card).to_have_attribute("aria-pressed", "true")
                expect(picker).to_have_attribute("data-current-theme", theme)
                expect(page.locator("iframe.preview-frame")).not_to_have_attribute("src", original_src)
                expect(frame.get_by_role("textbox").filter(has_text="换主题之前刚编辑的正文必须保留。")).to_be_visible()
                undo = page.get_by_role("button", name="回到上一版", exact=True)
                undo.click()
                expect(picker).to_have_attribute("data-current-theme", original)
                current_body = frame.get_by_role("textbox").filter(has_text="换主题之前刚编辑的正文必须保留。")
                expect(current_body).to_be_visible()

                def fail_save(route):
                    if route.request.method == "PATCH":
                        route.fulfill(status=422, json={"error": {"message": "模拟正文保存失败"}})
                    else:
                        route.continue_()

                page.route("**/content-editor", fail_save)
                count = len(writes)
                current_body.fill("尚未保存的正文也不能被换主题覆盖。")
                card.click()
                expect(page.locator(".toast-error")).to_contain_text("正文未保存，未切换主题")
                expect(picker).to_have_attribute("data-current-theme", original)
                expect(frame.get_by_role("textbox").filter(has_text="尚未保存的正文也不能被换主题覆盖。")).to_be_visible()
                assert [url.rsplit("/", 1)[-1] for url in writes[count:]] == ["content-editor"]
                page.unroute("**/content-editor", fail_save)
                card.click()
                expect(picker).to_have_attribute("data-current-theme", theme)
                expect(frame.get_by_role("textbox").filter(has_text="尚未保存的正文也不能被换主题覆盖。")).to_be_visible()

                filters.get_by_role("button", name="全部").click()
                expect(cards.get_by_role("button")).to_have_count(len(options))
                for width in (1440, 1101, 1080, 1024, 768, 405, 375):
                    page.set_viewport_size({"width": width, "height": 860})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
                    assert cards.evaluate("el => el.scrollHeight > el.clientHeight"), width
                    if width <= 1100:
                        expect(page.get_by_role("link", name="查看文章")).to_be_visible()
                assert not failures, failures
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.state.repository.connection.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="theme-quick-pick-") as directory:
        run(Path(directory), Path(__file__).resolve().parents[1])
    print("PASS: all theme cards and filters, default tab, save before apply, undo, save failure/retry, responsive layout")
