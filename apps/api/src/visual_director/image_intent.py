from __future__ import annotations

import copy
import re
from typing import Any

from .visual_dna import (
    compatibility_score,
    resolve_article_image_direction,
)


LAYOUT_FAMILIES = {
    "semantic_scene",
    "linear_progression",
    "binary_comparison",
    "comparison_matrix",
    "hierarchical_layers",
    "hub_spoke",
    "structural_breakdown",
    "timeline",
    "pathway",
}

VISUAL_ROLES = {
    "explain_sequence",
    "compare_options",
    "show_evolution",
    "explain_framework",
    "establish_context",
    "create_emotional_pause",
}

STYLE_TREATMENTS = {
    "tactile_editorial_collage",
    "soft_educational_illustration",
    "clean_spatial_geometry",
    "editorial_spatial_collage",
}

TEXT_MODES = {"label_only", "verbatim_full_copy"}

_TIME_RE = re.compile(
    r"(?:19|20)\d{2}(?:年)?|时间轴|时间线|历程|演变|阶段变化|过去.+如今|从\s*(?:19|20)\d{2}.+到\s*(?:19|20)\d{2}"
)
_COMPARE_RE = re.compile(r"对比|比较|差异|不同|前后|过去|现在|传统|新方式|转向|一方面|另一方面")
_SEQUENCE_RE = re.compile(r"步骤|流程|路径|顺序|依次|先.+再|第一|第二|第三|核对|提交|行动|完成")
_FRAMEWORK_RE = re.compile(r"结构|体系|框架|层级|维度|因素|要素|组成|分为|包含")
_PARALLEL_PATH_RE = re.compile(r"导向路径|培养路径|发展路径|选择方向|培养类型")
_LABEL_PHRASE_RE = re.compile(
    r"招生专业目录|招生章程与选科要求|招生章程|选科要求|培养方案|"
    r"升学、就业与校企合作信息|升学、就业与校友去向|升学与就业|校友去向|未来出口|"
    r"成绩和位次|准确位次|专业限制|官方截图|办学能力|师资力量|"
    r"课程结构|实践项目|就业方向|学术训练|项目实践|交叉培养"
)

_STRUCTURAL_TITLE_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"(?:"
    r"第[一二三四五六七八九十百0-9]+(?:层|章|节|部分|步|阶段)|"
    r"(?:PART|CHAPTER)\s*0*\d+|"
    r"(?:章节|层级|步骤)\s*0*\d+"
    r")\s*(?:[：:｜|·.．、/\-—]+\s*|\s+)|"
    r"[（(](?:[一二三四五六七八九十百]+|0*\d+)[）)]\s*(?:[：:｜|·.．、/\-—]+\s*)?|"
    r"(?:[一二三四五六七八九十百]+|0*\d+)\s*[：:｜|·.．、/\-—]+\s*"
    r")",
    re.IGNORECASE,
)

_STYLE_TREATMENT_BY_FAMILY = {
    "editorial_paper_cut": "tactile_editorial_collage",
    "soft_flat_illustration": "soft_educational_illustration",
    "clean_3d_geometry": "clean_spatial_geometry",
    "editorial_tech_collage": "editorial_spatial_collage",
    "oriental_ink_folio": "oriental_ink_folio_illustration",
    "archival_halftone_collage": "archival_halftone_collage",
    "graphic_poster_collage": "graphic_poster_collage",
    "botanical_field_illustration": "botanical_field_illustration",
    "executive_signal_editorial": "executive_signal_editorial",
    "cinematic_storyboard_collage": "cinematic_storyboard_collage",
}

_ROLE_LABELS = {
    "explain_sequence": "先后顺序与行动路径",
    "compare_options": "差异与对照关系",
    "show_evolution": "时间变化与阶段演进",
    "explain_framework": "组成部分与层级关系",
    "establish_context": "整体语境与核心概念",
    "create_emotional_pause": "章节情绪与阅读停顿",
}


def _clean(value: str, *, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize_source_copy(value: str) -> str:
    """Normalize Markdown display syntax without rewriting source wording."""
    plain = re.sub(r"\*\*|__|`", "", str(value or ""))
    plain = re.sub(r"^\s*(?:[-*+]\s+|\d+[.、]\s*)", "", plain)
    return _clean(plain, limit=160)


def strip_structural_title_prefix(value: str) -> str:
    """Remove authoring scaffolds while preserving the semantic source suffix."""
    source = normalize_source_copy(value)
    cleaned = _STRUCTURAL_TITLE_PREFIX_RE.sub("", source, count=1).strip()
    return cleaned or source


def theme_image_profile(
    visual_system: str | None,
    *,
    article_type: str = "viewpoint_trend",
    recent_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a backwards-compatible profile compiled from Visual DNA."""
    return resolve_article_image_direction(
        visual_system=visual_system,
        article_type=article_type,
        recent_summaries=recent_summaries,
    )


def apply_theme_to_image_slot(
    image_slot: dict[str, Any],
    visual_system: str | None,
    *,
    article_type: str | None = None,
    recent_summaries: list[dict[str, Any]] | None = None,
    art_direction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile the current theme into a generation-only image slot copy.

    Persisted article facts and image anchors stay untouched. This lets a user
    switch themes freely while ensuring only future generations adopt the new
    art direction.
    """
    revised = copy.deepcopy(image_slot)
    intent = revised.setdefault("visual_intent", {})
    profile = copy.deepcopy(art_direction) if art_direction else theme_image_profile(
        visual_system,
        article_type=article_type or str(intent.get("article_type") or "viewpoint_trend"),
        recent_summaries=recent_summaries,
    )
    intent["style_family"] = profile["style_family"]
    intent["style_treatment"] = profile["style_treatment"]
    intent["palette_roles"] = list(profile["palette_roles"])
    intent["palette_intent"] = list(profile["palette_roles"])
    intent["tone"] = list(profile.get("tone") or intent.get("tone") or [])[:4]
    intent["article_art_direction"] = profile
    grammar = intent.get("visual_grammar")
    if isinstance(grammar, dict):
        grammar["decorative_motifs"] = list(profile.get("decorative_motifs") or _decorative_motifs(profile["style_family"]))
        grammar["edge_treatment"] = str(profile.get("edge_treatment") or _edge_treatment(profile["style_family"]))
    return revised


def build_art_direction_snapshot(
    *,
    visual_system: str | None,
    visual_intent: dict[str, Any],
    plan_revision: int,
) -> dict[str, Any]:
    direction = visual_intent.get("article_art_direction")
    profile = copy.deepcopy(direction) if isinstance(direction, dict) else theme_image_profile(
        visual_system,
        article_type=str(visual_intent.get("article_type") or "viewpoint_trend"),
    )
    return {
        "schema_version": "image_art_direction_snapshot.v0.2",
        "visual_system": visual_system or "light_reading",
        "plan_revision": plan_revision,
        "style_family": str(visual_intent.get("style_family") or profile["style_family"]),
        "style_treatment": str(visual_intent.get("style_treatment") or profile["style_treatment"]),
        "palette_family": profile["palette_family"],
        "palette_roles": list(visual_intent.get("palette_roles") or profile["palette_roles"]),
        "surface_treatment": profile["surface_treatment"],
        "palette_variant": profile.get("palette_variant"),
        "composition_family": profile.get("composition_family"),
        "edge_treatment": profile.get("edge_treatment"),
        "scene_family": profile.get("scene_family"),
        "visual_dna": copy.deepcopy(profile.get("visual_dna") or {}),
        "score": profile.get("score"),
        "score_breakdown": copy.deepcopy(profile.get("score_breakdown") or {}),
    }


def evaluate_theme_compatibility(
    snapshot: dict[str, Any] | None,
    target_visual_system: str | None,
) -> dict[str, Any]:
    target_name = str(target_visual_system or "light_reading")
    if not snapshot:
        return {
            "level": "unknown",
            "generated_visual_system": None,
            "target_visual_system": target_name,
            "message": "历史图片没有保存美术方向快照，默认保留并由人工判断。",
        }
    source_name = str(snapshot.get("visual_system") or "")
    if source_name == target_name:
        level = "compatible"
        message = "图片与当前主题使用同一美术方向。"
    else:
        score = compatibility_score(snapshot, target_name)
        if score >= 0.72:
            level = "compatible"
            message = "图片与当前主题的视觉 DNA 协调，可直接保留。"
        elif score >= 0.56:
            level = "partial"
            message = "图片与当前主题存在部分气质差异，默认保留并由人工判断。"
        else:
            level = "incompatible"
            message = "图片与当前主题的视觉 DNA 差异较大；仍可保留，也可按新主题重新生成。"
    return {
        "level": level,
        "generated_visual_system": source_name or None,
        "target_visual_system": target_name,
        "message": message,
        "score": None if not snapshot else compatibility_score(snapshot, target_name),
    }


def extract_display_label(value: str, *, budget: int = 14) -> str:
    """Return a short, exact source substring suitable for an image label.

    The function never summarizes. It first honors an author-written bold lead,
    then a phrase before Chinese punctuation, and finally an exact prefix.
    """
    source = normalize_source_copy(value)
    if not source:
        return ""
    bold = re.match(r"^\s*\*\*([^*]{2,24})\*\*", str(value or ""))
    candidates = [bold.group(1).strip()] if bold else []
    candidates.extend(match.group(0) for match in _LABEL_PHRASE_RE.finditer(source))
    candidates.extend(part.strip() for part in re.split(r"[：:；;，,。]", source, maxsplit=1)[:1])
    for candidate in candidates:
        candidate = normalize_source_copy(candidate)
        if 2 <= len(candidate) <= budget and candidate in source:
            return candidate
    if len(source) <= budget:
        return source
    return source[:budget].rstrip("，。；：、 ")


def _node_visual(label: str, article_type: str) -> str:
    routes = (
        (r"研究|理论|论文|学术|知识", "打开的书页、研究笔记与一枚放大镜"),
        (r"实践|应用|项目|动手|作品", "工具、项目草图与正在成形的作品"),
        (r"交叉|融合|组合|跨", "相互咬合的结构与一座连接桥"),
        (r"目录|信息|核对|查询|查看", "资料页、索引签与放大镜"),
        (r"章程|要求|限制|规则|政策", "展开的规则清单与醒目标记"),
        (r"课程|培养|学习|专业", "课程书页、成长路径与学习工具"),
        (r"就业|出口|未来|发展", "通往不同方向的道路与远方地平线"),
        (r"学校|院校|校园|高校", "校园建筑、路标与开放入口"),
        (r"风险|警惕|注意|错误", "克制的提醒标记与防护边界"),
        (r"数据|分数|位次|比例", "数据刻度、坐标点与核验标记"),
    )
    for pattern, visual in routes:
        if re.search(pattern, label):
            return visual
    return {
        "data_policy": "资料页、核验标记与清晰坐标",
        "tutorial_steps": "行动工具、路径节点与完成标记",
        "lively_growth": "书页、植物与学生创作物",
        "viewpoint_trend": "路标、地平线与结构变化",
    }.get(article_type, "与该标签直接对应的一件具体物体")


def _decorative_motifs(style_family: str) -> list[str]:
    return {
        "editorial_paper_cut": ["自然纸张毛边", "铅笔批注", "小型索引签"],
        "soft_flat_illustration": ["手绘弧线", "微小星点", "轻盈植物或书页"],
        "clean_3d_geometry": ["统一材质小模型", "柔和投影", "细小坐标点"],
        "editorial_tech_collage": ["半透明信息薄片", "连续信号曲线", "克制的数据光晕"],
        "oriental_ink_folio": ["册页折线", "淡墨晕染", "克制朱砂印记"],
        "archival_halftone_collage": ["网点油墨", "剪报毛边", "窄版新闻索引"],
        "graphic_poster_collage": ["错位套印", "异形贴纸", "手绘速度线"],
        "botanical_field_illustration": ["植物线稿", "观察编号", "自然生长曲线"],
        "executive_signal_editorial": ["信号轨道", "指标圆盘", "克制方向箭头"],
        "cinematic_storyboard_collage": ["分镜框线", "电影票根", "细腻胶片颗粒"],
    }.get(style_family, ["细线", "少量手绘标记"])


def _edge_treatment(style_family: str) -> str:
    return {
        "editorial_paper_cut": "deckled_paper_frame",
        "soft_flat_illustration": "open_illustrated_edge",
        "clean_3d_geometry": "clean_spatial_edge",
        "editorial_tech_collage": "layered_translucent_edge",
        "oriental_ink_folio": "bound_folio_edge",
        "archival_halftone_collage": "clipped_newsprint_edge",
        "graphic_poster_collage": "misregistered_poster_edge",
        "botanical_field_illustration": "organic_specimen_edge",
        "executive_signal_editorial": "clean_signal_edge",
        "cinematic_storyboard_collage": "film_program_edge",
    }.get(style_family, "open_illustrated_edge")


def build_visual_grammar(
    *,
    layout_family: str,
    fact_anchors: list[str],
    style_family: str,
    article_type: str,
) -> dict[str, Any]:
    """Compile an illustration-first spatial script from source-bound facts."""
    labels = [extract_display_label(value) for value in fact_anchors]
    labels = [value for value in labels if value]
    full_copy = [normalize_source_copy(value) for value in fact_anchors]
    text_mode = (
        "verbatim_full_copy"
        if full_copy and all(len(value) <= 16 for value in full_copy)
        else "label_only"
    )
    if text_mode == "verbatim_full_copy":
        labels = full_copy

    recipes = {
        "linear_progression": (
            "一条可行走的学习路线串起连续行动",
            ["顶部短标题区", "中部连续路线与节点", "底部安静收束区"],
            "用一条不断裂的道路、脚印或细箭线按原文顺序连接",
        ),
        "pathway": (
            "从入口通往目标的单一路径",
            ["左上入口", "中央转折节点", "右下或右侧目标区"],
            "用连续路径和方向标记连接，不画孤立卡片",
        ),
        "binary_comparison": (
            "同一选择面前展开两种并列场景",
            ["顶部共同标题", "左右两个等权场景", "中央边界或连接桥"],
            "以共享基线和中央分界表达差异，不暗示未经原文支持的优劣",
        ),
        "comparison_matrix": (
            "共同入口分出多条不同路径",
            ["顶部共同主题", "中央分流枢纽", "四周错落路径节点"],
            "用分岔路线连接各节点，避免表格和等宽多列卡片",
        ),
        "hierarchical_layers": (
            "一个核心概念展开为层层递进的台阶",
            ["顶部总概念", "中央两到三层台阶", "底部基础层"],
            "用高度、台阶和承托关系表达从属，不用堆叠圆角框",
        ),
        "hub_spoke": (
            "中央主题向周围生长出多个知识岛",
            ["中央核心物", "环绕的错落节点", "节点之间的呼吸留白"],
            "用柔和曲线从中心辐射，节点不排成机械网格",
        ),
        "structural_breakdown": (
            "把一个完整对象拆解成可理解的组成部件",
            ["中央整体轮廓", "周围拆解部件", "短标签贴近对应部件"],
            "用引导线连接整体与部件，保持一个统一场景",
        ),
        "timeline": (
            "一条时间河流穿过不同阶段",
            ["左侧起点", "中央阶段节点", "右侧当前阶段"],
            "用单向时间带连接，只呈现原文已有日期或阶段",
        ),
    }
    metaphor, zones, connector = recipes.get(
        layout_family,
        ("一个清楚的教育主题场景", ["中央主场景", "四周留白"], "只保留一条主要阅读动线"),
    )
    motifs = _decorative_motifs(style_family)
    return {
        "grammar_version": "infographic_visual_grammar.v0.2",
        "scene_metaphor": metaphor,
        "spatial_zones": zones,
        "node_visuals": [_node_visual(label, article_type) for label in labels],
        "connector_language": connector,
        "label_budget": 14,
        "display_labels": labels,
        "decorative_motifs": motifs,
        "text_mode": text_mode,
        "title_mode": "semantic_suffix",
        "content_occupancy": "dense_70_85",
        "edge_treatment": _edge_treatment(style_family),
    }


def infer_structured_layout(subject: str, facts: list[str]) -> tuple[str, str]:
    """Infer an information relationship without inventing article facts."""
    clean_subject = _clean(subject)
    combined = " ".join([clean_subject, *(_clean(item) for item in facts)])
    # The heading/subject is the strongest relationship signal. A single list
    # item may contain a word such as “比较” without turning the whole list into
    # a comparison, while headings such as “改革前后” are explicit.
    if _COMPARE_RE.search(clean_subject):
        return "binary_comparison" if len(facts) == 2 else "comparison_matrix", "compare_options"
    if _TIME_RE.search(clean_subject):
        return "timeline", "show_evolution"
    if len(facts) >= 3 and sum(bool(_PARALLEL_PATH_RE.search(_clean(item))) for item in facts) >= 2:
        return "comparison_matrix", "compare_options"
    if _SEQUENCE_RE.search(combined):
        return "linear_progression", "explain_sequence"
    if _TIME_RE.search(combined):
        return "timeline", "show_evolution"
    if _COMPARE_RE.search(combined):
        return "binary_comparison" if len(facts) == 2 else "comparison_matrix", "compare_options"
    if _FRAMEWORK_RE.search(combined):
        if len(facts) >= 4:
            return "structural_breakdown", "explain_framework"
        return "hierarchical_layers", "explain_framework"
    if len(facts) == 2:
        return "binary_comparison", "compare_options"
    if len(facts) == 3:
        return "hub_spoke", "explain_framework"
    return "structural_breakdown", "explain_framework"


def build_visual_intent(
    *,
    purpose: str,
    subject: str,
    article_type: str,
    title: str | None = None,
    fact_anchors: list[str] | None = None,
    style_family: str = "editorial_paper_cut",
    palette_roles: list[str] | None = None,
    tone: list[str] | None = None,
    negative_space: str | None = None,
    requested_visual_role: str | None = None,
    requested_learning_objective: str | None = None,
    requested_layout_family: str | None = None,
) -> dict[str, Any]:
    """Compile provider-neutral visual intent from article-bound evidence.

    Host-agent suggestions may refine the role and layout, but only known enum
    values are accepted. Fact anchors always come from parsed article blocks.
    """
    clean_subject = _clean(subject) or "当前章节的核心关系"
    anchors = [_clean(value, limit=120) for value in (fact_anchors or []) if _clean(value)]
    anchors = anchors[:6]

    if purpose == "structured_infographic":
        inferred_layout, inferred_role = infer_structured_layout(clean_subject, anchors)
        compatible_layouts = {
            "explain_sequence": {"linear_progression", "pathway"},
            "compare_options": {"binary_comparison", "comparison_matrix"},
            "show_evolution": {"timeline"},
            "explain_framework": {"hierarchical_layers", "hub_spoke", "structural_breakdown"},
        }[inferred_role]
        layout_family = (
            requested_layout_family
            if requested_layout_family in compatible_layouts
            else inferred_layout
        )
        visual_role = (
            requested_visual_role
            if requested_visual_role == inferred_role
            else inferred_role
        )
        objective_subject = _clean(title or clean_subject, limit=80)
        learning_objective = _clean(
            requested_learning_objective
            or f"帮助读者看懂“{objective_subject}”中的{_ROLE_LABELS[visual_role]}，并按原文复述关键节点。",
            limit=180,
        )
        composition = {
            "binary_comparison": "layered",
            "comparison_matrix": "layered",
            "hierarchical_layers": "layered",
            "structural_breakdown": "layered",
            "hub_spoke": "centered",
        }.get(layout_family, "branching")
        default_negative_space = "lower_right"
        visual_grammar = build_visual_grammar(
            layout_family=layout_family,
            fact_anchors=anchors,
            style_family=style_family,
            article_type=article_type,
        )
    else:
        layout_family = "semantic_scene"
        visual_role = (
            requested_visual_role
            if requested_visual_role in {"establish_context", "create_emotional_pause"}
            else "establish_context"
        )
        learning_objective = _clean(
            requested_learning_objective
            or f"帮助读者在进入该章节时形成对“{clean_subject[:80]}”的整体情境认知。",
            limit=180,
        )
        anchors = []
        composition = "wide_scene"
        default_negative_space = "lower_third"
        visual_grammar = {
            "grammar_version": "infographic_visual_grammar.v0.2",
            "scene_metaphor": "单一语义场景",
            "spatial_zones": ["中央主场景", "四周留白"],
            "node_visuals": [],
            "connector_language": "只保留一条主要视觉动线",
            "label_budget": 14,
            "display_labels": [],
            "decorative_motifs": [],
            "text_mode": "label_only",
            "title_mode": "none",
            "content_occupancy": "dense_70_85",
            "edge_treatment": "open_illustrated_edge",
        }

    treatment = _STYLE_TREATMENT_BY_FAMILY.get(
        style_family,
        "tactile_editorial_collage",
    )
    return {
        "subject": clean_subject,
        "visual_role": visual_role,
        "learning_objective": learning_objective,
        "fact_anchors": anchors,
        "layout_family": layout_family,
        "composition": composition,
        "style_family": style_family,
        "style_treatment": treatment,
        "palette_role": "plan_palette",
        "palette_roles": list(palette_roles or [])[:5],
        "palette_intent": list(palette_roles or [])[:5],
        "tone": list(tone or [])[:4],
        "negative_space": negative_space or default_negative_space,
        "visual_grammar": visual_grammar,
        "intent_version": "image_visual_intent.v3",
        "article_type": article_type,
    }


def resolve_display_copy(
    visual_intent: dict[str, Any],
    title: str,
    items: list[str],
) -> tuple[str, list[str]]:
    """Resolve exactly what model-generated infographic text must contain."""
    grammar = visual_intent.get("visual_grammar") or build_visual_grammar(
        layout_family=str(visual_intent.get("layout_family") or "structural_breakdown"),
        fact_anchors=items,
        style_family=str(visual_intent.get("style_family") or "editorial_paper_cut"),
        article_type=str(visual_intent.get("article_type") or "viewpoint_trend"),
    )
    if grammar.get("text_mode") == "verbatim_full_copy":
        labels = [normalize_source_copy(value) for value in items]
    else:
        stored = [normalize_source_copy(value) for value in grammar.get("display_labels") or []]
        labels = stored if len(stored) == len(items) else [extract_display_label(value) for value in items]
    return strip_structural_title_prefix(title), labels


def layout_instruction(layout_family: str, item_count: int) -> str:
    instructions = {
        "linear_progression": "使用自上而下的递进路径，节点按原文顺序排列，箭头只表示既有先后关系",
        "binary_comparison": "使用清楚的双区对照，两组内容同等重要，避免把任一方画成附属说明",
        "comparison_matrix": "使用轻量比较矩阵，让各项差异沿统一基线阅读，不使用密集表格线",
        "hierarchical_layers": "使用由总到分的层级结构，上层概念与下层要点保持清楚从属关系",
        "hub_spoke": "使用中心主题与四周要点的辐射关系，连接线简洁，中心不重复正文长句",
        "structural_breakdown": "将整体拆成相互关联的组成部分，保留共同边界但不堆叠卡片",
        "timeline": "使用单向时间轴呈现阶段演进，节点间距均衡，不虚构日期或转折",
        "pathway": "使用一条连续阅读路径串联节点，路径有起点和终点但不增加原文没有的结论",
    }
    fallback = (
        "两条内容形成清楚对照"
        if item_count == 2
        else "节点沿单一阅读动线按原文顺序排列"
    )
    column_guard = {
        3: "，禁止三列并排",
        4: "，禁止四列并排",
    }.get(item_count, "")
    return f"{instructions.get(layout_family, fallback)}{column_guard}"
