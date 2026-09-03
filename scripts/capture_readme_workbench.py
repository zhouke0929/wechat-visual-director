"""Capture the real workbench using public fixtures and a fresh isolated database.

Requires the API dependencies, Playwright, Edge, and the built apps/web/dist.
No model calls, real credentials, publishing, or existing tasks are used.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    runtime = ROOT / ".visual-director-test-runtime" / f"readme-capture-{uuid.uuid4().hex[:8]}"
    runtime.mkdir(parents=True)
    # Only this short-lived process is changed; never load the user's env file.
    for key in list(os.environ):
        if key.startswith(("VISUAL_DIRECTOR_", "WECHAT_", "IMAGE_", "AGNES_", "GEMINI_")):
            del os.environ[key]
    os.environ.update({
        "VISUAL_DIRECTOR_PROJECT_ROOT": str(ROOT),
        "VISUAL_DIRECTOR_ENV_FILE": str(runtime / "unused.env"),
        "VISUAL_DIRECTOR_DB": str(runtime / "public-demo.db"),
        "VISUAL_DIRECTOR_IMAGE_PROVIDER": "manual",
    })
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright
    import uvicorn
    from visual_director.main import app

    def checked(response):
        response.raise_for_status()
        return response.json()

    with TestClient(app) as api:
        sample = ROOT / "samples/showcase/01-campus-project-portfolio.md"
        brief = json.loads((ROOT / "samples/showcase/brief-01-campus-project-portfolio.json").read_text(encoding="utf-8"))
        for intent in brief["image_intents"]:
            intent["forbidden_elements"] = list(dict.fromkeys(["text_in_model_image", *intent["forbidden_elements"]]))[:6]
        task = checked(api.post("/api/v1/article-tasks", files={"markdown_file": (sample.name, sample.read_bytes(), "text/markdown")}))["task"]
        task_path = f'/api/v1/article-tasks/{task["id"]}'
        checked(api.post(task_path + "/generate-plans", json={"mode": "start", "expected_task_version": task["version"], "planner": "host_agent", "editorial_brief": brief, "host_model": "public_showcase_fixture"}))
        task = checked(api.get(task_path))["task"]
        plan = checked(api.get(task_path + "/plans"))["plans"][0]
        plan_path = task_path + f'/plans/{plan["id"]}'
        if plan["visual_system"] != "youth_campus":
            checked(api.patch(plan_path + "/theme", json={"visual_system": "youth_campus", "expected_plan_revision": plan["revision"]}))
            task = checked(api.get(task_path))["task"]
        checked(api.post(plan_path + "/select", json={"plan_id": plan["id"], "expected_task_version": task["version"]}))
        slots = checked(api.get(plan_path + "/image-slots"))["items"]
        images = {"16:9": "campus-portfolio-steps.webp", "4:3": "campus-portfolio-scene.webp"}
        assert len(slots) == 2, "Public fixture should retain its two curated images"
        for slot in slots:
            asset = ROOT / "site/assets/generated" / images[slot["aspect_ratio"]]
            checked(api.post(plan_path + f'/image-slots/{slot["image_slot_id"]}/replace', data={"expected_image_revision": str(slot["state"]["image_revision"])}, files={"image_file": (asset.name, asset.read_bytes(), "image/webp")}))

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        assert server.started
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="msedge")
            context = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=2, reduced_motion="reduce")
            # The screenshot may access only this isolated loopback service.
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
            page = context.new_page()
            page.goto(base + f'/tasks/{task["id"]}', wait_until="networkidle")
            preview = page.frame_locator("iframe.preview-frame")
            editable = preview.locator("[data-workbench-inline-editor]").first
            editable.wait_for(state="visible")
            editable.click()
            page.get_by_text("正在原文修改 · 停顿后保存", exact=True).wait_for()
            page.screenshot(path=str(ROOT / "docs/assets/readme/article-review.png"))
            page.get_by_role("tab", name="手机预览", exact=True).click()
            page.locator(".preview-mode-mobile").wait_for(state="visible")
            preview.locator("main").wait_for(state="visible")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            page.screenshot(path=str(runtime / "mobile-review.png"))
            page.screenshot(path=str(ROOT / "docs/assets/readme/article-mobile-review.png"))
            context.close()
            browser.close()
        print(f"Captured real workbench: {runtime.name}")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


if __name__ == "__main__":
    main()
