"""Behavioral regression for optional browser review, not aesthetic grading."""
import importlib.util
import os
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('theme_review_checker', ROOT / 'skills/wechat-visual-director/scripts/check-theme-review.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_role_selection_preserves_profiles_lengths_and_manifest():
    manifest = dict(case_count=20, pages=[
        dict(file=f'{length}-{profile}.html', id=profile, length=length,
             roles=['hero', 'heading', 'quote'] if length == 'short' else ['hero', 'heading'])
        for length in ('short', 'long') for profile in ('mobile', 'proof', 'narrow', 'legacy')])
    snapshot = json.loads(json.dumps(manifest))
    pages, scope = checker.select_review_pages(manifest, ['hero', 'heading', 'hero'])
    assert len(pages) == 8 and all(p['roles'] == ['hero', 'heading'] for p in pages)
    assert scope == dict(check_scope='selected_roles', checked_roles=['heading', 'hero'],
                        unchecked_roles=['quote'], expected_case_count=16, full_bundle_case_count=20)
    assert manifest == snapshot
    all_pages, full = checker.select_review_pages(manifest)
    assert all_pages == manifest['pages'] and full['check_scope'] == 'full_bundle'
    assert full['expected_case_count'] == 20 and full['unchecked_roles'] == []
    assert checker.select_review_pages(manifest, ['quote'])[1]['expected_case_count'] == 4
    for roles in ([], ['not_a_role']):
        with pytest.raises(ValueError):
            checker.select_review_pages(manifest, roles)


def test_unknown_role_fails_before_output_or_browser_start(tmp_path, monkeypatch):
    review = tmp_path / 'review'
    review.mkdir()
    (review / 'manifest.json').write_text(json.dumps(dict(schema_version='theme_review.v2',
        pages=[dict(roles=['hero'])], case_count=1)), encoding='utf-8')
    output = tmp_path / 'output'
    monkeypatch.setattr('sys.argv', ['check', '--review', str(review), '--output', str(output),
                                  '--roles', 'not_a_role'])
    with pytest.raises(ValueError, match='Unknown review roles'):
        checker.main()
    assert not output.exists()
    monkeypatch.setattr('sys.argv', ['check', '--review', str(review), '--output', str(output),
        '--reuse-report', str(tmp_path / 'absent-report.json'), '--roles', 'hero'])
    with pytest.raises(ValueError, match='do not combine'):
        checker.main()
    assert not output.exists()


def test_cli_partial_check_captures_only_selected_roles_and_never_claims_full_pass(tmp_path, monkeypatch, capsys):
    from visual_director.preview_profiles import PREVIEW_CONFIG
    pytest.importorskip('playwright.sync_api')
    review = tmp_path / 'review'
    review.mkdir()
    pages = []
    for length in ('short', 'long'):
        for profile in PREVIEW_CONFIG['profiles']:
            width = profile['viewport_width'] - 48
            filename = f'{length}-{profile["id"]}.html'
            (review / filename).write_text('<html><body style="margin:0;padding:0 24px">'
                + ''.join(f'<article data-review-role="{role}" style="width:100%">'
                          f'<p data-theme-field="title">测试文本 {role}</p></article>'
                          for role in ('hero', 'heading', 'quote')) + '</body></html>', encoding='utf-8')
            pages.append({**profile, 'file': filename, 'length': length,
                          'content_width': width, 'roles': ['hero', 'heading', 'quote']})
    manifest = dict(schema_version='theme_review.v2', theme_sha256='current-theme',
                    renderer_version='renderer', missing_roles=[], case_count=24, pages=pages,
                    preview_config=PREVIEW_CONFIG, overview_profile='mobile')
    (review / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (review / 'index.html').write_text('<html>reference-free fixture</html>', encoding='utf-8')
    browser_args = ['--browser', os.environ['THEME_TEST_BROWSER']] if os.environ.get('THEME_TEST_BROWSER') else []
    for roles, expected_count, expected_scope in [(['hero', 'heading'], 16, 'selected_roles'), (None, 24, 'full_bundle')]:
        output = tmp_path / expected_scope
        argv = ['check', '--review', str(review), '--output', str(output), *browser_args]
        if roles:
            argv += ['--roles', *roles]
        monkeypatch.setattr('sys.argv', argv)
        assert checker.main() == 0
        summary = json.loads(capsys.readouterr().out)
        report = json.loads((output / 'browser-report.json').read_text(encoding='utf-8'))
        overview = json.loads((output / 'component-overview.json').read_text(encoding='utf-8'))
        assert summary['case_count'] == report['case_count'] == expected_count
        assert report['expected_case_count'] == expected_count and report['full_bundle_case_count'] == 24
        assert report['check_scope'] == overview['check_scope'] == expected_scope
        assert report['geometry'] == 'pass'
        assert report['full_bundle_geometry'] == ('not_verified' if roles else 'pass')
        assert report['visual_review'] == report['wechat_saved_roundtrip'] == 'not_verified'
        assert {r['profile_id'] for r in report['cases']} == {'mobile', 'proof', 'narrow', 'legacy'}
        assert report['unchecked_roles'] == (['quote'] if roles else [])
        assert set(overview['roles']) == (set(roles) if roles else {'hero', 'heading', 'quote'})
        assert (output / 'quote-short-mobile.png').exists() is (roles is None)
        document = (output / 'component-overview.html').read_text(encoding='utf-8')
        assert ('data-overview-scope="selected_roles"' in document) is bool(roles)
        if roles:
            original = (output / 'browser-report.json').read_bytes()
            reused_output = tmp_path / 'partial-reuse'
            monkeypatch.setattr('sys.argv', ['check', '--review', str(review), '--output', str(reused_output),
                '--reuse-report', str(output / 'browser-report.json'), *browser_args])
            assert checker.main() == 0
            reused = json.loads(capsys.readouterr().out)
            assert reused['check_scope'] == 'selected_roles' and reused['unchecked_roles'] == ['quote']
            assert reused['roles'] == ['heading', 'hero']
            assert not (reused_output / 'browser-report.json').exists()
            assert (output / 'browser-report.json').read_bytes() == original


def test_single_cjk_tail_is_reading_hint_not_overflow_or_text_length_rule():
    pw = pytest.importorskip('playwright.sync_api')
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **({'executable_path': os.environ['THEME_TEST_BROWSER']} if os.environ.get('THEME_TEST_BROWSER') else {}))
        try:
            page = browser.new_page(viewport={'width': 405, 'height': 900})
            for width, expected in [(60, True), (80, False), (40, False)]:
                page.set_content(f'<body style="margin:0"><article><p data-theme-field="title" style="width:{width}px;font:20px/30px sans-serif;margin:0">甲乙丙丁</p></article></body>')
                metric = page.locator('article').evaluate(checker.MEASURE)
                assert metric['fields'][0]['last_line_single_cjk_review'] is expected
                assert not metric['overflow']
                assert metric['fields'][0]['text_length'] == 4
        finally:
            browser.close()


def test_normal_article_capture_matches_workbench_profiles_and_keeps_source(tmp_path):
    from visual_director.preview_profiles import PREVIEW_CONFIG
    from PIL import Image
    pw = pytest.importorskip('playwright.sync_api')
    source_dir = tmp_path / 'source'
    source_dir.mkdir()
    Image.new('RGB', (2, 2), '#BB6633').save(source_dir / 'local.png')
    article = source_dir / 'article.html'
    article.write_text('<html><body style="margin:0;padding:0 24px"><main style="width:100%"><h2 data-theme-layout="heading"><span data-theme-field="title" style="font-size:20px">一个真实标题</span></h2><p data-theme-field="body">正文保持不变。</p><img src="local.png" width="2" height="2"></main></body></html>', encoding='utf-8')
    source = article.read_bytes()
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **({'executable_path': os.environ['THEME_TEST_BROWSER']} if os.environ.get('THEME_TEST_BROWSER') else {}))
        try:
            page = browser.new_page()
            report = checker.capture_normal_article(page, article, tmp_path,
                dict(preview_config=PREVIEW_CONFIG, theme_sha256='sample', renderer_version='renderer'))
            assert report['geometry'] == 'pass'
            assert [(r['viewport_width'], r['observed_content_width']) for r in report['profiles']] == [(405,357),(648,600),(368,320),(438,390)]
            assert [r['fields'][0]['font_size'] for r in report['profiles']] == [20,21.2,20,20]
            assert report['source_sha256'] == hashlib.sha256(source).hexdigest()
            assert report['visual_review'] == report['article_theme_binding'] == 'not_verified'
            assert article.read_bytes() == source
            assert report['preview_entry'] == 'article-preview.html'
            for profile in report['profiles']:
                path = tmp_path / profile['preview_file']
                assert path.is_file()
                page.set_viewport_size({'width': profile['viewport_width'], 'height': 900})
                page.goto(path.as_uri())
                assert page.locator('html').get_attribute('data-workbench-preview-mode') == profile['mode']
                assert page.locator('[data-theme-field="title"]').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)') == pytest.approx(20 * profile['font_scale'])
                assert page.locator('main').evaluate('(e)=>e.getBoundingClientRect().width') == profile['observed_content_width']
                assert page.locator('img').evaluate('(e)=>e.complete&&e.naturalWidth===2')
            page.set_viewport_size({'width': 1100, 'height': 900})
            page.goto((tmp_path / report['preview_entry']).as_uri())
            for name, width, font in [('校对阅读',648,21.2), ('手机阅读',405,20), ('校对阅读',648,21.2)]:
                page.get_by_role('button', name=name, exact=True).click()
                frame = page.locator('#article').content_frame
                assert frame.locator('[data-theme-field="title"]').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)') == pytest.approx(font)
                assert page.locator('#article').evaluate('(e)=>e.getBoundingClientRect().width') == width
            assert article.read_bytes() == source
        finally:
            browser.close()


def test_article_profile_ids_cannot_escape_output(tmp_path):
    from visual_director.preview_profiles import PREVIEW_CONFIG
    config = json.loads(json.dumps(PREVIEW_CONFIG))
    config['profiles'][0]['id'] = '../escape'
    with pytest.raises(ValueError, match='Invalid article preview profile ids'):
        checker.capture_normal_article(None, tmp_path/'absent.html', tmp_path,
                                       dict(preview_config=config))
    assert not list(tmp_path.iterdir())


def test_title_decoration_sidecar_review_tracks_geometry_not_character_count():
    pw = pytest.importorskip('playwright.sync_api')
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, **({'executable_path': os.environ['THEME_TEST_BROWSER']} if os.environ.get('THEME_TEST_BROWSER') else {}))
        except pw.Error as exc:
            pytest.skip(f'Local browser unavailable: {exc}')
        try:
            page = browser.new_page(viewport={'width': 320, 'height': 900})
            title = '<h1 data-theme-field="title" style="font:30px/45px sans-serif;margin:0">把一首歌听完，给下班后的自己留一点时间</h1>'
            art = '<section aria-hidden="true" style="height:40px;width:40px;background:blue"></section>'
            left = '<section style="display:inline-block;vertical-align:top;width:72%">'
            right = '<section style="display:inline-block;vertical-align:top;width:28%">'
            for markup, expected in [
                (left+title+'</section>'+right+art+'</section>', True),
                (art+title, False),
                (left+title+'</section>'+right+'<p data-theme-field="body">有用的旁注</p></section>', False),
                (left+title.replace('把一首歌听完，给下班后的自己留一点时间','短标题')+'</section>'+right+art+'</section>', False),
            ]:
                page.set_content('<body style="margin:0"><article>'+markup+'</article></body>')
                result = page.locator('article').evaluate(checker.MEASURE)
                field = result['fields'][0]
                assert field['text_length'] < 70
                assert bool(field['title_sidecar_review']) is expected
                assert result['overflow'] is False
        finally:
            browser.close()
