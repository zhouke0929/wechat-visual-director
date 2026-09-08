"""Three authored examples, not renderer presets. Also used by visual acceptance."""
from __future__ import annotations

from visual_director.theme_layouts import ROLE_FIELDS


def field(bind, **style):
    return {"type": "field", "bind": bind, "style": style}


def label(text, **style):
    return {"type": "text", "text": text, "style": {"size": "label", **style}}


def stack(children, **style):
    return {"type": "stack", "children": children, "style": style}


def rule(width=1, color="primary", style="solid"):
    return {"width": width, "color": color, "style": style}


def example_layouts(direction: str):
    """All article bindings are identical; ordering and structure are authored."""
    layouts = {}
    for role, (fields, collection) in ROLE_FIELDS.items():
        if role in {"divider", "image_caption", "closing_cta"}:
            continue
        title = field("title", size="subheading", font="serif", weight=700, margin=[0, 0, 12, 0])
        body = field("body", size="body")
        if collection:
            contents = [field("item")] if collection == "items" else [title, body]
            if direction == "signal":
                contents = [{"type": "row", "widths": [20, 80], "children": [field("index", color="accent", font="mono", size="heading"), stack(contents, padding=[0, 0, 0, 8])]}]
            elif direction == "herbarium":
                contents = [field("index", color="primary", font="serif", size="label"), *contents]
            else:
                contents = [field("index", color="accent", font="mono", size="label"), *contents]
            content = {"type": "repeat", "bind": collection, "style": {"padding": [16, 0, 16, 0], "border_bottom": rule(1, "secondary")}, "children": contents}
        elif fields == {"left", "right"}:
            if direction == "signal":
                content = stack([field("left", padding=12, background="pale"), {"type": "rule"}, field("right", padding=12, border_left=rule(4, "accent"))])
            else:
                content = {"type": "row", "widths": [50, 50], "children": [field("left", padding=[12, 12, 12, 0]), field("right", padding=[12, 0, 12, 12], border_left=rule())]}
        else:
            content = stack(([title] if "title" in fields else []) + ([body] if "body" in fields else []))
        if direction == "ledger":
            layouts[role] = stack([label("READING NOTES", color="accent", font="mono", margin=[0, 0, 12, 0]), content], border_top=rule(4), border_bottom=rule(), padding=[16, 0, 18, 0])
        elif direction == "herbarium":
            layouts[role] = stack([{"type": "shape", "width": 28, "height": 12, "style": {"background": "primary", "radius": [20, 0, 20, 0]}}, content, label("自然观察 · 留下细节", align="right", color="primary", margin=[16, 0, 0, 0])], padding=18, border_left=rule(2, "secondary"), radius=[36, 0, 0, 0], background="pale")
        else:
            layouts[role] = stack([{"type": "row", "widths": [25, 75], "children": [label("FIELD /\nNOTE", color="accent", font="mono"), content]}], border_top=rule(5), padding=[18, 0, 18, 0])

    if direction == "ledger":
        layouts["hero"] = stack([field("kicker", size="label", font="mono", color="accent"), {"type": "rule", "style": {"margin": [12, 0, 18, 0]}}, field("title", size="title", font="serif"), label("文字 · 观点 · 现场", margin=[18, 0, 0, 0], align="right")], border_top=rule(6), border_bottom=rule(3, style="double"), padding=[18, 0, 20, 0])
        layouts["heading"] = {"type": "row", "widths": [20, 80], "children": [field("index", size="heading", font="mono", color="accent"), field("title", size="heading", font="serif", border_bottom=rule(), padding=[0, 0, 12, 0])]}
    elif direction == "herbarium":
        layouts["hero"] = stack([label("THE BOTANICAL JOURNAL", color="primary", font="serif"), {"type": "shape", "width": 40, "height": 18, "style": {"background": "primary", "radius": [30, 0, 30, 0]}}, field("title", size="title", font="serif", margin=[18, 0, 22, 0]), field("kicker", size="label", color="primary")], align="center", padding=[36, 20, 28, 20], border=rule(1, "secondary"), radius=[64, 64, 0, 0], background="pale")
        layouts["heading"] = stack([field("title", size="heading", font="serif"), {"type": "rule", "style": {"margin": [16, 24, 0, 24], "border_top": rule(1, "secondary")}}], align="center", padding=[20, 0, 12, 0])
    else:
        layouts["hero"] = stack([field("kicker", size="label", font="mono", color="accent", margin=[0, 0, 14, 0]), {"type": "row", "widths": [20, 80], "children": [label("OBS /\n001", font="mono", color="accent"), field("title", size="title", font="sans", padding=[0, 0, 0, 12], border_left=rule(3))]}, {"type": "rule", "style": {"margin": [24, 0, 0, 0], "border_top": rule(7, "accent")}}], padding=[24, 0, 12, 0], border_top=rule(1))
        layouts["heading"] = stack([field("index", color="accent", font="mono", size="label"), field("title", size="heading", font="sans", margin=[10, 0, 0, 0])], padding=16, background="pale", border_left=rule(5))
    # Subheadings and lead are prose, not decorated component demonstrations.
    layouts["subheading"] = field("title", size="subheading", font="serif" if direction != "signal" else "sans", padding=[8, 0, 8, 0], border_bottom=rule(1, "secondary"))
    layouts["lead"] = field("body", size="body", padding=[12, 0, 12, 12], border_left=rule(3, "accent"))
    return layouts
