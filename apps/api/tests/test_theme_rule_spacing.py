"""Rules are decoration, never an inherited paragraph-height empty block."""
import copy
from bs4 import BeautifulSoup
import pytest

from visual_director.brief_compiler import visual_system_configuration
from visual_director.theme_layouts import render_layout
from visual_director.delivery import _responsive_delivery_document, build_clipboard_payload


def config():
    c=copy.deepcopy(visual_system_configuration('oriental_archive'))
    c['generated_design_system']={
        'typography':{'heading_scale':1,'body_scale':1,'heading_weight':700,'letter_spacing':'normal'},
        'rhythm':{'density':'balanced','section_gap':34,'component_gap':24},
        'layouts':{'lead':{'type':'stack','style':{'padding':[14,16,14,18]},'children':[
            {'type':'field','bind':'body'},
            {'type':'rule','style':{'margin':[10,0,0,0],'border_top':{'width':1,'style':'dashed','color':'secondary'}}}
        ]}}
    }
    return c


@pytest.mark.parametrize('path',['preview','api','clipboard'])
def test_rule_retains_border_without_an_inherited_linebox(path):
    c=config()
    before=copy.deepcopy(c)
    markup=render_layout('lead',{'body':'正文保持可编辑'},c)
    document='<html><body><main>'+markup+'</main></body></html>'
    if path=='api':
        document=_responsive_delivery_document(document)
    elif path=='clipboard':
        document=build_clipboard_payload({'frozen_html':document,'metadata':{'title':'测试'}},[],lambda _: '')['html']
    soup=BeautifulSoup(document,'html.parser')
    rule=soup.select_one('[data-theme-rule]')
    styles=dict(item.split(':',1) for item in rule['style'].split(';') if ':' in item)
    assert styles['font-size']==styles['line-height']==styles['height']==styles['min-height']=='0'
    assert styles['overflow']=='hidden'
    assert styles['margin']=='10px 0px 0px 0px'
    assert styles['border-top'].startswith('1px dashed')
    assert rule.get_text()=='\u200b'
    assert soup.select_one('[data-theme-field="body"]').get_text()=='正文保持可编辑'
    assert c==before


def test_unstyled_rules_get_the_same_protection():
    c=config()
    c['generated_design_system']['layouts']['lead']['children'][1]={'type':'rule'}
    html=render_layout('lead',{'body':'text'},c)
    assert 'data-theme-rule="true"' in html
    assert 'line-height:0;height:0;' in html
