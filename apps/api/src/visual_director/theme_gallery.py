from __future__ import annotations

from typing import Any

from .brief_compiler import visual_system_configuration, visual_system_variant
from .component_catalog import (
    COMPONENT_CATALOG,
    CORE_THEME_COMPONENTS,
    VISUAL_SYSTEM_CATALOG,
    VISUAL_SYSTEM_ORDER,
)
from .components import render_component
from .parser import ContentBlock, ParsedArticle, parse_markdown


THEME_GALLERY_SCHEMA_VERSION = "theme_gallery.v0.3"

THEME_FIXTURE = """# 把复杂选择变成一条清晰的行动路线

真正有效的排版，不是把每一段都装进卡片，而是帮助读者迅速看见重点、证据和下一步。

## 先理解问题，再决定行动

当信息越来越多，读者真正缺少的往往不是更多材料，而是判断材料的顺序。

### 什么是视觉节奏

视觉节奏是通过标题、留白、正文、图片和重点组件的交替，让长文章保持清晰而不显得拥挤。

> 好的组件不会替文章创造结论，只会让原文已有的结构更容易被读者看见。

- 先识别文章结构和读者任务
- 再选择与内容匹配的视觉主题
- 最后只在关键位置使用强调组件

过去常见的做法是每一段都叠加醒目的装饰。

更合适的做法是让正文承担叙事，让组件只服务于重点。

组件不得增加正文中不存在的事实、判断或行动建议。
"""


def _first_block(
    parsed: ParsedArticle,
    block_type: str,
    *,
    level: int | None = None,
    skip: int = 0,
) -> ContentBlock:
    matches = [
        block
        for block in parsed.blocks
        if block.type == block_type and (level is None or block.level == level)
    ]
    return matches[skip]


def _fixture_bindings(parsed: ParsedArticle) -> dict[str, dict[str, str | list[str]]]:
    paragraphs = [block for block in parsed.blocks if block.type == "paragraph"]
    concept_title = _first_block(parsed, "heading", level=3)
    evidence = _first_block(parsed, "quote")
    items = _first_block(parsed, "unordered_list")
    item_refs = [f"{items.id}:item:{index}" for index in range(len(items.content))]
    return {
        "numbered_insight": {"items": item_refs},
        "concept_explainer": {
            "title": concept_title.id,
            "definition": paragraphs[2].id,
        },
        "evidence_callout": {"evidence": evidence.id},
        "action_checklist": {"items": item_refs},
        "before_after_timeline": {
            "before": paragraphs[3].id,
            "after": paragraphs[4].id,
        },
        "warning_note": {"body": paragraphs[5].id},
        "comparison_card": {
            "left": paragraphs[3].id,
            "right": paragraphs[4].id,
        },
        "section_summary": {"items": item_refs},
    }


def _component_specimen(
    parsed: ParsedArticle,
    component_type: str,
    visual_system: str,
    palette: dict[str, str],
    bindings: dict[str, dict[str, str | list[str]]],
) -> dict[str, Any]:
    variant = visual_system_variant(component_type, visual_system)
    return {
        "component_type": component_type,
        "label": COMPONENT_CATALOG[component_type]["label"],
        "variant": variant,
        "variant_label": COMPONENT_CATALOG[component_type]["system_variants"][visual_system]["label"],
        "status": COMPONENT_CATALOG[component_type]
        .get("variant_statuses", {})
        .get(variant, COMPONENT_CATALOG[component_type]["status"]),
        "html": render_component(
            {
                "component_type": component_type,
                "variant": variant,
                "content_bindings": bindings[component_type],
            },
            parsed,
            palette,
        ),
    }


def _rhythm_primitives(
    visual_system: str,
    palette: dict[str, str],
) -> list[dict[str, str]]:
    primary = palette["primary"]
    secondary = palette["secondary"]
    accent = palette["accent"]
    sky = palette["sky"]
    pale = palette["pale"]
    ink = palette["ink"]
    if visual_system == "light_reading":
        return [
            {
                "role": "section_heading",
                "label": "章节标题",
                "html": (
                    f'<section style="margin:39px 0 18px;padding-left:13px;border-left:3px solid {primary};">'
                    '<p style="margin:0 0 5px;color:#76837E;font-family:Georgia,serif;font-size:9px;font-weight:700;letter-spacing:.18em;">SECTION</p>'
                    f'<strong style="display:block;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:21px;line-height:1.5;">先看清问题，再决定行动</strong>'
                    f'<p style="height:1px;margin:9px 0 0;background-color:{sky};"><span style="display:block;width:14px;height:8px;margin-left:-2px;border-radius:12px 2px 12px 2px;background-color:{primary};transform:rotate(-16deg);"></span></p></section>'
                ),
            },
            {
                "role": "subheading",
                "label": "叶片小标题",
                "html": (
                    '<section style="margin:27px 0 12px;white-space:normal;">'
                    f'<span style="display:inline-block;width:19px;height:13px;margin:3px 8px 0 0;border-radius:16px 3px 16px 3px;background-color:{primary};transform:rotate(-8deg);vertical-align:top;"></span>'
                    f'<section style="box-sizing:border-box;display:inline-block;width:87%;padding-bottom:7px;border-bottom:1px solid {secondary};vertical-align:top;"><strong style="color:{ink};font-size:18px;line-height:1.55;">把信息分成三个判断层级</strong></section></section>'
                ),
            },
            {
                "role": "inline_emphasis",
                "label": "行内重点",
                "html": (
                    f'<p style="margin:22px 0;color:{ink};font-size:16px;line-height:1.9;">真正需要强调的不是整段文字，而是'
                    f'<strong style="padding:0 3px;border-bottom:5px solid {accent};color:{primary};font-weight:800;">决定读者下一步的关键词</strong>。</p>'
                ),
            },
            {
                "role": "image_caption",
                "label": "图文呼吸位",
                "html": (
                    f'<section style="margin:28px 0;"><section style="height:158px;padding:20px;background-color:{pale};">'
                    f'<span style="display:block;width:55%;height:9px;margin:20px 0 15px;background-color:{sky};"></span>'
                    f'<span style="display:block;width:76%;height:9px;margin:0 0 15px 14%;background-color:{secondary};"></span>'
                    f'<span style="display:block;width:44%;height:9px;margin-left:37%;background-color:{accent};"></span></section>'
                    f'<p style="margin:8px 0 0;color:#75817C;font-size:11px;line-height:1.55;text-align:center;">图示　图片承担场景，正文负责解释</p></section>'
                ),
            },
            {
                "role": "divider",
                "label": "章节分割线",
                "html": (
                    f'<p style="margin:34px 0;text-align:center;white-space:nowrap;"><span style="display:inline-block;width:29%;height:1px;background-color:{sky};"></span>'
                    f'<span style="display:inline-block;width:15px;height:9px;margin:0 10px;border-radius:14px 3px 14px 3px;background-color:{secondary};transform:rotate(-15deg);"></span>'
                    f'<span style="display:inline-block;width:29%;height:1px;background-color:{sky};"></span></p>'
                ),
            },
            {
                "role": "closing_cta",
                "label": "结尾行动区",
                "html": (
                    f'<section style="margin:34px 0 0;padding:19px 20px;border-radius:24px 24px 7px 24px;background-color:{pale};box-shadow:5px 5px 0 {secondary};">'
                    f'<p style="margin:0 0 7px;color:{primary};font-size:16px;font-weight:800;line-height:1.65;">把复杂选择，变成今天能完成的一步</p>'
                    f'<p style="margin:0;color:{ink};font-size:13px;line-height:1.75;">保存文章，回到真实任务中继续验证。</p></section>'
                ),
            },
        ]
    if visual_system == "warm_humanist":
        return [
            {
                "role": "section_heading",
                "label": "手札章节标题",
                "html": (
                    f'<section style="margin:40px 0 20px;padding:3px 0 12px 17px;border-left:5px solid {secondary};border-bottom:1px solid #D7B995;">'
                    f'<p style="margin:-9px 0 11px -25px;"><span style="display:inline-block;padding:5px 10px;background-color:{palette["accent_pale"]};color:{accent};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.12em;transform:rotate(-2deg);">CHAPTER</span></p>'
                    f'<strong style="display:block;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:21px;line-height:1.52;">让故事成为判断的入口</strong>'
                    f'<p style="margin:9px 0 -17px;text-align:right;"><span style="display:inline-block;width:46px;height:9px;background-color:{secondary};opacity:.72;transform:rotate(-3deg);"></span></p></section>'
                ),
            },
            {
                "role": "subheading",
                "label": "页边小标题",
                "html": (
                    '<section style="margin:27px 0 12px;white-space:normal;">'
                    f'<span style="display:inline-block;width:23px;height:23px;margin-right:9px;border:1px solid {primary};border-radius:50%;color:{primary};font-size:12px;font-weight:800;line-height:23px;text-align:center;transform:rotate(-7deg);vertical-align:top;">✦</span>'
                    f'<strong style="box-sizing:border-box;display:inline-block;width:86%;padding-bottom:8px;border-bottom:1px dashed #D7B995;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;line-height:1.58;vertical-align:top;">把经历写成可以复用的经验</strong></section>'
                ),
            },
            {
                "role": "inline_emphasis",
                "label": "纸带行内重点",
                "html": (
                    f'<p style="margin:22px 0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:16px;line-height:1.92;">真正值得留下的，是'
                    f'<strong style="padding:1px 4px;border-bottom:7px solid {palette["secondary_pale"]};color:{accent};font-weight:800;">能改变下一次选择的经验</strong>。</p>'
                ),
            },
            {
                "role": "image_caption",
                "label": "相册图文位",
                "html": (
                    f'<section style="margin:29px 0;padding:8px 0 14px;border-bottom:1px solid #D7B995;">'
                    f'<section style="width:86%;height:153px;padding:12px;background-color:#FFF9EF;box-shadow:8px 8px 0 {palette["secondary_pale"]};transform:rotate(-1deg);">'
                    f'<span style="display:block;width:68%;height:11px;margin:27px 0 14px;background-color:{palette["accent_pale"]};"></span>'
                    f'<span style="display:block;width:48%;height:11px;margin-left:27%;background-color:{secondary};"></span></section>'
                    f'<p style="margin:14px 0 0;color:#7B6861;font-size:11px;line-height:1.55;text-align:right;">图示　让图片承接情绪，让正文解释意义</p></section>'
                ),
            },
            {
                "role": "divider",
                "label": "缝线分隔",
                "html": (
                    f'<p style="margin:35px 0;border-top:1px dashed #D7B995;text-align:center;"><span style="display:inline-block;width:11px;height:11px;margin-top:-7px;border:1px solid {primary};border-radius:50%;background-color:{palette["surface"]};"></span>'
                    f'<span style="display:inline-block;width:42px;height:9px;margin:-6px 0 0 9px;background-color:{secondary};opacity:.7;transform:rotate(-3deg);"></span></p>'
                ),
            },
            {
                "role": "closing_cta",
                "label": "落款行动区",
                "html": (
                    f'<section style="margin:35px 0 0;padding:4px 3px 15px 19px;border-left:5px solid {accent};border-bottom:1px solid #D7B995;">'
                    f'<p style="margin:-10px 0 15px -27px;"><span style="display:inline-block;width:72px;height:12px;background-color:{secondary};opacity:.72;transform:rotate(-3deg);"></span></p>'
                    f'<p style="margin:0 0 7px;color:{primary};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:800;line-height:1.65;">把这份经验，带回下一次真实选择</p>'
                    f'<p style="margin:0;color:{ink};font-size:13px;line-height:1.76;">保存文章，并在行动中继续验证。</p></section>'
                ),
            },
        ]
    if visual_system == "editorial_contrast":
        return [
            {
                "role": "section_heading",
                "label": "头条章节标题",
                "html": (
                    f'<section style="margin:40px 0 20px;padding:11px 0 13px;border-top:11px solid {ink};border-bottom:3px solid {ink};">'
                    f'<p style="margin:0 0 8px;color:{accent};font-family:Georgia,serif;font-size:12px;font-weight:800;letter-spacing:.1em;">IDX<span style="display:inline-block;width:46px;height:6px;margin-left:10px;background-color:{primary};"></span></p>'
                    f'<strong style="display:block;color:{ink};font-size:21px;font-weight:850;line-height:1.48;">观点需要证据，也需要清晰立场</strong></section>'
                ),
            },
            {
                "role": "subheading",
                "label": "编辑副标题",
                "html": (
                    f'<section style="margin:28px 0 12px;padding-bottom:8px;border-bottom:2px solid {ink};white-space:normal;">'
                    f'<span style="display:block;width:30px;height:7px;margin:0 0 8px;background-color:{accent};"></span>'
                    f'<strong style="display:block;color:{ink};font-size:18px;line-height:1.5;font-weight:850;">先把关键判断放在版面中央</strong></section>'
                ),
            },
            {
                "role": "inline_emphasis",
                "label": "头条式强调",
                "html": (
                    f'<p style="margin:22px 0;color:{ink};font-size:16px;line-height:1.9;"><span style="display:inline-block;margin-right:8px;padding:3px 7px;background-color:{ink};color:#FFFFFF;font-family:Georgia,serif;font-size:10px;font-weight:800;">POINT</span>'
                    f'<strong style="border-bottom:5px solid {accent};color:{primary};font-weight:850;">没有证据的醒目，只是噪声。</strong></p>'
                ),
            },
            {
                "role": "image_caption",
                "label": "跨栏图像位",
                "html": (
                    f'<section style="margin:29px 0;border-top:11px solid {ink};border-bottom:3px solid {ink};">'
                    f'<section style="height:154px;white-space:normal;"><span style="display:inline-block;width:34%;height:154px;background-color:{primary};vertical-align:top;"></span>'
                    f'<span style="display:inline-block;width:66%;height:126px;margin-top:28px;background-color:{pale};vertical-align:top;"><i style="display:block;width:42%;height:8px;margin:36px 0 14px 17px;background-color:{accent};"></i><i style="display:block;width:65%;height:8px;margin-left:17px;background-color:{secondary};"></i></span></section>'
                    f'<p style="margin:8px 0;color:#687370;font-family:Georgia,serif;font-size:9px;font-weight:800;letter-spacing:.12em;text-align:right;">FIG / VISUAL ARGUMENT</p></section>'
                ),
            },
            {
                "role": "divider",
                "label": "校样分隔线",
                "html": (
                    f'<p style="margin:35px 0;border-top:3px solid {ink};"><span style="display:block;width:31%;height:8px;background-color:{accent};"></span></p>'
                ),
            },
            {
                "role": "closing_cta",
                "label": "末版行动区",
                "html": (
                    f'<section style="margin:35px 0 0;padding:0;border-top:12px solid {ink};border-bottom:4px solid {ink};">'
                    f'<p style="width:32%;height:8px;margin:0 0 13px;background-color:{accent};"></p>'
                    f'<p style="margin:0 0 7px;color:{ink};font-size:18px;font-weight:850;line-height:1.58;">保留判断，进入真实验证</p>'
                    f'<p style="margin:0 0 14px;color:#687370;font-size:13px;line-height:1.72;">所有结论仍由人工确认。</p></section>'
                ),
            },
        ]
    if visual_system == "structured_grid":
        return [
            {
                "role": "section_heading",
                "label": "栏目索引标题",
                "html": (
                    f'<section style="margin:40px 0 19px;border-top:4px solid {primary};white-space:normal;">'
                    f'<span style="display:inline-block;width:21%;padding:12px 8px 10px 0;color:{secondary};font-family:Georgia,serif;font-size:20px;font-weight:800;vertical-align:top;">IDX</span>'
                    f'<strong style="box-sizing:border-box;display:inline-block;width:79%;padding:10px 0 11px 14px;border-left:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;color:{ink};font-size:21px;line-height:1.48;vertical-align:top;">建立判断坐标，而不是堆信息</strong></section>'
                ),
            },
            {
                "role": "subheading",
                "label": "索引小标题",
                "html": (
                    '<section style="margin:27px 0 12px;padding-bottom:8px;border-bottom:1px solid #B9C3BE;white-space:normal;">'
                    f'<span style="display:inline-block;width:35px;color:{accent};font-family:Georgia,serif;font-size:11px;font-weight:800;vertical-align:top;">SUB</span>'
                    f'<strong style="display:inline-block;width:86%;color:{ink};font-size:18px;line-height:1.55;vertical-align:top;">先定义评价维度</strong></section>'
                ),
            },
            {
                "role": "inline_emphasis",
                "label": "数据式强调",
                "html": (
                    f'<p style="margin:22px 0;color:{ink};font-size:16px;line-height:1.9;"><span style="display:inline-block;margin-right:8px;padding:2px 6px;background-color:{accent};color:#FFFFFF;font-family:Georgia,serif;font-size:11px;font-weight:800;">KEY</span>'
                    f'<strong style="border-bottom:2px solid {primary};color:{primary};">只有影响判断的信息，才进入组件。</strong></p>'
                ),
            },
            {
                "role": "image_caption",
                "label": "图像数据位",
                "html": (
                    f'<section style="margin:28px 0;border-top:4px solid {primary};"><section style="height:152px;padding:15px;background-color:{pale};white-space:normal;">'
                    f'<span style="display:inline-block;width:28%;height:112px;background-color:{primary};vertical-align:bottom;"></span>'
                    f'<span style="display:inline-block;width:28%;height:76px;margin-left:8%;background-color:{secondary};vertical-align:bottom;"></span>'
                    f'<span style="display:inline-block;width:28%;height:42px;margin-left:8%;background-color:{accent};vertical-align:bottom;"></span></section>'
                    f'<p style="margin:7px 0 0;color:#75817C;font-family:Georgia,serif;font-size:9px;letter-spacing:.12em;text-align:right;">FIG / VISUAL EVIDENCE</p></section>'
                ),
            },
            {
                "role": "divider",
                "label": "坐标分割线",
                "html": (
                    f'<p style="margin:34px 0;border-top:1px solid #AEBBB5;text-align:right;"><span style="display:inline-block;margin-top:-8px;padding-left:9px;background-color:{palette["surface"]};color:{accent};font-family:Georgia,serif;font-size:10px;font-weight:800;">NEXT</span></p>'
                ),
            },
            {
                "role": "closing_cta",
                "label": "执行摘要页尾",
                "html": (
                    f'<section style="margin:35px 0 0;padding:0;border-top:7px solid {primary};">'
                    f'<p style="margin:0;padding:12px 0;border-bottom:1px solid #AEBBB5;color:{primary};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.16em;">NEXT ACTION</p>'
                    f'<p style="margin:15px 0 4px;color:{ink};font-size:17px;font-weight:800;line-height:1.65;">保存方案，进入真实发布验证</p>'
                    f'<p style="margin:0;color:#65716D;font-size:13px;line-height:1.7;">所有结论继续由人工确认。</p></section>'
                ),
            },
        ]
    return []


def _full_preview(
    theme: dict[str, Any],
    specimens: list[dict[str, Any]],
    primitives: list[dict[str, str]],
    palette: dict[str, str],
) -> str:
    body: list[str] = [
        '<main style="box-sizing:border-box;width:100%;padding:34px 25px 42px;background-color:#FFFFFF;">'
    ]
    if theme["label"] == "温暖人文":
        body.extend(
            [
                f'<header style="padding:0 0 24px 18px;border-left:6px solid {palette["secondary"]};border-bottom:1px solid #D7B995;">',
                f'<p style="margin:0 0 13px -19px;"><span style="display:inline-block;padding:5px 11px;background-color:{palette["accent_pale"]};color:{palette["accent"]};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">{theme["label"]}</span></p>',
                f'<h1 style="margin:0;color:{palette["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:29px;line-height:1.42;">把复杂选择变成一条清晰的行动路线</h1>',
                '<p style="margin:16px 0 0;color:#7B6861;font-size:13px;line-height:1.75;">主题统一的是叙事温度与纸页节奏，而不是重复同一种卡片。</p></header>',
            ]
        )
    elif theme["label"] == "编辑对比":
        body.extend(
            [
                f'<header style="padding:0 0 22px;border-top:13px solid {palette["ink"]};border-bottom:4px solid {palette["ink"]};">',
                f'<p style="margin:15px 0 11px;color:{palette["accent"]};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.14em;">{theme["label"]}<span style="display:inline-block;width:52px;height:7px;margin-left:11px;background-color:{palette["primary"]};"></span></p>',
                f'<h1 style="margin:0;color:{palette["ink"]};font-size:30px;line-height:1.36;font-weight:850;">把复杂选择变成一条清晰的行动路线</h1>',
                '<p style="margin:16px 0 0;padding-top:8px;border-top:1px solid #202B33;color:#687370;font-size:13px;line-height:1.7;text-align:right;">主题统一的是编辑秩序与观点强度。</p></header>',
            ]
        )
    else:
        body.extend(
            [
                f'<p style="margin:0 0 12px;color:{palette["primary"]};font-size:10px;font-weight:750;letter-spacing:.16em;">{theme["label"]}</p>',
                f'<h1 style="margin:0;color:{palette["ink"]};font-family:Georgia,\'Noto Serif SC\',serif;font-size:29px;line-height:1.42;">把复杂选择变成一条清晰的行动路线</h1>',
                '<p style="margin:17px 0 28px;color:#65706D;font-size:13px;line-height:1.75;">主题统一的是设计基因，而不是把每一段都装进同一种卡片。</p>',
            ]
        )
    body.append(
        f'<p style="margin:26px 0 20px;color:{palette["ink"]};font-size:16px;line-height:1.9;text-align:justify;">真正有效的排版，不是把每一段都装进卡片，而是帮助读者迅速看见重点、证据和下一步。</p>'
    )
    primitive_by_role = {item["role"]: item["html"] for item in primitives}
    body.append(primitive_by_role.get("section_heading", ""))
    for index, specimen in enumerate(specimens):
        if index == 1:
            body.append(
                f'<p style="margin:23px 0;color:{palette["ink"]};font-size:16px;line-height:1.9;text-align:justify;">正文继续承担叙事。清楚的段落关系，不需要额外容器才能成立。</p>'
            )
            body.append(primitive_by_role.get("inline_emphasis", ""))
        if index == 3:
            body.append(primitive_by_role.get("image_caption", ""))
            body.append(primitive_by_role.get("subheading", ""))
        if index == 5:
            body.append(primitive_by_role.get("divider", ""))
        body.append(specimen["html"])
        if index in {2, 5}:
            body.append(
                f'<p style="margin:20px 0;color:{palette["ink"]};font-size:16px;line-height:1.9;text-align:justify;">'
                "组件只在信息关系需要被看见时出现。不同轮廓交替出现，长文章也不会产生刻意堆砌的感觉。</p>"
            )
    body.append(primitive_by_role.get("closing_cta", ""))
    body.append("</main>")
    return "".join(body)


def build_theme_gallery() -> list[dict[str, Any]]:
    parsed = parse_markdown(THEME_FIXTURE)
    bindings = _fixture_bindings(parsed)
    themes: list[dict[str, Any]] = []
    for visual_system in VISUAL_SYSTEM_ORDER:
        metadata = VISUAL_SYSTEM_CATALOG[visual_system]
        configuration = visual_system_configuration(visual_system)
        palette = configuration["palette"]
        production_triggers = {
            "section_heading": "Markdown H2",
            "subheading": "Markdown H3",
            "inline_emphasis": "Markdown **重点短语**",
            "image_caption": "Markdown 图片 alt；生成图只使用主题图框",
            "divider": "Markdown ---",
            "closing_cta": "品牌配置 fixed_footer",
        }
        primitives = [
            {
                **primitive,
                "production_status": "production",
                "production_trigger": production_triggers[primitive["role"]],
            }
            for primitive in _rhythm_primitives(visual_system, palette)
        ]
        specimens = [
            _component_specimen(parsed, component_type, visual_system, palette, bindings)
            for component_type in CORE_THEME_COMPONENTS
        ]
        themes.append(
            {
                "id": visual_system,
                **metadata,
                "core_component_count": len(specimens),
                "configuration": {
                    "heading_variant": configuration["heading_variant"],
                    "quote_variant": configuration["quote_variant"],
                    "list_variant": configuration["list_variant"],
                    "palette": palette,
                },
                "components": specimens,
                "rhythm_primitives": primitives,
                "full_preview_html": _full_preview(metadata, specimens, primitives, palette),
            }
        )
    return themes
