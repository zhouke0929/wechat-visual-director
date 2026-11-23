"""Verify the opt-in ordinary Markdown list renderer without changing theme output."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
import uvicorn
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from midnight_theme_fixture import midnight_manifest
from test_api_workflow import _png_bytes
from test_logic_path_pilot import _WechatTransportFixture
from test_theme_packs import _manifest, _manifest_with_design, _manifest_with_recipe
from visual_director.brief_compiler import apply_visual_system
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.image_provider import ManualImageProvider
from visual_director.main import create_app
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director.renderer import render_preview
from visual_director.text_planner import MockTextPlannerProvider
from visual_director.theme_packs import configure_theme_packs, install_theme_pack_bytes
from visual_director.wechat_publisher import WechatDraftPublisher


ROOT = Path(__file__).resolve().parents[3]
SWITCH = "WVD_RENDERER_PILOT"
STEP_SWITCH = "WVD_LOGIC_PATH_PILOT"
REF = "data-editor-list-ref"
PREFIX = "data-editor-list-prefix"
ORDERED_DUPLICATE = "这条编号文字原本重复。"
BULLET_DUPLICATE = "这条项目文字原本重复。"
ORDERED_EDIT = "仅修改第三条有序列表。"
BULLET_EDIT = "仅修改第三条无序列表。"
MARKDOWN = f"""---
title: 编辑普通列表时应保持其他内容不变
article_type: tutorial_steps
---
# 编辑普通列表时应保持其他内容不变

阅读这篇短文时，先辨认步骤和素材条目的区别。

## 操作流程

1. **先核对原稿**\\
   然后记录内容所在的原始位置。
2. 检查交付素材。
3. 保存最后的结果。

## 附件目录

1. **静态说明**\\
   查看 [说明](https://example.invalid/reader) 并保留 A < B & C。
2. {ORDERED_DUPLICATE}
3. {ORDERED_DUPLICATE}
4. 普通编号内容结束。

## 随手记

- **保留加粗**，以及 [引用文字](https://example.invalid/source)。
- {BULLET_DUPLICATE}
- {BULLET_DUPLICATE}
- 未参与规划的项目。

## 行动清单

- 观察第一项。
- 查看第二项。

## 对读笔记

### 观察案例

- 首个样本标记。
- 第二个样本标记。
"""

CUSTOM_INHERIT = "test_plain_lists_inherit"
CUSTOM_AUTHORED = "test_plain_lists_authored"
CUSTOM_BULLETS = "test_plain_lists_bullets"
CUSTOM_RECIPE = "test_plain_lists_recipe"
CUSTOM_THEMES = (CUSTOM_INHERIT, CUSTOM_AUTHORED, CUSTOM_BULLETS, CUSTOM_RECIPE)


def _install_custom_theme(theme: str) -> None:
    if theme == CUSTOM_INHERIT:
        # Inherit a built-in theme whose ordered list has a separate official override.
        pack = {**_manifest(), "base_theme": "color_paper_corners"}
    elif theme == CUSTOM_RECIPE:
        pack = _manifest_with_recipe()
    else:
        pack = midnight_manifest(_manifest_with_design())
        if theme == CUSTOM_BULLETS:
            pack["design_system"]["layouts"]["list"] = {
                "type": "repeat", "bind": "items", "children": [
                    {"type": "text", "text": "•"},
                    {"type": "field", "bind": "item"},
                ],
            }
    pack["id"] = theme
    install_theme_pack_bytes(json.dumps(pack, ensure_ascii=False).encode(), "ordinary-list-pilot.json")


def _configure_registry(path: Path) -> None:
    configure_theme_packs(path, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)


def _list_blocks(article):
    return [block for block in article.blocks if block.type in {"ordered_list", "unordered_list"}]


def _ordinary_marked_fields(article):
    return [f"{block.id}:item:{index}" for block in _list_blocks(article)[1:]
            for index in range(len(block.content))]


@pytest.mark.parametrize("theme", (*VISUAL_SYSTEM_ORDER, *CUSTOM_THEMES))
def test_plain_list_preview_matches_legacy_except_for_edit_anchors(tmp_path, monkeypatch, theme):
    _configure_registry(tmp_path / "packs")
    try:
        if theme in CUSTOM_THEMES:
            _install_custom_theme(theme)
        article = parse_markdown(MARKDOWN)
        step, ordered, bullets, _, _ = _list_blocks(article)
        assert ordered.content[1:3] == [ORDERED_DUPLICATE] * 2
        assert bullets.content[1:3] == [BULLET_DUPLICATE] * 2
        plan = apply_visual_system(generate_plans(article, "tutorial_steps", 5)[0], theme)
        plan["slots"] = [slot for slot in plan["slots"] if slot["component_type"] == "logic_path"
                         and slot["anchor_block_id"] == step.id]
        assert len(plan["slots"]) == 1
        # The semantic steps are already accepted; turn them on on both sides of this comparison.
        monkeypatch.setenv(STEP_SWITCH, "1")
        monkeypatch.delenv(SWITCH, raising=False)
        legacy = render_preview(article, plan, brand_profile={})
        assert REF not in legacy and "data-editor-step-ref" in legacy
        monkeypatch.delenv(STEP_SWITCH)
        candidate = render_preview(article, plan, brand_profile={})
        assert re.sub(rf' (?:{REF}|{PREFIX})="[^"]+"', "", candidate) == legacy
        # Every authored and fallback list must retain the same text host, not
        # just the same text. Enabling the rule reader is not a font migration.
        monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")
        assert render_preview(article, plan, brand_profile={}) == candidate

        dom = BeautifulSoup(candidate, "html.parser")
        assert [node[REF] for node in dom.select(f"[{REF}]")] == _ordinary_marked_fields(article)
        assert [node["data-editor-step-ref"] for node in dom.select("[data-editor-step-ref]")] == [
            f"{step.id}:item:{index}" for index in range(len(step.content))
        ]
        for block in (ordered, bullets):
            first = dom.select_one(f'[{REF}="{block.id}:item:0"]')
            assert first.find("strong")
            assert bool(first.find("br")) == (block is ordered)
            assert "example.invalid" in str(first)
        if theme == CUSTOM_BULLETS:
            fallback = dom.select_one('[data-theme-list-fallback="numbering"]')
            assert fallback is not None
            assert [index.get_text(strip=True) for index in fallback.select("[data-theme-list-index]")] == ["01", "02", "03", "04"]
            assert len(fallback.select(f"[{REF}]")) == len(ordered.content)
    finally:
        _configure_registry(tmp_path / "clean")


def _prepare_task(client: TestClient, theme: str) -> tuple[str, dict, list]:
    response = client.post("/api/v1/article-tasks", files={"markdown_file": (
        "ordinary-lists.md", MARKDOWN.encode(), "text/markdown",
    )})
    assert response.status_code == 201, response.text
    task = response.json()["task"]
    task_url = f'/api/v1/article-tasks/{task["id"]}'
    cover = client.post(f"{task_url}/preflight/findings/missing_cover/replace-asset", data={
        "expected_task_version": task["version"],
    }, files={"image_file": ("cover.png", _png_bytes(1080, 864), "image/png")})
    assert cover.status_code == 200, cover.text
    step, *ordinary = _list_blocks(parse_markdown(MARKDOWN))
    brief = {
        "schema_version": "editorial_brief.v0.1",
        "article": {"article_type": "tutorial_steps", "audience": ["编辑"],
                    "reader_task": "区分语义步骤和普通列表", "narrative": "兼容性试点。"},
        "sections": [{"source_block_ids": [step.id], "semantic_role": "logic_sequence", "visual_priority": "high",
                      "component_intent": "logic_path", "reasoning": "这组内容有明确的操作顺序。"}] + [
            {"source_block_ids": [block.id], "semantic_role": "plain_narrative", "visual_priority": "low",
             "component_intent": "plain", "reasoning": "普通列表保留，不变成步骤组件。"}
            for block in ordinary
        ],
        "image_intents": [],
        "art_direction": {"tone": ["清晰"], "palette_roles": ["deep_navy", "warm_ivory"],
                          "style_family": "editorial_paper_cut", "avoid_recent_patterns": []},
        "facts_locked": True,
    }
    generated = client.post(f"{task_url}/generate-plans", json={
        "mode": "start", "expected_task_version": cover.json()["task"]["version"],
        "planner": "host_agent", "editorial_brief": brief,
    })
    assert generated.status_code == 202, generated.text
    assert generated.json()["planner_metadata"]["planner_call_count"] == 0
    assert generated.json()["planner_metadata"]["fallback_used"] is False
    plans = client.get(f"{task_url}/plans").json()["plans"]
    plan = next(plan for plan in plans if any(slot["component_type"] == "logic_path" for slot in plan["slots"]))
    plan_url = f'{task_url}/plans/{plan["id"]}'
    selected = client.post(f"{plan_url}/select", json={"plan_id": plan["id"],
                           "expected_task_version": client.get(task_url).json()["task"]["version"]})
    assert selected.status_code == 200, selected.text
    if plan["visual_system"] != theme:
        changed = client.patch(f"{plan_url}/theme", json={"visual_system": theme, "expected_plan_revision": plan["revision"]})
        assert changed.status_code == 200, changed.text
        assert changed.json()["planner_called"] is False and changed.json()["images_regenerated"] is False
        plan = changed.json()["plan"]
    assert [slot["anchor_block_id"] for slot in plan["slots"] if slot["component_type"] == "logic_path"] == [step.id]
    assert not client.get(f"{plan_url}/image-slots").json()["items"]
    return task_url, plan, ordinary


def _check_delivery(markup: str) -> None:
    assert all(attribute not in markup for attribute in (REF, PREFIX, "data-editor-step-ref", "data-editor-block-ids"))
    dom = BeautifulSoup(markup, "html.parser")
    article = dom.get_text()
    for old, new in ((ORDERED_DUPLICATE, ORDERED_EDIT), (BULLET_DUPLICATE, BULLET_EDIT)):
        assert article.count(old) == article.count(new) == 1
        assert article.index(old) < article.index(new)
    assert "静态说明" in article and "保留加粗" in article and "example.invalid" in markup


@pytest.mark.parametrize("theme", ("light_reading", "pop_poster", "color_paper_corners", CUSTOM_BULLETS))
def test_ordinary_lists_workbench_edits_duplicate_by_index_and_delivers(tmp_path, monkeypatch, theme):
    required = os.environ.get("WVD_REQUIRE_LIST_PILOT_BROWSER") == "1"
    workbench = Path(os.environ.get("VISUAL_DIRECTOR_WEB_DIST") or ROOT / "apps/web/dist")
    if required:
        from playwright import sync_api as playwright

        assert (workbench / "index.html").is_file(), "Build the isolated workbench first"
    else:
        playwright = pytest.importorskip("playwright.sync_api")
        if not (workbench / "index.html").is_file():
            pytest.skip("Build the workbench to run the ordinary list browser test")
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(tmp_path / "isolated.env"))
    monkeypatch.setenv("VISUAL_DIRECTOR_THEME_PACK_DIR", str(tmp_path / "packs"))
    monkeypatch.setenv("VISUAL_DIRECTOR_WEB_DIST", str(workbench.resolve()))
    for key in (SWITCH, "WECHAT_APP_ID", "WECHAT_APP_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(STEP_SWITCH, "1")
    remote = _WechatTransportFixture()
    publisher = WechatDraftPublisher(ROOT, token_endpoint="https://wechat-pilot.invalid/token",
                                     api_base="https://wechat-pilot.invalid", requester=remote)
    app = create_app(str(tmp_path / "pilot.db"), image_provider=ManualImageProvider(),
                     text_planner_provider=MockTextPlannerProvider(), wechat_publisher=publisher)
    server = worker = None
    try:
        with TestClient(app) as client:
            if theme in CUSTOM_THEMES:
                _install_custom_theme(theme)
            task_url, plan, (ordered, bullets, actions, _) = _prepare_task(client, theme)
            assert REF not in client.get(plan["preview_url"]).text
        monkeypatch.delenv(STEP_SWITCH)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
        worker = threading.Thread(target=server.run, daemon=True)
        worker.start()
        deadline = time.monotonic() + 12
        while not server.started:
            assert worker.is_alive() and time.monotonic() < deadline
            time.sleep(.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        with playwright.sync_playwright() as browser_runtime:
            try:
                browser = browser_runtime.chromium.launch(headless=True)
            except playwright.Error as error:
                if required:
                    raise
                pytest.skip(f"Chromium unavailable: {error}")
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 960},
                                        permissions=["clipboard-read", "clipboard-write"])
                page.goto(f"{base}/tasks/{task_url.rsplit('/', 1)[-1]}", wait_until="networkidle")
                article_frame = page.frame_locator('iframe[title$="公众号移动端预览"]')
                assert article_frame.locator(f"[{REF}]").count() == 0
                # An ordinary plain list in the archived preview still uses the legacy
                # text-discovery fallback. Rich bullet items with literal Markdown links
                # are checked after the pilot refresh; not every legacy layout mapped them.
                old_rows = article_frame.locator(f'[data-workbench-inline-block-id="{actions.id}"]')
                playwright.expect(old_rows.first).to_have_text(actions.content[0], timeout=8000)
                refreshed = page.request.patch(f'{base}{task_url}/plans/{plan["id"]}/theme', data={
                    "visual_system": theme, "expected_plan_revision": plan["revision"], "refresh_current": True,
                })
                assert refreshed.status == 200, refreshed.text()
                assert refreshed.json()["planner_called"] is False and refreshed.json()["images_regenerated"] is False
                assert REF in page.request.get(base + refreshed.json()["preview_url"]).text()
                page.reload(wait_until="networkidle")
                expected_by_block = {}
                for block, before, after in ((ordered, ORDERED_DUPLICATE, ORDERED_EDIT), (bullets, BULLET_DUPLICATE, BULLET_EDIT)):
                    second = article_frame.locator(f'[{REF}="{block.id}:item:1"]')
                    third = article_frame.locator(f'[{REF}="{block.id}:item:2"]')
                    playwright.expect(third).to_have_attribute("contenteditable", "true", timeout=8000)
                    assert second.inner_text().strip() == third.inner_text().strip() == before
                    old_values = list(block.content)
                    old_values[2] = after
                    expected_by_block[block.id] = old_values
                    with page.expect_response(lambda item: item.url.endswith("/content-editor") and item.request.method == "PATCH") as patch:
                        third.fill(after)
                        page.get_by_role("tab", name="内容校对", exact=True).click()
                    assert patch.value.status == 200, patch.value.text()
                    applied = page.request.get(f"{base}{task_url}/content-editor").json()
                    actual_by_block = {saved["block_id"]: saved["content"] for saved in applied["blocks"]
                                       if saved["block_id"] in expected_by_block}
                    assert actual_by_block == expected_by_block
                    page.reload(wait_until="networkidle")

                monkeypatch.setenv(SWITCH, "0")
                page.reload(wait_until="networkidle")
                for block, value in ((ordered, ORDERED_EDIT), (bullets, BULLET_EDIT)):
                    playwright.expect(article_frame.locator(f'[{REF}="{block.id}:item:2"]')).to_have_text(value)
                with page.expect_response(lambda item: "/clipboard?" in item.url) as copied:
                    page.get_by_role("button", name="复制图文", exact=True).click()
                assert copied.value.status == 200, copied.value.text()
                _check_delivery(copied.value.json()["html"])
                assert not page.request.get(f"{base}{task_url}/publication-revisions").json()["items"]
                with page.expect_response(lambda item: item.url.endswith("/publication-revisions") and item.request.method == "POST") as frozen:
                    page.get_by_role("button", name="保存最终版本", exact=True).click()
                assert frozen.value.status == 201, frozen.value.text()
                revision = frozen.value.json()["revision"]
                revision_url = f'{base}/api/v1/publication-revisions/{revision["id"]}'
                _check_delivery(page.request.get(f"{revision_url}/content").text())
                _check_delivery(page.request.get(f"{revision_url}/clipboard").json()["html"])
                bundle = page.request.get(f"{revision_url}/bundle")
                assert bundle.status == 200, bundle.text()
                with ZipFile(BytesIO(bundle.body())) as archive:
                    html_entries = [name for name in archive.namelist() if name.endswith(".html")]
                    assert html_entries
                    for name in html_entries:
                        _check_delivery(archive.read(name).decode())

                monkeypatch.setenv("WECHAT_APP_ID", "offline-app-id")
                monkeypatch.setenv("WECHAT_APP_SECRET", "offline-placeholder")
                draft = page.request.post(f"{revision_url}/wechat-draft", data={
                    "expected_task_version": frozen.value.json()["task"]["version"],
                    "draft_slot": revision["suggested_draft_slot"],
                }, headers={"Idempotency-Key": "ordinary-lists", "X-Operator-Id": "operator"})
                assert draft.status == 200 and draft.json()["operation"]["status"] == "succeeded", draft.text()
                assert remote.paths.count("/draft/add") == len(remote.articles) == 1
                _check_delivery(remote.articles[0]["content"])
            finally:
                browser.close()
    finally:
        if server is not None and worker is not None:
            server.should_exit = True
            worker.join(timeout=10)
        app.state.repository.connection.close()
        _configure_registry(tmp_path / "clean")
