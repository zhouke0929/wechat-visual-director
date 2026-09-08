"""Both delivery paths share image references; no real WeChat requests in tests."""
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from test_delivery import _assets, _revision, _Response
from test_api_workflow import _prepare_publication_ready_task, _freeze_publication
from visual_director.delivery import build_clipboard_payload
from visual_director.main import create_app
from visual_director.repository import Repository
from visual_director.wechat_publisher import WechatDraftPublisher


def make_publisher(tmp_path, calls, *, cache=None, account='test-account', fail=False):
    def request(req, **kwargs):
        if '/media/uploadimg?' in req.full_url:
            calls.append('body-upload')
            if fail:
                return _Response({'errcode':40164, 'errmsg':'invalid ip'})
            return _Response({'url':f'https://mmbiz.qpic.cn/clipboard-{len(calls)}'})
        if '/material/add_material?' in req.full_url:
            calls.append('material-upload')
            return _Response({'url':f'https://mmbiz.qpic.cn/material-{len(calls)}', 'media_id':f'material-{len(calls)}'})
        if '/draft/add?' in req.full_url:
            calls.append('draft-create')
            return _Response({'media_id':'test-draft'})
        raise AssertionError('Unexpected network operation')
    p = WechatDraftPublisher(tmp_path, requester=request,
        image_cache_get=cache.get_wechat_image_upload if cache else None,
        image_cache_set=cache.save_wechat_image_upload if cache else None)
    p._credentials = lambda: (account, 'test-only-secret', 'test')
    p._access_token = lambda **kwargs: 'test-only-token'
    return p


@pytest.mark.parametrize('role', ['theme_decoration', 'planned_image', 'source_image'])
def test_copy_uploads_all_image_roles_without_cover_or_draft(tmp_path, role):
    assets, paths = _assets(tmp_path)
    assets[1]['asset_role'] = role
    # The same picture occurs twice and has two asset records; upload once by bytes.
    duplicate = {**assets[1], 'id':'duplicate', 'asset_token':'duplicate-token'}
    assets.append(duplicate)
    paths['duplicate'] = paths['body-id']
    revision = _revision()
    revision['frozen_html'] = revision['frozen_html'].replace('</main>', '<img src="asset://duplicate-token" /></main>')
    original = copy.deepcopy(revision)
    calls = []
    publisher = make_publisher(tmp_path, calls)
    prepared = publisher.prepare_clipboard_images(revision, assets, lambda id: paths[id])
    assert calls == ['body-upload']
    assert prepared['asset_urls']['body-id'] == prepared['asset_urls']['duplicate']
    payload = build_clipboard_payload(revision, assets, lambda id: 'http://127.0.0.1/'+id, hosted_asset_urls=prepared['asset_urls'])
    assert payload['image_transport'] == 'wechat_hosted'
    assert payload['image_count'] == 2
    assert '127.0.0.1' not in payload['html'] and 'asset://' not in payload['html']
    assert revision == original


def test_api_uploads_are_reused_by_copy_across_restart_but_not_accounts(tmp_path):
    assets, paths = _assets(tmp_path)
    repo = Repository(str(tmp_path/'cache.db'))
    calls = []
    publisher = make_publisher(tmp_path, calls, cache=repo)
    assert publisher.publish(_revision(), assets, lambda id: paths[id]).status == 'succeeded'
    assert calls == ['material-upload', 'material-upload', 'draft-create']
    other = make_publisher(tmp_path, calls, cache=repo)
    assert other.prepare_clipboard_images(_revision(), assets, lambda id: paths[id])['asset_urls']
    assert len(calls) == 3
    changed = make_publisher(tmp_path, calls, cache=repo, account='another-account')
    changed.prepare_clipboard_images(_revision(), assets, lambda id: paths[id])
    assert calls[-1] == 'body-upload' and len(calls) == 4
    serialized = str(repo.connection.execute('SELECT * FROM wechat_image_upload_cache').fetchall())
    assert 'test-only-secret' not in serialized and 'test-only-token' not in serialized


def test_copy_preparation_failure_keeps_local_fallback_and_no_draft(tmp_path):
    assets, paths = _assets(tmp_path)
    calls = []
    publisher = make_publisher(tmp_path, calls, fail=True)
    prepared = publisher.prepare_clipboard_images(_revision(), assets, lambda id: paths[id])
    assert prepared['error']['code'] == 'wechat_ip_not_whitelisted'
    assert 'asset_urls' not in prepared and calls == ['body-upload']
    local = build_clipboard_payload(_revision(), assets, lambda id: 'http://127.0.0.1/'+id)
    assert local['image_transport'] == 'local_urls'
    assert any('本机图片' in warning for warning in local['warnings'])
    with pytest.raises(ValueError):
        build_clipboard_payload(_revision(), assets, lambda id: 'http://127.0.0.1/'+id, hosted_asset_urls={})


def test_explicit_copy_endpoint_supports_official_decorations_and_never_mutates_drafts(tmp_path):
    calls = []
    publisher = make_publisher(tmp_path, calls)
    with TestClient(create_app(str(tmp_path/'workflow.db'), wechat_publisher=publisher)) as client:
        task, plan = _prepare_publication_ready_task(client)
        switched = client.patch(f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/theme', json={'visual_system':'oriental_archive', 'expected_plan_revision':plan['revision']})
        assert switched.status_code == 200
        task = client.get(f'/api/v1/article-tasks/{task["id"]}').json()['task']
        frozen = _freeze_publication(client, task)
        revision_id = frozen['revision']['id']
        repo = client.app.state.repository
        before = copy.deepcopy(repo.get_publication_revision(revision_id))
        task_before = client.get(f'/api/v1/article-tasks/{task["id"]}').json()
        url = f'/api/v1/publication-revisions/{revision_id}/clipboard'
        local = client.get(url).json()
        assert local['image_transport'] == 'embedded_data' and local['image_count'] > 0
        assert 'data:image/' in local['html'] and 'asset://' not in local['html']
        assert not calls
        assert client.post(url+'/wechat').status_code == 403
        assert client.post(url+'/wechat', headers={'X-Local-Intent':'local-operator','Origin':'https://untrusted.invalid'}).status_code == 403
        assert not calls
        ready = client.post(url+'/wechat', headers={'X-Local-Intent':'local-operator'})
        assert ready.status_code == 200, ready.text
        payload = ready.json()
        assert payload['draft_created'] is False and payload['image_transport'] == 'wechat_hosted'
        assert '127.0.0.1' not in payload['html'] and 'asset://' not in payload['html']
        assert calls and set(calls) == {'body-upload'}
        assert repo.get_publication_revision(revision_id) == before
        assert client.get(f'/api/v1/article-tasks/{task["id"]}').json() == task_before
        assert not repo.list_draft_operations(task['id'])
