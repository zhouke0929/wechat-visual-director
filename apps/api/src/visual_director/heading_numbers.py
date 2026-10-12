"""Recognize source numbering without rewriting editable heading text."""
import re


EXPLICIT_HEADING_NUMBER_RE = re.compile(
    r"^\s*(?:[^\w\u4e00-\u9fff]{0,4}\s*)?"
    r"(?:PART\s*\d+|第[一二三四五六七八九十百0-9]+(?:章|节|部分|步|问)|"
    r"[一二三四五六七八九十百]+[、.．]|\d+[、．]|\d+\.(?!\d)|"
    r"\d{1,3}\s+(?=\S)|"
    r"(?:痛点|问题|步骤|信号|核心功能)[一二三四五六七八九十百0-9]+)",
    flags=re.IGNORECASE,
)


def has_explicit_heading_number(value: str) -> bool:
    return bool(EXPLICIT_HEADING_NUMBER_RE.match(value.replace("**", "").replace("__", "")))
