from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from typing import Any

from .delivery_markup import DeliveryMarkup
from .theme_delivery import legacy_drawing_present


PUBLICATION_SCHEMA_VERSION = "publication_revision.v0.8"
COMPATIBILITY_RULESET_VERSION = "wechat_compatibility.local.v0.4"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def structure_hash(document: str) -> str:
    normalized = re.sub(
        r'(\bsrc=")[^"]+("?)',
        r'\1asset://normalized\2',
        document,
        flags=re.IGNORECASE,
    )
    return sha256_text(normalized)


@dataclass(frozen=True)
class CompatibilityReport:
    status: str
    ruleset_version: str
    checks: dict[str, str]
    messages: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ruleset_version": self.ruleset_version,
            "checks": self.checks,
            "messages": self.messages,
            "verification_scope": "local_static_checks",
            "wechat_saved_roundtrip": "not_verified",
        }


def check_frozen_html(document: str, *, asset_tokens: set[str] | None = None) -> CompatibilityReport:
    markup = DeliveryMarkup(document)
    uncontrolled_image = any(
        not source.startswith("asset://") or not source.removeprefix("asset://")
        or (asset_tokens is not None and source.removeprefix("asset://") not in asset_tokens)
        for source in markup.image_sources
    )
    checks = {
        "document_present": "pass" if document.strip() else "blocking",
        "no_scripts": "blocking" if markup.has_script else "pass",
        "no_event_handlers": "blocking" if markup.has_event_handler else "pass",
        "no_waiting_source_images": "blocking" if markup.waiting_source else "pass",
        "no_waiting_planned_images": "blocking" if markup.waiting_planned else "pass",
        "no_empty_decorative_nodes": (
            "blocking" if markup.has_empty_decoration else "pass"
        ),
        "controlled_image_sources": "blocking" if uncontrolled_image else "pass",
        "no_legacy_positioned_drawings": "blocking" if legacy_drawing_present(document) else "pass",
    }
    messages = [key for key, value in checks.items() if value == "blocking"]
    return CompatibilityReport(
        status="pass" if not messages else "blocking",
        ruleset_version=COMPATIBILITY_RULESET_VERSION,
        checks=checks,
        messages=messages,
    )


def describe_html_compatibility_blockers(codes: list[str]) -> str:
    labels = {
        "document_present": "没有可交付的正文",
        "no_scripts": "正文含不支持的脚本标签",
        "no_event_handlers": "正文含不支持的交互属性",
        "no_waiting_source_images": "仍有原稿图片未导入",
        "no_waiting_planned_images": "仍有配图占位未处理",
        "no_empty_decorative_nodes": "主题含空装饰，请检查或更换当前主题",
        "controlled_image_sources": "正文含未进入本地资产库的图片，请检查原图或配图",
    }
    details = "；".join(labels[code] for code in codes if code in labels)
    return f"交付检查未通过：{details}" if details else "最终 HTML 未通过兼容性检查"


def replace_asset_urls(document: str, url_to_token: dict[str, str]) -> str:
    return DeliveryMarkup(document).rewrite_image_sources({source: f"asset://{token}" for source, token in url_to_token.items()})


def strip_workbench_editor_attributes(document: str) -> str:
    """Remove preview-only editing hooks before freezing publication HTML."""
    return re.sub(
        r'\sdata-editor-(?:title|block-ids|block-type)="[^"]*"',
        "",
        document,
        flags=re.IGNORECASE,
    )


def render_frozen_asset_urls(document: str, token_to_url: dict[str, str]) -> str:
    return DeliveryMarkup(document).rewrite_image_sources({f"asset://{token}": url for token, url in token_to_url.items()})


def _placeholder_metadata(markup: str) -> tuple[str, str]:
    frame_match = re.search(r'\bdata-image-frame="([^"]*)"', markup)
    caption_match = re.search(r'\bdata-image-caption="([^"]*)"', markup)
    return (
        frame_match.group(1) if frame_match else "neutral",
        caption_match.group(1) if caption_match else "",
    )


def _materialized_image_markup(
    *,
    element_id: str,
    anchor_class: str,
    content_url: str,
    width: int,
    height: int,
    alt: str,
    frame_variant: str,
    caption_html: str = "",
    theme_config: dict[str, Any] | None = None,
) -> str:
    if theme_config:
        from .theme_layouts import render_layout

        custom = render_layout("image_caption", {
            "caption": html.unescape(caption_html), "media": {"src": content_url, "alt": alt},
        }, theme_config)
        if custom is not None:
            return (f'<section id="{html.escape(element_id, quote=True)}" class="{anchor_class}" '
                    f'data-image-frame="custom-layout" style="scroll-margin-top:18px;">{custom}</section>')
    if frame_variant == "airy_organic":
        wrapper_style = (
            "scroll-margin-top:18px;margin:28px 0;padding:6px 0 13px;"
            "border-bottom:1px solid #8BB9C0;"
        )
        image_style = "border-radius:18px 18px 5px 18px;"
        caption_style = "margin:8px 0 0;color:#75817C;font-size:11px;line-height:1.55;text-align:center;"
    elif frame_variant == "warm_storybook":
        wrapper_style = (
            "scroll-margin-top:18px;margin:29px 0;padding:8px 8px 14px;"
            "border-bottom:1px solid #D7B995;background-color:#FFF9EF;box-shadow:7px 7px 0 #FBF2D8;"
        )
        image_style = "border-radius:0;"
        caption_style = "margin:12px 0 0;color:#7B6861;font-size:11px;line-height:1.55;text-align:right;"
    elif frame_variant == "editorial_masthead":
        wrapper_style = (
            "scroll-margin-top:18px;margin:29px 0;padding:0;"
            "border-top:11px solid #202B33;border-bottom:3px solid #202B33;"
        )
        image_style = "border-radius:0;"
        caption_style = (
            "margin:8px 0;color:#687370;font-family:Georgia,serif;font-size:9px;"
            "font-weight:800;letter-spacing:.12em;text-align:right;"
        )
    elif frame_variant == "structured_ledger":
        wrapper_style = (
            "scroll-margin-top:18px;margin:28px 0;padding:0 0 9px;"
            "border-top:4px solid #526A43;border-bottom:1px solid #AEBBB5;"
        )
        image_style = "border-radius:0;"
        caption_style = "margin:8px 0 0;color:#687370;font-size:10px;line-height:1.55;text-align:right;"
    else:
        wrapper_style = "scroll-margin-top:18px;margin:26px 0;"
        image_style = "border-radius:12px;"
        caption_style = "margin:8px 0 0;color:#75817C;font-size:11px;line-height:1.55;text-align:center;"
    caption = (
        f'<p data-content-role="image-caption" style="{caption_style}">{caption_html}</p>'
        if caption_html
        else ""
    )
    return (
        f'<section id="{html.escape(element_id)}" class="{anchor_class}" '
        f'data-image-frame="{html.escape(frame_variant)}" style="{wrapper_style}">'
        f'<img src="{html.escape(content_url)}" width="{width}" height="{height}" '
        f'loading="eager" decoding="sync" alt="{html.escape(alt)}" '
        f'style="display:block;width:100%;height:auto;aspect-ratio:{width}/{height};'
        f'object-fit:cover;margin:0;border:0;{image_style}" />'
        f"{caption}</section>"
    )


def _custom_image_config(markup: str) -> dict[str, Any] | None:
    match = re.search(r'\bdata-theme-image-config="([^"]*)"', markup)
    return json.loads(html.unescape(match.group(1))) if match else None


def materialize_preview_document(
    repository: Any, artifact_id: str, *, adopted_slots: set[str] | None = None
) -> str:
    artifact = repository.get_artifact_record(artifact_id)
    document = artifact["html"]
    if adopted_slots is not None:
        # The stored preview can contain suggestions even before slot state exists.
        document = re.sub(
            r'<section id="([^"]+)" class="image-slot-anchor".*?</section>',
            lambda match: match.group(0) if html.unescape(match[1]) in adopted_slots else "",
            document,
            flags=re.DOTALL,
        )
    states = repository.list_image_slot_states(artifact["task_id"], artifact["plan_id"])
    for state in states:
        slot_id = str(state["image_slot_id"])
        pattern = re.compile(
            rf'<section id="{re.escape(slot_id)}" class="image-slot-anchor".*?</section>',
            re.DOTALL,
        )
        # A generation attempt can change status without changing the
        # user's decision, including on drafts created by older builds.
        decision = state.get("decision") or state.get("status")
        if decision == "skipped":
            document = pattern.sub("", document)
            continue
        selected = next(
            (item for item in state["candidates"] if item["id"] == state["selected_candidate_id"]),
            None,
        )
        if selected and (
            slot_id in adopted_slots if adopted_slots is not None
            else decision in {"accepted", "replaced"}
        ):
            image_width = int(selected["width"])
            image_height = int(selected["height"])
            def replace_generated(match: re.Match[str]) -> str:
                frame_variant, _ = _placeholder_metadata(match.group(0))
                return _materialized_image_markup(
                    element_id=slot_id,
                    anchor_class="image-slot-anchor",
                    content_url=str(selected["content_url"]),
                    width=image_width,
                    height=image_height,
                    alt="运营已确认的文章配图",
                    frame_variant=frame_variant,
                    theme_config=_custom_image_config(match.group(0)),
                )

            document = pattern.sub(replace_generated, document)
    source_assets = repository.list_preflight_asset_replacements(artifact["task_id"])
    for asset in source_assets:
        if asset["asset_role"] != "body_image" or not asset["block_id"]:
            continue
        block_id = str(asset["block_id"])
        pattern = re.compile(
            rf'<section id="{re.escape(block_id)}" class="source-image-anchor".*?</section>',
            re.DOTALL,
        )
        def replace_source(match: re.Match[str]) -> str:
            frame_variant, caption_html = _placeholder_metadata(match.group(0))
            return _materialized_image_markup(
                element_id=block_id,
                anchor_class="source-image-anchor",
                content_url=str(asset["content_url"]),
                width=int(asset["width"]),
                height=int(asset["height"]),
                alt=html.unescape(caption_html) or "运营替换的原稿图片",
                frame_variant=frame_variant,
                caption_html=caption_html,
                theme_config=_custom_image_config(match.group(0)),
            )

        document = pattern.sub(replace_source, document)
    return document
