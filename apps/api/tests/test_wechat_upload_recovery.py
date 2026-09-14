"""Transport regression tests: no live credentials or WeChat requests."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from test_delivery import _assets, _revision, _Response
from test_api_workflow import _prepare_publication_ready_task, _freeze_publication
from visual_director.main import create_app
from visual_director.wechat_publisher import WechatDraftPublisher, WechatApiError


def publisher(tmp_path, request):
    p = WechatDraftPublisher(tmp_path, requester=request)
    p._credentials = lambda: ('test-account', 'test-secret', 'test')
    return p


@pytest.mark.parametrize('clipboard', [False, True])
@pytest.mark.parametrize('alpha', [False, True])
def test_webp_transport_conversion_preserves_source_and_alpha(tmp_path, clipboard, alpha):
    assets, paths = _assets(tmp_path)
    file = tmp_path / 'original.webp'
    Image.new('RGBA' if alpha else 'RGB', (32, 24), (220, 40, 30, 80) if alpha else (220, 40, 30)).save(file, 'WEBP', lossless=True)
    original = file.read_bytes()
    assets[1].update(relative_filename=file.name, output_sha256=hashlib.sha256(original).hexdigest())
    uploads = []
    def request(req, **kwargs):
        uploads.append(req)
        return _Response({'url':'https://mmbiz.qpic.cn/test','media_id':'test-media'})
    p = publisher(tmp_path, request)
    p._upload_cached_image('test-token', assets[1], file, 'image/webp', clipboard=clipboard)
    wire = uploads[0].data
    assert b'filename="original.png"' in wire
    assert b'Content-Type: image/png' in wire
    raw = wire.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n--', 1)[0]
    with Image.open(BytesIO(raw)) as converted:
        assert converted.format == 'PNG' and converted.size == (32, 24)
        if alpha:
            assert converted.getpixel((0, 0))[3] == 80
    assert file.read_bytes() == original
    p._upload_cached_image('test-token', assets[1], file, 'image/webp', clipboard=clipboard)
    assert len(uploads) == 1


@pytest.mark.parametrize('code', [40001, 40014, 42001])
@pytest.mark.parametrize('stage', ['material', 'clipboard', 'draft'])
def test_explicit_token_rejection_refreshes_once(tmp_path, code, stage):
    assets, paths = _assets(tmp_path)
    tokens, rejected, creates = [], [], []
    def request(req, **kwargs):
        if '/token?' in req.full_url:
            tokens.append(1)
            return _Response({'access_token':f'test-token-{len(tokens)}','expires_in':7200})
        token = parse_qs(urlsplit(req.full_url).query)['access_token'][0]
        target = ('/draft/add?' if stage=='draft' else '/media/uploadimg?' if stage=='clipboard' else '/material/add_material?')
        if '/draft/add?' in req.full_url:
            creates.append(token)
        if target in req.full_url and not rejected:
            rejected.append(token)
            return _Response({'errcode':code,'errmsg':'test-only rejection'})
        if '/draft/add?' in req.full_url:
            return _Response({'media_id':'test-draft'})
        return _Response({'media_id':'test-image','url':'https://mmbiz.qpic.cn/test'})
    p = publisher(tmp_path, request)
    if stage=='clipboard':
        assert 'asset_urls' in p.prepare_clipboard_images(_revision(), assets, lambda id: paths[id])
        assert not creates
    else:
        assert p.publish(_revision(), assets, lambda id: paths[id]).status == 'succeeded'
    assert len(tokens) == 2


def test_persistent_rejection_stops_and_does_not_create_draft(tmp_path):
    assets, paths = _assets(tmp_path)
    calls = []
    def request(req, **kwargs):
        calls.append(urlsplit(req.full_url).path)
        if '/token?' in req.full_url:
            return _Response({'access_token':'test-token','expires_in':7200})
        return _Response({'errcode':40001,'errmsg':'must not leak test-token'})
    result = publisher(tmp_path, request).publish(_revision(), assets, lambda id:paths[id])
    assert result.status == 'failed' and result.error['code']=='wechat_token_invalid'
    assert calls.count('/cgi-bin/material/add_material') == 2
    assert '/cgi-bin/draft/add' not in calls
    assert 'test-token' not in json.dumps(result.error)


def test_token_requests_are_serialized_and_stale_rejections_reuse_refresh(tmp_path):
    calls = []
    def request(req, **kwargs):
        calls.append(1)
        return _Response({'access_token':f'test-token-{len(calls)}','expires_in':7200})
    p = publisher(tmp_path, request)
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert set(pool.map(lambda _:p._access_token(), range(30))) == {'test-token-1'}
        assert set(pool.map(lambda _:p._refresh_rejected_token('test-token-1'), range(30))) == {'test-token-2'}
    assert len(calls)==2
    p.invalidate_token_cache()
    assert p._access_token()=='test-token-3'


def test_format_error_is_actionable_and_not_blindly_retryable():
    result = WechatDraftPublisher._classified_error(WechatApiError(40113,'private raw error',stage='upload_image'),stage='upload_image')
    assert result.error['code']=='wechat_image_format_unsupported'
    assert result.error['retryable'] is False
    assert 'private raw error' not in str(result.error)


def test_animated_webp_is_not_silently_flattened():
    out=BytesIO()
    first=Image.new('RGB',(24,24),'red')
    first.save(out,'WEBP',save_all=True,append_images=[Image.new('RGB',(24,24),'blue')],duration=100,loop=0)
    with pytest.raises(WechatApiError) as error:
        WechatDraftPublisher._prepare_upload_image('animation.webp','image/webp',out.getvalue())
    assert error.value.errcode==40113


def test_draft_timeout_after_explicit_rejection_remains_unknown(tmp_path):
    assets,paths=_assets(tmp_path)
    creates=[]
    def request(req,**kwargs):
        if '/token?' in req.full_url:
            return _Response({'access_token':'test-token','expires_in':7200})
        if '/draft/add?' in req.full_url:
            creates.append(1)
            if len(creates)==1:
                return _Response({'errcode':40001,'errmsg':'test-rejection'})
            raise TimeoutError('test-timeout')
        return _Response({'media_id':'test-image','url':'https://mmbiz.qpic.cn/test'})
    result=publisher(tmp_path,request).publish(_revision(),assets,lambda id:paths[id])
    assert result.status=='unknown' and not result.error['retryable']
    assert len(creates)==2


def test_connection_probe_invalidates_publisher_cache(tmp_path, monkeypatch):
    monkeypatch.setenv('VISUAL_DIRECTOR_ENV_FILE', str(tmp_path/'unused.env'))
    class Probe:
        def probe(self, *args):
            return {'ok':True,'code':'wechat_connection_ready'}
    p = publisher(tmp_path, lambda *a,**kw:pytest.fail('No external request expected'))
    p._token_cache['test-account']=('old-test-token',9999999999)
    with TestClient(create_app(str(tmp_path/'test.db'),wechat_publisher=p,wechat_connection_probe=Probe())) as client:
        result=client.post('/api/v1/settings/wechat-publisher/probe',headers={'X-Settings-Intent':'local-operator'})
        assert result.status_code==200
        assert not p._token_cache
        assert 'old-test-token' not in result.text


def test_parallel_frozen_asset_reads_and_upload_cache_writes(tmp_path):
    with TestClient(create_app(str(tmp_path/'test.db'))) as client:
        task, plan = _prepare_publication_ready_task(client)
        frozen = _freeze_publication(client, task)
        repo = client.app.state.repository
        assets = repo.list_publication_assets(frozen['revision']['id'])
        def action(index):
            asset = assets[index % len(assets)]
            path, mime = repo.get_publication_asset(asset['id'])
            assert path.is_file() and mime.startswith('image/')
            repo.save_wechat_image_upload(f'cache-{index}',{'url':'https://mmbiz.qpic.cn/test'},9999999999)
            assert repo.get_wechat_image_upload(f'cache-{index}')
            assert repo.list_publication_assets(frozen['revision']['id'])
        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(action,range(160)))
        assert repo.connection.execute('PRAGMA quick_check').fetchone()[0]=='ok'
