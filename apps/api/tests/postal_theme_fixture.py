"""Reference-led theme, authored as exportable data (135 reference 89326).

Only the scalloped paper/inset relationship is studied; no source photo,
wording, markup or commercial asset is embedded in the exported theme.
"""
import copy
import math

from theme_layout_fixtures import field, label, rule, stack
from midnight_theme_fixture import row, repeat


def paper(children, fill="sky_pale", **style):
    return {"type": "cutout", "fill": fill, "radius": 4, "pitch": 20,
            "inset": 12, "children": children, "style": style}


def tab(text, **style):
    return label(text, fit="content", color="sky_pale", background="primary",
                 padding=[3, 10, 3, 10], font="mono", **style)


def postmark(bind="index"):
    return field(bind, size="subheading", font="serif", color="primary", width=52, align="center",
                 padding=[8, 0, 8, 0], border=rule(3, "primary", "double"), radius=64, rotate=-6)


def line(points, color="sky", weight=1):
    return {"kind": "polyline", "points": points, "stroke": color, "stroke_width": weight}


def oval(x, y, w, h, color="primary", fill=None, weight=1):
    return {"kind": "ellipse", "x": x, "y": y, "w": w, "h": h,
            "stroke": color, "stroke_width": weight, **({"fill": fill} if fill else {})}


def drawing(width, height, parts, **style):
    return {"type": "drawing", "width": width, "height": height, "parts": parts, "style": style}


def waves(width=96, color="sky"):
    return drawing(width, 24, [line([[round(x*width/24, 2), round(y+2*math.sin(x*math.pi/6), 2)]
                                   for x in range(25)], color) for y in (5, 12, 19)])


def landscape():
    # An authored miniature: warm sun behind ridgelines, two distant birds.
    return drawing(72, 58, [
        oval(46, 7, 14, 14, "accent", "accent", .7),
        line([[4, 43], [25, 15], [42, 40], [52, 27], [68, 43]], "sky", 1.4),
        line([[17, 26], [25, 30], [30, 23]], "sky", .8),
        line([[4, 48], [68, 48]], "sky", .7),
        line([[9, 12], [13, 14], [17, 11]], "primary", .8),
        line([[17, 7], [20, 9], [24, 7]], "primary", .8),
        line([[17, 53], [54, 53]], "secondary", .6),
    ])


def stamp():
    return {"type": "cutout", "fill": "pale", "radius": 2, "pitch": 12, "inset": 10,
            "children": [stack([landscape()], background="sky_pale", padding=4,
                               border=rule(1, "secondary"))], "style": {"width": 104, "fit": "content"}}


def envelope():
    return drawing(112, 64, [
        line([[4, 20], [56, 3], [108, 20], [108, 60], [4, 60], [4, 20]], "sky"),
        line([[4, 20], [56, 46], [108, 20]], "sky"),
        line([[4, 60], [39, 37]], "sky", .7), line([[108, 60], [73, 37]], "sky", .7),
        oval(49, 39, 14, 14, "primary", "accent_pale", 1),
    ])


def airmail():
    # A short edge detail, not a full-page border or another component wrapper.
    return drawing(144, 10, [line([[x, 9], [x+7, 1]], "primary" if i % 2 == 0 else "sky", 3)
                              for i, x in enumerate(range(4, 136, 14))])


def clip():
    return drawing(28, 42, [line([[9, 30], [9, 9], [12, 5], [18, 5], [22, 9], [22, 32],
                               [18, 37], [10, 37], [5, 32], [5, 8], [9, 2], [20, 2],
                               [26, 8], [26, 31]], "secondary", 1.2)])


def folded_corner():
    return drawing(40, 34, [line([[2, 3], [37, 3], [37, 31]], "secondary"),
                           line([[17, 3], [17, 21], [37, 21], [17, 3]], "sky", .8)])


def small_stamp(text=None, bind=None):
    contents = field(bind, color="primary", font="mono", size="subheading", align="center") if bind else label(text, color="primary", font="serif", size="subheading", align="center")
    return {"type": "cutout", "fill": "pale", "radius": 2, "pitch": 12, "inset": 10,
            "children": [stack([contents], background="surface", padding=[1, 0, 1, 0])],
            "style": {"width": 54}}


def bird():
    return drawing(70, 35, [
        line([[4, 6], [31, 15], [57, 4], [43, 19], [65, 15], [51, 24], [37, 25], [28, 32], [30, 23], [4, 6]], "sky", 1),
        line([[16, 13], [34, 19], [49, 12]], "sky", .6),
    ])


def postal_manifest(template):
    value = copy.deepcopy(template)
    value.update(id="postal_letters", name="远方来信", english="LETTERS FROM AFAR",
                 description="白纸上的旅行来信：远山邮票、航空信纹、展开的信笺与邮路站点，把远方的片刻轻轻留在纸上。",
                 ideal_for=["旅行随笔", "城市观察", "人文叙事"], personality=["温暖", "轻盈", "怀旧"],
                 material_tags=["letter_paper", "printed_ink", "postage_perforation"], tone=["亲切", "文艺", "从容"])
    value["palette"] = dict(primary="#873D4B", secondary="#B4A48E", accent="#B57B42", sky="#456877",
                            pale="#EDE9E2", secondary_pale="#FAF6EE", accent_pale="#F2E3DF",
                            sky_pale="#FFFFFF", surface="#FFFFFF", ink="#373936")
    value["version"] = "1.2.0"
    value["visual_dna"].update(warmth=.76, saturation=.28, contrast=.55, geometry=.65, tactility=.8,
                               dimensionality=.25, energy=.3, information_density=.38, brand_formality=.35)
    design = value["design_system"]
    design.update(motifs=["none"], frame="open_corner", marker="coordinate", surface="quiet")
    design["ornament"].update(density=0, corner_radius=0)
    design["typography"].update(heading_scale=1.02, heading_weight=650, body_scale=1, letter_spacing="normal")
    design["rhythm"].update(section_gap=42, component_gap=28, inset=18)
    design["layouts"] = {
        "hero": stack([
            row(stack([field("kicker", size="label", font="mono", color="sky", margin=[8, 0, 18, 0]),
                       waves(96, "secondary")]), stack([stamp()], align="right"), widths=(60, 40)),
            field("title", size="title", font="serif", weight=650, margin=[18, 0, 24, 0]),
            airmail(),
        ], padding=[0, 4, 12, 4]),
        "heading": stack([
            row(stack([postmark(), waves(50, "secondary")], padding=[0, 4, 0, 0]),
                field("title", size="heading", font="serif", padding=[10, 0, 12, 8],
                      border_bottom=rule(1, "primary")), widths=(20, 80)),
        ], padding=[4, 0, 4, 0]),
        "subheading": stack([
            field("title", size="subheading", color="sky", weight=700, padding=[0, 0, 8, 12], border_left=rule(3, "primary")),
            {"type": "rule", "style": {"width": 64, "margin": [0, 0, 0, 12], "border_top": rule(1, "secondary", "dotted")}},
        ]),
        "lead": stack([
            field("body", font="serif", size="subheading", padding=[4, 8, 16, 16], border_left=rule(3, "primary", "double")),
            stack([bird()], align="right"),
        ]),
        "quote": stack([
            row(label("“", size="display", font="serif", color="primary", line_height=1.35),
                stack([envelope()], align="right"), widths=(50, 50), margin=[-12, 0, 8, 0]),
            field("body", font="serif", size="subheading", padding=[0, 2, 20, 2]),
            {"type": "rule", "style": {"border_top": rule(1, "secondary", "dotted")}},
        ], padding=[18, 20, 22, 20], border=rule(1, "pale"), background="surface",
            shadow={"x": 5, "y": 5, "blur": 0, "color": "pale"}, margin=[0, 6, 6, 0]),
        "list": repeat("items", [row(
            field("index", size="caption", font="mono", color="sky", align="center", width=30,
                  padding=[3, 0, 5, 0], border_bottom=rule(1, "secondary")),
            field("item", padding=[2, 0, 8, 0]), widths=(20, 80))], padding=[2, 0, 2, 0]),
        "question_hook": stack([
            row(small_stamp("?"), stack([folded_corner()], align="right"), widths=(50, 50), margin=[0, 0, 14, 0]),
            field("title", size="heading", font="serif", padding=[0, 2, 14, 2]),
            {"type": "rule", "style": {"border_top": rule(1, "secondary", "dotted")}},
        ], border_top=rule(1, "secondary"), border_bottom=rule(1, "secondary"), padding=[14, 14, 18, 14]),
        "numbered_insight": repeat("items", [row(
            small_stamp(bind="index"),
            field("item", padding=[12, 0, 18, 8], border_bottom=rule(1, "secondary", "dotted")), widths=(20, 80))], padding=[10, 0, 2, 0]),
        "evidence_callout": stack([
            row(label("证据摘录", color="primary", font="serif", padding=[8, 0, 0, 0]),
                stack([clip()], align="right", margin=[-22, 0, 0, 0]), widths=(50, 50), margin=[0, 0, 8, 0]),
            field("body", font="serif", padding=[4, 6, 8, 14], border_left=rule(3, "primary", "double")),
            stack([waves(72)], align="right", margin=[12, 0, 0, 0]),
        ], padding=[12, 16, 16, 16], border=rule(1, "pale"),
            shadow={"x": 4, "y": 4, "blur": 0, "color": "pale"}, margin=[12, 5, 5, 0]),
        "before_after_timeline": stack([
            row(label("此前", color="sky", font="serif", border=rule(1, "sky"), width=48, align="center", padding=[5, 0, 5, 0], radius=24),
                field("left", padding=[2, 0, 12, 12]), widths=(20, 80)),
            drawing(48, 28, [line([[24, 2], [24, 24]], "secondary"), line([[20, 19], [24, 24], [28, 19]], "secondary")], margin=[2, 0, 8, 0]),
            row(label("此后", color="primary", font="serif", border=rule(3, "primary", "double"), width=48, align="center", padding=[5, 0, 5, 0], radius=24),
                field("right", padding=[2, 0, 12, 12], border_bottom=rule(1, "secondary", "dotted")), widths=(20, 80)),
        ]),
        "logic_path": stack([
            row(label("沿途记录", color="sky", font="serif", padding=[8, 0, 0, 0]),
                stack([drawing(76, 34, [line([[3, 25], [72, 3], [47, 31], [35, 20], [3, 25]], "sky"),
                                       line([[35, 20], [72, 3]], "sky")])], align="right"), widths=(60, 40), margin=[0, 0, 14, 0]),
            repeat("items", [row(
                field("index", size="caption", color="sky", font="mono", border=rule(1, "sky"),
                      radius=64, width=34, align="center", padding=[4, 0, 4, 0]),
                field("item", padding=[2, 0, 20, 12], border_left=rule(1, "secondary", "dashed")), widths=(20, 80))]),
        ]),
        "concept_explainer": repeat("entries", [stack([
            row(field("title", size="subheading", color="primary", font="serif", padding=[4, 8, 0, 0]),
                stack([field("index", size="caption", font="mono", color="sky", fit="content", padding=[3, 8, 3, 8], border=rule(1, "secondary"))], align="right"), widths=(80, 20), margin=[0, 0, 14, 0]),
            field("body", padding=[0, 0, 2, 0]),
        ], padding=[16, 14, 18, 14], border_top=rule(3, "primary", "double"), border_bottom=rule(1, "secondary"))], margin=[0, 0, 16, 0]),
        "case_card": stack([
            row(tab("现场来信", rotate=-3, margin=[-24, 0, 16, 0]),
                stack([drawing(54, 28, [line([[2, 2], [52, 2], [52, 26], [2, 26], [2, 2]], "sky"),
                                       line([[2, 2], [27, 17], [52, 2]], "sky")])], align="right"), widths=(60, 40)),
            field("title", size="subheading", font="serif", color="primary", margin=[0, 0, 14, 0]),
            field("body"),
        ], padding=[18, 18, 22, 18], background="sky_pale", border=rule(1, "secondary"),
            shadow={"x": 5, "y": 5, "blur": 0, "color": "pale"}, margin=[12, 6, 6, 0]),
        "warning_note": stack([
            row(label("留意", color="primary", fit="content", border=rule(3, "primary", "double"), padding=[3, 10, 3, 10], rotate=-4),
                stack([airmail()], align="right"), widths=(40, 60), margin=[0, 0, 16, 0]),
            field("body", padding=[0, 0, 0, 10], border_left=rule(2, "primary")),
        ], border_bottom=rule(1, "primary"), padding=[8, 4, 18, 4]),
        "action_checklist": stack([
            row(label("行动清单", color="sky", font="serif", size="subheading"),
                stack([clip()], align="right", margin=[-16, 0, 0, 0]), widths=(70, 30), margin=[0, 0, 8, 0]),
            repeat("items", [row(label("□", size="subheading", color="sky"),
                                 field("item", padding=[0, 0, 12, 0], border_bottom=rule(1, "secondary", "dotted")), widths=(20, 80))], padding=[10, 0, 0, 0]),
        ], padding=[14, 16, 18, 16], border_top=rule(1, "secondary"), border_bottom=rule(1, "secondary")),
        "faq_card": stack([
            row(small_stamp("问"), field("title", size="subheading", font="serif", padding=[8, 0, 0, 8]), widths=(20, 80), padding=[0, 0, 18, 0]),
            row(label("答", size="subheading", font="serif", color="sky", width=42, align="center", border=rule(1, "sky"), radius=64, padding=[4, 0, 4, 0]),
                field("body", padding=[2, 0, 12, 8], border_bottom=rule(1, "secondary", "dotted")), widths=(20, 80), padding=[0, 0, 0, 0]),
        ]),
        "comparison_card": row(
            stack([label("一面", color="sky", font="serif", margin=[0, 0, 12, 0]), field("left"),
                   stack([waves(52, "secondary")], margin=[16, 0, 0, 0])], padding=[14, 12, 16, 0], border_top=rule(2, "sky")),
            stack([label("另一面", color="primary", font="serif", margin=[0, 0, 12, 0]), field("right"),
                   stack([folded_corner()], align="right", margin=[12, 0, 0, 0])], padding=[14, 0, 16, 12], border_top=rule(2, "primary"), border_left=rule(1, "secondary", "dotted")),
            widths=(50, 50)),
        "section_summary": stack([
            row(stack([label("把这些留下", size="subheading", font="serif", color="primary", margin=[4, 0, 10, 0]),
                       airmail()]), stack([envelope()], align="right"), widths=(60, 40), margin=[0, 0, 14, 0]),
            repeat("items", [row(field("index", size="caption", font="mono", color="primary"),
                                 field("item", padding=[0, 0, 12, 0], border_bottom=rule(1, "secondary", "dotted")),
                                 widths=(20, 80))], padding=[8, 0, 0, 0]),
        ], padding=[18, 18, 22, 18], border=rule(1, "secondary"),
            shadow={"x": 4, "y": 4, "blur": 0, "color": "pale"}, margin=[0, 5, 5, 0]),
        "divider": stack([
            waves(96, "secondary"),
        ], align="center", padding=[8, 0, 8, 0]),
        "image_caption": paper([stack([
            {"type": "media"},
            row(field("caption", size="caption", color="sky", padding=[14, 8, 0, 0]),
                stack([waves(60, "primary")], align="right", padding=[16, 0, 0, 0]), widths=(80, 20)),
        ], padding=10, border=rule(1, "secondary"))], fill="secondary_pale", shadow={"x": 0, "y": 1, "blur": 3, "color": "secondary"}),
        "closing_cta": stack([
            row(stack([airmail()], padding=[12, 0, 0, 0]), stack([bird()], align="right"), widths=(60, 40), margin=[0, 0, 18, 0]),
            field("body", font="serif", margin=[0, 0, 18, 0], padding=[0, 0, 16, 0], border_bottom=rule(1, "secondary", "dotted")),
            {"type": "media"},
        ], padding=[8, 0, 0, 0]),
    }
    return value
