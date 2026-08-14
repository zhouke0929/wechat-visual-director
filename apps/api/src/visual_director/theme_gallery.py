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
from .theme_extensions import EXTENDED_THEME_IDS, extended_rhythm_primitives


THEME_GALLERY_SCHEMA_VERSION = "theme_gallery.v0.4"

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
    if visual_system in EXTENDED_THEME_IDS:
        return extended_rhythm_primitives(visual_system, palette)
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
                    f'<p style="margin:-9px 0 11px -18px;"><span style="display:inline-block;padding:5px 10px;background-color:{palette["accent_pale"]};color:{accent};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.12em;transform:rotate(-2deg);">CHAPTER</span></p>'
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
                    f'<p style="margin:-10px 0 15px -18px;"><span style="display:inline-block;width:72px;height:12px;background-color:{secondary};opacity:.72;transform:rotate(-3deg);"></span></p>'
                    f'<p style="margin:0 0 7px;color:{primary};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:800;line-height:1.65;">把这份经验，带回下一次真实选择</p>'
                    f'<p style="margin:0;color:{ink};font-size:13px;line-height:1.76;">保存文章，并在行动中继续验证。</p></section>'
                ),
            },
        ]
    if visual_system == "youth_campus":
        return [
            {
                "role": "section_heading",
                "label": "活页公告章节",
                "html": (
                    f'<section style="margin:40px 0 20px;padding:0 8px 8px 0;"><p style="margin:0 0 -8px 17px;"><span style="display:inline-block;padding:5px 12px;background-color:{secondary};color:{ink};font-size:9px;font-weight:800;letter-spacing:.13em;transform:rotate(-2deg);">COURSE NOTE</span></p>'
                    f'<section style="padding:19px 17px 16px 26px;border-left:10px dotted {sky};border-bottom:3px solid {primary};background-color:{palette["surface"]};box-shadow:7px 7px 0 {palette["secondary_pale"]};"><strong style="display:block;color:{ink};font-size:21px;line-height:1.5;">把信息变成愿意参与的校园议题</strong></section></section>'
                ),
            },
            {
                "role": "subheading",
                "label": "荧光笔小标题",
                "html": (
                    f'<section style="margin:27px 0 12px;white-space:normal;"><span style="display:inline-block;width:32px;height:13px;margin:5px 9px 0 0;background-color:{secondary};transform:rotate(-4deg);vertical-align:top;"></span>'
                    f'<strong style="box-sizing:border-box;display:inline-block;width:84%;padding:0 0 8px;border-bottom:2px dashed {sky};color:{ink};font-size:18px;line-height:1.55;vertical-align:top;">先找到学生真正关心的问题</strong></section>'
                ),
            },
            {
                "role": "inline_emphasis",
                "label": "手账划线重点",
                "html": (
                    f'<p style="margin:22px 0;color:{ink};font-size:16px;line-height:1.9;">年轻感不等于信息噪声，真正要强调的是 '
                    f'<strong style="padding:1px 4px;border-bottom:7px solid {palette["secondary_pale"]};color:{primary};font-weight:850;">能让读者参与判断的关键词</strong>。</p>'
                ),
            },
            {
                "role": "image_caption",
                "label": "相册冲印图位",
                "html": (
                    f'<section style="margin:30px 7px;padding:10px 10px 16px;background-color:{palette["surface"]};box-shadow:8px 8px 0 {palette["sky_pale"]};transform:rotate(-1deg);"><p style="width:68px;height:11px;margin:-17px auto 12px;background-color:{secondary};"></p>'
                    f'<section style="height:148px;background-color:{pale};"><span style="display:block;width:67%;height:12px;margin:0 0 17px;background-color:{secondary};"></span><span style="display:block;width:48%;height:12px;margin-left:34%;background-color:{accent};"></span></section>'
                    f'<p style="margin:11px 0 0;color:#63718A;font-size:11px;line-height:1.55;text-align:center;">图示 · 用场景建立参与感</p></section>'
                ),
            },
            {
                "role": "divider",
                "label": "票根分隔",
                "html": (
                    f'<p style="margin:35px 0;text-align:center;white-space:nowrap;"><span style="display:inline-block;width:19%;height:1px;border-top:2px dashed {sky};"></span>'
                    f'<span style="display:inline-block;width:30px;height:12px;margin:0 10px;background-color:{secondary};transform:rotate(-4deg);vertical-align:middle;"></span><span style="display:inline-block;width:10px;height:10px;margin-right:10px;border-radius:50%;background-color:{accent};vertical-align:middle;"></span>'
                    f'<span style="display:inline-block;width:19%;height:1px;border-top:2px dashed {sky};"></span></p>'
                ),
            },
            {
                "role": "closing_cta",
                "label": "公告栏收束",
                "html": (
                    f'<section style="margin:35px 0 0;padding:20px 18px 17px;border:2px dashed {primary};background-color:{palette["secondary_pale"]};box-shadow:7px 7px 0 {palette["sky_pale"]};"><p style="margin:-29px 0 15px;"><span style="display:inline-block;padding:5px 11px;background-color:{accent};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">NOTICEBOARD</span></p>'
                    f'<p style="margin:0 0 7px;color:{primary};font-size:17px;font-weight:850;line-height:1.65;">把今天的判断带进下一次真实行动</p><p style="margin:0;color:{ink};font-size:13px;line-height:1.76;">保存文章，再回到自己的选择中验证。</p></section>'
                ),
            },
        ]
    if visual_system == "_legacy_youth_campus":
        return [
            {
                "role": "section_heading",
                "label": "贴纸章节标题",
                "html": (
                    f'<section style="margin:40px 0 20px;padding:5px 0 14px;border-bottom:2px solid {sky};">'
                    f'<p style="width:64px;height:12px;margin:0 0 -6px 14px;background-color:{secondary};transform:rotate(-4deg);"></p>'
                    f'<section style="padding:16px 17px;border:2px solid {primary};border-radius:5px 20px 20px 20px;background-color:{palette["surface"]};box-shadow:6px 6px 0 {palette["accent_pale"]};">'
                    f'<p style="margin:0 0 7px;color:{accent};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.13em;">CAMPUS NOTE</p>'
                    f'<strong style="display:block;color:{ink};font-size:21px;line-height:1.5;">把信息变成愿意参与的校园议题</strong></section></section>'
                ),
            },
            {
                "role": "subheading",
                "label": "徽章小标题",
                "html": (
                    '<section style="margin:27px 0 12px;white-space:normal;">'
                    f'<span style="display:inline-block;width:25px;height:25px;margin-right:9px;border-radius:9px 9px 3px 9px;background-color:{accent};color:#FFFFFF;font-size:12px;font-weight:800;line-height:25px;text-align:center;transform:rotate(-5deg);vertical-align:top;">✦</span>'
                    f'<strong style="box-sizing:border-box;display:inline-block;width:85%;padding:1px 0 8px;border-bottom:2px dashed {sky};color:{ink};font-size:18px;line-height:1.55;vertical-align:top;">先找到学生真正关心的问题</strong></section>'
                ),
            },
            {
                "role": "inline_emphasis",
                "label": "荧光笔重点",
                "html": (
                    f'<p style="margin:22px 0;color:{ink};font-size:16px;line-height:1.9;">年轻感不等于信息噪声，真正需要突出的是'
                    f'<strong style="padding:1px 4px;border-bottom:7px solid {palette["secondary_pale"]};color:{primary};font-weight:850;">能让读者参与判断的关键词</strong>。</p>'
                ),
            },
            {
                "role": "image_caption",
                "label": "校园贴页图位",
                "html": (
                    f'<section style="margin:29px 0;padding:7px;border:2px dashed {sky};border-radius:20px 7px 20px 20px;box-shadow:6px 6px 0 {palette["accent_pale"]};">'
                    f'<section style="height:148px;background-color:{pale};"><span style="display:block;width:67%;height:12px;margin:0 0 17px;background-color:{secondary};transform:rotate(-2deg);"></span><span style="display:block;width:48%;height:12px;margin-left:34%;background-color:{accent};"></span></section>'
                    f'<p style="margin:10px 0 2px;color:#63718A;font-size:11px;line-height:1.55;text-align:center;">图示　用场景建立参与感</p></section>'
                ),
            },
            {
                "role": "divider",
                "label": "徽章分隔",
                "html": (
                    f'<p style="margin:35px 0;text-align:center;white-space:nowrap;"><span style="display:inline-block;width:23%;height:2px;background-color:{sky};"></span>'
                    f'<span style="display:inline-block;width:18px;height:18px;margin:0 10px;border:3px solid {accent};border-radius:6px;transform:rotate(13deg);vertical-align:middle;"></span>'
                    f'<span style="display:inline-block;width:23%;height:2px;background-color:{secondary};"></span></p>'
                ),
            },
            {
                "role": "closing_cta",
                "label": "打卡行动区",
                "html": (
                    f'<section style="margin:35px 0 0;padding:20px 18px;border:2px dashed {sky};border-radius:20px 7px 20px 20px;background-color:{palette["surface"]};box-shadow:6px 6px 0 {palette["accent_pale"]};">'
                    f'<p style="margin:0 0 7px;color:{primary};font-size:17px;font-weight:850;line-height:1.65;">把今天的判断，带进下一次真实行动</p>'
                    f'<p style="margin:0;color:{ink};font-size:13px;line-height:1.76;">保存文章，再回到自己的选择中验证。</p></section>'
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
    if visual_system == "future_tech":
        return [
            {
                "role": "section_heading",
                "label": "杂志大号章节",
                "html": (
                    f'<section style="margin:44px 0 22px;padding:0 0 10px;white-space:normal;"><span style="display:inline-block;width:19%;color:{palette["sky_pale"]};font-family:Georgia,serif;font-size:46px;font-weight:800;line-height:.92;vertical-align:top;">01</span>'
                    f'<section style="box-sizing:border-box;display:inline-block;width:81%;padding:2px 0 10px 16px;border-left:5px solid {secondary};vertical-align:top;"><strong style="display:block;color:{ink};font-size:21px;line-height:1.52;">从趋势信号中识别真正变化</strong>'
                    f'<p style="height:3px;margin:11px 0 0;background:linear-gradient(90deg,{accent} 0%,{accent} 28%,{palette["sky_pale"]} 28%);"></p></section></section>'
                ),
            },
            {
                "role": "subheading",
                "label": "极光叶片小标题",
                "html": (
                    f'<section style="margin:29px 0 13px;white-space:normal;"><span style="display:inline-block;width:18px;height:8px;margin:6px 10px 0 0;border-radius:12px 2px 12px 2px;background-color:{secondary};transform:rotate(-12deg);vertical-align:top;"></span>'
                    f'<strong style="box-sizing:border-box;display:inline-block;width:87%;padding:0 0 8px;color:{ink};font-size:18px;line-height:1.55;vertical-align:top;">先确认技术真正改变了什么</strong></section>'
                ),
            },
            {
                "role": "inline_emphasis",
                "label": "柔光划线重点",
                "html": (
                    f'<p style="margin:22px 0;color:{ink};font-size:16px;line-height:1.9;">前沿感来自 '
                    f'<strong style="padding:1px 4px;border-bottom:6px solid {palette["secondary_pale"]};color:{primary};font-weight:820;">清晰、可验证的变化信号</strong>，而不是黑色背景。</p>'
                ),
            },
            {
                "role": "image_caption",
                "label": "极光视觉图位",
                "html": (
                    f'<section style="margin:30px 0;padding:12px;border-radius:4px 36px 4px 24px;background:linear-gradient(135deg,{pale},{palette["secondary_pale"]});box-shadow:6px 6px 0 {palette["sky_pale"]};">'
                    f'<section style="height:150px;border-radius:3px 28px 3px 20px;background:linear-gradient(140deg,{palette["sky_pale"]},{palette["secondary_pale"]});"><span style="display:block;width:72%;height:8px;margin:24px 0 16px;border-radius:10px;background-color:{secondary};"></span><span style="display:block;width:47%;height:8px;margin-left:24%;border-radius:10px;background-color:{accent};"></span></section>'
                    f'<p style="margin:9px 2px 2px;color:#69738F;font-size:9px;font-weight:800;letter-spacing:.1em;text-align:right;">VISUAL / FUTURE EDITION</p></section>'
                ),
            },
            {
                "role": "divider",
                "label": "极光轨迹分隔",
                "html": (
                    f'<p style="margin:36px 0;text-align:center;white-space:nowrap;"><span style="display:inline-block;width:20%;height:1px;background-color:{sky};vertical-align:middle;"></span><span style="display:inline-block;width:18px;height:7px;margin:0 8px;border-radius:12px 2px 12px 2px;background-color:{secondary};transform:rotate(-12deg);vertical-align:middle;"></span>'
                    f'<span style="display:inline-block;width:7px;height:7px;margin-right:8px;border-radius:50%;background-color:{accent};vertical-align:middle;"></span><span style="display:inline-block;width:20%;height:1px;background-color:{primary};vertical-align:middle;"></span></p>'
                ),
            },
            {
                "role": "closing_cta",
                "label": "极光要点收束",
                "html": (
                    f'<section style="margin:36px 0 0;padding:19px 18px;border-radius:4px 42px 4px 26px;background:linear-gradient(135deg,{palette["secondary_pale"]},{pale});box-shadow:7px 7px 0 {palette["sky_pale"]};">'
                    f'<p style="margin:0 0 9px;color:{primary};font-size:10px;font-weight:800;">要点回收</p><p style="margin:0;color:{ink};font-size:16px;font-weight:750;line-height:1.75;">保留有效信号，进入下一次真实验证</p></section>'
                ),
            },
        ]
    if visual_system == "_legacy_future_tech":
        return [
            {
                "role": "section_heading",
                "label": "信号章节标题",
                "html": (
                    f'<section style="margin:40px 0 20px;border-top:6px solid {primary};border-bottom:1px solid #B9D8D2;white-space:normal;">'
                    f'<span style="display:inline-block;width:20%;padding:12px 8px 11px 0;color:{accent};font-family:Georgia,serif;font-size:17px;font-weight:800;vertical-align:top;">S01</span>'
                    f'<strong style="box-sizing:border-box;display:inline-block;width:80%;padding:10px 0 12px 15px;border-left:2px solid {secondary};color:{ink};font-size:21px;line-height:1.5;vertical-align:top;">从趋势信号中识别真正变化</strong></section>'
                ),
            },
            {
                "role": "subheading",
                "label": "节点小标题",
                "html": (
                    '<section style="margin:27px 0 12px;padding-bottom:8px;border-bottom:1px solid #B9D8D2;white-space:normal;">'
                    f'<span style="display:inline-block;width:35px;color:{accent};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.1em;vertical-align:top;">NODE</span>'
                    f'<strong style="box-sizing:border-box;display:inline-block;width:86%;padding-left:12px;border-left:2px solid {secondary};color:{ink};font-size:18px;line-height:1.55;vertical-align:top;">先确认技术真正改变了什么</strong></section>'
                ),
            },
            {
                "role": "inline_emphasis",
                "label": "信号线重点",
                "html": (
                    f'<p style="margin:22px 0;color:{ink};font-size:16px;line-height:1.9;">前沿感不来自深色背景，而来自'
                    f'<strong style="padding:1px 3px;border-bottom:3px solid {secondary};color:{primary};font-weight:820;">清楚、可验证的变化信号</strong>。</p>'
                ),
            },
            {
                "role": "image_caption",
                "label": "信号图像位",
                "html": (
                    f'<section style="margin:28px 0;border-top:6px solid {primary};border-left:5px solid {secondary};border-bottom:1px solid #B9D8D2;">'
                    f'<section style="height:150px;padding:16px;background-color:{pale};"><span style="display:block;width:72%;height:8px;margin:24px 0 16px;background-color:{secondary};"></span><span style="display:block;width:47%;height:8px;margin-left:24%;background-color:{accent};"></span></section>'
                    f'<p style="margin:8px 10px;color:#607985;font-family:Georgia,serif;font-size:9px;font-weight:800;letter-spacing:.12em;text-align:right;">VISUAL SIGNAL</p></section>'
                ),
            },
            {
                "role": "divider",
                "label": "轨道分隔",
                "html": (
                    f'<p style="margin:35px 0;border-top:1px solid #B9D8D2;text-align:right;"><span style="display:inline-block;width:24%;height:5px;background-color:{secondary};"></span>'
                    f'<span style="display:inline-block;width:7px;height:7px;margin-left:8px;border-radius:50%;background-color:{accent};vertical-align:middle;"></span></p>'
                ),
            },
            {
                "role": "closing_cta",
                "label": "下一信号页尾",
                "html": (
                    f'<section style="margin:35px 0 0;padding:20px 16px 17px;border-top:7px solid {primary};border-left:5px solid {secondary};border-bottom:1px solid #B9D8D2;background-color:#F5FBFA;">'
                    f'<p style="margin:0 0 7px;color:{primary};font-size:17px;font-weight:820;line-height:1.65;">保留信号，进入下一次真实验证</p>'
                    f'<p style="margin:0;color:{ink};font-size:13px;line-height:1.75;">技术判断仍由事实与人工确认共同完成。</p></section>'
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
    elif theme["label"] == "青春校园":
        body.extend(
            [
                f'<header style="padding:0 0 24px;border-bottom:2px solid {palette["sky"]};">',
                f'<p style="width:72px;height:12px;margin:0 0 -4px 17px;background-color:{palette["secondary"]};transform:rotate(-4deg);"></p>',
                f'<section style="padding:18px;border:2px solid {palette["primary"]};border-radius:6px 22px 22px 22px;background-color:{palette["surface"]};box-shadow:7px 7px 0 {palette["accent_pale"]};"><p style="margin:0 0 11px;color:{palette["accent"]};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.14em;">{theme["label"]}</p>',
                f'<h1 style="margin:0;color:{palette["ink"]};font-size:29px;line-height:1.4;font-weight:820;">把复杂选择变成一条清晰的行动路线</h1>',
                '<p style="margin:16px 0 0;color:#63718A;font-size:13px;line-height:1.75;">主题统一的是参与感和贴页节奏，不是堆满彩色卡片。</p></section></header>',
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
    elif theme["label"] == "未来科技":
        body.extend(
            [
                f'<header style="padding:0 0 23px;border-top:8px solid {palette["primary"]};border-bottom:1px solid #B9D8D2;">',
                f'<p style="width:29%;height:5px;margin:0 0 15px;background-color:{palette["secondary"]};"></p>',
                f'<section style="white-space:normal;"><span style="display:inline-block;width:21%;color:{palette["accent"]};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.13em;vertical-align:top;">{theme["label"]}</span><section style="box-sizing:border-box;display:inline-block;width:79%;padding-left:15px;border-left:2px solid {palette["secondary"]};vertical-align:top;">',
                f'<h1 style="margin:0;color:{palette["ink"]};font-size:29px;line-height:1.4;font-weight:820;">把复杂选择变成一条清晰的行动路线</h1>',
                '<p style="margin:16px 0 0;color:#607985;font-size:13px;line-height:1.75;">主题统一的是信号轨道和模块秩序，而不是黑底科技感。</p></section></section></header>',
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
    if theme.get("english") == "CAMPUS BULLETIN":
        body = [
            '<main style="box-sizing:border-box;width:100%;padding:34px 25px 42px;background-color:#FFFFFF;">',
            f'<header style="padding:0 8px 27px 0;"><p style="margin:0 0 -8px 19px;"><span style="display:inline-block;padding:5px 12px;background-color:{palette["secondary"]};color:{palette["ink"]};font-size:9px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">CAMPUS BULLETIN</span></p>',
            f'<section style="padding:22px 18px 19px 28px;border-left:11px dotted {palette["sky"]};border-bottom:4px solid {palette["primary"]};background-color:{palette["surface"]};box-shadow:8px 8px 0 {palette["secondary_pale"]};"><h1 style="margin:0;color:{palette["ink"]};font-size:29px;line-height:1.4;font-weight:830;">把复杂选择变成一条清晰的行动路线</h1>',
            f'<p style="margin:16px 0 0;padding-top:11px;border-top:2px dashed {palette["sky"]};color:#63718A;font-size:13px;line-height:1.75;">主题统一的是公告栏、活页与票根节奏，不是重复彩色卡片。</p></section></header>',
        ]
    elif theme.get("english") == "FUTURE EDITION":
        body = [
            '<main style="box-sizing:border-box;width:100%;padding:34px 25px 42px;background-color:#FFFFFF;">',
            f'<header style="padding:24px 20px 20px;border-left:6px solid {palette["primary"]};border-radius:0 62px 0 24px;background:linear-gradient(135deg,{palette["surface"]} 0%,{palette["pale"]} 48%,{palette["secondary_pale"]} 100%);box-shadow:8px 8px 0 {palette["sky_pale"]};">',
            f'<p style="margin:0 0 15px;color:{palette["primary"]};font-size:9px;font-weight:800;letter-spacing:.18em;">FUTURE EDITION <span style="color:{palette["accent"]};">●</span></p>',
            f'<h1 style="margin:0;color:{palette["ink"]};font-size:29px;line-height:1.4;font-weight:830;">把复杂选择变成一条清晰的行动路线</h1><p style="margin:16px 0 0;padding-top:11px;border-top:1px solid {palette["sky"]};color:#69738F;font-size:13px;line-height:1.75;">主题统一的是极光色带、错位留白和科学杂志节奏，不是技术术语与密集线框。</p><p style="margin:10px 0 -28px;text-align:right;"><span style="display:inline-block;width:58px;height:10px;border-radius:16px 3px 16px 3px;background-color:{palette["secondary"]};transform:rotate(-6deg);"></span><span style="display:inline-block;width:8px;height:8px;margin-left:8px;border-radius:50%;background-color:{palette["accent"]};"></span></p></header>',
        ]
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
