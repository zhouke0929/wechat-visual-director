"""Browser regression for an explicitly isolated, empty source/test workbench.

Requires Python Playwright and local Edge (or --channel chromium). No real state
is written; task management uses intercepted fake responses.
Never run against the user's formal installation: runtime identity is checked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


def geometry(page) -> dict:
    return page.evaluate("""() => ({
        page: [innerWidth, innerHeight, document.documentElement.scrollWidth,
               document.documentElement.scrollHeight, scrollY],
        boxes: ['.hero-copy h1', '.agent-start', '.desk-recent-link'].map(selector => {
            const r = document.querySelector(selector).getBoundingClientRect();
            return [r.x, r.y, r.width, r.height];
        })
    })""")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--channel", default="msedge")
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    assert parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
    with urlopen(f"{args.url}/health") as response:
        identity = json.load(response)["runtime_identity"]
    assert identity["mode"] != "installed" and identity["install_root"] is None
    assert Path(identity["data_root"]).resolve() == args.data_root.resolve()
    assert identity["task_count"] == 0
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel=args.channel)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()
        errors: list[str] = []
        task_writes: list[str] = []
        task_reads: list[str] = []
        guide_requests: list[str] = []
        page.on("request", lambda request: guide_requests.append(request.url) if "/settings/onboarding" in request.url else None)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: task_writes.append(request.url) if request.method == "POST" and request.url.endswith("/article-tasks") else None)
        page.on("request", lambda request: task_reads.append(request.url) if request.method == "GET" and "/article-tasks?" in request.url else None)
        page.goto(args.url, wait_until="networkidle")
        expect(page.locator(".getting-started button")).to_have_count(0)
        guide = page.get_by_role("region", name="从规划到交付")
        expect(guide).to_be_visible()
        expect(page.get_by_role("link", name="上手指南")).to_have_count(0)
        expect(page.locator('input[type="file"], form, .task-list')).to_have_count(0)
        expect(page.get_by_role("link", name="继续已有任务")).to_have_attribute("href", "/tasks")
        expect(page.get_by_role("link", name="最近任务", exact=True)).to_have_attribute("href", "/tasks")
        assert not task_reads, "Homepage must not fetch the task list"

        for width, height in [(1280, 720), (1366, 768), (1440, 900), (1920, 1080)]:
            page.set_viewport_size({"width": width, "height": height})
            frame = geometry(page)
            assert frame["page"][2:4] == [width, height], frame
            assert all(y >= 0 and y + h <= height for _, y, _, h in frame["boxes"]), frame
            print(f"PASS: single-screen {width}x{height}")
        page.set_viewport_size({"width": 1366, "height": 768})
        page.screenshot(path=str(args.output / "desktop.png"), full_page=True)
        before = geometry(page)
        prompt = page.get_by_label("可以这样对 Agent 说")
        copy = page.locator("button[data-copy-state]")
        assert "【填写主题】" in prompt.input_value() and "语义规划" in prompt.input_value()
        # Never access the user's clipboard.
        page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText: async text => { window.copiedPrompt = text; }}})")
        copy.click()
        expect(copy).to_have_attribute("data-copy-state", "copied")
        assert page.evaluate("window.copiedPrompt") == prompt.input_value()
        assert geometry(page) == before
        expect(copy).to_have_attribute("data-copy-state", "idle", timeout=3000)
        assert geometry(page) == before
        page.get_by_role("button", name="我有一篇文章").click()
        assert "保留事实" in prompt.input_value() and "语义规划" in prompt.input_value()
        assert "【填写主题】" not in prompt.input_value()
        assert geometry(page) == before
        copy.click()
        expect(copy).to_have_attribute("data-copy-state", "copied")
        assert page.evaluate("window.copiedPrompt") == prompt.input_value()
        assert geometry(page) == before
        page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText: async () => { throw new Error('denied'); }}})")
        copy.click()
        expect(copy).to_have_attribute("data-copy-state", "failed")
        expect(page.get_by_role("status").filter(has_text="请手动复制")).to_be_visible()
        expect(prompt).to_be_focused()
        assert prompt.evaluate("el => el.selectionEnd - el.selectionStart") == len(prompt.input_value())
        assert geometry(page) == before
        # An outstanding copy must not restore stale success after switching modes.
        page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText: () => new Promise(resolve => { window.finishCopy = resolve; })}})")
        copy.click()
        expect(copy).to_be_disabled()
        page.get_by_role("button", name="我有一个选题").click()
        page.evaluate("window.finishCopy()")
        expect(copy).to_have_attribute("data-copy-state", "idle")
        assert geometry(page) == before

        # Guidance is static: no persistence request or confirmation is required.
        page.reload(wait_until="networkidle")
        expect(page.locator(".getting-started button")).to_have_count(0)
        expect(guide).to_be_visible()
        assert geometry(page) == before
        assert not guide_requests, guide_requests

        page.get_by_role("link", name="继续已有任务").click()
        expect(page).to_have_url(f"{args.url}/tasks")
        expect(page.get_by_role("heading", name="还没有视觉任务")).to_be_visible()
        page.reload(wait_until="networkidle")
        expect(page.locator("header strong")).to_have_text("最近任务")
        expect(page.get_by_role("link", name="返回任务台", exact=True)).to_have_attribute("href", "/")
        expect(page.locator("header nav")).to_have_count(0)
        page.get_by_role("link", name="回到首页开始").click()
        expect(page.get_by_role("heading", level=1)).to_contain_text("先让 Agent 读懂")

        # Exercise existing pagination/selection/deletion with fake tasks only.
        tasks = [{"id": f"ui-{i}", "title": f"界面测试文章 {i}", "article_type": "viewpoint_trend", "history_window": 5, "updated_at": "2026-09-03T00:00:00Z", "status": "plans_ready"} for i in range(1, 11)]
        deleted: list[str] = []

        def fake_tasks(route):
            path = urlsplit(route.request.url).path
            if path.endswith("/batch-delete"):
                ids = route.request.post_data_json["task_ids"]
                deleted.extend(ids)
                tasks[:] = [task for task in tasks if task["id"] not in ids]
                route.fulfill(json={"deleted_count": len(ids), "asset_cleanup_warnings": []})
            elif path.endswith("/article-tasks"):
                number = int(parse_qs(urlsplit(route.request.url).query)["page"][0])
                route.fulfill(json={"schema_version": "article_task_page.v0.1", "items": tasks[(number-1)*8:number*8], "total": len(tasks), "page": number, "page_size": 8, "total_pages": max(1, (len(tasks)+7)//8)})
            else:
                route.fulfill(status=404, json={"error": {"message": "测试任务不存在"}})

        page.route("**/api/v1/article-tasks**", fake_tasks)
        page.get_by_role("link", name="最近任务", exact=True).click()
        expect(page.locator(".task-row")).to_have_count(8)
        page.get_by_role("button", name="下一页").click()
        expect(page.locator(".task-row")).to_have_count(2)
        expect(page.locator(".task-index").first).to_have_text("09")
        page.get_by_role("button", name="管理历史任务").click()
        page.get_by_role("button", name="全选本页").click()
        page.get_by_role("button", name="删除所选").click()
        expect(page.get_by_role("dialog")).to_be_visible()
        page.get_by_role("button", name="保留任务").click()
        assert not deleted
        page.get_by_role("button", name="删除所选").click()
        page.get_by_role("button", name="确认永久删除").click()
        expect(page.locator(".task-row")).to_have_count(8)
        expect(page.get_by_role("navigation", name="历史任务分页")).to_contain_text("第 1 / 1 页")
        assert deleted == ["ui-9", "ui-10"]
        page.screenshot(path=str(args.output / "tasks.png"), full_page=True)
        page.locator(".task-row").first.click()
        page.get_by_role("link", name="返回最近任务").click()
        expect(page).to_have_url(f"{args.url}/tasks")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.get_by_role("link", name="返回任务台", exact=True).click()
        assert page.evaluate("scrollY") == 0
        assert geometry(page) == before

        # A new browser context shows the same guide without an acknowledgement.
        mobile = browser.new_context(viewport={"width": 390, "height": 844})
        phone = mobile.new_page()
        phone.on("pageerror", lambda error: errors.append(str(error)))
        phone.goto(args.url, wait_until="networkidle")
        expect(phone.locator(".getting-started button")).to_have_count(0)
        expect(phone.get_by_role("region", name="从规划到交付")).to_be_visible()
        phone.get_by_role("button", name="我有一篇文章").click()
        assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")
        phone.screenshot(path=str(args.output / "mobile.png"), full_page=True)
        phone.get_by_role("link", name="最近任务", exact=True).click()
        expect(phone.get_by_role("heading", name="还没有视觉任务")).to_be_visible()
        assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")
        phone.route("**/settings/onboarding", lambda route: route.fulfill(status=503, body="unavailable"))
        phone.goto(args.url, wait_until="networkidle")
        expect(phone.locator(".getting-started button")).to_have_count(0)
        expect(phone.locator("button[data-copy-state]")).to_be_visible()
        assert not errors, errors
        assert not task_writes, task_writes
        assert context.request.get(f"{args.url}/health").json()["runtime_identity"]["task_count"] == 0
        browser.close()
    print("PASS: one-screen home, stable copy, prompt modes, static guide without acknowledgement requests, independent tasks, mock pagination/deletion, mobile, no real task writes")


if __name__ == "__main__":
    main()
