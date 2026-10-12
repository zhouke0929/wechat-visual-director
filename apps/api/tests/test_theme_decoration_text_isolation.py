"""Zero-height decorative line boxes must never govern visible article text."""
import copy
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from visual_director.delivery import build_clipboard_payload, _responsive_delivery_document
from visual_director.publication import replace_asset_urls
from visual_director.theme_delivery import compiled_decoration_assets, theme_delivery_report
from visual_director.theme_layouts import render_layout


def manifest():
    root = Path(__file__).resolve().parents[3]
    data = json.loads((root / 'skills/wechat-visual-director/assets/theme-pack-template.json').read_text(encoding='utf-8'))
    drawing = {'type':'drawing','width':32,'height':16,'parts':[
        {'kind':'polyline','points':[[2,12],[16,3],[30,12]],'stroke':'secondary','stroke_width':1},
    ]}
    data['design_system']['layouts'] = {'quote': {'type':'stack','children':[
        drawing,
        {'type':'cutout','fill':'secondary_pale','radius':3,'pitch':18,'inset':12,'children':[
            {'type':'text','text':'阅读提示'}, {'type':'field','bind':'body'},
        ]},
        {'type':'rule'},
        {'type':'ornament_rule','slot_width':20,'line_color':'secondary','children':[copy.deepcopy(drawing)]},
    ]}}
    return data


def styles(element):
    return {key.strip():value.strip() for part in element.get('style','').split(';') if ':' in part for key,value in [part.split(':',1)]}


def inherited(element, property_name):
    for node in [element, *element.parents]:
        if getattr(node,'attrs',None) is not None:
            value = styles(node).get(property_name)
            if value is not None:
                return value
    return None


@pytest.mark.parametrize('path', ['preview','api','clipboard'])
def test_decorations_and_text_keep_separate_line_boxes(path):
    theme = manifest()
    original = copy.deepcopy(theme)
    config = {'palette':theme['palette'],'generated_design_system':theme['design_system']}
    body = '这段文字可以换行；图片装饰和分隔线不能让正文继承零行高。'
    markup = render_layout('quote',{'body':body},config)
    decorations = compiled_decoration_assets(markup)
    assert len(decorations) == 1  # Repeated ornaments share their deterministic PNG.
    document = '<main>' + replace_asset_urls(markup,{a['source_url']:a['asset_token'] for a in decorations}) + '</main>'
    if path == 'api':
        document = _responsive_delivery_document(document)
    elif path == 'clipboard':
        assets = [{'id':a['asset_token'],'asset_token':a['asset_token'],'asset_role':'theme_decoration'} for a in decorations]
        document = build_clipboard_payload({'frozen_html':document,'metadata':{'title':'零行高隔离测试'}},assets,lambda key:'http://127.0.0.1/controlled/'+key)['html']
    soup = BeautifulSoup(document,'html.parser')
    assert soup.select_one('[data-theme-field="body"]').get_text() == body
    assert soup.select_one('[data-theme-static]').get_text() == '阅读提示'
    assert len(soup.select('img[data-theme-decoration]')) == 2
    zero_boxes = [node for node in soup.select('[style]') if styles(node).get('line-height') == '0']
    assert zero_boxes
    for box in zero_boxes:
        assert not box.get_text().replace('\u200b','').replace('\xa0','').strip()
        assert not box.select('[data-theme-field],[data-theme-static]')
    for text in soup.select('[data-theme-field],[data-theme-static]'):
        assert inherited(text,'line-height') not in (None,'0','0px')
        assert inherited(text,'font-size') not in (None,'0','0px')
    assert theme == original


def test_gradient_edge_risk_does_not_become_automatic_wechat_pass():
    theme = manifest()
    before = copy.deepcopy(theme)
    report = theme_delivery_report(theme)
    warnings = [finding for finding in report['findings'] if finding['code'] == 'gradient_edge']
    assert len(warnings) == 1 and warnings[0]['role'] == 'quote'
    assert warnings[0]['severity'] == 'review'
    assert report['rehearsal']['status'] == 'pass'
    assert report['local_delivery'] == 'review_required'
    assert report['wechat_saved_roundtrip'] == 'not_verified'
    assert theme == before
