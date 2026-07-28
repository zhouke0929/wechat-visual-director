from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

import yaml


class MarkdownInputError(ValueError):
    pass


@dataclass(frozen=True)
class ContentBlock:
    id: str
    type: str
    content: Any
    level: int | None = None


@dataclass(frozen=True)
class ParsedArticle:
    title: str
    title_source: str
    frontmatter: dict[str, Any]
    body: str
    blocks: list[ContentBlock]
    section_count: int
    image_reference_count: int
    source_hash: str


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
UNORDERED_RE = re.compile(r"^\s*[-*+]\s+(.+)$")
ORDERED_RE = re.compile(r"^\s*\d+[.)、]\s+(.+)$")
DECORATIVE_BULLET_RE = re.compile(
    r"^\s*(?:🟥|🟦|🟧|🟩|🟨|💡|✅|❌|🔹|🔸|⚠️?)\s*(.+)$"
)
IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]*\)")
IMAGE_LINE_RE = re.compile(r'^!\[([^\]]*)]\(([^)]+)\)\s*$')
HORIZONTAL_RULE_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
SOURCE_PREFIX_RE = re.compile(
    r"^(?:[📊📚🔗]\s*)?(?:\*\*)?(?:(?:数据|资料|规则|政策|核验|信息)\s*)?来源\s*[:：]",
    flags=re.IGNORECASE,
)


def _is_source_text(value: str) -> bool:
    return bool(SOURCE_PREFIX_RE.match(value.strip()))


def _split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    normalized = markdown.replace("\r\n", "\n").lstrip("\ufeff")
    if not normalized.startswith("---\n"):
        return {}, normalized
    closing = normalized.find("\n---\n", 4)
    if closing == -1:
        raise MarkdownInputError("frontmatter 缺少结束分隔符 ---")
    raw = normalized[4:closing]
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise MarkdownInputError(f"frontmatter 不是有效 YAML：{exc}") from exc
    if not isinstance(data, dict):
        raise MarkdownInputError("frontmatter 必须是键值对象")
    return data, normalized[closing + 5 :]


def _flush_paragraph(blocks: list[ContentBlock], buffer: list[str]) -> None:
    if not buffer:
        return
    content = "\n".join(buffer).strip()
    if content:
        block_type = "source" if _is_source_text(content) else "paragraph"
        blocks.append(ContentBlock(id=f"block-{len(blocks) + 1:03d}", type=block_type, content=content))
    buffer.clear()


def parse_markdown(markdown: str, title_override: str | None = None) -> ParsedArticle:
    if not markdown.strip():
        raise MarkdownInputError("Markdown 文件为空")

    frontmatter, body = _split_frontmatter(markdown)
    h1_match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    frontmatter_title = str(frontmatter.get("title", "")).strip()
    override = (title_override or "").strip()
    if override:
        title, title_source = override, "override"
    elif frontmatter_title:
        title, title_source = frontmatter_title, "frontmatter"
    elif h1_match:
        title, title_source = h1_match.group(1).strip(), "first_h1"
    else:
        raise MarkdownInputError("缺少标题：请在 frontmatter 提供 title，或使用一级标题 #")

    blocks: list[ContentBlock] = []
    paragraph: list[str] = []
    lines = body.splitlines()
    cursor = 0

    while cursor < len(lines):
        line = lines[cursor]
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            _flush_paragraph(blocks, paragraph)
            cursor += 1
            continue

        if HORIZONTAL_RULE_RE.fullmatch(stripped):
            _flush_paragraph(blocks, paragraph)
            blocks.append(
                ContentBlock(
                    id=f"block-{len(blocks) + 1:03d}",
                    type="thematic_break",
                    content="---",
                )
            )
            cursor += 1
            continue

        image_reference = IMAGE_LINE_RE.fullmatch(stripped)
        if image_reference:
            _flush_paragraph(blocks, paragraph)
            source = image_reference.group(2).strip()
            blocks.append(
                ContentBlock(
                    id=f"block-{len(blocks) + 1:03d}",
                    type="image_reference",
                    content={
                        "alt": image_reference.group(1).strip(),
                        "source": source,
                        "placeholder": "picsum.photos" in source.lower(),
                    },
                )
            )
            cursor += 1
            continue

        heading = HEADING_RE.match(stripped)
        if heading:
            _flush_paragraph(blocks, paragraph)
            blocks.append(
                ContentBlock(
                    id=f"block-{len(blocks) + 1:03d}",
                    type="heading",
                    content=heading.group(2).strip(),
                    level=len(heading.group(1)),
                )
            )
            cursor += 1
            continue

        if stripped.startswith(">"):
            _flush_paragraph(blocks, paragraph)
            quote_lines: list[str] = []
            while cursor < len(lines) and lines[cursor].strip().startswith(">"):
                quote_lines.append(lines[cursor].strip().lstrip("> "))
                cursor += 1
            quote_content = "\n".join(quote_lines)
            block_type = "source" if _is_source_text(quote_content) else "quote"
            blocks.append(ContentBlock(f"block-{len(blocks) + 1:03d}", block_type, quote_content))
            continue

        unordered = UNORDERED_RE.match(line)
        ordered = ORDERED_RE.match(line)
        if unordered or ordered:
            _flush_paragraph(blocks, paragraph)
            ordered_list = bool(ordered)
            items: list[str] = []
            while cursor < len(lines):
                candidate = ORDERED_RE.match(lines[cursor]) if ordered_list else UNORDERED_RE.match(lines[cursor])
                if not candidate:
                    break
                items.append(candidate.group(1).strip())
                cursor += 1
            blocks.append(
                ContentBlock(
                    f"block-{len(blocks) + 1:03d}",
                    "ordered_list" if ordered_list else "unordered_list",
                    items,
                )
            )
            continue

        decorative = DECORATIVE_BULLET_RE.match(line)
        next_decorative = (
            DECORATIVE_BULLET_RE.match(lines[cursor + 1])
            if cursor + 1 < len(lines)
            else None
        )
        if decorative and next_decorative:
            _flush_paragraph(blocks, paragraph)
            items: list[str] = []
            while cursor < len(lines):
                candidate = DECORATIVE_BULLET_RE.match(lines[cursor])
                if not candidate:
                    break
                items.append(candidate.group(1).strip())
                cursor += 1
            blocks.append(
                ContentBlock(
                    f"block-{len(blocks) + 1:03d}",
                    "unordered_list",
                    items,
                )
            )
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            _flush_paragraph(blocks, paragraph)
            rows: list[list[str]] = []
            while cursor < len(lines):
                candidate = lines[cursor].strip()
                if not (candidate.startswith("|") and candidate.endswith("|")):
                    break
                cells = [cell.strip() for cell in candidate.strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    rows.append(cells)
                cursor += 1
            if rows:
                blocks.append(ContentBlock(f"block-{len(blocks) + 1:03d}", "table", rows))
            continue

        paragraph.append(stripped)
        cursor += 1

    _flush_paragraph(blocks, paragraph)
    section_count = sum(1 for block in blocks if block.type == "heading" and (block.level or 0) >= 2)
    image_count = len(IMAGE_RE.findall(body))
    source_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    return ParsedArticle(
        title=title,
        title_source=title_source,
        frontmatter=frontmatter,
        body=body,
        blocks=blocks,
        section_count=section_count,
        image_reference_count=image_count,
        source_hash=source_hash,
    )


def classify_article(parsed: ParsedArticle, requested_type: str | None = None) -> str:
    allowed = {"data_policy", "viewpoint_trend", "tutorial_steps", "lively_growth"}
    if requested_type in allowed:
        return requested_type
    frontmatter_type = str(parsed.frontmatter.get("article_type", ""))
    if frontmatter_type in allowed:
        return frontmatter_type

    corpus = f"{parsed.title}\n{parsed.body}"
    scores = {
        "data_policy": sum(corpus.count(word) for word in ("数据", "政策", "分数", "位次", "招生", "官方")),
        "tutorial_steps": sum(corpus.count(word) for word in ("步骤", "第一步", "第二步", "如何", "教程", "清单")),
        "lively_growth": sum(corpus.count(word) for word in ("成长", "体验", "活动", "学生", "游戏", "好玩")),
        "viewpoint_trend": sum(corpus.count(word) for word in ("趋势", "观点", "意味着", "时代", "为什么", "焦虑")),
    }
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "viewpoint_trend"
