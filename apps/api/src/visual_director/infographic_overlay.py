from __future__ import annotations

from typing import Any

from .parser import ParsedArticle


class InfographicOverlayError(RuntimeError):
    pass


def resolve_overlay_copy(parsed: ParsedArticle, fact_bindings: dict[str, Any]) -> tuple[str, list[str]]:
    """Resolve model-visible infographic labels from locked source blocks."""
    blocks = {block.id: block for block in parsed.blocks}
    title_ref = fact_bindings.get("title_ref")
    title = str(blocks[title_ref].content) if title_ref in blocks else ""
    items: list[str] = []
    for reference in fact_bindings.get("item_refs", []):
        block_id, _, item_part = reference.partition(":item:")
        block = blocks.get(block_id)
        if block is None or not item_part.isdigit() or not isinstance(block.content, list):
            continue
        index = int(item_part)
        if index < len(block.content):
            items.append(str(block.content[index]))
    if not title and fact_bindings.get("item_refs"):
        item_block_id = str(fact_bindings["item_refs"][0]).partition(":item:")[0]
        item_position = next(
            (index for index, block in enumerate(parsed.blocks) if block.id == item_block_id),
            -1,
        )
        for block in reversed(parsed.blocks[:item_position]):
            if block.type == "heading" and block.level != 1:
                title = str(block.content)
                break
    title = title or "关键步骤"
    if not 2 <= len(items) <= 4:
        raise InfographicOverlayError("结构信息图必须绑定 2–4 个原文节点")
    return title, items
