"""Bounded filled contours stay decorative; prose and delivery remain independent."""
import io
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator
from PIL import Image

from visual_director.theme_drawings import drawing_png, validate_drawing
from visual_director.delivery import _responsive_delivery_document, build_clipboard_payload
from visual_director.theme_layouts import PALETTE_KEYS, render_layout, validate_layouts
from visual_director.theme_delivery import compiled_decoration_assets
from visual_director.publication import check_frozen_html, replace_asset_urls, strip_workbench_editor_attributes

ROOT=Path(__file__).resolve().parents[3]
PALETTE=dict.fromkeys(PALETTE_KEYS,'#FFFFFF') | {'primary':'#D94A2F','ink':'#352925'}

def cap():
    return {'type':'drawing','width':160,'height':8,'sizing':'full_width','parts':[
        {'kind':'polygon','points':[[0,8],[12,0],[148,0],[160,8]],'fill':'primary','stroke':'primary','stroke_width':.5}]}

def config():
    m=json.loads((ROOT/'skills/wechat-visual-director/assets/theme-pack-template.json').read_text(encoding='utf-8'))
    m['design_system']['layouts']={'quote':{'type':'stack','children':[cap(),{'type':'field','bind':'body'}]}}
    return {'palette':PALETTE,'generated_design_system':m['design_system']}

def test_polygon_schema_core_pixels_and_delivery():
    node=cap()
    schema=json.loads((ROOT/'contracts/theme-pack-v1.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator({'$ref':'#/$defs/layoutNode','$defs':schema['$defs']}).validate(node)
    assert validate_drawing(node,PALETTE_KEYS)==[]
    data=drawing_png(node,PALETTE)
    with Image.open(io.BytesIO(data)) as im:
        assert im.size==(640,32)
        assert im.getpixel((0,0))[3]==0
        assert im.getpixel((320,16))[:3]==(217,74,47)
    # Sizing changes layout, not asset bytes: same bitmap can be deduplicated.
    assert data==drawing_png(dict(node,sizing='natural'),PALETTE)
    text='保留原文 <不是标签> & 长短文案都可以编辑。'
    document=render_layout('quote',{'body':text},config())
    soup=BeautifulSoup(document,'html.parser')
    assert soup.select_one('[data-theme-field="body"]').get_text()==text
    assert not soup.select('svg,script')
    assets=compiled_decoration_assets(document)
    assert len(assets)==1
    frozen=strip_workbench_editor_attributes(replace_asset_urls(document,{a['source_url']:a['asset_token'] for a in assets}))
    assert check_frozen_html(frozen).status=='pass'
    assert 'width:100%' in BeautifulSoup(frozen,'html.parser').select_one('img')['style']

@pytest.mark.parametrize('patch',[
    {'points':[[0,0],[1,1]]}, {'points':[[0,0],[160,0],[161,8]]},
    {'points':[[0,0],[160,0],[float('nan'),8]]}, {'fill':'url(https://example.com)'},
    {'fill':[]}, {'onclick':'run()'}, {'stroke_width':True},
])
def test_reject_invalid_polygon(patch):
    node=cap(); node['parts'][0].update(patch)
    assert validate_drawing(node,PALETTE_KEYS)
    with pytest.raises(ValueError): drawing_png(node,PALETTE)

def test_sizing_is_bounded_and_no_field_loss():
    for sizing in ['cover',{},None]:
        assert validate_drawing(dict(cap(),sizing=sizing),PALETTE_KEYS)
    c=config()
    assert not validate_layouts(c['generated_design_system']['layouts'])
    c['generated_design_system']['layouts']['quote']['children'].append({'type':'field','bind':'body'})
    assert validate_layouts(c['generated_design_system']['layouts'])

@pytest.mark.parametrize('delivery_path',['preview','api_preparation','clipboard'])
def test_full_width_caps_follow_container_without_covering_text(delivery_path,tmp_path):
    pw=pytest.importorskip('playwright.sync_api')
    with pw.sync_playwright() as p:
        try: browser=p.chromium.launch(headless=True)
        except pw.Error: pytest.skip('Chromium unavailable; run local visual matrix separately')
        try:
            page=browser.new_page()
            for width in (320,390,600):
                for text in ['短句。','长正文保持独立可编辑，不挤进图形内部。'*30]:
                    page.set_viewport_size({'width':width,'height':900})
                    document='<main>'+render_layout('quote',{'body':text},config())+'</main>'
                    assets=compiled_decoration_assets(document)
                    frozen=strip_workbench_editor_attributes(replace_asset_urls(document,{a['source_url']:a['asset_token'] for a in assets}))
                    if delivery_path=='api_preparation':
                        # Local URL substitution only; does not contact WeChat.
                        document=_responsive_delivery_document(frozen)
                        for asset in assets:
                            document=document.replace('asset://'+asset['asset_token'],asset['source_url'])
                    elif delivery_path=='clipboard':
                        for asset in assets:
                            asset['id']=asset['asset_token']
                            (tmp_path/(asset['id']+'.png')).write_bytes(asset['content'])
                        payload=build_clipboard_payload({'frozen_html':frozen,'metadata':{'title':'测试'}},assets,lambda _: '',read_asset=lambda asset_id:(tmp_path/(asset_id+'.png'),'image/png'))
                        assert payload['image_transport']=='embedded_data'
                        assert 'asset://' not in payload['html']
                        document=payload['html']
                    page.set_content('<body style="margin:0">'+document,wait_until='networkidle')
                    assert page.locator('[data-theme-field]').inner_text()==text
                    bounds=page.evaluate('''()=>{const a=document.querySelector('img').getBoundingClientRect(),b=document.querySelector('[data-theme-field]').getBoundingClientRect();return {width:a.width,height:a.height,bottom:a.bottom,top:b.top,overflow:document.documentElement.scrollWidth>innerWidth}}''')
                    assert bounds['width']==pytest.approx(width)
                    assert bounds['height']==pytest.approx(width/20)
                    assert bounds['bottom']<=bounds['top']+.5
                    assert not bounds['overflow']
        finally: browser.close()
