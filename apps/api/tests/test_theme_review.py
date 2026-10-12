import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from PIL import Image

from visual_director.generated_theme import render_generated_heading
from visual_director.heading_numbers import has_explicit_heading_number
from visual_director.theme_review import build_theme_review

ROOT = Path(__file__).resolve().parents[3]


def manifest():
    return json.loads((ROOT / 'skills/wechat-visual-director/assets/theme-pack-template.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('title,numbered', [
    ('01 先确定方向', True), ('一、先确定方向', True), ('第十二章 方向', True),
    ('PART 02 方向', True), ('**01** 先确定方向', True),
    ('2026 年的新变化', False), ('3.5 倍增长', False), ('先确定方向', False),
])
def test_heading_number_detection(title, numbered):
    assert has_explicit_heading_number(title) is numbered


@pytest.mark.parametrize('custom', [True, False])
def test_numbered_title_preserved_without_duplicate_or_empty_badge(custom):
    m = manifest()
    m['design_system']['layouts']['heading'] = {'type': 'marker_row', 'marker_width': 13, 'gap': 8, 'children': [
        {'type': 'field', 'bind': 'index', 'style': {'background': 'primary'}}, {'type': 'field', 'bind': 'title'}]}
    if not custom:
        m['design_system'].pop('layouts')
    config = {'palette': m['palette'], 'generated_design_system': m['design_system']}
    soup = BeautifulSoup(render_generated_heading('01 先确定方向', 2, 1, config), 'html.parser')
    assert soup.get_text().strip() == '01 先确定方向'
    assert not soup.select('[data-theme-marker]')
    if custom:
        assert soup.select_one('[data-theme-field="title"]').get_text() == '01 先确定方向'
    plain = BeautifulSoup(render_generated_heading('先确定方向', 2, 1, config), 'html.parser')
    assert '01' in plain.get_text()


def test_review_bundle_is_complete_offline_and_does_not_claim_acceptance(tmp_path):
    theme = tmp_path / 'theme.json'
    theme.write_text(json.dumps(manifest()), encoding='utf-8')
    photo = tmp_path / 'photo.png'
    Image.new('RGB', (40, 30), 'blue').save(photo)
    out = tmp_path / 'review'
    result = build_theme_review(theme, out, photo, [photo])
    assert result['case_count'] == 164  # Four profiles; divider has no prose.
    assert not result['missing_roles']
    assert result['visual_review'] == result['wechat_saved_roundtrip'] == 'not_verified'
    soup = BeautifulSoup((out / 'long-narrow.html').read_text(encoding='utf-8'), 'html.parser')
    assert len(soup.select('[data-review-role]')) == 20
    assert all(i['src'].startswith('data:image/png;base64,') for i in soup.select('img'))
    assert len(soup.select('[data-theme-media="true"]')) == 2
    assert 'padding' not in soup.main['style']
    assert len(soup.select('[data-review-heading]')) == 3
    profiles = {p['id']: p for p in result['pages']}
    assert [(profiles[k]['viewport_width'], profiles[k]['content_width'], profiles[k]['primary'])
            for k in ('mobile', 'proof', 'narrow', 'legacy')] == [
                (405, 357, True), (648, 600, True), (368, 320, False), (438, 390, False)]
    mobile = BeautifulSoup((out / 'short-mobile.html').read_text(encoding='utf-8'), 'html.parser')
    proof = BeautifulSoup((out / 'short-proof.html').read_text(encoding='utf-8'), 'html.parser')
    assert mobile.html['data-workbench-preview-mode'] == 'mobile'
    assert 'padding:0 24px' in mobile.body['style']
    import re
    get_size = lambda s: float(re.search(r'font-size:([\d.]+)px', s.select_one('[data-theme-field="title"]')['style'])[1])
    assert get_size(proof) == pytest.approx(round(get_size(mobile) * 1.06, 2))
    with pytest.raises(ValueError, match='已存在'):
        build_theme_review(theme, out, photo)


def test_partial_layouts_report_missing_without_fallback_claim(tmp_path):
    m = manifest()
    m['design_system']['layouts'] = {'heading': m['design_system']['layouts']['heading']}
    theme = tmp_path / 'theme.json'
    theme.write_text(json.dumps(m), encoding='utf-8')
    photo = tmp_path / 'photo.png'
    Image.new('RGB', (10, 10)).save(photo)
    result = build_theme_review(theme, tmp_path / 'review', photo)
    assert len(result['missing_roles']) == 20
    assert result['case_count'] == 8


def test_review_rejects_invalid_image_before_creating_output(tmp_path):
    theme = tmp_path / 'theme.json'
    theme.write_text(json.dumps(manifest()), encoding='utf-8')
    photo = tmp_path / 'not-an-image.png'
    photo.write_text('not an image', encoding='utf-8')
    with pytest.raises(OSError):
        build_theme_review(theme, tmp_path / 'review', photo)
    assert not (tmp_path / 'review').exists()


def test_offline_review_does_not_initialize_or_change_theme_registry(tmp_path):
    from visual_director import theme_packs
    previous = (theme_packs._pack_dir, theme_packs._reserved_ids, theme_packs._core_components, dict(theme_packs._installed))
    theme = tmp_path / 'theme.json'
    theme.write_text(json.dumps(manifest()), encoding='utf-8')
    photo = tmp_path / 'photo.png'
    Image.new('RGB', (10, 10)).save(photo)
    build_theme_review(theme, tmp_path / 'review', photo)
    assert previous == (theme_packs._pack_dir, theme_packs._reserved_ids, theme_packs._core_components, dict(theme_packs._installed))


def test_review_cli_reports_error_as_json_without_starting_service(tmp_path, capsys):
    from visual_director.cli import run
    code = run(['theme', 'review', '--file', str(tmp_path / 'missing.json'),
                '--image', str(tmp_path / 'missing.png'), '--output', str(tmp_path / 'out'), '--json'])
    response = json.loads(capsys.readouterr().out)
    assert code != 0
    assert response['error']['code'] == 'theme_review_failed'
    assert not (tmp_path / 'out').exists()
