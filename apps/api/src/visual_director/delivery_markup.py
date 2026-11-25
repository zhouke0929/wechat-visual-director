"""Inspect and edit the renderer's HTML without searching in article text."""
from __future__ import annotations

import html
import re
from collections.abc import Mapping
from html.parser import HTMLParser


_EVENT_ATTRIBUTE = re.compile(r"on[a-z]+")
_ATTRIBUTE = re.compile(
    r"""\s+([^\s=/>]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))?"""
)
_WHITESPACE = re.compile(r"[ \t\n\r\f]*")
_ZERO_LENGTH = re.compile(r"(?:0+(?:\.0+)?|\.0+)(?:px|em|rem|%)?")
_NO_BORDER = {"0", "0px", "none", "hidden", "initial", "unset", "transparent"}


class DeliveryMarkup(HTMLParser):
    """Collect the actual tags, attributes and controlled media in an HTML fragment."""

    def __init__(self, document: str, *, omit_attributes: frozenset[str] = frozenset()):
        super().__init__()
        self.document = document
        self._omit_attributes = omit_attributes
        self._attribute_edits: list[tuple[int, int, str]] = []
        self.has_script = False
        self.has_event_handler = False
        self.waiting_source = False
        self.waiting_planned = False
        self.image_sources: list[str] = []
        self._image_tags: list[tuple[int, str, str]] = []
        self._empty_nodes: list[tuple[int, int, str, dict[str, str | None]]] = []
        self._pending: tuple[str, int, str, dict[str, str | None]] | None = None
        self._line_offsets = [0, *(m.end() for m in re.finditer("\n", document))]
        self.feed(document)
        self.close()

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_offsets[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._pending = None
        attributes = dict(attrs)
        if self._omit_attributes and not self._omit_attributes.isdisjoint(attributes):
            offset = self._offset()
            for match in _ATTRIBUTE.finditer(self.get_starttag_text(), len(tag) + 1):
                if match[1].lower() in self._omit_attributes:
                    self._attribute_edits.append((offset + match.start(), offset + match.end(), ""))
        self.has_script |= tag == "script"
        self.has_event_handler |= any(_EVENT_ATTRIBUTE.fullmatch(name) for name, _ in attrs)
        if tag == "section" and "data-image-caption" in attributes:
            # Materialized image wrappers no longer carry placeholder metadata.
            classes = (attributes.get("class") or "").split()
            self.waiting_source |= "source-image-anchor" in classes
            self.waiting_planned |= "image-slot-anchor" in classes
        elif tag == "img":
            sources = [value for name, value in attrs if name == "src"]
            source = (sources[0] or "") if len(sources) == 1 else ""
            self.image_sources.append(source)
            if source:
                self._image_tags.append((self._offset(), self.get_starttag_text(), source))
        elif tag in {"span", "p"} and attributes.get("style"):
            if sum(name == "style" for name, _ in attrs) == 1:
                self._pending = (tag, self._offset(), self.get_starttag_text(), attributes)

    def handle_endtag(self, tag: str) -> None:
        pending, self._pending = self._pending, None
        if pending is None or pending[0] != tag:
            return
        _, start, opening, attrs = pending
        end = self._offset()
        if _WHITESPACE.fullmatch(self.document[start + len(opening):end]):
            closing = self.document.index(">", end) + 1
            self._empty_nodes.append((start, closing, opening, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self._pending = None

    def rewrite_image_sources(self, by_source: Mapping[str, str]) -> str:
        edits = []
        for start, opening, source in self._image_tags:
            if source not in by_source:
                continue
            for attribute in _ATTRIBUTE.finditer(opening, 4):
                if attribute[1].lower() == "src":
                    value_start, value_end = attribute.span(2)
                    edits.append((start + value_start, start + value_end,
                                  '"' + html.escape(by_source[source], quote=True) + '"'))
                    break
        return self._rewrite(edits)

    def _rewrite(self, edits: list[tuple[int, int, str]]) -> str:
        pieces = []
        cursor = 0
        for start, end, replacement in edits:
            pieces.extend((self.document[cursor:start], replacement))
            cursor = end
        pieces.append(self.document[cursor:])
        return "".join(pieces)

    def without_omitted_attributes(self) -> str:
        return self._rewrite(self._attribute_edits) if self._attribute_edits else self.document

    @property
    def has_empty_decoration(self) -> bool:
        return any(_empty_style(attrs["style"]) == "preserve" for _, _, _, attrs in self._empty_nodes)

    def normalize_empty_elements(self) -> str:
        edits = []
        for start, end, opening, attrs in self._empty_nodes:
            style = attrs["style"]
            action = _empty_style(style)
            if action == "remove":
                if set(attrs) <= {"style", "aria-hidden", "data-theme-field", "data-theme-static"}:
                    edits.append((start, end, ""))
            elif action == "preserve":
                insert = start + len(opening)
                if not re.search(r"(?:^|;)\s*font-size\s*:", style, re.I):
                    attribute = next(a for a in _ATTRIBUTE.finditer(opening) if a[1].lower() == "style")
                    value_start, value_end = attribute.span(2)
                    edits.append((start + value_start, start + value_end,
                                  '"' + html.escape("font-size:0;line-height:0;" + style, quote=True) + '"'))
                edits.append((insert, insert, "&#160;"))
        return self._rewrite(edits)


def _empty_style(style: str) -> str | None:
    """Keep ornamental geometry; only delete provably inert legacy spans/paragraphs."""
    declarations = [tuple(part.split(":", 1)) for part in style.lower().split(";") if ":" in part]
    declarations = [(name.strip(), value.strip()) for name, value in declarations]
    geometry = False
    for name, value in declarations:
        if name in {"width", "height", "min-width", "min-height", "max-width", "max-height"}:
            geometry = True
            if not name.startswith("max-") and value != "auto" and not _ZERO_LENGTH.fullmatch(value):
                return "preserve"
        elif name.startswith("background-") or name == "background":
            geometry = True
            if value not in {"transparent", "none", "initial", "unset"}:
                return "preserve"
        elif re.fullmatch(r"border(?:-(?:top|right|bottom|left))?(?:-(?:width|style|color))?", name):
            geometry = True
            if value not in _NO_BORDER:
                return "preserve"
    if not geometry:
        return None
    # Unknown declarations, negative spacing, and box shadows may affect layout.
    for name, value in declarations:
        if name in {"margin", "padding"} and any(not _ZERO_LENGTH.fullmatch(part) for part in value.split()):
            return "preserve"
        if name in {"box-shadow", "outline", "transform"} and value != "none":
            return "preserve"
        if name in {"display", "position", "float", "clear"} and value not in {"inline", "block", "inline-block", "static", "none"}:
            return "preserve"
        if name not in {
            "color", "opacity", "display", "position", "float", "clear", "text-align",
            "overflow", "overflow-wrap", "box-sizing", "vertical-align",
            "width", "height", "min-width", "min-height", "max-width", "max-height",
            "margin", "padding", "box-shadow", "outline", "transform",
        } and not re.match(r"^(?:background|border|font|line-height|letter-spacing)(?:-|$)", name):
            return "preserve"
    return "remove"


def preserve_wechat_decorative_nodes(document: str) -> str:
    return DeliveryMarkup(document).normalize_empty_elements()
