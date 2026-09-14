"""Semantic marker columns and ornament bands retain text and asset contracts."""
import copy
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from visual_director.theme_layouts import render_layout, validate_layouts
from visual_director.theme_delivery import compiled_decoration_assets, rehearse_theme_delivery
from visual_director.delivery import _responsive_delivery_document, build_clipboard_payload

ROOT = Path(__file__).resolve().parents[3]


def manifest():
    value = json.loads((ROOT / 'skills/wechat-visual-director/assets/theme-pack-template.json').read_text(encoding='utf-8'))
    value['design_system']['layouts']['list'] = {
        'type': 'repeat', 'bind': 'items', 'children': [{
            'type': 'marker_row', 'marker_width': 8, 'gap': 4, 'children': [
                {'type': 'text', 'text': '•', 'style': {'size': 'body'}},
                {'type': 'field', 'bind': 'item'}]}]}
    value['design_system']['layouts']['divider'] = {
        'type': 'ornament_rule', 'slot_width': 24, 'line_color': 'secondary', 'children': [{
            'type': 'drawing', 'width': 64, 'height': 16, 'parts': [{
                'kind': 'polyline', 'points': [[1, 8], [32, 1], [63, 8], [32, 15], [1, 8]],
                'stroke': 'secondary', 'stroke_width': 1}]}]}
    return value


def test_schema_runtime_and_delivery_agree():
    value = manifest()
    schema = json.loads((ROOT / 'contracts/theme-pack-v1.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(value)
    assert not validate_layouts(value['design_system']['layouts'])
    assert rehearse_theme_delivery(value)['status'] == 'pass'


@pytest.mark.parametrize('path', ['preview', 'api', 'clipboard'])
def test_markers_preserve_editable_fields_order_and_hanging_columns(path):
    value = manifest()
    config = {'palette': value['palette'], 'generated_design_system': value['design_system']}
    before = copy.deepcopy(config)
    items = ['第一项', '很长的正文需要自然换行。' * 8, '**重要**事项']
    markup = render_layout('list', {'items': items}, config)
    document = '<html><body><main>' + markup + '</main></body></html>'
    if path == 'api':
        document = _responsive_delivery_document(document)
    if path == 'clipboard':
        document = build_clipboard_payload({'frozen_html': document, 'metadata': {'title': '测试'}}, [], lambda _: '')['html']
    soup = BeautifulSoup(document, 'html.parser')
    rows = soup.select('[data-theme-marker-row]')
    assert len(rows) == 3
    assert [r.select_one('[data-theme-field="item"]').get_text() for r in rows] == [s.replace('**', '') for s in items]
    for row in rows:
        assert len(row.find_all('section', recursive=False)) == 2
        assert 'width:8%' in row.select_one('[data-theme-marker]')['style']
        assert 'width:92%' in row.select_one('[data-theme-marker-body]')['style']
        assert 'vertical-align:top' in row.select_one('[data-theme-marker-body]')['style']
    assert config == before


def test_ornament_is_single_band_and_materializes_as_a_verified_asset():
    value = manifest()
    config = {'palette': value['palette'], 'generated_design_system': value['design_system']}
    markup = render_layout('divider', {}, config)
    assert len(compiled_decoration_assets(markup)) == 1
    soup = BeautifulSoup(markup, 'html.parser')
    band = soup.select_one('[data-theme-ornament-rule]')
    assert len(band.find_all('section', recursive=False)) == 3
    assert 'position:' not in markup and 'calc(' not in markup
    assert not soup.select('[data-theme-field]')


@pytest.mark.parametrize('change', [
    lambda n: n.update(marker_width=30),
    lambda n: n.update(gap=-1),
    lambda n: n['children'].append({'type': 'rule'}),
    lambda n: n['children'].__setitem__(0, {'type': 'field', 'bind': 'item'}),
])
def test_invalid_marker_layout_is_rejected(change):
    layouts = manifest()['design_system']['layouts']
    change(layouts['list']['children'][0])
    assert validate_layouts(layouts)


@pytest.mark.parametrize('change', [
    lambda n: n.update(line_color=[]),
    lambda n: n.update(slot_width=70),
    lambda n: n['children'][0].update(height=60),
    lambda n: n['children'][0].update(style={'margin': -12}),
    lambda n: n['children'].__setitem__(0, {'type': 'field', 'bind': 'body'}),
])
def test_ornament_cannot_hide_text_or_claim_zero_space(change):
    layouts = manifest()['design_system']['layouts']
    change(layouts['divider'])
    assert validate_layouts(layouts)
