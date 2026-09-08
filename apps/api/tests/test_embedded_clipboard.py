"""Embedded copy is local, complete, bounded and byte-preserving."""
import base64
import copy
import hashlib
import io
import re
import random

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from test_delivery import _assets, _revision
from test_api_workflow import _prepare_publication_ready_task, _freeze_publication
from visual_director import delivery
from visual_director.delivery import build_clipboard_payload, ClipboardPreparationError
from visual_director.main import create_app


def fixture(tmp_path, format="PNG"):
    assets, paths = _assets(tmp_path)
    image = Image.new("RGBA" if format == "PNG" else "RGB", (120, 60), (90, 140, 100, 0) if format == "PNG" else (90, 140, 100))
    image.save(paths['body-id'][0], format=format)
    data = paths['body-id'][0].read_bytes()
    assets[1]['output_sha256'] = hashlib.sha256(data).hexdigest()
    return assets, paths, data


@pytest.mark.parametrize('format,mime', [('PNG','image/png'), ('JPEG','image/jpeg'), ('WEBP','image/webp'), ('GIF','image/gif')])
@pytest.mark.parametrize('role', ['theme_decoration', 'planned_image', 'source_image'])
def test_embeds_referenced_images_only_and_preserves_original_bytes(tmp_path, format, mime, role):
    assets, paths, data = fixture(tmp_path, format)
    assets[1]['asset_role'] = role
    revision = _revision()
    revision['frozen_html'] = revision['frozen_html'].replace('</main>', '<p>段落 B</p><img src="asset://body-one" /><p>段落 C</p></main>')
    before = copy.deepcopy(revision)
    reads = []
    def read(id):
        reads.append(id)
        return paths[id]
    payload = build_clipboard_payload(revision, assets, lambda id: 'http://127.0.0.1/'+id, read_asset=read)
    assert reads == ['body-id']  # Neither unused cover nor repeated occurrence is read again.
    assert payload['image_transport'] == 'embedded_data' and payload['image_count'] == 2
    assert payload['html_bytes'] == len(payload['html'].encode('utf-8'))
    sources = re.findall(r'<img src="([^"]+)"', payload['html'])
    assert len(sources) == 2 and sources[0] == sources[1]
    assert sources[0].startswith(f'data:{mime};base64,')
    copied = base64.b64decode(sources[0].split(',',1)[1])
    if format == 'PNG' and role == 'theme_decoration':
        assert len(copied) > 1024
        assert Image.open(io.BytesIO(copied)).convert('RGBA').tobytes() == Image.open(io.BytesIO(data)).convert('RGBA').tobytes()
    else:
        assert copied == data
    if format == 'PNG':
        assert Image.open(io.BytesIO(data)).getpixel((0,0))[3] == 0
    assert '段落 B' in payload['text'] and '段落 C' in payload['text']
    assert '127.0.0.1' not in payload['html'] and 'asset://' not in payload['html']
    assert revision == before


def test_clipboard_fixed_label_tilt_does_not_modify_frozen_or_nonlabels(tmp_path):
    revision = _revision()
    revision['frozen_html'] = revision['frozen_html'].replace('</main>', '<p data-theme-static="true" style="width:52px;transform:rotate(-6deg);border:3px double #123;">01</p><p style="width:52px;transform:rotate(-6deg);">正文</p></main>')
    before = copy.deepcopy(revision)
    assets, _, _ = fixture(tmp_path)
    result = build_clipboard_payload(revision, assets, lambda id:id)
    assert 'width:52px;border:3px double #123;' in result['html']
    assert '<p style="width:52px;transform:rotate(-6deg);">正文</p>' in result['html']
    assert revision == before


@pytest.mark.parametrize('failure,code', [('missing','clipboard_image_unavailable'), ('changed','clipboard_image_changed'), ('corrupt','clipboard_image_invalid'), ('unresolved','clipboard_image_unresolved'), ('file_limit','clipboard_too_large'), ('html_limit','clipboard_too_large'), ('count_limit','clipboard_too_large')])
def test_failure_never_returns_partial_payload(tmp_path, monkeypatch, failure, code):
    assets, paths, data = fixture(tmp_path)
    revision = _revision()
    if failure == 'missing': paths['body-id'][0].unlink()
    if failure == 'changed': paths['body-id'][0].write_bytes(b'changed')
    if failure == 'corrupt':
        paths['body-id'][0].write_bytes(b'not-a-png')
        assets[1]['output_sha256'] = hashlib.sha256(b'not-a-png').hexdigest()
    if failure == 'unresolved': revision['frozen_html'] = revision['frozen_html'].replace('asset://body-one','http://127.0.0.1/missing')
    if failure == 'file_limit': monkeypatch.setattr(delivery, 'CLIPBOARD_IMAGE_MAX_BYTES', len(data)-1)
    if failure == 'html_limit': monkeypatch.setattr(delivery, 'CLIPBOARD_HTML_MAX_BYTES', 200)
    if failure == 'count_limit': monkeypatch.setattr(delivery, 'CLIPBOARD_MAX_IMAGES', 0)
    with pytest.raises(ClipboardPreparationError) as caught:
        build_clipboard_payload(revision, assets, lambda id: 'http://localhost/'+id, read_asset=lambda id: paths[id])
    assert caught.value.code == code
    assert str(tmp_path) not in str(caught.value)


def test_repeated_images_count_toward_expanded_html_budget(tmp_path, monkeypatch):
    assets, paths, _ = fixture(tmp_path)
    revision = _revision()
    one = build_clipboard_payload(revision, assets, lambda id: id, read_asset=lambda id: paths[id])
    monkeypatch.setattr(delivery, 'CLIPBOARD_HTML_MAX_BYTES', one['html_bytes'] + 50)
    revision['frozen_html'] = revision['frozen_html'].replace('</main>', '<img src="asset://body-one" /></main>')
    with pytest.raises(ClipboardPreparationError, match='24 MiB'):
        build_clipboard_payload(revision, assets, lambda id: id, read_asset=lambda id: paths[id])


def test_text_only_does_not_read_assets(tmp_path):
    assets, _, _ = fixture(tmp_path)
    revision = _revision()
    revision['frozen_html'] = revision['frozen_html'].replace('<img src="asset://body-one" />','')
    def unexpected(id): raise AssertionError('No image should be read')
    result = build_clipboard_payload(revision, assets, lambda id: id, read_asset=unexpected)
    assert result['image_transport'] == 'no_images'


def test_multiple_large_photos_and_transparent_decoration(tmp_path):
    assets, paths, decoration = fixture(tmp_path)
    revision = _revision()
    rng = random.Random(19)
    expected = [decoration]
    for index in range(3):
        path = tmp_path / f'photo-{index}.jpg'
        Image.frombytes('RGB', (1600, 1000), rng.randbytes(1600 * 1000 * 3)).save(path, quality=92)
        data = path.read_bytes()
        expected.append(data)
        asset_id = f'photo-{index}'
        assets.append({'id':asset_id, 'asset_token':asset_id, 'asset_role':'planned_image', 'output_sha256':hashlib.sha256(data).hexdigest()})
        paths[asset_id] = (path, 'image/jpeg')
        revision['frozen_html'] = revision['frozen_html'].replace('</main>', f'<p>配图 {index}</p><img src="asset://{asset_id}" /></main>')
    payload = build_clipboard_payload(revision, assets, lambda id:id, read_asset=lambda id:paths[id])
    assert payload['image_count'] == 4
    assert 5 * 1024 * 1024 < payload['html_bytes'] < delivery.CLIPBOARD_HTML_MAX_BYTES
    actual = [base64.b64decode(src.split(',',1)[1]) for src in re.findall(r'<img src="([^"]+)"',payload['html'])]
    assert actual == expected


def test_local_endpoint_never_uses_publisher_and_returns_safe_errors(tmp_path, monkeypatch):
    with TestClient(create_app(str(tmp_path/'workflow.db'))) as client:
        task, plan = _prepare_publication_ready_task(client)
        switched = client.patch(f'/api/v1/article-tasks/{task["id"]}/plans/{plan["id"]}/theme', json={'visual_system':'oriental_archive', 'expected_plan_revision':plan['revision']})
        assert switched.status_code == 200
        task = client.get(f'/api/v1/article-tasks/{task["id"]}').json()['task']
        frozen = _freeze_publication(client, task)
        revision_id = frozen['revision']['id']
        repo = client.app.state.repository
        def unexpected(*args, **kwargs): raise AssertionError('No WeChat access allowed')
        monkeypatch.setattr(client.app.state.wechat_publisher, 'prepare_clipboard_images', unexpected)
        monkeypatch.setattr(client.app.state.wechat_publisher, '_credentials', unexpected)
        url = f'/api/v1/publication-revisions/{revision_id}/clipboard'
        before = copy.deepcopy(repo.get_publication_revision(revision_id))
        response = client.get(url)
        assert response.status_code == 200, response.text
        assert response.headers['cache-control'] == 'private, no-store'
        assert response.json()['image_transport'] == 'embedded_data'
        monkeypatch.setattr(delivery, 'CLIPBOARD_HTML_MAX_BYTES', 1)
        error = client.get(url)
        assert error.status_code == 409 and error.json()['error']['code'] == 'clipboard_too_large'
        assert 'html' not in error.json()
        assert repo.get_publication_revision(revision_id) == before
        assert not repo.list_draft_operations(task['id'])
