"""Evidence presentation must not turn geometry success into visual approval."""
import base64
import importlib.util
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('theme_compare', ROOT / 'skills/wechat-visual-director/scripts/check-theme-review.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_comparison_includes_references_and_exact_matched_cases_without_grading(tmp_path):
    review, before, after = [tmp_path / name for name in ('review', 'before', 'after')]
    for folder in (review, before, after):
        folder.mkdir()
        Image.new('RGB', (2, 2), 'white').save(folder / 'shot.png')
    uri = 'data:image/png;base64,' + base64.b64encode((review / 'shot.png').read_bytes()).decode()
    (review / 'index.html').write_text(f'<img src="{uri}"><img src="https://not-loaded.example/image.png">')
    current = dict(role='hero', length='short', content_width=390, screenshot='shot.png')
    long = dict(current, length='long', content_width=320)
    old = dict(theme_sha256='old', cases=[dict(current)])
    (before / 'browser-report.json').write_text(json.dumps(old))
    report = dict(theme_sha256='new', visual_review='not_verified', cases=[current, long])
    result = Path(checker.build_visual_comparison(review, after, report, before)).read_text(encoding='utf-8')
    assert '修改前 hero' in result and '当前 hero' in result and '长文 hero' in result
    assert '参考 1' in result and 'not-loaded.example' not in result
    assert report['visual_review'] == 'not_verified'
    assert 'default-src' in result and '<script' not in result
    old['cases'][0]['content_width'] = 600
    (before / 'browser-report.json').write_text(json.dumps(old))
    result = Path(checker.build_visual_comparison(review, after, report, before)).read_text(encoding='utf-8')
    assert '无匹配的修改前截图' in result


@pytest.mark.parametrize('path', ['../private.png', '..\\private.png', '/private.png', 'x.html'])
def test_comparison_rejects_paths_outside_screenshot_directory(tmp_path, path):
    with pytest.raises(ValueError):
        checker._screenshot_uri(tmp_path, {'screenshot': path})


def test_reference_html_does_not_import_remote_or_attribute_injections():
    parser = checker._ReferenceImages()
    parser.feed('<img src="https://example.com/x"><img src="data:image/png;base64,not-valid" onerror="alert(1)">')
    assert parser.sources == []


class OverviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.roles = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'figure':
            self.roles.append(attrs.get('data-overview-role'))
        if tag == 'img':
            self.images.append(attrs)


def test_overview_preserves_all_same_width_roles_and_source_pixels(tmp_path):
    source, output = tmp_path / 'source', tmp_path / 'output'
    source.mkdir()
    output.mkdir()
    roles = [r for _, _, group in checker.OVERVIEW_GROUPS for r in group]
    records = []
    for index, role in enumerate(roles):
        filename = role + '.png'
        Image.new('RGB', (390, 80 + index), (index, 120, 200)).save(source / filename)
        records.append(dict(role=role, length='short', content_width=390, screenshot=filename))
    # A different-width record is not eligible for this inspection material.
    records.append(dict(role='not_in_overview', length='short', content_width=600, screenshot='absent.png'))
    report = dict(theme_sha256='sample', renderer_version='renderer', visual_review='not_verified', cases=records)
    snapshot = json.loads(json.dumps(report))
    overview = checker.build_component_overview(output, report, source)
    parser = OverviewParser()
    parser.feed(Path(overview['overview_file']).read_text(encoding='utf-8'))
    assert set(overview['roles']) == set(roles) and len(overview['roles']) == 21
    assert set(parser.roles) == set(roles)
    assert sum(len(g['roles']) for g in overview['groups']) == 21
    assert report == snapshot and overview['visual_review'] == 'not_verified'
    for attrs in parser.images:
        role = attrs['alt'].split(' · ')[0]
        assert attrs['width'] == '390'
        assert base64.b64decode(attrs['src'].split(',', 1)[1]) == (source / (role + '.png')).read_bytes()


def test_overview_rejects_stretched_evidence(tmp_path):
    Image.new('RGB', (600, 100)).save(tmp_path / 'shot.png')
    report = dict(theme_sha256='sample', cases=[dict(role='hero', length='short', content_width=390, screenshot='shot.png')])
    with pytest.raises(ValueError, match='native 390px'):
        checker.build_component_overview(tmp_path, report)


def test_current_overview_uses_native_mobile_content_width_not_legacy(tmp_path):
    from visual_director.preview_profiles import PREVIEW_CONFIG
    Image.new('RGB', (357, 80)).save(tmp_path / 'mobile.png')
    report = dict(theme_sha256='sample', overview_profile='mobile', preview_config=PREVIEW_CONFIG,
                  cases=[dict(role='hero', length='short', content_width=357, profile_id='mobile', screenshot='mobile.png'),
                         dict(role='quote', length='short', content_width=390, profile_id='legacy', screenshot='absent.png')])
    overview = checker.build_component_overview(tmp_path, report)
    assert overview['content_width'] == 357 and overview['profile_id'] == 'mobile'
    assert overview['roles'] == ['hero']
    parser = OverviewParser()
    parser.feed(Path(overview['overview_file']).read_text(encoding='utf-8'))
    assert all(i['width'] == '357' for i in parser.images)


def test_comparison_does_not_mix_profiles_with_same_content_width(tmp_path):
    from visual_director.preview_profiles import PREVIEW_CONFIG
    review, before, after = [tmp_path / name for name in ('review', 'before', 'after')]
    for folder in (review, before, after):
        folder.mkdir()
        Image.new('RGB', (357, 80)).save(folder / 'shot.png')
    (review / 'index.html').write_text('no references')
    current = dict(role='hero', length='short', content_width=357, profile_id='mobile', font_scale=1, screenshot='shot.png')
    (before / 'browser-report.json').write_text(json.dumps(dict(theme_sha256='old', cases=[dict(current, profile_id='proof')])) )
    report = dict(theme_sha256='new', overview_profile='mobile', preview_config=PREVIEW_CONFIG, cases=[current])
    document = Path(checker.build_visual_comparison(review, after, report, before)).read_text(encoding='utf-8')
    assert '无匹配的修改前截图' in document


def test_overview_reuse_rejects_stale_theme_or_renderer_before_creating_output(tmp_path, monkeypatch):
    review = tmp_path / 'review'
    review.mkdir()
    manifest = dict(schema_version='theme_review.v1', theme_sha256='current', renderer_version='new')
    (review / 'manifest.json').write_text(json.dumps(manifest))
    report = tmp_path / 'browser-report.json'
    output = tmp_path / 'new-output'
    monkeypatch.setattr('sys.argv', ['check', '--review', str(review), '--output', str(output), '--reuse-report', str(report)])
    for theme_hash, renderer in [('old', 'new'), ('current', 'old')]:
        report.write_text(json.dumps(dict(theme_sha256=theme_hash, renderer_version=renderer)))
        with pytest.raises(ValueError, match='must match'):
            checker.main()
        assert not output.exists()
