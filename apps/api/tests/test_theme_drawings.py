import copy

import pytest
from bs4 import BeautifulSoup

from postal_theme_fixture import landscape
from visual_director.theme_layouts import PALETTE_KEYS, validate_layouts
from visual_director.theme_drawings import render_drawing, validate_drawing


@pytest.mark.parametrize('bad', [
    {'width': True}, {'width': 999}, {'height': None}, {'parts': []},
    {'parts': ['<script>']}, {'parts': [{'kind': []}]},
    {'parts': [{'kind': 'polyline', 'points': [[0, 0], [999, 1]], 'stroke': 'sky', 'stroke_width': 1}]},
    {'parts': [{'kind': 'ellipse', 'x': 60, 'y': 0, 'w': 30, 'h': 20, 'stroke': 'sky', 'stroke_width': 1}]},
    {'parts': [{'kind': 'ellipse', 'x': 0, 'y': 0, 'w': 20, 'h': 20, 'stroke': [], 'fill': 'url(x)', 'stroke_width': True}]},
    {'parts': [{'kind': 'polyline', 'points': [[0, 0], [1, 1]], 'stroke': 'sky', 'stroke_width': 1, 'onclick': 'x'}]},
])
def test_invalid_drawing_is_rejected(bad):
    assert validate_drawing({**landscape(), **bad}, PALETTE_KEYS)


def test_drawing_is_decorative_bounded_and_theme_independent():
    node = landscape()
    assert not validate_drawing(node, PALETTE_KEYS)
    palette = dict.fromkeys(PALETTE_KEYS, '#123456')
    markup = render_drawing(node, palette)
    soup = BeautifulSoup(markup, 'html.parser')
    assert soup.select_one('[data-theme-drawing][aria-hidden="true"]')
    assert not soup.select('svg,script,[data-theme-field]')
    assert len(soup.select('img[data-theme-decoration]')) == 1
    assert not soup.get_text().strip()
    assert 'pointer-events:none' in markup and 'position:absolute' not in markup
    from visual_director.theme_delivery import compiled_decoration_assets
    from visual_director.publication import replace_asset_urls
    assets = compiled_decoration_assets(markup)
    assert len(assets) == 1 and assets[0]['width'] == node['width'] * 4
    from visual_director.publication import check_frozen_html, strip_workbench_editor_attributes
    frozen = strip_workbench_editor_attributes(replace_asset_urls(markup, {a['source_url']: a['asset_token'] for a in assets}))
    assert check_frozen_html(frozen).status == 'pass'
    assert BeautifulSoup(frozen, 'html.parser').select_one('[data-theme-drawing]')
    assert not validate_layouts({'quote': {'type': 'stack', 'children': [node, {'type': 'field', 'bind': 'body'}]}})
    excessive = copy.deepcopy(node)
    excessive['parts'] = [node['parts'][0]] * 32
    assert validate_layouts({'quote': {'type': 'stack', 'children': [excessive] * 4 + [{'type': 'field', 'bind': 'body'}]}})
