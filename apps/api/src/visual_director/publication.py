from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from typing import Any


PUBLICATION_SCHEMA_VERSION = "publication_revision.v0.8"
COMPATIBILITY_RULESET_VERSION = "wechat_compatibility.mock.v0.1"


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
        }


def check_frozen_html(document: str) -> CompatibilityReport:
    lowered = document.lower()
    checks = {
        "document_present": "pass" if document.strip() else "blocking",
        "no_scripts": "pass" if "<script" not in lowered else "blocking",
        "no_event_handlers": "pass" if not re.search(r"\son[a-z]+\s*=", lowered) else "blocking",
        "no_waiting_source_images": "pass" if "source image · waiting" not in lowered else "blocking",
        "no_waiting_planned_images": "pass" if "image plan ·" not in lowered else "blocking",
        "controlled_image_sources": "pass",
    }
    image_sources = re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', document, flags=re.IGNORECASE)
    if any(not source.startswith("asset://") for source in image_sources):
        checks["controlled_image_sources"] = "blocking"
    messages = [key for key, value in checks.items() if value == "blocking"]
    return CompatibilityReport(
        status="pass" if not messages else "blocking",
        ruleset_version=COMPATIBILITY_RULESET_VERSION,
        checks=checks,
        messages=messages,
    )


def replace_asset_urls(document: str, url_to_token: dict[str, str]) -> str:
    result = document
    for source_url, token in sorted(url_to_token.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(f'src="{source_url}"', f'src="asset://{token}"')
    return result


def render_frozen_asset_urls(document: str, token_to_url: dict[str, str]) -> str:
    result = document
    for token, target_url in token_to_url.items():
        result = result.replace(f'src="asset://{token}"', f'src="{target_url}"')
    return result


def materialize_preview_document(repository: Any, artifact_id: str) -> str:
    artifact = repository.get_artifact_record(artifact_id)
    document = artifact["html"]
    states = repository.list_image_slot_states(artifact["task_id"], artifact["plan_id"])
    for state in states:
        slot_id = str(state["image_slot_id"])
        pattern = re.compile(
            rf'<section id="{re.escape(slot_id)}" class="image-slot-anchor".*?</section>',
            re.DOTALL,
        )
        if state["status"] == "skipped":
            document = pattern.sub("", document)
            continue
        selected = next(
            (item for item in state["candidates"] if item["id"] == state["selected_candidate_id"]),
            None,
        )
        if selected and state["status"] in {"accepted", "replaced", "generated", "failed"}:
            image_width = int(selected["width"])
            image_height = int(selected["height"])
            replacement = (
                f'<section id="{html.escape(slot_id)}" class="image-slot-anchor" '
                'style="scroll-margin-top:18px;margin:26px 0;">'
                f'<img src="{html.escape(selected["content_url"])}" width="{image_width}" height="{image_height}" '
                'loading="eager" decoding="sync" alt="运营已确认的文章配图" '
                f'style="display:block;width:100%;height:auto;aspect-ratio:{image_width}/{image_height};'
                'object-fit:cover;margin:0;border:0;border-radius:12px;" />'
                '</section>'
            )
            document = pattern.sub(lambda _: replacement, document)
    source_assets = repository.list_preflight_asset_replacements(artifact["task_id"])
    for asset in source_assets:
        if asset["asset_role"] != "body_image" or not asset["block_id"]:
            continue
        block_id = str(asset["block_id"])
        pattern = re.compile(
            rf'<section id="{re.escape(block_id)}" class="source-image-anchor".*?</section>',
            re.DOTALL,
        )
        replacement = (
            f'<section id="{html.escape(block_id)}" class="source-image-anchor" '
            'style="scroll-margin-top:18px;margin:24px 0;">'
            f'<img src="{html.escape(asset["content_url"])}" width="{int(asset["width"])}" '
            f'height="{int(asset["height"])}" loading="eager" decoding="sync" '
            'alt="运营替换的原稿图片" '
            f'style="display:block;width:100%;height:auto;aspect-ratio:{int(asset["width"])}/{int(asset["height"])};'
            'object-fit:cover;margin:0;border:0;border-radius:12px;" />'
            '</section>'
        )
        document = pattern.sub(lambda _: replacement, document)
    return document
