"""Map source blocks to reading roles, before a theme is chosen."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .parser import ContentBlock, ParsedArticle


@dataclass(frozen=True, slots=True)
class FoundationBlock:
    """A source block plus its display role, with no dependency on a theme."""

    role: str
    block: ContentBlock
    section_index: int = 0
    lead_label: str = ""
    list_context: str = "key_points"


def bind_foundation_block(
    parsed: ParsedArticle, index: int, section_index: int,
    opening: tuple[str | None, str | None],
) -> FoundationBlock | None:
    block = parsed.blocks[index]
    role = block.type
    if role == "heading":
        if block.level == 1:
            return None  # The document title is projected exactly once as the hero.
        role = "section_heading" if (block.level or 2) == 2 else "subheading"
    elif role == "paragraph" and block.id == opening[0]:
        return FoundationBlock("lead", block, lead_label=opening[1] or "本文导读")
    elif role in {"ordered_list", "unordered_list"}:
        return FoundationBlock(role, block, list_context=_list_semantic_role(parsed, index, role == "ordered_list"))
    elif role == "thematic_break":
        role = "divider"
    elif role == "image_reference":
        role = "image_caption"
    elif role not in {"paragraph", "quote", "table", "source", "reference_list"}:
        return None
    return FoundationBlock(role, block, section_index=section_index)


CONCLUSION_CUE_RE = re.compile(r"结论(?:是|：|:)|核心判断|答案是|最重要的是|建议是|这意味着")
GUIDE_CUE_RE = re.compile(r"本文|这篇|今天|接下来|逐个|一次性|直接回答|告诉你|梳理")
CASE_LIST_CONTEXT_RE = re.compile(r"案例|样本|实例|两校|两种学校|同名专业|现实样本|对比|差异")
ACTION_LIST_CONTEXT_RE = re.compile(
    r"行动清单|核验清单|检查清单|操作清单|准备清单|办理清单|"
    r"(?:怎么|如何)(?:做|选|办|核验|检查|准备)|"
    r"(?:提交|申请|填报|办理|操作|执行|核验|检查|准备)(?:前|时|步骤|事项)|"
    r"建议|下一步|注意事项"
)


def _opening_highlight(parsed: ParsedArticle) -> tuple[str | None, str | None]:
    """Select one substantive pre-section lead instead of styling the first paragraph.

    A short scene setter such as “7月来了。” is not a conclusion. Only
    paragraphs before the first H2 can become a lead, and they need an explicit
    conclusion or guide cue plus enough information to stand on their own.
    """
    candidates: list[ContentBlock] = []
    for block in parsed.blocks:
        if block.type == "heading" and block.level == 2:
            break
        if block.type == "paragraph":
            candidates.append(block)
    for pattern, label in ((CONCLUSION_CUE_RE, "先看结论"), (GUIDE_CUE_RE, "本文导读")):
        for block in reversed(candidates):
            plain = re.sub(r"\*\*", "", str(block.content)).strip()
            if len(plain) >= 28 and pattern.search(plain):
                return block.id, label
    return None, None


def _list_semantic_role(parsed: ParsedArticle, block_index: int, ordered: bool) -> str:
    if ordered:
        return "numbered_insight"

    context: list[str] = []
    nearest_subheading = ""
    for previous in reversed(parsed.blocks[:block_index]):
        if previous.type == "heading":
            context.append(str(previous.content))
            if (previous.level or 0) >= 3 and not nearest_subheading:
                nearest_subheading = str(previous.content)
            if (previous.level or 0) <= 2:
                break
        elif len(context) < 3 and previous.type in {"paragraph", "quote"}:
            context.append(str(previous.content))

    combined = " ".join(context[:4])
    if nearest_subheading and CASE_LIST_CONTEXT_RE.search(nearest_subheading):
        return "case_points"
    if ACTION_LIST_CONTEXT_RE.search(combined):
        return "action_checklist"
    return "key_points"
