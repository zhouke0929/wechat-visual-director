"""Public specimens built by the article renderer, without tasks or user data."""
from __future__ import annotations

import base64
import html
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from PIL import Image

from .brief_compiler import apply_visual_system
from .parser import parse_markdown
from .planner import generate_plans
from .publication import _materialized_image_markup, _placeholder_metadata
from .renderer import _opening_highlight, render_preview

ARTICLE = """# 给好内容留一点呼吸的空间

本文从标题层级、正文节奏与图文关系出发，帮你用清楚的结构，让读者看见重点，也愿意继续读下去。

排版不是给每一段加一个框。正文负责叙事，**装饰只服务于重点**，留白让不同的信息关系更容易被理解。

## 一、先看内容，再选择表达

### 为什么信息越多，反而越难理解？

当所有段落都同样醒目时，读者很难分清哪些是问题、哪些是解释。先确定阅读顺序，再选择少量需要强调的位置。

> 好的排版不是替文章创造结论，而是让已有的意思更容易被看见。

这里的引用保留为普通引用；并不是所有引文都必须变成证据卡片。

- 标题告诉读者这一节在谈什么。
- 正文保留事实和完整的解释。
- 图片承接叙事，不挤占文字的位置。

![植物插画：演示图片与图注的真实布局](gallery-illustration.png)

## 二、在完整文章中检查节奏

### 三个阅读检查点

1. 看标题能否自然换行，编号是否清楚。
2. 看列表标记与内容是否从同一行开始。
3. 看图片、引用与正文之间是否有合适的停顿。

这些检查不需要把每个组件都塞进一篇文章。部件库负责展示完整能力，成稿负责保持适度的密度。

| 内容关系 | 表达方式 |
| --- | --- |
| 连贯解释 | 普通正文 |
| 并列事项 | 列表 |
| 真实引文 | 引用 |

---

最后回到手机阅读场景，检查标题、文字与图片的关系。工作台预览是本地检查，微信保存后的效果仍需单独确认。

来源：本文为公开排版示例，不包含真实业务数据。

### 参考资料

- [项目说明](https://github.com/zhouke0929/wechat-visual-director)
"""

BRAND = {
    "standard_kicker": "公众号 · 阅读指南",
    "editorial_kicker": "WECHAT · READING NOTES",
    "fixed_footer": {"enabled": True, "text": "把阅读的余量，留给下一篇好内容。"},
}


class _Nodes(HTMLParser):
    """Extract exact source slices; never introduce a second HTML renderer."""

    def __init__(self, document: str):
        super().__init__(convert_charrefs=False)
        self.document = document
        self.offsets = [0]
        for match in re.finditer("\n", document):
            self.offsets.append(match.end())
        self.stack: list[tuple[str, dict, int]] = []
        self.nodes: list[tuple[str, dict, str]] = []
        self.feed(document)

    def _position(self) -> int:
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list):
        if tag not in {"img", "br", "hr", "meta", "link", "input", "source", "wbr"}:
            self.stack.append((tag, dict(attrs), self._position()))

    def handle_startendtag(self, tag: str, attrs: list):
        pass

    def handle_endtag(self, tag: str):
        if not self.stack or self.stack[-1][0] != tag:
            return
        _, attrs, start = self.stack.pop()
        end = self.document.index(">", self._position()) + 1
        self.nodes.append((tag, attrs, self.document[start:end]))


def build_production_specimens(visual_system: str) -> tuple[list[dict[str, Any]], str]:
    parsed = parse_markdown(ARTICLE)
    lead_id, _ = _opening_highlight(parsed)
    if lead_id is None:
        raise ValueError("样本册原稿没有可由正式渲染器识别的导读，不能用普通正文代替")
    plan = apply_visual_system(generate_plans(parsed, "tutorial_steps", 5)[0], visual_system, recent_summaries=[])
    configuration = plan["configuration"]
    plan["image_slots"] = []
    # The library exposes unconsumed Markdown primitives, unlike semantic cards.
    plain_plan = {**plan, "slots": []}
    document = render_preview(parsed, plain_plan, brand_profile=BRAND)
    image_block = next(block for block in parsed.blocks if block.type == "image_reference")
    placeholder = next(markup for _, attrs, markup in _Nodes(document).nodes if attrs.get("id") == image_block.id)
    frame, caption = _placeholder_metadata(placeholder)
    configured_root = os.environ.get("VISUAL_DIRECTOR_PROJECT_ROOT")
    project_root = Path(configured_root).expanduser().resolve() if configured_root else Path(__file__).resolve().parents[4]
    image_path = project_root / "assets/theme-stickers/atlas-leaf.png"
    # This public, bundled illustration works offline and never reads user assets.
    with Image.open(image_path) as image:
        width, height = image.size
    uri = "data:image/png;base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")
    picture = _materialized_image_markup(
        element_id=image_block.id, anchor_class="source-image-anchor", content_url="/api/v1/theme-assets/atlas-leaf.png",
        width=width, height=height, alt="公开植物插画 · 图框演示", frame_variant=frame,
        caption_html=html.escape(html.unescape(caption)), theme_config=configuration,
    )
    # Keep the theme compiler's controlled-asset boundary; embed only after rendering.
    picture = picture.replace('src="/api/v1/theme-assets/atlas-leaf.png"', f'src="{uri}"')
    document = document.replace(placeholder, picture)
    nodes = _Nodes(document).nodes
    lead = next(markup for _, attrs, markup in nodes if attrs.get("data-editor-block-ids") == lead_id)

    def block_markup(block_type: str, *, level: int | None = None, skip: int = 0) -> str:
        blocks = [block for block in parsed.blocks if block.type == block_type and (level is None or block.level == level)]
        block = blocks[skip]
        return next(markup for _, attrs, markup in nodes if attrs.get("data-editor-block-ids") == block.id)

    def role_markup(role: str) -> str:
        return next(markup for _, attrs, markup in nodes if attrs.get("data-content-role") == role
                    or (role == "thematic-break" and attrs.get("data-theme-layout") == "divider"))

    # Authored heroes are arbitrary declarative sections, not necessarily <header>.
    hero = re.search(r'<body[^>]*>(.*?)<main\b', document, re.DOTALL).group(1)

    samples = [
        ("hero", "文章标题与开场", "文章标题；仅用于预览，微信正文交付不重复插入文章标题", hero),
        ("lead", "导读", "首个主章节前，原文中说明阅读目标或核心判断的导读段落；不会自动新增", lead),
        ("paragraph", "普通正文与行内强调", "正文段落与 Markdown **重点短语**", block_markup("paragraph", skip=1)),
        ("section_heading", "章节标题", "Markdown H2", block_markup("heading", level=2)),
        ("subheading", "小标题", "Markdown H3；没有选为问答等语义组件时保留小标题", block_markup("heading", level=3)),
        ("quote", "普通引用", "Markdown > 引文；与证据强调组件分别展示", block_markup("quote")),
        ("unordered_list", "无序列表", "Markdown - 列表；没有映射为强调组件时保留列表", block_markup("unordered_list")),
        ("ordered_list", "有序列表", "Markdown 1. 列表；没有映射为步骤组件时保留列表", block_markup("ordered_list")),
        ("image_caption", "真实图片与图注", "原稿图片与 alt 图注；示例使用公开插画，不调用生图", picture),
        ("table", "表格", "Markdown 表格；列数和文字长度仍会影响手机阅读", block_markup("table")),
        ("divider", "分割线", "Markdown ---", role_markup("thematic-break")),
        ("source", "来源说明", "以“来源：”开头的原文段落", block_markup("source")),
        ("reference_list", "参考资料", "参考资料标题后的链接列表", block_markup("reference_list")),
        ("closing_cta", "品牌页尾", "本地品牌配置 fixed_footer；没有配置时不会自动添加", role_markup("brand-cta")),
    ]
    specimens = [{"role": role, "label": label, "production_trigger": trigger,
                  "production_status": "production", "html": markup} for role, label, trigger, markup in samples]
    article = render_preview(parsed, plan, brand_profile=BRAND).replace(placeholder, picture)
    # Return only body content for embedding; retain the body's production padding.
    content = re.search(r'<body[^>]*>(.*)</body>', article, re.DOTALL).group(1)
    style = re.search(r'<body style="([^"]*)"', article).group(1)
    return specimens, f'<div data-gallery-production-article="true" style="{style}">{content}</div>'
