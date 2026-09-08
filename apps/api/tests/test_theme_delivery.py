"""Generic delivery regressions. Local failure simulations are not WeChat tests."""
import copy
import io
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from PIL import Image

from visual_director.theme_drawings import render_drawing, drawing_png
from visual_director.theme_delivery import compiled_decoration_assets, theme_delivery_report
from visual_director.publication import check_frozen_html


def drawing():
    # Independent geometry, not a postal preset or official theme composition.
    return {"type": "drawing", "width": 90, "height": 50, "parts": [
        {"kind": "polyline", "points": [[3, 40], [24, 8], [48, 40], [86, 5]], "stroke": "ink", "stroke_width": 1.5},
        {"kind": "ellipse", "x": 52, "y": 10, "w": 15, "h": 15, "stroke": "ink", "stroke_width": 1, "fill": "accent"},
    ]}


def test_png_is_deterministic_transparent_and_deduplicated():
    palette = {"ink": "#132742", "accent": "#CC3311"}
    node = drawing()
    content = drawing_png(node, palette)
    assert content == drawing_png(copy.deepcopy(node), dict(reversed(list(palette.items()))))
    with Image.open(io.BytesIO(content)) as img:
        assert img.mode == 'RGBA' and img.size == (360, 200)
        assert img.getpixel((0, 0))[3] == 0
        assert img.getbbox() is not None
    markup = render_drawing(node, palette)
    assert len(compiled_decoration_assets(markup * 5)) == 1
    for prop in ('position:', 'left:', 'top:', 'transform:', 'padding-top:'):
        assert prop not in markup
    changed = dict(palette, accent='#11CC33')
    assert compiled_decoration_assets(render_drawing(node, changed))[0]['asset_token'] != compiled_decoration_assets(markup)[0]['asset_token']


def test_rejects_tampering_and_unmaterialized_freeze():
    markup = render_drawing(drawing(), {'ink': '#123456', 'accent': '#CC3311'})
    assert check_frozen_html(markup).status == 'blocking'
    soup = BeautifulSoup(markup, 'html.parser')
    for bad in ('https://example.com/a.png', 'data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,!!!!'):
        soup.img['src'] = bad
        with pytest.raises(ValueError):
            compiled_decoration_assets(str(soup))
    soup = BeautifulSoup(markup, 'html.parser')
    soup.img['data-theme-decoration'] = '0' * 64
    with pytest.raises(ValueError):
        compiled_decoration_assets(str(soup))


def test_old_positioned_drawing_is_not_a_delivery_pass():
    legacy = '<section data-theme-drawing="true"><span style="position:absolute;left:25%;top:10%">&#160;</span></section>'
    report = check_frozen_html(legacy).to_dict()
    assert report['checks']['no_legacy_positioned_drawings'] == 'blocking'
    assert report['wechat_saved_roundtrip'] == 'not_verified'
    assert report['verification_scope'] == 'local_static_checks'


def test_risk_report_is_per_capability_not_theme_name():
    node = {'type': 'stack', 'style': {'rotate': 2, 'margin': [0, 0, 0, -2]}, 'children': [drawing(), {'type': 'field', 'bind': 'body'}]}
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / 'skills/wechat-visual-director/assets/theme-pack-template.json').read_text(encoding='utf-8'))
    manifest['id'] = 'never_seen_before'
    manifest['design_system']['layouts'] = {'quote': node}
    report = theme_delivery_report(manifest)
    assert report['wechat_saved_roundtrip'] == 'not_verified'
    assert report['capabilities']['raster_decoration'] == ['quote']
    assert {f['code'] for f in report['findings']} == {'rotated_layout', 'overlap_spacing'}
    assert report['representative_roles'] == ['quote']
    assert all(f['path'].startswith('design_system.layouts.quote') for f in report['findings'])
    assert report['rehearsal']['status'] == 'pass'
    manifest['id'] = 'another_theme'
    assert theme_delivery_report(manifest) == report


def test_custom_decoration_freeze_copy_export_and_publisher_share_bytes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from test_api_workflow import _prepare_publication_ready_task, _freeze_publication
    from visual_director.main import create_app
    from visual_director.delivery import build_delivery_files, build_clipboard_payload
    from visual_director.wechat_publisher import WechatDraftPublisher

    root = Path(__file__).resolve().parents[3]
    monkeypatch.setenv('VISUAL_DIRECTOR_THEME_PACK_DIR', str(tmp_path / 'packs'))
    monkeypatch.setenv('VISUAL_DIRECTOR_ENV_FILE', str(tmp_path / 'private.env'))
    manifest = json.loads((root / 'skills/wechat-visual-director/assets/theme-pack-template.json').read_text(encoding='utf-8'))
    manifest.update(id='angular_delivery_test', name='折线实验', english='ANGULAR TEST')
    manifest['design_system']['layouts']['quote'] = {'type': 'stack', 'children': [drawing(), {'type': 'field', 'bind': 'body'}]}
    with TestClient(create_app(str(tmp_path / 'test.db'))) as client:
        response = client.post('/api/v1/theme-packs', headers={'X-Local-Intent': 'local-operator'}, files={'theme_file': ('theme.json', json.dumps(manifest).encode(), 'application/json')})
        assert response.status_code == 200, response.text
        assert response.json()['delivery_report']['wechat_saved_roundtrip'] == 'not_verified'
        task, plan = _prepare_publication_ready_task(client)
        changed = client.patch(f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/theme', json={'visual_system': manifest['id'], 'expected_plan_revision': plan['revision']})
        assert changed.status_code == 200, changed.text
        task = client.get(f'/api/v1/article-tasks/{task["id"]}').json()['task']
        frozen = _freeze_publication(client, task)['revision']
        repo = client.app.state.repository
        revision = repo.get_publication_revision(frozen['id'])
        assets = repo.list_publication_assets(frozen['id'])
        compiled = [a for a in assets if a['source_resource_type'] == 'compiled_theme_decoration']
        assert len(compiled) == 1
        read_asset = repo.get_publication_asset
        expected = drawing_png(drawing(), manifest['palette'])
        assert read_asset(compiled[0]['id'])[0].read_bytes() == expected
        assert 'data:image/' not in revision['frozen_html']
        assert 'position:absolute' not in revision['frozen_html']
        files = build_delivery_files(revision, assets, read_asset)
        assert expected in files.values()
        clipboard = build_clipboard_payload(revision, assets, lambda asset_id: 'http://127.0.0.1:8000/controlled/' + asset_id)
        assert compiled[0]['id'] in clipboard['html']
        assert 'asset://' not in clipboard['html'] and 'data:image/' not in clipboard['html']
        assert BeautifulSoup(clipboard['html'], 'html.parser').select('[data-theme-field="body"]')
        # Publisher exercised using a local fake transport below: never real WeChat.
        publisher = WechatDraftPublisher(tmp_path, env_file=tmp_path / 'unused.env')
        uploaded, articles = [], []
        monkeypatch.setattr(publisher, 'status', lambda: {'ready': True})
        monkeypatch.setattr(publisher, '_access_token', lambda **kwargs: 'local-test-token')

        def upload(token, **kwargs):
            uploaded.append(kwargs['content'])
            return {'url': f'https://test.invalid/image/{len(uploaded)}', 'media_id': 'local-cover'}, token

        monkeypatch.setattr(publisher, '_upload_image_with_token_refresh', upload)
        monkeypatch.setattr(publisher, '_create_draft', lambda token, article: articles.append(article) or {'media_id': 'local-test-draft'})
        result = publisher.publish(revision, assets, read_asset)
        assert result.media_id == 'local-test-draft'
        assert expected in uploaded
        assert 'asset://' not in articles[0]['content'] and 'data:image/' not in articles[0]['content']
        assert 'https://test.invalid/image/' in articles[0]['content']


def test_legacy_frozen_publication_is_stopped_before_any_network(tmp_path):
    from visual_director.wechat_publisher import WechatDraftPublisher
    def forbidden(*args, **kwargs):
        raise AssertionError('No network call is allowed')
    publisher = WechatDraftPublisher(tmp_path, requester=forbidden)
    result = publisher.publish({'frozen_html': '<section data-theme-drawing="true"><span style="position:absolute"></span></section>'}, [], forbidden)
    assert result.status == 'failed' and result.error['code'] == 'theme_delivery_refresh_required'


def test_explicit_render_refresh_preserves_working_copy_and_frozen_history(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from test_api_workflow import _prepare_publication_ready_task, _freeze_publication
    from visual_director.main import create_app
    import visual_director.main as main_module

    with TestClient(create_app(str(tmp_path / 'refresh.db'))) as client:
        task, plan = _prepare_publication_ready_task(client)
        repo = client.app.state.repository
        url = f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/theme'
        body = {'visual_system': plan['visual_system'], 'expected_plan_revision': plan['revision']}
        assert client.patch(url, json=body).status_code == 409
        assert client.patch(url, json={**body, 'refresh_current': True, 'visual_system': 'nonexistent_theme'}).status_code == 422
        frozen = _freeze_publication(client, task)
        old_html = repo.get_publication_revision(frozen['revision']['id'])['frozen_html']
        assert client.patch(url, json={**body, 'refresh_current': True}).status_code == 409
        resumed = client.post(f'/api/v1/publication-revisions/{frozen["revision"]["id"]}/continue-editing', json={'expected_task_version': frozen['task']['version']})
        assert resumed.status_code == 200
        before = copy.deepcopy(repo.get_plan(task['id'], plan['id']))
        editor_before = client.get(f'/api/v1/article-tasks/{task["id"]}/content-editor').json()['blocks']
        assets_before = client.get(f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots').json()
        # Simulate a future compiler upgrade without changing saved article data.
        monkeypatch.setattr(main_module, 'RENDERER_VERSION', 'preview_renderer.test-upgrade')
        public = client.get(f'/api/v1/article-tasks/{task["id"]}/plans').json()['plans'][0]
        assert public['render_refresh_available'] is True
        refreshed = client.patch(url, json={**body, 'refresh_current': True})
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()['planner_called'] is False
        assert refreshed.json()['images_regenerated'] is False
        assert refreshed.json()['plan']['render_refresh_available'] is False
        after = repo.get_plan(task['id'], plan['id'])
        assert after['revision'] == before['revision'] + 1
        assert after['renderer_version'] == 'preview_renderer.test-upgrade'
        for key in ('configuration', 'slots', 'visual_system', 'image_art_direction', 'structure_fingerprint'):
            assert after.get(key) == before.get(key), key
        assert client.get(f'/api/v1/article-tasks/{task["id"]}/content-editor').json()['blocks'] == editor_before
        assert client.get(f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/image-slots').json() == assets_before
        assert repo.get_publication_revision(frozen['revision']['id'])['frozen_html'] == old_html
        assert client.patch(url, json={**body, 'refresh_current': True}).status_code == 409
        assert repo.list_audit_events(task['id'])[-1]['event_type'] == 'visual_theme_render_refreshed'


def test_decoration_survives_local_offset_removal_at_multiple_widths():
    """Reproduce the observed class of failure, without impersonating WeChat."""
    from postal_theme_fixture import envelope, waves
    from visual_director.theme_layouts import PALETTE_KEYS
    playwright = pytest.importorskip('playwright.sync_api')
    palette = dict.fromkeys(PALETTE_KEYS, '#183642')
    palette['accent'] = '#BD3540'
    nodes = [drawing(), envelope(), waves()]
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in (320, 405, 600):
                page = browser.new_page(viewport={'width': width, 'height': 500}, device_scale_factor=2)
                try:
                    markup = ''.join(render_drawing(n, palette) for n in nodes)
                    page.set_content('<main style="width:100%">' + markup + '<p data-theme-field="body">正文仍是可编辑的文字。</p></main>', wait_until='load')
                    assert page.locator('img').evaluate_all('(images) => images.every(i => i.complete && i.naturalWidth > 0)')
                    before = page.screenshot()
                    page.evaluate('''() => document.querySelectorAll('*').forEach(e => ['position','top','left','right','bottom','transform','transform-origin'].forEach(p => e.style.removeProperty(p)))''')
                    assert page.screenshot() == before
                    assert page.locator('[data-theme-field]').inner_text() == '正文仍是可编辑的文字。'
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                finally:
                    page.close()
        finally:
            browser.close()
