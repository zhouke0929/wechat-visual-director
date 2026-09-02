from __future__ import annotations

from dataclasses import replace
from typing import Any

from .parser import ContentBlock, ParsedArticle


CONTENT_EDITS_SCHEMA_VERSION = "content_edits.v0.1"
EDITABLE_BLOCK_TYPES = {
    "heading",
    "paragraph",
    "quote",
    "source",
    "ordered_list",
    "unordered_list",
    "reference_list",
    "table",
}


def empty_content_edits() -> dict[str, Any]:
    return {
        "schema_version": CONTENT_EDITS_SCHEMA_VERSION,
        "revision": 0,
        "blocks": {},
    }


def apply_content_edits(parsed: ParsedArticle, edits: dict[str, Any] | None) -> ParsedArticle:
    overrides = (edits or {}).get("blocks") or {}
    blocks = [
        replace(block, content=overrides.get(block.id, block.content))
        for block in parsed.blocks
    ]
    return replace(parsed, blocks=blocks)


def content_editor_document(
    parsed: ParsedArticle,
    edits: dict[str, Any],
    *,
    task_id: str,
    plan_id: str,
    preview_url: str,
) -> dict[str, Any]:
    return {
        "schema_version": "content_editor_document.v0.1",
        "task_id": task_id,
        "plan_id": plan_id,
        "revision": int(edits.get("revision") or 0),
        "title": parsed.title,
        "preview_url": preview_url,
        "blocks": [
            {
                "block_id": block.id,
                "type": block.type,
                "level": block.level,
                "content": block.content,
            }
            for block in parsed.blocks
            if block.type in EDITABLE_BLOCK_TYPES
        ],
    }


def validate_content_for_block(block: ContentBlock, value: Any) -> Any:
    if block.type not in EDITABLE_BLOCK_TYPES:
        raise ValueError("该内容块不支持在工作台中编辑")
    if block.type in {"ordered_list", "unordered_list", "reference_list"}:
        if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
            raise ValueError("列表内容必须是非空文本数组")
        normalized = [item.strip() for item in value]
        if any(not item or len(item) > 1200 for item in normalized):
            raise ValueError("列表项不能为空，且每项不能超过 1200 字")
        return normalized
    if block.type == "table":
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(row, list) and row for row in value)
            or not all(isinstance(cell, str) for row in value for cell in row)
        ):
            raise ValueError("表格内容必须是非空二维文本数组")
        widths = {len(row) for row in value}
        if len(widths) != 1:
            raise ValueError("表格每一行必须保持相同列数")
        normalized_rows = [[cell.strip() for cell in row] for row in value]
        if any(not cell or len(cell) > 600 for row in normalized_rows for cell in row):
            raise ValueError("表格单元格不能为空，且每格不能超过 600 字")
        return normalized_rows
    if not isinstance(value, str):
        raise ValueError("正文内容必须是文本")
    normalized_text = value.strip()
    if not normalized_text:
        raise ValueError("正文内容不能为空")
    if len(normalized_text) > 6000:
        raise ValueError("单个内容块不能超过 6000 字")
    return normalized_text
