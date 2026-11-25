from __future__ import annotations

import html
import re
import os
from pathlib import Path
from typing import Any

from .brand import load_brand_profile
from .component_catalog import VISUAL_SYSTEM_ORDER
from .components import render_bound_component
from .delivery_markup import DeliveryMarkup, preserve_wechat_decorative_nodes
from .foundation_content import _opening_highlight, bind_foundation_block
from .foundation_renderer import FoundationRenderer
from .foundation_media import _render_fixed_footer, _render_image_placeholder, _render_source_image_placeholder
from .foundation_structure import _render_heading
from .parser import ParsedArticle
from .plan_schema import validate_plan_for_article
from .preview_profiles import BODY_PADDING_X
from .reading_rules import resolve_reading_profile
from .render_pilot import renderer_pilot_enabled
from .semantic_content import SemanticSource


def _mark_editor_target(markup: str, block_ids: list[str], block_type: str) -> str:
    """Attach inert workbench hooks without changing WeChat layout markup."""
    if not markup or not block_ids:
        return markup
    attributes = (
        f' data-editor-block-ids="{html.escape(",".join(block_ids))}"'
        f' data-editor-block-type="{html.escape(block_type)}"'
    )
    return re.sub(r"<([a-zA-Z][\w:-]*)\b", rf"<\1{attributes}", markup, count=1)


def render_preview(
    parsed: ParsedArticle,
    plan: dict[str, Any],
    *,
    brand_profile: dict[str, Any] | None = None,
) -> str:
    validated = validate_plan_for_article(plan, parsed)
    configured_root = os.environ.get("VISUAL_DIRECTOR_PROJECT_ROOT")
    project_root = (
        Path(configured_root).expanduser().resolve()
        if configured_root
        else Path(__file__).resolve().parents[4]
    )
    profile = brand_profile if brand_profile is not None else load_brand_profile(project_root)
    config = validated["configuration"]
    visual_system = validated.get("visual_system") or config.get("visual_system")
    accent = config["accent"]
    palette = config.get("palette", {"primary": accent})
    generated_theme = bool(config.get("generated_design_system"))

    slots_by_anchor = {slot["anchor_block_id"]: slot for slot in validated.get("slots", [])}
    image_slots_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for image_slot in validated.get("image_slots", []):
        image_slots_by_anchor.setdefault(image_slot["anchor_block_id"], []).append(image_slot)
    consumed = {block_id for slot in validated.get("slots", []) for block_id in slot["consume_block_ids"]}
    body: list[str] = []
    bind_list_fields = renderer_pilot_enabled()
    reading = resolve_reading_profile(config, official=visual_system in VISUAL_SYSTEM_ORDER, theme_id=visual_system) if bind_list_fields else None
    semantic_source = SemanticSource.from_article(parsed, reading)
    section_index = 0
    foundation = FoundationRenderer.for_theme(config, reading, bind_list_fields)
    opening = _opening_highlight(parsed)

    for block_index, block in enumerate(parsed.blocks):
        editor_start = len(body)
        editor_block_ids: list[str] = []
        editor_block_type = block.type
        if block.id in slots_by_anchor:
            slot = slots_by_anchor[block.id]
            editor_block_ids = list(slot["consume_block_ids"])
            editor_block_type = f'component:{slot["component_type"]}'
            body.append(
                f'<section id="{html.escape(slot["slot_id"])}" class="component-anchor" style="scroll-margin-top:18px;">'
                f'{render_bound_component(semantic_source.bind(slot), slot["variant"], palette, config, visual_system=visual_system)}</section>'
            )
        elif block.id in consumed:
            pass
        else:
            if block.type == "heading" and block.level == 2:
                section_index += 1
            field = bind_foundation_block(parsed, block_index, section_index, opening)
            if field is None and block.type == "heading" and block.level == 1:
                continue
            if field is not None:
                body.append(foundation.block(field))
        if len(body) > editor_start:
            if not editor_block_ids and block.type not in {"thematic_break", "image_reference"}:
                editor_block_ids = [block.id]
            if editor_block_ids:
                body[editor_start] = _mark_editor_target(
                    body[editor_start],
                    editor_block_ids,
                    editor_block_type,
                )
        for image_slot in image_slots_by_anchor.get(block.id, []):
            body.append(_render_image_placeholder(image_slot, config))

    hero = foundation.hero(parsed.title, profile, validated)
    cta = foundation.closing_cta(profile)
    document = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>html{scroll-behavior:smooth}.component-anchor:target,.image-slot-anchor:target,.source-image-anchor:target{outline:2px solid #8FD6CE;outline-offset:7px;border-radius:10px}</style>'
        f'<title>{html.escape(parsed.title)}</title></head>'
        f'<body style="box-sizing:border-box;margin:0;padding:0 {BODY_PADDING_X}px;background-color:{palette["surface"] if generated_theme else "#FFFFFF"};font-family:\'Noto Sans SC\',\'Microsoft YaHei\',Arial,sans-serif;">'
        f'{hero}<main style="box-sizing:border-box;width:100%;max-width:100%;margin:0 auto;padding:0 0 34px;">'
        f'{"".join(body)}{cta}</main></body></html>'
    )
    markup = DeliveryMarkup(document)
    if markup.has_script or markup.has_event_handler:
        raise ValueError("渲染产物包含禁止脚本或事件属性")
    return markup.normalize_empty_elements()
