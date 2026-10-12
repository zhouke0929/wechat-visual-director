"""Delivery capabilities and bounded materialization, shared by all theme packs.

This is a local risk model, never a claim to emulate WeChat's sanitizer.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from PIL import Image

from .theme_drawings import DRAWING_COMPILER_VERSION

DELIVERY_PROFILE_VERSION = "theme_delivery.v1"
MAX_DECORATIONS = 128
MAX_DECORATION_BYTES = 1024 * 1024
MAX_TOTAL_DECORATION_BYTES = 8 * 1024 * 1024


class _DecorationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: dict[str, dict[str, Any]] = {}
        self.total = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag != "img" or "data-theme-decoration" not in values:
            return
        source, digest = values.get("src") or "", values["data-theme-decoration"]
        if source.startswith("asset://"):
            return
        prefix = "data:image/png;base64,"
        if (not source.startswith(prefix) or len(source) > MAX_DECORATION_BYTES * 4 // 3 + 64
                or not re.fullmatch(r"[a-f0-9]{64}", digest or "")
                or values.get("data-decoration-compiler") != DRAWING_COMPILER_VERSION):
            raise ValueError("主题装饰资产无效，请重新渲染主题")
        if digest in self.assets:
            if self.assets[digest]["source_url"] != source:
                raise ValueError("主题装饰摘要冲突")
            return
        content = base64.b64decode(source[len(prefix):], validate=True)
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("主题装饰资产摘要不一致")
        self.total += len(content)
        if len(self.assets) >= MAX_DECORATIONS or self.total > MAX_TOTAL_DECORATION_BYTES:
            raise ValueError("主题装饰资产超出交付预算")
        with Image.open(io.BytesIO(content)) as image:
            if image.format != "PNG" or image.mode != "RGBA" or not (1 <= image.width <= 640 and 1 <= image.height <= 640):
                raise ValueError("主题装饰必须是有界透明 PNG")
            width, height = image.size
            image.verify()
        self.assets[digest] = {
            "asset_token": "decoration-" + digest, "asset_role": "theme_decoration",
            "source_resource_type": "compiled_theme_decoration", "source_resource_id": digest,
            "source_url": source, "content": content, "content_type": "image/png",
            "output_sha256": digest, "width": width, "height": height,
            "block_id": None, "image_slot_id": None,
        }


def compiled_decoration_assets(document: str) -> list[dict[str, Any]]:
    parser = _DecorationParser()
    parser.feed(document)
    return list(parser.assets.values())


def legacy_drawing_present(document: str) -> bool:
    # Scope this rule to line-art containers, not unrelated legacy official CSS.
    class Scanner(HTMLParser):
        def __init__(self):
            super().__init__()
            self.sections = []
            self.found = False

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "section":
                self.sections.append(bool(self.sections and self.sections[-1]) or "data-theme-drawing" in values)
            if self.sections and self.sections[-1] and re.search(r'position\s*:\s*absolute', values.get("style") or "", re.I):
                self.found = True

        def handle_endtag(self, tag):
            if tag == "section" and self.sections:
                self.sections.pop()

    scanner = Scanner()
    scanner.feed(document)
    return scanner.found


def theme_layout_coverage(manifest: dict[str, Any]) -> dict[str, Any]:
    """Declaration coverage only; not an aesthetic score or delivery certification."""
    from .theme_layouts import ROLE_FIELDS

    layouts = manifest.get("design_system", {}).get("layouts", {})
    covered = [role for role in ROLE_FIELDS if role in layouts]
    missing = [role for role in ROLE_FIELDS if role not in layouts]
    return {
        "status": "complete" if not missing else "partial" if covered else "inherited",
        "covered_count": len(covered), "total_count": len(ROLE_FIELDS),
        "covered_roles": covered, "missing_roles": missing,
        "scope": "layout_declarations_only",
    }


def theme_delivery_report(manifest: dict[str, Any]) -> dict[str, Any]:
    findings = []
    roles: dict[str, list[str]] = {}
    layouts = manifest.get("design_system", {}).get("layouts", {})

    def visit(node, path, role):
        kind, style = node["type"], node.get("style", {})
        capability = "raster_decoration" if kind == "drawing" else "editable_html"
        roles.setdefault(capability, [])
        if role not in roles[capability]:
            roles[capability].append(role)
        for present, code, message in (
            (kind == "text" and bool(re.search(r"[^\W\d_]", node.get("text", ""), re.UNICODE)),
             "fixed_label_review", f"固定标签「{node.get('text', '')}」需换文案核对，不能替原文命名对象、补充场景或改变比较含义。"),
            (kind == "cutout", "gradient_edge", "周期性凹口依赖多层渐变；需保存后核对边缘。"),
            (bool(style.get("rotate")), "rotated_layout", "文字或容器旋转仍由 HTML 承担；需保存后核对位置与换行。"),
            ("shadow" in style, "surface_shadow", "阴影效果需保存后核对，不作为正文布局支撑。"),
            (any(v < 0 for v in (style.get("margin", []) if isinstance(style.get("margin"), list) else [style.get("margin", 0)])),
             "overlap_spacing", "负外边距可能在字体或宽度变化时遮挡正文；需检查长文本。"),
        ):
            if present:
                findings.append({"code": code, "role": role, "path": path, "severity": "review", "message": message})
        for i, child in enumerate(node.get("children", [])):
            visit(child, f"{path}.children[{i}]", role)

    for role, node in layouts.items():
        visit(node, f"design_system.layouts.{role}", role)
    rehearsal = rehearse_theme_delivery(manifest)
    coverage = theme_layout_coverage(manifest)
    configured_root = os.environ.get("VISUAL_DIRECTOR_PROJECT_ROOT")
    project_root = Path(configured_root).expanduser().resolve() if configured_root else Path(__file__).resolve().parents[4]
    template_file = project_root / "skills/wechat-visual-director/assets/theme-pack-template.json"
    try:
        template_layouts = json.loads(template_file.read_text(encoding="utf-8"))["design_system"]["layouts"]
        unchanged = [role for role, node in layouts.items() if node == template_layouts.get(role)]
        design_review = {"status": "review_required" if unchanged else "no_exact_template_matches",
                         "scope": "exact_layout_comparison_only", "unchanged_template_roles": unchanged,
                         "visual_review": "not_verified"}
    except (OSError, ValueError, KeyError):
        design_review = {"status": "not_checked", "scope": "exact_layout_comparison_only",
                         "unchanged_template_roles": [], "visual_review": "not_verified"}
    return {
        "profile_version": DELIVERY_PROFILE_VERSION,
        "drawing_compiler": DRAWING_COMPILER_VERSION,
        "structure": "valid",
        "coverage": coverage,
        "visual_review": "not_verified",
        "local_delivery": ("not_checked" if rehearsal["status"] == "not_applicable" else
                           "blocking" if rehearsal["status"] == "blocking" else ("review_required" if findings else "static_pass")),
        "wechat_saved_roundtrip": "not_verified",
        "findings": findings,
        "capabilities": roles,
        "rehearsal": rehearsal,
        "design_review": design_review,
        "representative_roles": list(dict.fromkeys([f["role"] for f in findings] + roles.get("raster_decoration", [])))[:6],
        "next_action": ("fix_delivery" if rehearsal["status"] == "blocking" else
                        "complete_theme_layouts" if coverage["status"] == "partial" else
                        "review_complete_theme" if coverage["status"] == "complete" else "review_inherited_theme"),
    }


def rehearse_theme_delivery(manifest: dict[str, Any]) -> dict[str, Any]:
    """Compile all authored roles before installation, without writing a task.

    Deliberately synthetic data; tests asset materialization and static delivery,
    not browser typography, reference fidelity, or a real WeChat round trip.
    """
    from .theme_layouts import render_layout
    from .publication import check_frozen_html, replace_asset_urls
    from .theme_production import check_theme_production

    design = manifest.get("design_system", {})
    layouts = design.get("layouts", {})
    if not layouts:
        return {"status": "not_applicable", "scope": "authored_layouts_only", "roles": []}
    phrase = "交付试样：保留独立正文与完整信息。"
    payload = {"title": "代表组件的长标题与换行检查", "kicker": "DELIVERY SAMPLE", "index": "01",
               "body": phrase * 8, "left": phrase * 3, "right": phrase * 4,
               "caption": "仅为交付检查的示例图注", "items": [phrase * n for n in (1, 2, 3)],
               "entries": [{"title": "概念一", "body": phrase * 3}, {"title": "概念二", "body": phrase * 4}],
               "media": {"src": "asset://rehearsal-media", "alt": "受控媒体试样"}}
    config = {"palette": manifest["palette"], "generated_design_system": design}
    results = []
    for role in layouts:
        try:
            markup = render_layout(role, payload, config)
            assets = compiled_decoration_assets(markup)
            frozen = replace_asset_urls(markup, {a["source_url"]: a["asset_token"] for a in assets})
            report = check_frozen_html(frozen)
            results.append({"role": role, "status": report.status, "checks": report.checks,
                            "decoration_assets": len(assets), "decoration_bytes": sum(len(a["content"]) for a in assets)})
        except (ValueError, OSError, KeyError) as exc:
            results.append({"role": role, "status": "blocking", "message": str(exc)})
    production = check_theme_production(manifest)
    return {"status": "blocking" if any(r["status"] == "blocking" for r in results) or production["status"] == "blocking" else "pass",
            "scope": "local_compile_and_asset_materialization", "roles": results,
            "production": production}
