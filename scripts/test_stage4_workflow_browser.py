"""Isolated task lookup, host-image handoff and theme undo smoke test.

Uses synthetic articles and an empty private runtime. No model, WeChat or actual
clipboard writes. Requires built apps/web/dist and Python Playwright.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18724)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    if not (out.is_relative_to(repo / ".tmp") or out.is_relative_to(repo / "artifacts")) or out.exists():
        raise SystemExit("Use a new output directory inside .tmp or artifacts")
    if args.port == 8000 or not 1024 <= args.port <= 65535:
        raise SystemExit("Use an isolated unprivileged port")
    for key in list(os.environ):
        if key.startswith(("VISUAL_DIRECTOR_", "WECHAT_", "OPENAI_", "GEMINI_")):
            del os.environ[key]
    out.mkdir(parents=True)
    (out / "brand.json").write_text(json.dumps({"schema_version": "brand_profile.v0.1",
        "name": "公开测试", "fixed_footer": {"enabled": False}}), encoding="utf-8")
    os.environ.update({
        "VISUAL_DIRECTOR_PROJECT_ROOT": str(out / "isolated-root"),
        "VISUAL_DIRECTOR_HOME": str(out / "runtime"),
        "VISUAL_DIRECTOR_DB": str(out / "runtime/data/visual-director.db"),
        "VISUAL_DIRECTOR_ENV_FILE": str(out / "empty.env"),
        "VISUAL_DIRECTOR_THEME_PACK_DIR": str(out / "theme-packs"),
        "VISUAL_DIRECTOR_BRAND_PROFILE": str(out / "brand.json"),
        "VISUAL_DIRECTOR_WEB_DIST": str(repo / "apps/web/dist"),
        "VISUAL_DIRECTOR_IMAGE_PROVIDER": "manual",
    })
    sys.path.insert(0, str(repo / "apps/api/src"))
    from fastapi.testclient import TestClient
    from playwright.sync_api import expect, sync_playwright
    import uvicorn
    from visual_director.main import create_app
    app = create_app()
    with TestClient(app) as client:
        for index in range(10):
            title = "阶段四出游文章" if index == 0 else f"测试记录 {index}"
            content = f"---\ntitle: {title}\narticle_type: tutorial_steps\n---\n# {title}\n\n## 三步行动\n\n1. 确定范围\n2. 记录细节\n3. 整理笔记\n\n> 留下可复核的记录。\n"
            response = client.post("/api/v1/article-tasks", files={"markdown_file": ("article.md", content.encode(), "text/markdown")})
            assert response.status_code == 201, response.text
            if index == 0:
                task = response.json()["task"]
        result = client.post(f"/api/v1/article-tasks/{task['id']}/generate-plans",
                            json={"mode": "start", "expected_task_version": task["version"]})
        assert result.status_code in (200, 202), result.text
        plans = client.get(f"/api/v1/article-tasks/{task['id']}/plans").json()
        assert plans["plans"], plans
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning"))
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    deadline = time.monotonic() + 20
    while not server.started:
        if not worker.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("Isolated server did not start")
        time.sleep(.05)
    base = f"http://127.0.0.1:{args.port}"
    checks, errors, forbidden = [], [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.add_init_script("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.copied=text}}});")
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: forbidden.append(request.url) if request.method == "POST" and any(
                part in request.url for part in ("/generate", "/host-image-context", "/draft-operations")) else None)
            for width in (1440, 405):
                page.set_viewport_size({"width": width, "height": 1000})
                page.goto(base + "/tasks", wait_until="networkidle")
                expect(page.locator(".task-row")).to_have_count(8)
                page.get_by_label("按文章标题查找").fill("阶段四出游")
                page.get_by_role("button", name="查找", exact=True).click()
                expect(page.locator(".task-row")).to_have_count(1)
                expect(page.locator(".task-row")).to_contain_text("阶段四出游文章")
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                page.screenshot(path=str(out / f"search-{width}.png"), full_page=True)
                page.get_by_label("按文章标题查找").fill("无匹配")
                page.get_by_role("button", name="查找", exact=True).click()
                expect(page.get_by_role("heading", name="没有找到匹配的任务")).to_be_visible()
                page.get_by_role("button", name="显示全部").click()
                expect(page.locator(".task-row")).to_have_count(8)
            checks.append("title search finds off-page task; no-match and reset; desktop/mobile layout")
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.goto(base + f"/tasks/{task['id']}", wait_until="networkidle")
            page.locator(".editor-controls").screenshot(path=str(out / "host-image-toolbar.png"))
            page.get_by_role("button", name="让 Agent 配图", exact=True).click()
            dialog = page.get_by_role("dialog", name="让 Agent 生成正文配图", exact=True)
            expect(dialog).to_be_visible()
            expect(page.get_by_label("给 Agent 的正文配图指令")).to_be_visible()
            expect(dialog.locator("details")).to_have_count(0)
            assert page.get_by_label("给 Agent 的正文配图指令").evaluate("e=>e.clientHeight") >= 300
            expect(page.locator("body")).to_have_css("overflow", "hidden")
            page.get_by_role("button", name="复制正文配图指令").click()
            body_prompt = page.get_by_label("给 Agent 的正文配图指令").input_value()
            assert page.evaluate("window.copied") == body_prompt and task["id"] in body_prompt
            expect(dialog.get_by_role("status")).to_contain_text("已复制")
            page.screenshot(path=str(out / "host-image-dialog-desktop.png"))
            page.keyboard.press("Escape")
            expect(dialog).to_have_count(0)
            expect(page.get_by_role("button", name="让 Agent 配图", exact=True)).to_be_focused()
            expect(page.locator("body")).not_to_have_css("overflow", "hidden")
            page.get_by_role("tab", name="文章封面").click()
            page.get_by_role("button", name="让 Agent 生成", exact=True).click()
            page.get_by_role("button", name="复制封面指令").click()
            assert page.evaluate("window.copied") == page.get_by_label("给 Agent 的封面指令").input_value()
            assert "生成封面" in page.evaluate("window.copied")
            page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('denied')}}})")
            page.get_by_role("button", name="复制封面指令").click()
            expect(page.locator(".host-image-dialog [role=status]")).to_contain_text("手动复制")
            textbox = page.get_by_label("给 Agent 的封面指令")
            expect(textbox).to_be_visible()
            expect(textbox).to_be_focused()
            assert textbox.evaluate("e=>e.selectionEnd-e.selectionStart") == len(textbox.input_value())
            page.locator(".host-image-dialog").screenshot(path=str(out / "host-image-manual-copy.png"))
            page.get_by_role("button", name="关闭配图指令窗口").click()
            for width in (405, 320):
                page.set_viewport_size({"width": width, "height": 740})
                page.get_by_role("button", name="让 Agent 生成", exact=True).click()
                dialog = page.get_by_role("dialog", name="让 Agent 生成封面", exact=True)
                expect(dialog).to_be_visible()
                assert dialog.evaluate("e=>e.scrollWidth<=e.clientWidth")
                box = dialog.bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= width
                # The supported 405px workbench must fit as a whole. At 320px,
                # this focused check covers the dialog rather than the entire desk.
                if width == 405:
                    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                page.get_by_role("button", name="复制封面指令").click()
                expect(page.get_by_label("给 Agent 的封面指令")).to_be_focused()
                page.screenshot(path=str(out / f"host-image-dialog-{width}.png"))
                page.keyboard.press("Escape")
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.get_by_role("tab", name="配图审核").click()
            page.get_by_role("button", name="让 Agent 配图", exact=True).click()
            dialog = page.get_by_role("dialog", name="让 Agent 生成正文配图", exact=True)
            expect(dialog).to_be_visible()
            page.mouse.click(5, 5)
            expect(dialog).to_have_count(0)
            page.screenshot(path=str(out / "workbench-desktop.png"))
            checks.append("compact body/cover entries; task-bound prompt; clipboard failure manual selection; native dialog focus/Escape/backdrop; 320/405px layouts; no model calls")
            before = page.locator("select").first.input_value()
            page.get_by_role("button", name="换一个主题", exact=True).click()
            expect(page.get_by_role("button", name="回到上一版", exact=True)).to_be_enabled()
            page.get_by_role("button", name="回到上一版", exact=True).click()
            expect(page.locator("select").first).to_have_value(before)
            expect(page.get_by_role("button", name="回到上一版", exact=True)).to_have_count(0)
            checks.append("theme switch and undo restore original selection without regeneration")
            page.goto(base + "/settings", wait_until="networkidle")
            expect(page.get_by_text("这里配置的是工作台图片 API。", exact=False)).to_be_visible()
            assert not forbidden, forbidden
            assert not errors, errors
            browser.close()
        (out / "report.json").write_text(json.dumps({"ok": True, "checks": checks, "task_id": task["id"],
            "real_model_calls": 0, "wechat_calls": 0, "production_data_access": False}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "checks": checks}, ensure_ascii=False))
    finally:
        server.should_exit = True
        worker.join(timeout=10)


if __name__ == "__main__":
    main()
