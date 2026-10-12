"""Offline review fixtures, compiled by the production theme renderer.

No service, installation, private task data or WeChat credentials are needed.
Fixture generation is not a visual or saved-roundtrip acceptance result.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
from pathlib import Path

from PIL import Image

from .component_catalog import RENDERER_VERSION, VISUAL_SYSTEM_ORDER, CORE_THEME_COMPONENTS
from .generated_theme import render_generated_heading
from .theme_layouts import ROLE_FIELDS, render_layout
from .theme_packs import THEME_PACK_MAX_BYTES, validate_theme_pack_bytes
from .preview_profiles import BODY_PADDING_X, PREVIEW_CONFIG, REVIEW_PROFILES, preview_css, scale_preview_fonts


def review_payload(long: bool = False) -> dict:
    body = "先观察眼前的细节，给临时停留留出空间；记录实际感受，不补写没有发生的故事。"
    return {
        "title": "怎样为一次新的尝试保留余量" if not long else "面对不同的选择与临时变化，怎样保留清楚的判断，同时找到适合自己的下一步",
        "kicker": "阅读指南", "index": "01",
        "body": body * (5 if long else 1),
        "left": "先确定大致方向，考虑已有条件与需要解决的问题。" * (6 if long else 1),
        "right": "根据实际反馈调整，不把完成计划当作唯一目标，也保留重新选择的空间。" * (5 if long else 1),
        "items": [text * (3 if long else 1) for text in (
            "看清现有条件，记下具体感受而不是预先准备好的评价。",
            "留出调整空间，尝试之后再判断哪些安排适合自己。",
            "只记录能够确认的信息，不替其他人补写经历。")],
        "entries": [{"title": title, "body": body * (4 if long else 1)} for title in ("观察与判断", "记录与回顾")],
        "caption": "本地布局测试图片，不是为本篇生成的成稿配图。" * (3 if long else 1),
        "media": {"src": "/api/v1/theme-review-image", "alt": "本地布局测试图片"},
    }


def _image_uri(path: Path) -> str:
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("自检图片不得超过 16 MiB")
    with Image.open(path) as image:
        if image.format not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > 25_000_000:
            raise ValueError("自检图片须为不超过 2500 万像素的 PNG/JPEG/WebP")
        image.load()
        image = image.convert("RGBA")
        image.thumbnail((1600, 1600))
        stream = io.BytesIO()
        image.save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def _page(title: str, body: str, profile: dict | None = None) -> str:
    style = "width:100%;max-width:100%;margin:auto" if profile else "max-width:1000px;margin:auto;padding:24px"
    mode = f' data-workbench-preview-mode="{profile["mode"]}"' if profile else ''
    padding = f'padding:0 {BODY_PADDING_X}px;' if profile else ''
    return (f'<!doctype html><html lang="zh-CN"{mode}><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'">'
            f'<title>{html.escape(title)}</title><style>{preview_css()}</style>'
            f'<body style="box-sizing:border-box;margin:0;{padding}background:#fff;font-family:\'Noto Sans SC\',\'Microsoft YaHei\',Arial,sans-serif;">'
            f'<main style="{style}">{body}</main></body></html>')


def build_theme_review(file: Path, output: Path, image: Path, references: list[Path] | None = None) -> dict:
    if file.stat().st_size > THEME_PACK_MAX_BYTES:
        raise ValueError("主题包超过大小限制")
    content = file.read_bytes()
    manifest = validate_theme_pack_bytes(content, file.name, reserved_ids=VISUAL_SYSTEM_ORDER, core_components=CORE_THEME_COMPONENTS)
    config = {"palette": manifest["palette"], "generated_design_system": manifest.get("design_system", {})}
    layouts = config["generated_design_system"].get("layouts", {})
    if not layouts:
        raise ValueError("此工具用于含独立 layouts 的主题；不将继承主题伪报为完整新设计")
    photo = _image_uri(image)
    reference_uris = [_image_uri(p) for p in references or []]
    if output.exists():
        raise ValueError("输出目录已存在，请使用新的目录以保留修订前证据")
    pages, documents = [], {}
    for profile in REVIEW_PROFILES:
        width = profile['content_width']
        for length in ("short", "long"):
            payload = review_payload(length == "long")
            specimens = []
            roles = [role for role in ROLE_FIELDS if role in layouts and not (role == "divider" and length == "long")]
            for role in roles:
                markup = render_layout(role, payload, config)
                # Only this known fixture asset is inlined. Theme-supplied media
                # remains prohibited by render_layout; no remote fetching.
                markup = markup.replace('/api/v1/theme-review-image', photo)
                markup = scale_preview_fonts(markup, profile)
                specimens.append(f'<article id="{role}" data-review-role="{role}"><p style="font:12px sans-serif;color:#666">{role} / {length} / {profile["id"]} · 视口 {profile["viewport_width"]}px / 正文 {width}px</p>{markup}</article>')
            # Exercise article heading entry point as well as the layout alone.
            for number, title in enumerate(("01 先确定方向", "一、先确定方向", "先确定方向")):
                heading = scale_preview_fonts(render_generated_heading(title, 2, 1, config), profile)
                specimens.append(f'<article data-review-heading="{number}">{heading}</article>')
            name = f'{length}-{profile["id"]}.html'
            documents[name] = _page(manifest["name"], "".join(specimens), profile)
            pages.append({"file": name, **profile, "length": length, "roles": roles})
    links = ''.join(f'<li><a href="{p["file"]}">{p["length"]} · {p["id"]} · 视口 {p["viewport_width"]}px / 正文 {p["content_width"]}px · {"主验收" if p["primary"] else "补充适配"}</a></li>' for p in pages)
    refs = ''.join(f'<figure><img src="{uri}" style="max-width:100%"><figcaption>参考 {i + 1}：{html.escape((references or [])[i].name)}</figcaption></figure>' for i, uri in enumerate(reference_uris))
    documents['index.html'] = _page(manifest['name'] + ' · 自检',
        f'<h1>{html.escape(manifest["name"])} · 组件自检</h1><p>这是检查材料，不是验收通过报告。分别查看短文、长文与真实图片；正常文章节奏与微信保存后效果须另行检查。</p><ul>{links}</ul><h2>参考对照</h2>' + (refs or '<p>未提供参考截图，请另行对照实际查看的来源。</p>'))
    result = {"ok": True, "schema_version": "theme_review.v2", "preview_config": PREVIEW_CONFIG,
        "overview_profile": "mobile", "theme_id": manifest['id'],
        "theme_version": manifest['version'], "renderer_version": RENDERER_VERSION,
        "theme_sha256": hashlib.sha256(content).hexdigest(), "pages": pages,
        "case_count": sum(len(p['roles']) for p in pages),
        "missing_roles": [r for r in ROLE_FIELDS if r not in layouts],
        "real_image_fixture": True, "reference_count": len(reference_uris),
        "browser_geometry": "not_verified", "visual_review": "not_verified",
        "normal_article": "not_verified", "wechat_saved_roundtrip": "not_verified",
        "review_file": str((output / 'index.html').resolve())}
    output.mkdir(parents=True, exist_ok=False)
    for name, document in documents.items():
        (output / name).write_text(document, encoding='utf-8')
    (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
