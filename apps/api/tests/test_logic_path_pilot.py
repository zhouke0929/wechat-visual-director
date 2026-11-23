"""Characterize the opt-in logic path against legacy and a real local workbench."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile

import pytest
import uvicorn
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from test_api_workflow import _png_bytes
from visual_director.brief_compiler import apply_visual_system, visual_system_configuration, visual_system_variant
from visual_director.component_catalog import CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.image_provider import ManualImageProvider
from visual_director.main import create_app
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director.renderer import render_preview
from visual_director.text_planner import MockTextPlannerProvider
from visual_director.theme_extensions import extended_variant_theme
from visual_director.theme_packs import BUNDLED_THEME_IDS, configure_theme_packs, install_theme_pack_bytes
from visual_director.wechat_publisher import WechatDraftPublisher


ROOT = Path(__file__).resolve().parents[3]
SWITCH = "WVD_LOGIC_PATH_PILOT"
REF_ATTRIBUTE = "data-editor-step-ref"
PREFIX_ATTRIBUTE = "data-editor-step-prefix"
DETAIL_SELECTOR = 'span[style="display:block;padding-top:2px;font-weight:400;"]'
REPEATED = "确认编辑目标。"
EDITED = "只改第三项，不改同名的第二项。"
ITEMS = ["**先看原文**\n保留原图与 **原来的位置**。", REPEATED, REPEATED, "**注意：** 只做行内强调。"]
MARKDOWN = (
    "---\ntitle: 带重复内容的交付试点\narticle_type: tutorial_steps\n---\n"
    "# 带重复内容的交付试点\n\n"
    "先对照原稿，再逐条处理，最后检查读者能不能找到需要的信息。\n\n"
    "## 操作流程\n\n"
    "1. **先看原文**\\\n   保留原图与 **原来的位置**。\n"
    f"2. {REPEATED}\n3. {REPEATED}\n"
    "4. **注意：** 只做行内强调。\n\n"
    "## 附件\n\n1. 归档截图\n2. 归档字体\n"
)
FAMILIES = (
    ("light_reading", "primary", True),
    ("pop_poster", "kit", True),
    ("folded_fan_detail", "bundled", True),
    ("pilot_pack_on", "custom_opt_in", True),
    ("pilot_pack_inherited", "custom_inherit", False),
)
CASES = FAMILIES + (("light_reading", "manual_plain", True),)


def _install_test_themes() -> None:
    template = ROOT / "skills/wechat-visual-director/assets/theme-pack-template.json"
    authored = json.loads(template.read_text(encoding="utf-8"))
    authored["id"] = "pilot_pack_on"
    install_theme_pack_bytes(json.dumps(authored).encode(), "pilot_pack_on.json")
    inherited = {key: value for key, value in authored.items() if key != "design_system"}
    inherited.update(id="pilot_pack_inherited", base_theme="folded_fan_detail")
    install_theme_pack_bytes(json.dumps(inherited).encode(), "pilot_pack_inherited.json")


def _assert_render_source(theme: str, family: str, config: dict, markup: str) -> None:
    variant = visual_system_variant("logic_path", theme)
    if family in {"primary", "manual_plain"}:
        assert not config.get("generated_design_system") and extended_variant_theme(variant) is None
    elif family == "kit":
        assert extended_variant_theme(variant) == theme and 'data-extended-theme="pop_poster"' in markup
    elif family == "bundled":
        assert theme in BUNDLED_THEME_IDS and config["generated_design_system"]["layouts"]["logic_path"]
    else:
        assert theme not in VISUAL_SYSTEM_ORDER and config["theme_pack_version"] == "1.0.0"
        assert config["generated_design_system"]["layouts"]["logic_path"]
        if family == "custom_inherit":
            assert config["base_theme"] == "folded_fan_detail"


@pytest.mark.parametrize("theme,family,has_explicit_hierarchy", CASES)
def test_logic_path_pilot_preserves_entire_old_preview_except_editing_identity(
    tmp_path, monkeypatch, theme, family, has_explicit_hierarchy
):
    configure_theme_packs(tmp_path / "packs", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    try:
        if family.startswith("custom_"):
            _install_test_themes()
        article = parse_markdown(MARKDOWN)
        block = next(block for block in article.blocks if block.type == "ordered_list")
        assert block.content == ITEMS
        plan = apply_visual_system(generate_plans(article, "tutorial_steps", 5)[0], theme)
        # Fix the semantic choice and keep the second source list as an ordinary-list control.
        plan["slots"] = [slot for slot in plan["slots"] if slot["component_type"] == "logic_path"]
        assert len(plan["slots"]) == 1
        if family == "manual_plain":
            plan["slots"][0]["variant"] = "plain_steps"
        refs = [f"{block.id}:item:{index}" for index in range(len(ITEMS))]
        assert plan["slots"][0]["content_bindings"]["items"] == refs
        monkeypatch.delenv(SWITCH, raising=False)
        legacy = render_preview(article, plan, brand_profile={})
        monkeypatch.setenv(SWITCH, "1")
        pilot = render_preview(article, plan, brand_profile={})
        _assert_render_source(theme, family, visual_system_configuration(theme), legacy)
        assert REF_ATTRIBUTE not in legacy
        assert re.sub(rf' (?:{REF_ATTRIBUTE}|{PREFIX_ATTRIBUTE})="[^"]+"', "", pilot) == legacy
        soup = BeautifulSoup(pilot, "html.parser")
        assert [row[REF_ATTRIBUTE] for row in soup.select(f"[{REF_ATTRIBUTE}]")] == refs
        assert len(soup.select(DETAIL_SELECTOR)) == int(has_explicit_hierarchy)
        assert [row.get_text(strip=True) for row in soup.select(f"[{REF_ATTRIBUTE}]")][1:3] == (
            [f"02.{REPEATED}", f"03.{REPEATED}"] if family == "manual_plain" else [REPEATED, REPEATED]
        )
        assert len(soup.select(f"[{PREFIX_ATTRIBUTE}]")) == (len(ITEMS) if family == "manual_plain" else 0)
        assert "归档截图" in soup.get_text() and "归档字体" in soup.get_text()
    finally:
        configure_theme_packs(tmp_path / "clean", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)


def _prepare_task(client: TestClient, theme: str, *, use_rule_plan: bool = False, plain_variant: bool = False) -> tuple[str, dict, str]:
    created = client.post(
        "/api/v1/article-tasks",
        files={"markdown_file": ("logic-path.md", MARKDOWN.encode(), "text/markdown")},
    )
    assert created.status_code == 201, created.text
    task = created.json()["task"]
    url = f'/api/v1/article-tasks/{task["id"]}'
    cover = client.post(
        f"{url}/preflight/findings/missing_cover/replace-asset",
        data={"expected_task_version": task["version"]},
        files={"image_file": ("cover.png", _png_bytes(1080, 864), "image/png")},
    )
    assert cover.status_code == 200, cover.text
    path_block, ordinary_block = [block.id for block in parse_markdown(MARKDOWN).blocks if block.type == "ordered_list"]
    # Submit a fixed, valid host plan. A rule-generated structured-image plan
    # currently has a separate fold/newline fact-anchor limitation when edited.
    # This rendering acceptance must neither repair that planner path nor invoke a model.
    brief = {
        "schema_version": "editorial_brief.v0.1",
        "article": {
            "article_type": "tutorial_steps", "audience": ["编辑"],
            "reader_task": "验证步骤编辑与交付", "narrative": "同一篇文章比较新旧渲染。",
        },
        "sections": [
            {"source_block_ids": [path_block], "semantic_role": "logic_sequence", "visual_priority": "high",
             "component_intent": "logic_path", "reasoning": "是一组有明确先后关系的操作步骤。"},
            {"source_block_ids": [ordinary_block], "semantic_role": "plain_narrative", "visual_priority": "low",
             "component_intent": "plain", "reasoning": "附件列表保留普通结构。"},
        ],
        "image_intents": [],
        "art_direction": {"tone": ["清晰"], "palette_roles": ["deep_navy", "warm_ivory"],
                          "style_family": "editorial_paper_cut", "avoid_recent_patterns": []},
        "facts_locked": True,
    }
    generate = {"mode": "start", "expected_task_version": cover.json()["task"]["version"]}
    if not use_rule_plan:
        generate.update(planner="host_agent", editorial_brief=brief)
    generated = client.post(f"{url}/generate-plans", json=generate)
    assert generated.status_code == 202, generated.text
    if not use_rule_plan:
        metadata = generated.json()["planner_metadata"]
        assert metadata["fallback_used"] is False and metadata["planner_call_count"] == 0
    plans = client.get(f"{url}/plans").json()["plans"]
    plan = next(plan for plan in plans if any(slot["component_type"] == "logic_path" for slot in plan["slots"]))
    plan_url = f'{url}/plans/{plan["id"]}'
    selected = client.post(f"{plan_url}/select", json={
        "plan_id": plan["id"], "expected_task_version": client.get(url).json()["task"]["version"],
    })
    assert selected.status_code == 200, selected.text
    if plan["visual_system"] != theme:
        changed = client.patch(f"{plan_url}/theme", json={
            "visual_system": theme, "expected_plan_revision": plan["revision"],
        })
        assert changed.status_code == 200, changed.text
        assert changed.json()["planner_called"] is False and changed.json()["images_regenerated"] is False
        plan = changed.json()["plan"]
    if plain_variant:
        logic = next(slot for slot in plan["slots"] if slot["component_type"] == "logic_path")
        changed = client.patch(f'{plan_url}/slots/{logic["slot_id"]}', json={
            "variant": "plain_steps", "expected_plan_revision": plan["revision"],
        })
        assert changed.status_code == 200, changed.text
        plan = changed.json()["plan"]
    slots = client.get(f"{plan_url}/image-slots").json()["items"]
    if not use_rule_plan:
        assert not slots
    for entry in slots:
        skipped = client.post(f'{plan_url}/image-slots/{entry["image_slot_id"]}/skip', json={
            "expected_image_revision": entry["state"]["image_revision"],
        })
        assert skipped.status_code == 200, skipped.text
    editor = client.get(f"{url}/content-editor").json()
    block = next(block for block in editor["blocks"] if block["type"] == "ordered_list")
    assert block["content"] == ITEMS
    return url, plan, block["block_id"]


class _WechatTransportFixture:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.articles: list[dict] = []

    def __call__(self, request, *, timeout):
        url = urlsplit(request.full_url)
        assert url.hostname == "wechat-pilot.invalid"
        self.paths.append(url.path)
        if url.path == "/token":
            reply = {"access_token": "offline-token", "expires_in": 7200}
        elif url.path == "/material/add_material":
            assert b"Content-Disposition: form-data" in request.data
            reply = {"media_id": "offline-cover-id", "url": "https://wechat-pilot.invalid/frozen-cover.png"}
        elif url.path == "/draft/add":
            self.articles.extend(json.loads(request.data)["articles"])
            reply = {"media_id": "offline-draft-id"}
        else:
            pytest.fail(f"Unexpected remote request in pilot: {url.path}")
        return BytesIO(json.dumps(reply).encode())


def _assert_delivery(markup: str) -> None:
    assert REF_ATTRIBUTE not in markup and PREFIX_ATTRIBUTE not in markup and "data-editor-block-ids" not in markup
    text = BeautifulSoup(markup, "html.parser").get_text()
    assert text.count(REPEATED) == 1 and text.count(EDITED) == 1
    assert text.index(REPEATED) < text.index(EDITED)
    assert "先看原文" in text and "原来的位置" in text
    assert "归档截图" in text and "归档字体" in text


@pytest.mark.parametrize("theme,family,has_explicit_hierarchy", CASES)
def test_logic_path_pilot_live_workbench_and_frozen_delivery(
    tmp_path, monkeypatch, theme, family, has_explicit_hierarchy
):
    # The standard suite can run without a Web build; pilot acceptance requires this
    # test by name with WVD_REQUIRE_PILOT_BROWSER=1, turning unavailable Chrome into failure.
    required = os.environ.get("WVD_REQUIRE_PILOT_BROWSER") == "1"
    dist = Path(os.environ.get("VISUAL_DIRECTOR_WEB_DIST") or ROOT / "apps/web/dist")
    if required:
        from playwright import sync_api as playwright
        assert (dist / "index.html").is_file(), "Build the actual workbench before pilot acceptance"
    else:
        playwright = pytest.importorskip("playwright.sync_api")
        if not (dist / "index.html").is_file():
            pytest.skip("Build workbench before browser integration test")
    monkeypatch.setenv("VISUAL_DIRECTOR_ENV_FILE", str(tmp_path / "synthetic.env"))
    monkeypatch.setenv("VISUAL_DIRECTOR_THEME_PACK_DIR", str(tmp_path / "packs"))
    monkeypatch.setenv("VISUAL_DIRECTOR_WEB_DIST", str(dist.resolve()))
    monkeypatch.delenv("WECHAT_APP_ID", raising=False)
    monkeypatch.delenv("WECHAT_APP_SECRET", raising=False)
    remote = _WechatTransportFixture()
    publisher = WechatDraftPublisher(
        ROOT, token_endpoint="https://wechat-pilot.invalid/token", api_base="https://wechat-pilot.invalid",
        requester=remote,
    )
    monkeypatch.delenv(SWITCH, raising=False)
    app = create_app(str(tmp_path / "pilot.db"), image_provider=ManualImageProvider(),
                     text_planner_provider=MockTextPlannerProvider(), wechat_publisher=publisher)
    server = None
    thread = None
    try:
        with TestClient(app) as client:
            if family.startswith("custom_"):
                _install_test_themes()
            task_url, plan, block_id = _prepare_task(client, theme, plain_variant=family == "manual_plain")
            assert REF_ATTRIBUTE not in client.get(plan["preview_url"]).text
        monkeypatch.setenv(SWITCH, "1")
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 12
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline
            time.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        with playwright.sync_playwright() as runner:
            try:
                browser = runner.chromium.launch(headless=True)
            except playwright.Error as exc:
                if required:
                    raise
                pytest.skip(f"Chromium unavailable: {exc}")
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 960},
                                        permissions=["clipboard-read", "clipboard-write"])
                page.goto(f"{base}/tasks/{task_url.rsplit('/', 1)[-1]}", wait_until="networkidle")
                frame = page.frame_locator('iframe[title$="公众号移动端预览"]')
                # Turning on the pilot must not rewrite stored old markup or
                # disable the saved preview's legacy text-based edit discovery.
                old_third = frame.locator(f'[data-workbench-inline-block-id="{block_id}"][aria-label="直接编辑编号列表第 3 项"]')
                playwright.expect(old_third).to_have_text(REPEATED, timeout=8000)
                assert frame.locator(f"[{REF_ATTRIBUTE}]").count() == 0
                refreshed = page.request.patch(
                    f'{base}{task_url}/plans/{plan["id"]}/theme',
                    data={"visual_system": theme, "expected_plan_revision": plan["revision"], "refresh_current": True},
                )
                assert refreshed.status == 200, refreshed.text()
                assert refreshed.json()["planner_called"] is False and refreshed.json()["images_regenerated"] is False
                assert REF_ATTRIBUTE in page.request.get(base + refreshed.json()["preview_url"]).text()
                page.reload(wait_until="networkidle")
                first = frame.locator(f'[{REF_ATTRIBUTE}="{block_id}:item:0"]')
                second = frame.locator(f'[{REF_ATTRIBUTE}="{block_id}:item:1"]')
                third = frame.locator(f'[{REF_ATTRIBUTE}="{block_id}:item:2"]')
                if family == "manual_plain":
                    ordinal = third.locator(f"[{PREFIX_ATTRIBUTE}]")
                    assert ordinal.inner_text() == "03."
                    assert ordinal.get_attribute("contenteditable") is None
                    second = second.locator('[contenteditable="true"]')
                    third = third.locator('[contenteditable="true"]')
                playwright.expect(third).to_have_attribute("contenteditable", "true", timeout=8000)
                assert third.get_attribute("aria-label") == "直接编辑编号列表第 3 项"
                assert second.inner_text().strip() == third.inner_text().strip() == REPEATED
                assert first.locator(DETAIL_SELECTOR).count() == int(has_explicit_hierarchy)
                editor_url = f"{task_url}/content-editor"

                with page.expect_response(lambda item: item.url.endswith(editor_url) and item.request.method == "PATCH") as patch:
                    third.fill(EDITED)
                    page.get_by_role("tab", name="内容校对", exact=True).click()
                assert patch.value.status == 200, patch.value.text()
                editor = page.request.get(base + editor_url).json()
                assert next(block["content"] for block in editor["blocks"] if block["block_id"] == block_id) == [
                    ITEMS[0], REPEATED, EDITED, ITEMS[3],
                ]

                # A newly written artifact stays readable after rollback; reopening
                # and both delivery operations must not invoke another renderer.
                monkeypatch.delenv(SWITCH, raising=False)
                page.reload(wait_until="networkidle")
                playwright.expect(third).to_have_text(EDITED)
                assert second.inner_text().strip() == REPEATED
                if family == "manual_plain":
                    assert ordinal.inner_text() == "03."
                with page.expect_response(lambda item: "/clipboard?" in item.url) as copied:
                    page.get_by_role("button", name="复制图文", exact=True).click()
                assert copied.value.status == 200, copied.value.text()
                _assert_delivery(copied.value.json()["html"])
                assert not page.request.get(f"{base}{task_url}/publication-revisions").json()["items"]
                with page.expect_response(lambda item: item.url.endswith("/publication-revisions") and item.request.method == "POST") as frozen:
                    page.get_by_role("button", name="保存最终版本", exact=True).click()
                assert frozen.value.status == 201, frozen.value.text()
                revision = frozen.value.json()["revision"]
                revision_url = f'{base}/api/v1/publication-revisions/{revision["id"]}'
                _assert_delivery(page.request.get(f"{revision_url}/content").text())
                frozen_copy = page.request.get(f"{revision_url}/clipboard")
                assert frozen_copy.status == 200, frozen_copy.text()
                _assert_delivery(frozen_copy.json()["html"])
                bundle = page.request.get(f"{revision_url}/bundle")
                assert bundle.status == 200, bundle.text()
                with ZipFile(BytesIO(bundle.body())) as archive:
                    html_entries = [name for name in archive.namelist() if name.endswith(".html")]
                    assert html_entries
                    for name in html_entries:
                        _assert_delivery(archive.read(name).decode())
                # Test unconfigured copy/freeze above; enable only synthetic
                # credentials to exercise the real adapter against fake HTTP.
                monkeypatch.setenv("WECHAT_APP_ID", "offline-app-id")
                monkeypatch.setenv("WECHAT_APP_SECRET", "offline-placeholder")
                draft_data = {"expected_task_version": frozen.value.json()["task"]["version"],
                              "draft_slot": revision["suggested_draft_slot"]}
                operation_id = None
                for attempt in range(2):
                    draft = page.request.post(f"{revision_url}/wechat-draft", data=draft_data, headers={
                        "Idempotency-Key": "offline-pilot", "X-Operator-Id": "operator",
                    })
                    assert draft.status == 200, draft.text()
                    operation = draft.json()["operation"]
                    assert operation["status"] == "succeeded", draft.text()
                    if attempt == 0:
                        operation_id = operation["id"]
                    else:
                        assert draft.json()["idempotency_replayed"] is True and operation["id"] == operation_id
                assert remote.paths.count("/draft/add") == len(remote.articles) == 1
                _assert_delivery(remote.articles[0]["content"])
            finally:
                browser.close()
    finally:
        if server is not None and thread is not None:
            server.should_exit = True
            thread.join(timeout=10)
        app.state.repository.connection.close()
        configure_theme_packs(tmp_path / "clean", reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
