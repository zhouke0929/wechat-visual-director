"""Save a real Workbench edit immediately on blur, without a one-frame scroll reset."""

import os
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

import test_logic_path_pilot as sample
from test_api_workflow import _png_bytes
from test_logic_path_pilot import ITEMS, _prepare_task
from visual_director.image_provider import ManualImageProvider
from visual_director.main import create_app
from visual_director.text_planner import MockTextPlannerProvider


@pytest.fixture
def blur_task(tmp_path, monkeypatch, request):
    root = Path(__file__).resolve().parents[3]
    dist = Path(os.environ.get("VISUAL_DIRECTOR_WEB_DIST") or root / "apps/web/dist")
    if not (dist / "index.html").is_file():
        if os.environ.get("WVD_REQUIRE_PILOT_BROWSER") == "1":
            pytest.fail("Build the workbench before running the browser acceptance")
        pytest.skip("Workbench build unavailable")
    monkeypatch.setenv("VISUAL_DIRECTOR_WEB_DIST", str(dist.resolve()))
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(tmp_path / "synthetic.env"))
    monkeypatch.setenv("VISUAL_DIRECTOR_THEME_PACK_DIR", str(tmp_path / "packs"))
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    for key in ("WECHAT_APP_ID", "WECHAT_APP_SECRET"):
        monkeypatch.delenv(key, raising=False)
    app = create_app(
        str(tmp_path / "inline-blur.db"),
        image_provider=ManualImageProvider(),
        text_planner_provider=MockTextPlannerProvider(),
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    try:
        with TestClient(app) as client:
            has_image = getattr(request, "param", None) == "source-image"
            if has_image:
                monkeypatch.setattr(
                    sample,
                    "MARKDOWN",
                    sample.MARKDOWN.replace(
                        "## 操作流程",
                        "![原稿测试图片](./photo.png)\n\n## 操作流程",
                    ),
                )
            url, _, block_id = _prepare_task(client, "pop_poster")
            if has_image:
                image_block = next(
                    b.id for b in sample.parse_markdown(sample.MARKDOWN).blocks if b.type == "image_reference"
                )
                imported = client.post(
                    f"{url}/preflight/findings/source_image_requires_import/replace-asset",
                    data={
                        "expected_task_version": client.get(url).json()["task"]["version"],
                        "block_id": image_block,
                    },
                    files={"image_file": ("photo.png", _png_bytes(800, 400), "image/png")},
                )
                assert imported.status_code == 200, imported.text
        thread.start()
        deadline = time.monotonic() + 12
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline
            time.sleep(0.05)
        yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}", url, block_id
    finally:
        if thread.is_alive():
            server.should_exit = True
            thread.join(timeout=10)
        app.state.repository.connection.close()


@pytest.fixture
def live_page(blur_task):
    if os.environ.get("WVD_REQUIRE_PILOT_BROWSER") == "1":
        from playwright import sync_api as pw
    else:
        pw = pytest.importorskip("playwright.sync_api")
    base, task_url, _ = blur_task
    with pw.sync_playwright() as runner:
        try:
            browser = runner.chromium.launch()
        except pw.Error:
            if os.environ.get("WVD_REQUIRE_PILOT_BROWSER") == "1":
                raise
            pytest.skip("Chromium unavailable")
        try:
            page = browser.new_page(viewport={"width": 1360, "height": 720})
            page.goto(f"{base}/tasks/{task_url.rsplit('/', 1)[-1]}", wait_until="networkidle")
            yield page, pw
        finally:
            browser.close()


@pytest.mark.parametrize("blank", ("frame_gutter", "workbench"))
def test_quick_click_blank_saves_without_stale_editing_or_scroll_jump(blur_task, live_page, blank):
    page, pw = live_page
    base, task_url, block_id = blur_task
    iframe = page.locator('iframe[title$="公众号移动端预览"]')
    field = iframe.content_frame.get_by_role("textbox", name="直接编辑编号列表第 3 项", exact=True)
    pw.expect(field).to_have_text(ITEMS[2])
    field.evaluate("e => e.scrollIntoView({block:'center'})")
    field.click()
    coordinates = iframe.evaluate(
        """frame => {
                const w = frame.contentWindow, d = frame.contentDocument, r = frame.getBoundingClientRect();
                const x = 3, y = Math.round(w.innerHeight / 2);
                if (d.elementFromPoint(x,y)?.closest('[contenteditable=true]')) throw Error('No blank gutter');
                return {x:r.left + x * r.width/frame.offsetWidth, y:r.top + y*r.height/frame.offsetHeight};
            }"""
    )
    # Use the outer page's clock: an iframe-only RAF loop dies on document replacement
    # and would miss exactly the top -> previous-position flash this test is about.
    page.evaluate(
        """() => {
                const f = () => document.querySelector('iframe.preview-frame');
                const p = window.blurProbe = {start:f().contentWindow.scrollY, samples:[], active:true};
                function tick() {
                    if (!p.active) return;
                    p.samples.push(f()?.contentWindow?.scrollY ?? -1);
                    requestAnimationFrame(tick);
                }
                tick();
            }"""
    )
    assert page.evaluate("window.blurProbe.start") > 150, "Probe must start below the first screen"
    text = "核准**第三项**内容。"
    rendered = "核准第三项内容。"
    saves = []
    page.on(
        "request",
        lambda req: (
            saves.append(req.post_data_json)
            if req.method == "PATCH" and req.url.endswith("/content-editor")
            else None
        ),
    )
    with page.expect_response(
        lambda r: r.request.method == "PATCH" and r.url.endswith("/content-editor")
    ) as saved:
        field.fill(text)
        if blank == "frame_gutter":
            page.mouse.click(coordinates["x"], coordinates["y"])
        else:
            page.locator(".preview-simulation-note").click()
    assert saved.value.ok, saved.value.text()
    pw.expect(field).to_have_text(rendered)
    pw.expect(field.locator("strong")).to_have_text("第三项")
    # Allow both the saved badge and the former 1.4s stale callback to expire.
    page.wait_for_timeout(1750)
    note = page.locator(".preview-editing-note")
    probe = page.evaluate(
        """() => {
                const p = window.blurProbe; p.active = false;
                return {start:p.start, min:Math.min(...p.samples), end:p.samples.at(-1),
                        samples:p.samples.length};
            }"""
    )
    state = note.get_attribute("data-state")
    assert state in {"saved", "idle"} and probe["min"] >= probe["start"] - 12, (blank, state, probe)
    assert abs(probe["end"] - probe["start"]) <= 12 and probe["samples"] > 3, probe
    assert len(saves) == 1, saves
    stored = page.request.get(base + task_url + "/content-editor").json()
    assert next(b["content"] for b in stored["blocks"] if b["block_id"] == block_id) == [
        ITEMS[0],
        ITEMS[1],
        text,
        ITEMS[3],
    ]
    page.reload(wait_until="networkidle")
    pw.expect(field).to_have_text(rendered)
    pw.expect(field.locator("strong")).to_have_text("第三项")


def test_mobile_preview_does_not_discard_a_failed_edit(blur_task, live_page):
    page, pw = live_page
    base, url, block_id = blur_task
    proof = page.get_by_role("tab", name="内容校对", exact=True)
    mobile = page.get_by_role("tab", name="手机预览", exact=True)
    frame = page.frame_locator("iframe.preview-frame")
    field = frame.get_by_role("textbox", name="直接编辑编号列表第 3 项", exact=True)
    stop = True

    def gate(route):
        if stop and route.request.method == "PATCH":
            route.fulfill(status=503, json={"error": {"message": "测试：此刻不能保存"}})
        else:
            route.continue_()

    page.route("**/content-editor", gate)
    with page.expect_response(lambda r: r.request.method == "PATCH" and r.status == 503):
        field.fill("尚未成功保存的内容。")
        page.locator(".preview-simulation-note").click()
    pw.expect(page.locator(".preview-editing-note")).to_have_attribute("data-state", "error")
    with page.expect_response(lambda r: r.request.method == "PATCH" and r.status == 503):
        mobile.click()
    pw.expect(proof).to_have_attribute("aria-selected", "true")
    pw.expect(field).to_have_text("尚未成功保存的内容。")

    stop = False
    new = "网络恢复后保留**最后一版**。"
    field.fill(new)
    mobile.click()
    pw.expect(mobile).to_have_attribute("aria-selected", "true")
    pw.expect(frame.get_by_text("最后一版", exact=True)).to_be_visible()
    stored = page.request.get(base + url + "/content-editor").json()
    assert next(b["content"] for b in stored["blocks"] if b["block_id"] == block_id)[2] == new


def test_slow_mobile_switch_yields_to_a_new_edit(blur_task, live_page):
    page, pw = live_page
    _, _, block_id = blur_task
    frame = page.frame_locator("iframe.preview-frame")
    group = frame.locator(f'[data-workbench-inline-block-id="{block_id}"]')
    second = group.and_(frame.get_by_role("textbox", name="直接编辑编号列表第 2 项", exact=True))
    third = group.and_(frame.get_by_role("textbox", name="直接编辑编号列表第 3 项", exact=True))
    pending = []

    def hold_first(route):
        if route.request.method == "PATCH" and not pending:
            pending.append(route)
        else:
            route.continue_()

    page.route("**/content-editor", hold_first)
    mobile = page.get_by_role("tab", name="手机预览", exact=True)
    with page.expect_request(lambda r: r.method == "PATCH" and r.url.endswith("/content-editor")):
        third.fill("第一处修改。")
        mobile.click()
    with page.expect_response(lambda r: r.request.method == "PATCH" and "继续编辑" in r.request.post_data):
        second.fill("继续编辑这一项。")
        pending[0].continue_()
    pw.expect(second).to_be_focused()
    pw.expect(mobile).to_have_attribute("aria-selected", "false")
    mobile.click()
    pw.expect(mobile).to_have_attribute("aria-selected", "true")


def test_slow_blur_save_does_not_evict_the_next_edit(blur_task, live_page):
    page, pw = live_page
    base, task_url, block_id = blur_task
    frame = page.frame_locator('iframe[title$="公众号移动端预览"]')
    second = frame.locator(
        f'[data-workbench-inline-block-id="{block_id}"][aria-label="直接编辑编号列表第 2 项"]'
    )
    third = frame.locator(
        f'[data-workbench-inline-block-id="{block_id}"][aria-label="直接编辑编号列表第 3 项"]'
    )
    pending = []

    def delay_first(route):
        if route.request.method == "PATCH" and not pending:
            pending.append(route)
        else:
            route.continue_()

    page.route("**/content-editor", delay_first)
    editor_url = base + task_url + "/content-editor"
    second_text, third_text = "第二项的新说明。", "第三项的新说明。"
    with page.expect_request(lambda r: r.url == editor_url and r.method == "PATCH"):
        third.fill(third_text)
        page.locator(".preview-simulation-note").click()
    second.fill(second_text)
    assert pending
    # The newer draft already has focus when the older blur completes. A late
    # acknowledgement may save it, but must not replace its active document.
    with page.expect_response(
        lambda r: r.url == editor_url
        and r.request.method == "PATCH"
        and second_text in r.request.post_data_json["content"]
    ) as second_save:
        pending[0].continue_()
    assert second_save.value.ok, second_save.value.text()
    pw.expect(second).to_be_focused()
    page.locator(".preview-simulation-note").click()
    page.reload(wait_until="networkidle")
    pw.expect(second).to_have_text(second_text)
    pw.expect(third).to_have_text(third_text)


def test_old_proof_response_cannot_replace_an_active_newer_edit(blur_task, live_page):
    page, pw = live_page
    base, task_url, block_id = blur_task
    frame = page.frame_locator('iframe[title$="公众号移动端预览"]')
    second = frame.locator(
        f'[data-workbench-inline-block-id="{block_id}"][aria-label="直接编辑编号列表第 2 项"]'
    )
    third = frame.locator(
        f'[data-workbench-inline-block-id="{block_id}"][aria-label="直接编辑编号列表第 3 项"]'
    )
    proof_routes = []

    def delay_first_proof(route):
        if not proof_routes and route.request.method == "GET":
            proof_routes.append(route)
        else:
            route.continue_()

    page.route("**/api/v1/render-artifacts/*/content*", delay_first_proof)
    second_text, third_text = "校对第二项后半段。", "核准第三项的原话。"
    editor_url = base + task_url + "/content-editor"
    with page.expect_request(lambda r: r.method == "GET" and "/api/v1/render-artifacts/" in r.url):
        with page.expect_response(lambda r: r.request.method == "PATCH" and r.url == editor_url) as first_save:
            third.fill(third_text)
            page.locator(".preview-simulation-note").click()
    assert first_save.value.ok
    with page.expect_response(
        lambda r: r.request.method == "PATCH"
        and r.url == editor_url
        and second_text in r.request.post_data_json["content"]
    ) as second_save:
        second.fill(second_text)
        second.evaluate("el => window.blurProbeSecond = el")
        assert len(proof_routes) == 1
        stale_url = proof_routes[0].request.url
        with page.expect_response(lambda r: r.url == stale_url and r.request.method == "GET"):
            proof_routes[0].continue_()
        page.evaluate(
            "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
        )
        pw.expect(second).to_have_text(second_text)
        pw.expect(second).to_be_focused()
        assert second.evaluate("el => window.blurProbeSecond === el")
    assert second_save.value.ok, second_save.value.text()
    pw.expect(second).to_be_focused()
    page.locator(".preview-simulation-note").click()
    page.reload(wait_until="networkidle")
    pw.expect(second).to_have_text(second_text)
    pw.expect(third).to_have_text(third_text)


@pytest.mark.parametrize("blur_task", ["source-image"], indirect=True)
def test_delayed_source_image_does_not_reveal_article_top(blur_task, live_page, record_property):
    page, pw = live_page
    frame = page.frame_locator('iframe[title$="公众号移动端预览"]')
    img = frame.locator('img[alt="原稿测试图片"]')
    pw.expect(img).to_have_count(1)
    url = img.evaluate("im => im.src")
    assert "/api/v1/" in url and img.evaluate("im => im.naturalWidth") == 800
    requests = []

    def delay_image(route):
        requests.append(route.request.url)
        time.sleep(0.4)  # delay only a real controlled asset; Chromium continues to paint
        route.continue_()

    page.route(url, delay_image)
    field = frame.get_by_role("textbox", name="直接编辑编号列表第 3 项", exact=True)
    field.evaluate("e => e.scrollIntoView({block:'center'})")
    field.click()
    page.evaluate(
        """() => {
        const f=document.querySelector('iframe.preview-frame');
        const item=()=>f.contentDocument?.querySelector('[data-editor-step-ref$=":item:2"]')?.getBoundingClientRect().top;
        const p=window.imageProbe={start:f.contentWindow.scrollY, top:item(), offsets:[], visible:[], loading:[], active:true};
        function sample() {
            if (!p.active) return;
            const overlay=f.parentElement.querySelector('.preview-frame-state');
            const hidden=overlay && overlay.getClientRects().length;
            (hidden ? p.loading : p.visible).push(f.contentWindow.scrollY);
            if (!hidden && item() != null) p.offsets.push(Math.abs(item()-p.top));
            requestAnimationFrame(sample);
        }
        sample();
    }"""
    )
    with page.expect_response(lambda r: r.request.method == "PATCH" and r.url.endswith("/content-editor")):
        field.fill("编辑含**原图**的测试文章。")
        page.locator(".preview-simulation-note").click()
    page.wait_for_load_state("networkidle")
    pw.expect(field).to_have_text("编辑含原图的测试文章。")
    pw.expect(field.locator("strong")).to_have_text("原图")
    pw.expect(page.locator(".preview-frame-state")).to_have_count(0)
    pw.expect(img).to_have_js_property("naturalWidth", 800)
    result = page.evaluate(
        """() => {
        const p=window.imageProbe; p.active=false;
        return {start:p.start, minVisible:Math.min(...p.visible), end:p.visible.at(-1),
                visible:p.visible.length, loading:p.loading.length, minLoading:Math.min(...p.loading),
                maxTextShift:Math.max(...p.offsets)};
    }"""
    )
    record_property("image_probe", {**result, "requests": len(requests)})
    assert result["start"] > 150 and result["visible"] and result["minVisible"] >= result["start"] - 12, result
    # A reused image need not re-request anything; only actual reading position
    # and visible content matter, not whether an implementation uses a mask.
    assert abs(result["end"] - result["start"]) <= 12 and result["maxTextShift"] <= 12, result
