"""Authored acceptance theme. Exported as data, never a renderer preset."""
from __future__ import annotations

import copy

from theme_layout_fixtures import field, label, rule, stack


def row(left, right, widths=(25, 75), **style):
    return {"type": "row", "widths": list(widths), "children": [left, right], "style": style}


def repeat(bind, children, **style):
    return {"type": "repeat", "bind": bind, "children": children, "style": style}


def midnight_manifest(template):
    value = copy.deepcopy(template)
    value.update(id="midnight_screening", name="午夜放映", english="MIDNIGHT SCREENING",
                 description="深色片头与暖白长文交替，场记编号、镜头边界和琥珀色字幕构成一套克制的放映语言。",
                 ideal_for=["文化观察", "人物叙事", "深度观点"], personality=["沉静", "鲜明", "叙事感"],
                 material_tags=["matte_film", "warm_paper"], tone=["沉静", "电影感", "清晰"])
    value["palette"] = dict(primary="#202321", secondary="#72766E", accent="#D4A346", sky="#8A968E",
                            pale="#EAE6DC", secondary_pale="#F3E3BD", accent_pale="#F8EAD0",
                            sky_pale="#E7EBE5", surface="#FFFCF4", ink="#292C29")
    value["visual_dna"].update(warmth=.62, saturation=.22, contrast=.85, geometry=.88,
                               tactility=.6, dimensionality=.08, energy=.4, information_density=.45)
    design = value["design_system"]
    design.update(motifs=["none"], frame="open_corner", surface="quiet", marker="coordinate")
    design["ornament"].update(density=0, corner_radius=0)
    design["rhythm"].update(section_gap=46, component_gap=28, inset=18)
    design["typography"].update(heading_scale=1.25, heading_weight=800, letter_spacing="normal")

    # Three restrained frame perforations. Only the opening uses this motif.
    perforations = {"type": "row", "widths": [33, 34, 33], "children": [
        stack([{"type": "shape", "width": 28, "height": 5, "style": {"background": "surface"}}], align=align)
        for align in ("left", "center", "right")
    ]}
    layouts = {
        "hero": stack([
            perforations,
            row(label("夜场", size="display", font="serif", color="accent", line_height=1.35),
                label("MIDNIGHT /\nSCREENING\n\n另一种观看方式", color="surface", font="mono", align="right", padding=[12, 0, 0, 0]),
                widths=(60, 40), margin=[24, 0, 26, 0]),
            field("title", size="title", font="sans", color="surface", line_height=1.5, padding=[0, 64, 0, 0]),
            stack([field("kicker", size="caption", color="primary", font="mono")],
                  background="accent", padding=[12, 14, 12, 14], margin=[32, 0, 0, 0]),
            label("一篇文章 · 一次凝视", color="surface", align="right", margin=[16, 0, 0, 0]),
        ], background="primary", padding=[20, 22, 24, 22]),
        "heading": row(
            stack([label("SCENE", font="mono"), field("index", size="title", font="mono", weight=800)],
                  background="accent", padding=[8, 8, 10, 8], align="center"),
            field("title", size="heading", padding=[4, 0, 8, 16], border_bottom=rule(2)), widths=(20, 80)),
        "subheading": field("title", size="subheading", weight=800, padding=[0, 0, 8, 0], border_bottom=rule(1, "secondary")),
        "lead": field("body", size="subheading", font="serif", padding=[0, 0, 0, 14], border_left=rule(3, "accent")),
        "quote": stack([
            label("“", size="title", color="accent", font="serif"),
            field("body", size="subheading", font="serif", align="center", padding=[0, 12, 16, 12]),
            {"type": "rule", "style": {"margin": [0, 64, 0, 64], "border_top": rule(2, "accent")}},
        ]),
        "list": repeat("items", [row(field("index", size="label", color="secondary", font="mono"),
                                       field("item"), widths=(20, 80))], padding=[8, 0, 8, 0]),
        "question_hook": stack([
            label("镜头向内 / QUESTION", color="secondary", font="mono", margin=[0, 0, 12, 0]),
            field("title", size="heading", font="serif"),
        ], padding=[12, 0, 12, 14], border_left=rule(2), border_bottom=rule(1, "secondary")),
        "numbered_insight": repeat("items", [row(
            field("index", size="title", font="mono", color="accent"),
            field("item", padding=[4, 0, 0, 8]))], padding=[16, 0, 16, 0], border_bottom=rule(1, "secondary")),
        "evidence_callout": stack([
            label("原始记录 / ON RECORD", color="primary", font="mono", background="accent", padding=[6, 10, 6, 10]),
            field("body", font="serif", padding=[18, 16, 18, 16], border_left=rule(1), border_right=rule(1), border_bottom=rule(1)),
        ]),
        "before_after_timeline": stack([
            row(label("BEFORE", font="mono", color="secondary"), field("left"), padding=[0, 0, 20, 0]),
            row(label("AFTER", font="mono", color="primary"), field("right", padding=[0, 0, 0, 12], border_left=rule(3, "accent")),
                padding=[20, 0, 0, 0], border_top=rule(1, "secondary")),
        ]),
        "logic_path": repeat("items", [row(
            stack([label("CUT", font="mono", size="label"), field("index", font="mono", size="subheading")], align="center", color="surface", background="primary", padding=6),
            field("item", padding=[0, 0, 0, 16]), widths=(20, 80))], padding=[0, 0, 18, 0]),
        "concept_explainer": repeat("entries", [
            field("title", size="subheading", weight=800, margin=[0, 0, 8, 0]),
            field("body", padding=[0, 0, 0, 14], border_left=rule(2, "accent")),
        ], padding=[16, 0, 16, 0]),
        "case_card": stack([
            label("特写 / CLOSE-UP", color="accent", font="mono", margin=[0, 0, 12, 0]),
            field("title", size="subheading", color="surface", margin=[0, 0, 18, 0]),
            field("body", color="surface"),
        ], padding=22, background="primary", border_bottom=rule(5, "accent")),
        "warning_note": row(label("注意", font="mono", weight=800), field("body"), widths=(20, 80),
                            background="accent_pale", padding=16, border_top=rule(3, "accent")),
        "action_checklist": repeat("items", [row(label("□", size="heading", color="secondary"), field("item"), widths=(20, 80))],
                                   padding=[12, 0, 12, 0], border_bottom=rule(1, "secondary")),
        "faq_card": stack([
            row(label("Q", size="heading", font="mono", color="accent"), field("title", size="subheading"), widths=(20, 80), padding=[0, 0, 16, 0]),
            row(label("A", size="heading", font="mono", color="secondary"), field("body"), widths=(20, 80), padding=[16, 0, 0, 0], border_top=rule(1, "secondary")),
        ]),
        "comparison_card": stack([
            stack([label("视角 A", font="mono", margin=[0, 0, 8, 0]), field("left")], padding=18, background="pale"),
            stack([label("视角 B", font="mono", color="primary", margin=[0, 0, 8, 0]), field("right")], padding=18, border_left=rule(3, "accent")),
        ]),
        "section_summary": stack([
            label("带走这些 / TAKEAWAYS", font="mono", color="accent", margin=[0, 0, 12, 0]),
            repeat("items", [field("item", color="surface")], padding=[8, 0, 8, 0]),
        ], background="primary", padding=20),
        "divider": row(label("· · ·", font="mono", color="secondary"),
                       label("换一个视角 →", font="mono", align="right", color="secondary"), padding=[12, 0, 12, 0]),
        "image_caption": stack([
            label("STILL / 画面记录", font="mono", color="accent", margin=[0, 0, 10, 0]),
            {"type": "media"},
            field("caption", size="caption", color="surface", margin=[10, 0, 0, 0]),
        ], background="primary", padding=[12, 10, 12, 10]),
        "closing_cta": stack([
            label("END CREDITS", font="mono", color="secondary", margin=[0, 0, 16, 0]),
            field("body", font="serif", size="subheading", margin=[0, 0, 20, 0]),
            {"type": "media"},
            {"type": "shape", "width": 40, "height": 5, "style": {"background": "accent"}},
        ], border_top=rule(2), padding=[24, 0, 0, 0]),
    }
    design["layouts"] = layouts
    return value
