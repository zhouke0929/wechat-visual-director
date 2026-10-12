"""Optional Playwright companion for `theme review`; never calls WeChat.

Requires a host-provided Python + Playwright environment. Without it, inspect
the generated HTML using the host browser; do not require end users to install
Python just to create a theme.
"""
import argparse
import base64
import html
import hashlib
import json
import struct
from html.parser import HTMLParser
from pathlib import Path


MEASURE = """e => {
  const r=e.getBoundingClientRect();
  const overflow=[...e.querySelectorAll('*')].some(n=>{
    const b=n.getBoundingClientRect();return b.left<r.left-1||b.right>r.right+1;
  });
    return {overflow,container_width:r.width,broken_images:[...e.querySelectorAll('img')].filter(i=>!i.complete||!i.naturalWidth).length,
    height:r.height, fields:[...e.querySelectorAll('[data-theme-field]')].map(f=>{
      const s=getComputedStyle(f), b=f.getBoundingClientRect();
      const net=f.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight);
      const font=parseFloat(s.fontSize);const text=f.textContent.trim();
      const line=parseFloat(s.lineHeight);
      const rows=new Map(), walker=document.createTreeWalker(f,NodeFilter.SHOW_TEXT);
      let textNode;
      while(textNode=walker.nextNode()){
        for(let i=0;i<textNode.length;i++){
          const range=document.createRange();range.setStart(textNode,i);range.setEnd(textNode,i+1);
          const box=range.getBoundingClientRect();if(!box.width||!box.height)continue;
          const top=Math.round(box.top);rows.set(top,(rows.get(top)||'')+textNode.textContent[i]);
        }
      }
      const lines=[...rows.values()].map(s=>s.trim()).filter(Boolean);
      let sidecar=null;
      // A decorative column may end well before a short multi-line title.
      // Inspect rendered sibling columns, not a theme name or text length.
      if(f.dataset.themeField==='title'&&b.height>=line*1.8){
        for(let col=f;col&&col!==e;col=col.parentElement){
          if(getComputedStyle(col).display!=='inline-block')continue;
          for(const peer of col.parentElement.children){
            if(peer===col||getComputedStyle(peer).display!=='inline-block')continue;
            if(peer.querySelector('[data-theme-field]')||peer.textContent.trim())continue;
            const art=[...peer.querySelectorAll('img,[aria-hidden="true"]')]
              .map(n=>n.getBoundingClientRect()).filter(a=>a.width>0&&a.height>0);
            if(!art.length)continue;
            const bottom=Math.max(...art.map(a=>a.bottom));
            const blank=Math.max(0,b.bottom-bottom), column=peer.getBoundingClientRect();
            if(blank>=line*.8&&column.width>=font){
              sidecar={column_width:column.width,unused_height:blank,title_lines:b.height/line};
            }
          }
        }
      }
      return {field:f.dataset.themeField,content_width:net,font_size:font,height:b.height,
        approximate_cjk_per_line:net/font,text_length:text.length,
        narrow_long_text:text.length>=70&&net/font<9,title_sidecar_review:sidecar,
        rendered_lines:lines,last_line_single_cjk_review:f.dataset.themeField==='title'&&lines.length>1&&/^[\\u3400-\\u9fff]$/.test(lines.at(-1))};
    })};
}"""


class _ReferenceImages(HTMLParser):
    """Extract only embedded reference PNGs from core-generated review index."""
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        source = dict(attrs).get('src', '')
        if tag == 'img' and source.startswith('data:image/png;base64,'):
            try:
                data = base64.b64decode(source.split(',', 1)[1], validate=True)
            except ValueError:
                return
            if data.startswith(b'\x89PNG\r\n\x1a\n'):
                self.sources.append(source)


def _screenshot_uri(directory, record):
    name = record.get('screenshot', '')
    if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name:
        raise ValueError('Invalid comparison screenshot path')
    path = (directory / name).resolve()
    if path.parent != directory.resolve() or path.suffix != '.png':
        raise ValueError('Comparison screenshots must stay inside their report directory')
    data = path.read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Comparison screenshot is not a PNG')
    return 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')


def _overview_scale(report):
    profile_id = report.get('overview_profile')
    if profile_id:
        profile = next(p for p in report['preview_config']['profiles'] if p['id'] == profile_id)
        return profile['viewport_width'] - 2 * report['preview_config']['body_padding_x'], profile_id
    # Historical reports remain viewable, explicitly at their old net width.
    return 390, None


def _at_scale(record, width, profile_id):
    return record['content_width'] == width and record.get('profile_id') == profile_id


def select_review_pages(manifest, requested_roles=None):
    """Select fresh evidence, never merge stale roles into a new theme report."""
    available = {role for page in manifest['pages'] for role in page['roles']}
    if requested_roles is not None:
        if not requested_roles:
            raise ValueError('Select at least one review role')
        unknown = set(requested_roles) - available
        if unknown:
            raise ValueError('Unknown review roles: ' + ', '.join(sorted(unknown)))
    selected = available if requested_roles is None else set(requested_roles)
    pages = []
    for page in manifest['pages']:
        roles = [role for role in page['roles'] if role in selected]
        if roles:
            pages.append({**page, 'roles': roles})
    count = sum(len(page['roles']) for page in pages)
    return pages, {
        'check_scope': 'full_bundle' if selected == available else 'selected_roles',
        'checked_roles': sorted(selected), 'unchecked_roles': sorted(available - selected),
        'expected_case_count': count, 'full_bundle_case_count': manifest['case_count'],
    }


def _scope_notice(report):
    if report.get('check_scope') != 'selected_roles':
        return ''
    checked = ', '.join(report.get('checked_roles', []))
    unchecked = ', '.join(report.get('unchecked_roles', []))
    return (f'<p><strong>局部复核，不是全主题验收。</strong>本轮检查：{html.escape(checked)}；'
            f'未检查：{html.escape(unchecked)}。旧版截图不代表这些角色在当前版本已复测。</p>')


def build_visual_comparison(review, output, report, previous=None):
    """A human/agent inspection aid, never an aesthetic score or pass gate."""
    old = json.loads((previous / 'browser-report.json').read_text(encoding='utf-8')) if previous else {}
    # Match actual fixture role, length and width; do not compare different widths.
    key = lambda r: (r['role'], r['length'], r['content_width'], r.get('profile_id'), r.get('font_scale'))
    old_cases = {key(r): r for r in old.get('cases', [])}
    refs = _ReferenceImages()
    refs.feed((review / 'index.html').read_text(encoding='utf-8'))
    reference_html = ''.join(f'<img alt="参考 {i+1}" src="{html.escape(src, quote=True)}">'
                             for i, src in enumerate(refs.sources))
    groups = []
    width, profile_id = _overview_scale(report)
    for record in report['cases']:
        if record['length'] != 'short' or not _at_scale(record, width, profile_id):
            continue
        role = html.escape(record['role'])
        before = old_cases.get(key(record))
        before_html = (f'<img alt="修改前 {role}" src="{_screenshot_uri(previous, before)}">'
                       if before else '<p>无匹配的修改前截图</p>')
        after = _screenshot_uri(output, record)
        long_record = next((r for r in report['cases'] if r['role'] == record['role']
                            and r['length'] == 'long' and r['content_width'] == 320), None)
        long_html = (f'<details><summary>展开 320px 长文</summary><img style="width:320px" '
                     f'alt="长文 {role}" src="{_screenshot_uri(output, long_record)}"></details>'
                     if long_record else '')
        groups.append(f'<section><h2>{role}</h2><div class="pair"><figure><figcaption>修改前 · 正文 {width}px</figcaption>{before_html}</figure>'
                      f'<figure><figcaption>当前 · 正文 {width}px</figcaption><img alt="当前 {role}" src="{after}">{long_html}</figure></div></section>')
    hashes = html.escape(f"修改前 {old.get('theme_sha256', '未提供')} / 当前 {report['theme_sha256']}")
    document = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'">'
        '<title>主题参考与修订对照</title><style>body{margin:24px auto;padding:0 20px;max-width:1000px;font:16px/1.7 sans-serif;color:#243a3b;background:#fff}'
        'h2{font-size:20px}.references img{max-width:100%;display:block;margin:12px 0}.pair{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}'
        f'figure{{margin:0;width:{width}px;max-width:100%}}figure img{{max-width:100%;height:auto}}figcaption{{color:#667}}section{{border-top:1px solid #ddd;padding:20px 0}}'
        'code{overflow-wrap:anywhere;font-size:11px}summary{cursor:pointer}details{margin-top:12px}</style>'
        '<h1>主题参考与修订对照</h1><p>这是视觉检查材料，不是自动通过报告。先看参考中的轮廓、贴附与比例，再看当前组件是否实际体现；'
        '修复溢出后也要重新比较。短文同宽并列，长文可展开；若两轮更改过测试文案，另行核对，不能直接比较高度。</p>'
        f'<p><code>{hashes}</code></p>{_scope_notice(report)}<details class="references" open><summary>实际参考</summary>{reference_html or "<p>未提供参考图片</p>"}</details>'
        + ''.join(groups) + '</html>')
    path = output / 'visual-comparison.html'
    path.write_text(document, encoding='utf-8')
    return str(path.resolve())


OVERVIEW_GROUPS = (
    ('emphasis', '重点与信息关系', ('question_hook', 'faq_card', 'evidence_callout', 'case_card',
                                'comparison_card', 'before_after_timeline', 'concept_explainer', 'section_summary')),
    ('identity', '标题与图文', ('hero', 'heading', 'subheading', 'quote', 'image_caption')),
    ('reading', '列表与阅读节奏', ('lead', 'list', 'numbered_insight', 'logic_path',
                                'action_checklist', 'warning_note', 'divider', 'closing_cta')),
)


def build_component_overview(output, report, screenshots=None):
    """Same-width role families; preserve natural heights and the source evidence."""
    source = (screenshots or output).resolve()
    width, profile_id = _overview_scale(report)
    records = {r['role']: r for r in report['cases']
               if r['length'] == 'short' and _at_scale(r, width, profile_id)}
    sections, groups, used = [], [], set()
    definitions = list(OVERVIEW_GROUPS)
    extra = sorted(set(records) - {r for _, _, roles in definitions for r in roles})
    if extra:
        definitions.append(('other', '其他角色', tuple(extra)))
    for group_id, title, roles in definitions:
        cards, present = [], []
        for role in roles:
            if role not in records:
                continue
            record = records[role]
            # The screenshot must actually be the declared width. CSS must not
            # stretch unrelated evidence into a convincing same-scale diagram.
            uri = _screenshot_uri(source, record)
            data = base64.b64decode(uri.split(',', 1)[1])
            if len(data) < 24 or data[12:16] != b'IHDR' or struct.unpack('>I', data[16:20])[0] != width:
                raise ValueError(f'Overview requires native {width}px screenshots')
            escaped = html.escape(role, quote=True)
            cards.append(f'<figure data-overview-role="{escaped}"><figcaption>{escaped}</figcaption>'
                         f'<img width="{width}" alt="{escaped} · 正文 {width}px" src="{uri}"></figure>')
            present.append(role)
            used.add(role)
        if not cards:
            continue
        grid = '<div class="grid">' + ''.join(cards) + '</div>'
        # The cropped PNG must retain the same scope warning as the HTML.
        note = ('<p data-overview-scope="selected_roles">局部复核 · 当前仅检查：'
                + html.escape(', '.join(report.get('checked_roles', [])))
                + '；不是全主题验收。</p>') if report.get('check_scope') == 'selected_roles' else ''
        sections.append(f'<section id="{group_id}"><h2>{title}</h2>'
                        f'<div class="sheet" data-overview-sheet="{group_id}">{note}{grid}</div>'
                        f'<details><summary>灰度辅助查看轮廓</summary><div class="sheet grayscale">{note}{grid}</div></details></section>')
        groups.append({'id': group_id, 'roles': present, 'screenshot': f'component-overview-{group_id}.png'})
    if not used:
        raise ValueError(f'No short {width}px screenshots for component overview')
    document = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'">'
        '<title>主题组件同尺度总览</title><style>'
        'body{margin:24px;font:15px/1.7 "Microsoft YaHei",sans-serif;color:#243a3b;background:#fff}'
        'section{margin:28px 0}h1{font-size:24px}h2{font-size:18px}code{font-size:11px;overflow-wrap:anywhere}'
        f'.sheet{{width:{2*width+48}px;padding:12px;background:#f3f5f2}}.grid{{display:grid;grid-template-columns:{width}px {width}px;gap:24px;align-items:start}}'
        f'figure{{margin:0;width:{width}px;min-width:{width}px}}figcaption{{font-size:12px;color:#526a66;margin:0 0 6px}}'
        f'img{{display:block;width:{width}px;max-width:none;height:auto}}.grayscale img{{filter:grayscale(1)}}'
        'details{margin-top:14px}summary{cursor:pointer}</style>'
        f'<h1>主题组件同尺度总览</h1><p>每个组件保留 {width}px 原始净宽和自然高度；{("工作台手机主验收" if profile_id == "mobile" else "历史补充尺寸，不代表当前工作台")}；按阅读任务放在一起看。'
        '观察标题、容器、图片与装饰的关系是否反复相同，再回到正常文章检查连续阅读。'
        '灰度只帮助观察轮廓，仍保留图标与文字，不能自动判定设计重复或美观。</p>'
        f'<p><code>主题 {html.escape(report["theme_sha256"])} / 渲染器 {html.escape(report.get("renderer_version", "未知"))}</code></p>{_scope_notice(report)}'
        + ''.join(sections) + '</html>')
    path = output / 'component-overview.html'
    path.write_text(document, encoding='utf-8')
    return {'schema_version': 'theme_component_overview.v1', 'theme_sha256': report['theme_sha256'],
            'renderer_version': report.get('renderer_version'), 'content_width': width,
            'profile_id': profile_id,
            **{k: report[k] for k in ('check_scope', 'checked_roles', 'unchecked_roles') if k in report},
            'length': 'short', 'roles': sorted(used), 'groups': groups,
            'overview_file': str(path.resolve()), 'visual_review': 'not_verified'}


def capture_component_overview(output, report, browser_path=None, screenshots=None):
    overview = build_component_overview(output, report, screenshots)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, **({'executable_path': browser_path} if browser_path else {}))
        page = browser.new_page(viewport={'width': 900, 'height': 900}, device_scale_factor=1)
        page.route('http://**/*', lambda route: route.abort())
        page.route('https://**/*', lambda route: route.abort())
        page.goto(Path(overview['overview_file']).as_uri(), wait_until='load')
        page.evaluate('() => Promise.all([...document.images].map(i => i.decode()))')
        for group in overview['groups']:
            page.locator(f'[data-overview-sheet="{group["id"]}"]').screenshot(path=str(output / group['screenshot']))
        browser.close()
    (output / 'component-overview.json').write_text(json.dumps(overview, ensure_ascii=False, indent=2), encoding='utf-8')
    return overview


def build_article_preview_entry(output, profiles):
    """Navigate captured documents, not a width-only imitation of profiles."""
    primary = [p for p in profiles if p.get('primary')]
    if not primary:
        primary = profiles[:1]
    labels = {'mobile': '手机阅读', 'proof': '校对阅读'}
    buttons = ''.join(
        f'<button type="button" data-article-profile="{p["id"]}">{html.escape(labels.get(p["id"], p["id"]))}</button>'
        for p in primary)
    settings = {p['id']: {'file': p['preview_file'], 'width': p['viewport_width']} for p in primary}
    first = primary[0]
    doc = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>完整文章预览</title><style>body{margin:0;background:#f5f3ef;font:14px/1.6 system-ui}'
        'nav{padding:12px 16px;background:white;display:flex;gap:12px;align-items:center;flex-wrap:wrap}'
        'button{padding:7px 14px;background:white;border:1px solid #b9b0a3;cursor:pointer}'
        'button[aria-pressed="true"]{background:#e8e3d9}'
        'iframe{display:block;max-width:100%;height:calc(100vh - 72px);border:0;margin:16px auto;background:white}'
        '</style><body><nav><span>完整文章</span>' + buttons
        + f'<a href="component-overview.html">组件总览</a></nav><iframe id="article" title="完整文章" '
        + f'src="{first["preview_file"]}" style="width:{first["viewport_width"]}px"></iframe>'
        + '<script>const profiles=' + json.dumps(settings) + ';'
        + 'function selectProfile(id){const p=profiles[id];if(!p)return;const f=document.getElementById("article");'
        + 'f.src=p.file;f.style.width=p.width+"px";document.querySelectorAll("[data-article-profile]")'
        + '.forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.articleProfile===id)));}'
        + 'document.querySelectorAll("[data-article-profile]").forEach(b=>b.addEventListener("click",()=>selectProfile(b.dataset.articleProfile)));'
        + 'selectProfile(' + json.dumps(first['id']) + ');</script></body></html>')
    (output / 'article-preview.html').write_text(doc, encoding='utf-8')
    return 'article-preview.html'


def capture_normal_article(page, article, output, manifest):
    """Read a rendered article; never rewrite it or turn hints into acceptance."""
    config = manifest['preview_config']
    ids = [p['id'] for p in config['profiles']]
    if len(ids) != len(set(ids)) or any(i not in {'mobile', 'proof', 'narrow', 'legacy'} for i in ids):
        raise ValueError('Invalid article preview profile ids')
    records = []
    for profile in config['profiles']:
        page.set_viewport_size({'width': profile['viewport_width'], 'height': 950})
        page.goto(article.resolve().as_uri(), wait_until='load')
        page.evaluate('''p => {
          document.documentElement.dataset.workbenchPreviewMode=p.mode;
          document.querySelectorAll('[style]').forEach(e=>{
            const v=e.style.fontSize;
            if(v.endsWith('px')&&parseFloat(v)>0)e.style.fontSize=`${Math.round(parseFloat(v)*p.font_scale*100)/100}px`;
          });
        }''', profile)
        page.add_style_tag(content=config['normalization_css'] + config['mobile_css'])
        page.evaluate('() => Promise.all([...document.images].map(i=>i.decode().catch(()=>{})))')
        # Persist the exact adjusted DOM that is measured. A base keeps local
        # relative assets anchored to the source when the result is elsewhere.
        page.evaluate('''p => {
          document.documentElement.dataset.articlePreviewProfile=p.id;
          if(!document.querySelector('base')){
            const base=document.createElement('base');base.href=p.source;
            document.head.prepend(base);
          }
        }''', {'id': profile['id'], 'source': article.resolve().as_uri()})
        preview_file = f'article-{profile["id"]}.html'
        (output / preview_file).write_text(page.content(), encoding='utf-8')
        metric = page.locator('body').evaluate(MEASURE)
        observed = page.locator('main').evaluate('e=>e.getBoundingClientRect().width')
        expected = profile['viewport_width'] - 2 * config['body_padding_x']
        full = f'article-{profile["id"]}.png'
        page.screenshot(path=str(output / full), full_page=True)
        height = page.evaluate('document.documentElement.scrollHeight')
        parts = []
        for label, y in [('start', 0), ('middle', max(0, (height-950)/2)), ('end', max(0, height-950))]:
            page.evaluate('y=>window.scrollTo(0,y)', y)
            page.wait_for_timeout(100)
            name = f'article-{profile["id"]}-{label}.png'
            page.screenshot(path=str(output / name))
            parts.append(name)
        headings = page.locator('[data-theme-layout="heading"]').evaluate_all(
            'nodes=>nodes.map(e=>({text:e.textContent.trim(),top:e.getBoundingClientRect().top+window.scrollY}))')
        records.append({**profile, 'preview_file': preview_file, 'content_width': expected, 'observed_content_width': observed,
                        'width_matches_profile': abs(observed-expected)<1, 'screenshot': full,
                        'section_screenshots': parts, 'headings': headings, **metric})
    entry_file = build_article_preview_entry(output, records)
    result = {'source_sha256': hashlib.sha256(article.read_bytes()).hexdigest(),
              'preview_entry': entry_file,
              'review_theme_sha256': manifest['theme_sha256'], 'review_renderer_version': manifest['renderer_version'],
              'article_theme_binding': 'not_verified',
              'geometry': 'pass' if all(not r['overflow'] and not r['broken_images'] and r['width_matches_profile'] for r in records) else 'fail',
              'single_cjk_title_reviews': [dict(profile_id=r['id'], primary=r['primary'], lines=f['rendered_lines'])
                                           for r in records for f in r['fields'] if f['last_line_single_cjk_review']],
              'visual_review': 'not_verified', 'wechat_saved_roundtrip': 'not_verified', 'profiles': records}
    (output / 'article-browser-report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--browser', help='Optional Chromium/Edge executable')
    parser.add_argument('--previous-output', type=Path, help='Earlier screenshot directory; adds same-width visual comparisons')
    parser.add_argument('--reuse-report', type=Path, help='Existing browser-report.json; create only the overview in a new output directory')
    parser.add_argument('--article', type=Path, help='Production-rendered normal article HTML; capture using the same workbench profiles')
    parser.add_argument('--roles', nargs='+', help='Capture only these affected roles; partial evidence, not final full-theme acceptance')
    args = parser.parse_args()
    root = args.review.resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') not in {'theme_review.v1', 'theme_review.v2'}:
        raise ValueError('Not a theme_review bundle')
    if args.article and (args.reuse_report or not manifest.get('preview_config')):
        raise ValueError('Article capture requires a fresh theme_review.v2 check')
    if args.reuse_report and args.roles is not None:
        raise ValueError('Reused overview preserves its original scope; do not combine --reuse-report with --roles')
    if args.output.exists():
        raise ValueError('Use a new output directory to preserve earlier evidence')
    if args.reuse_report:
        report = json.loads(args.reuse_report.read_text(encoding='utf-8'))
        if (report['theme_sha256'] != manifest['theme_sha256']
                or report.get('renderer_version') != manifest.get('renderer_version')
                or report.get('preview_config') != manifest.get('preview_config')):
            raise ValueError('Reused report must match the review theme and renderer')
        args.output.mkdir(parents=True)
        overview = capture_component_overview(args.output, report, args.browser, args.reuse_report.resolve().parent)
        print(json.dumps(overview, ensure_ascii=False))
        return 0
    pages, scope = select_review_pages(manifest, args.roles)
    from playwright.sync_api import sync_playwright
    args.output.mkdir(parents=True)
    records = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, **({'executable_path': args.browser} if args.browser else {}))
        page = browser.new_page()
        # These fixtures are self-contained. Never allow a modified review to
        # send requests off-machine while it is being measured.
        page.route('http://**/*', lambda route: route.abort())
        page.route('https://**/*', lambda route: route.abort())
        for case in pages:
            path = (root / case['file']).resolve()
            if path.parent != root or path.suffix != '.html':
                raise ValueError('Invalid review page path')
            page.set_viewport_size({'width': case.get('viewport_width', case['content_width']), 'height': 900})
            page.goto(path.as_uri(), wait_until='load')
            page.evaluate('() => Promise.all([...document.images].map(i => i.decode().catch(()=>{})))')
            for role in case['roles']:
                if not role.replace('_', '').isalnum():
                    raise ValueError('Invalid role')
                node = page.locator(f'[data-review-role="{role}"]')
                metric = node.evaluate(MEASURE)
                name = f'{role}-{case["length"]}-{case.get("id", case["content_width"])}.png'
                node.screenshot(path=str(args.output / name))
                records.append({'role': role, 'length': case['length'], 'content_width': case['content_width'],
                    **({k: case[k] for k in ('viewport_width', 'primary', 'mode', 'font_scale')} if 'id' in case else {}),
                    **({'profile_id': case['id']} if 'id' in case else {}), 'screenshot': name, **metric})
        article_report = capture_normal_article(page, args.article, args.output, manifest) if args.article else None
        browser.close()
    failures = [r for r in records if r['overflow'] or r['broken_images'] or abs(r['container_width']-r['content_width'])>=1]
    narrow = [r for r in records if any(f['narrow_long_text'] for f in r['fields'])]
    sidecars = [r for r in records if any(f['title_sidecar_review'] for f in r['fields'])]
    result = {'theme_sha256': manifest['theme_sha256'], 'renderer_version': manifest['renderer_version'],
        **scope,
        'case_count': len(records), 'missing_roles': manifest['missing_roles'],
        'geometry': 'pass' if not failures and len(records) == scope['expected_case_count']
                    and (scope['check_scope'] != 'full_bundle' or len(records) == manifest['case_count']) else 'fail',
        'failure_count': len(failures), 'narrow_text_review_count': len(narrow),
        'title_sidecar_review_count': len(sidecars),
        'single_cjk_title_review_count': sum(any(f['last_line_single_cjk_review'] for f in r['fields']) for r in records),
        'visual_review': 'not_verified', 'normal_article': 'not_verified',
        'wechat_saved_roundtrip': 'not_verified', 'cases': records}
    result['full_bundle_geometry'] = result['geometry'] if scope['check_scope'] == 'full_bundle' else 'not_verified'
    if manifest.get('preview_config'):
        result.update(preview_config=manifest['preview_config'], overview_profile=manifest['overview_profile'])
    if article_report:
        result['normal_article'] = 'browser_checked_not_visual_acceptance'
        result['article_report_file'] = str((args.output / 'article-browser-report.json').resolve())
        result['article_geometry'] = article_report['geometry']
        result['article_preview_file'] = str((args.output / article_report['preview_entry']).resolve())
        result['article_single_cjk_title_review_count'] = len(article_report['single_cjk_title_reviews'])
    result['visual_comparison_file'] = build_visual_comparison(root, args.output, result, args.previous_output)
    overview = capture_component_overview(args.output, result, args.browser)
    result['component_overview_file'] = overview['overview_file']
    result['component_overview_images'] = [str((args.output / g['screenshot']).resolve()) for g in overview['groups']]
    (args.output / 'browser-report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, ensure_ascii=False))
    return 1 if result['geometry'] != 'pass' or (article_report and article_report['geometry'] != 'pass') else 0


if __name__ == '__main__':
    raise SystemExit(main())
