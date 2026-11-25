"""Before/after layouts: one pair of source fields, theme palette, optional stored recipe."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .semantic_content import BoundSemanticContent, SemanticField, field_inline

if TYPE_CHECKING:
    from .component_presentation import ComponentRecipe

# Existing accepted variant names, not a new layout language. Additional native
# shapes below are still selectable using their pre-existing slot variant.
TIMELINE_LAYOUTS = frozenset({"stacked_before_after", "split_page_flip"})


def timeline_margin(recipe: ComponentRecipe | None, default_gap: int) -> str:
    return recipe.margin_css(default_gap) if recipe is not None else f"margin:{default_gap}px 0;"


def timeline_field(value: str | SemanticField, field: str, recipe: ComponentRecipe | None,
                   inline: Callable[[str], str]) -> str:
    if recipe is None or field not in recipe.field_sizes_px:
        return field_inline(value, inline)
    # Only size the authored field. Existing labels, arrows and typography of
    # surrounding decoration stay outside it, and the inline projector escapes
    # source text before any markup is inserted.
    style = recipe.field_css("", field)
    return field_inline(value, lambda source: f'<span style="{style}">{inline(source)}</span>')


def render_timeline(content: BoundSemanticContent, variant: str, colors: dict[str, str],
                    inline: Callable[[str], str], recipe: ComponentRecipe | None) -> str:
    before = timeline_field(content.one("before"), "left", recipe, inline)
    after = timeline_field(content.one("after"), "right", recipe, inline)
    primary, secondary, accent, sky = (colors[key] for key in ("primary", "secondary", "accent", "sky"))
    pale, secondary_pale, accent_pale, sky_pale = (colors[key] for key in ("pale", "secondary_pale", "accent_pale", "sky_pale"))
    surface, ink = colors["surface"], colors["ink"]
    if variant == "stacked_before_after":
        return (
            f'<section style="{timeline_margin(recipe, 25)}">'
            f'<p style="margin:0 0 10px;padding:14px;border-left:4px solid {accent};background-color:{accent_pale};line-height:1.7;"><strong>之前：</strong>{before}</p>'
            f'<p style="margin:0;padding:14px;border-left:4px solid {primary};background-color:{pale};line-height:1.7;"><strong>之后：</strong>{after}</p></section>'
        )
    if variant == "paired_current":
        return (
            f'<section style="{timeline_margin(recipe, 30)}padding:2px 0;white-space:normal;">'
            f'<section style="width:88%;padding:0 0 15px;border-bottom:1px solid {accent};">'
            f'<span style="display:inline-block;width:28px;height:28px;border-radius:50% 50% 50% 5px;background-color:{accent};color:#FFFFFF;font-size:11px;font-weight:800;line-height:28px;text-align:center;vertical-align:top;">前</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:1px 0 0 13px;color:{ink};font-size:14px;line-height:1.78;vertical-align:top;">{before}</p></section>'
            f'<p style="width:12%;height:24px;margin:0 0 0 44%;border-right:2px dotted {sky};"></p>'
            f'<section style="width:88%;margin-left:12%;padding:0 0 15px;border-bottom:1px solid {primary};">'
            f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding:1px 13px 0 0;color:{ink};font-size:14px;line-height:1.78;text-align:right;vertical-align:top;">{after}</p>'
            f'<span style="display:inline-block;width:28px;height:28px;border-radius:50% 5px 50% 50%;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:800;line-height:28px;text-align:center;vertical-align:top;">后</span></section>'
            f'</section>'
        )
    if variant == "shift_axis":
        return (
            f'<section style="{timeline_margin(recipe, 30)}padding-left:19px;border-left:2px solid {primary};">'
            f'<section style="margin:0 0 20px;white-space:normal;">'
            f'<span style="display:inline-block;width:62px;margin-left:-16px;padding:6px 5px;background-color:{accent};color:#FFFFFF;font-size:11px;font-weight:800;text-align:center;vertical-align:top;">基线</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:74%;margin:0;padding:0 0 13px 15px;border-bottom:1px solid #BCC6C1;color:{ink};font-size:14px;line-height:1.76;vertical-align:top;">{before}</p></section>'
            f'<section style="margin:0 0 0 31px;white-space:normal;">'
            f'<span style="display:inline-block;width:62px;margin-left:-16px;padding:6px 5px;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:800;text-align:center;vertical-align:top;">变化</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:70%;margin:0;padding:0 0 13px 15px;border-bottom:4px solid {secondary};color:{ink};font-size:14px;font-weight:650;line-height:1.76;vertical-align:top;">{after}</p></section>'
            f'</section>'
        )
    if variant == "split_page_flip":
        return (
            f'<section style="{timeline_margin(recipe, 31)}padding:10px 8px 16px;background-color:{sky_pale};white-space:normal;">'
            f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:15px 13px;border:1px dashed {accent};background-color:{surface};transform:rotate(-1deg);vertical-align:top;">'
            f'<span style="display:block;margin-bottom:10px;color:{accent};font-size:10px;font-weight:800;letter-spacing:.14em;">BEFORE PAGE</span>'
            f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.77;">{before}</p></section>'
            f'<span style="display:inline-block;width:6%;padding-top:53px;color:{primary};font-size:18px;text-align:center;vertical-align:top;">›</span>'
            f'<section style="box-sizing:border-box;display:inline-block;width:47%;margin-top:15px;padding:15px 13px;border-bottom:5px solid {primary};background-color:{secondary_pale};transform:rotate(1deg);vertical-align:top;">'
            f'<span style="display:block;margin-bottom:10px;color:{primary};font-size:10px;font-weight:800;letter-spacing:.14em;">NEXT PAGE</span>'
            f'<p style="margin:0;color:{ink};font-size:14px;font-weight:650;line-height:1.77;">{after}</p></section></section>'
        )
    if variant == "airy_before_after":
        return (
            f'<section style="{timeline_margin(recipe, 28)}padding:9px 0;border-top:1px solid {sky};border-bottom:1px solid {sky};white-space:normal;">'
            f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:15px 14px;border-radius:18px 18px 5px 18px;background-color:{accent_pale};vertical-align:top;">'
            f'<span style="display:inline-block;width:22px;height:4px;margin-bottom:10px;background-color:{accent};"></span>'
            f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{before}</p></section>'
            f'<span style="display:inline-block;width:6%;padding-top:42px;color:{primary};font-size:18px;text-align:center;vertical-align:top;">→</span>'
            f'<section style="box-sizing:border-box;display:inline-block;width:47%;padding:15px 14px;border-radius:18px 18px 18px 5px;background-color:{pale};vertical-align:top;">'
            f'<span style="display:inline-block;width:22px;height:4px;margin-bottom:10px;background-color:{primary};"></span>'
            f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{after}</p></section></section>'
        )
    if variant == "stitched_before_after":
        return (
            f'<section style="{timeline_margin(recipe, 31)}padding:4px 0 2px 18px;border-left:1px dashed #D7B995;">'
            f'<section style="width:88%;padding:0 0 14px;border-bottom:1px solid #E1CDB2;white-space:normal;">'
            f'<span style="display:inline-block;width:48px;margin-left:-14px;padding:5px 7px;background-color:{accent_pale};color:{accent};font-size:11px;font-weight:800;text-align:center;transform:rotate(-3deg);vertical-align:top;">从前</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:1px 0 0 13px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:14px;line-height:1.82;vertical-align:top;">{before}</p></section>'
            f'<p style="height:27px;margin:0 0 0 47%;border-left:2px dotted {secondary};"></p>'
            f'<section style="width:88%;margin-left:8%;padding:0 0 14px;border-bottom:4px solid {primary};white-space:normal;">'
            f'<span style="display:inline-block;width:48px;margin-left:-14px;padding:5px 7px;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:800;text-align:center;transform:rotate(2deg);vertical-align:top;">后来</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:1px 0 0 13px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:14px;font-weight:650;line-height:1.82;vertical-align:top;">{after}</p></section></section>'
        )
    if variant == "editorial_before_after":
        return (
            f'<section style="{timeline_margin(recipe, 31)}border-top:10px solid {ink};border-bottom:2px solid {ink};white-space:normal;">'
            f'<section style="box-sizing:border-box;display:inline-block;width:43%;min-height:158px;padding:17px 13px 20px 0;border-right:6px solid {accent};vertical-align:top;">'
            f'<span style="display:block;margin-bottom:15px;color:{accent};font-family:Georgia,serif;font-size:14px;font-weight:800;letter-spacing:.08em;">BEFORE</span>'
            f'<p style="margin:0;color:{ink};font-size:14px;line-height:1.78;">{before}</p></section>'
            f'<section style="box-sizing:border-box;display:inline-block;width:57%;min-height:158px;margin-top:18px;padding:16px 0 19px 17px;background-color:{pale};vertical-align:top;">'
            f'<span style="display:block;margin-bottom:13px;color:{primary};font-family:Georgia,serif;font-size:27px;font-weight:800;line-height:1;">AFTER</span>'
            f'<p style="margin:0;color:{ink};font-size:15px;font-weight:700;line-height:1.78;">{after}</p></section></section>'
        )
    if variant == "vector_shift":
        return (
            f'<section style="{timeline_margin(recipe, 34)}padding:4px 0 8px;">'
            f'<section style="width:80%;padding:15px 17px;border-radius:4px 28px 28px 18px;background-color:{accent_pale};"><span style="color:{accent};font-size:10px;font-weight:800;">变化前</span><p style="margin:7px 0 0;color:{ink};font-size:14px;line-height:1.77;">{before}</p></section>'
            f'<p style="height:29px;margin:0 0 0 47%;border-left:2px dotted {secondary};"><span style="display:inline-block;width:8px;height:8px;margin:20px 0 0 -5px;border-radius:50%;background-color:{secondary};"></span></p>'
            f'<section style="width:80%;margin-left:12%;padding:15px 17px;border-radius:28px 4px 18px 28px;background:linear-gradient(135deg,{secondary_pale},{pale});box-shadow:5px 5px 0 {sky_pale};"><span style="color:{primary};font-size:10px;font-weight:800;">变化后</span><p style="margin:7px 0 0;color:{ink};font-size:14px;font-weight:650;line-height:1.77;">{after}</p></section>'
            f'</section>'
        )
    if variant == "change_register":
        return (
            f'<section style="{timeline_margin(recipe, 28)}border:1px solid {primary};background-color:{surface};">'
            f'<section style="height:8px;background-color:{primary};"><span style="display:inline-block;width:24%;height:8px;background-color:{secondary};"></span></section>'
            f'<section style="border-bottom:1px solid #B7C5C0;white-space:normal;"><span style="display:inline-block;width:48px;padding:16px 8px;color:{accent};font-size:12px;font-weight:750;vertical-align:top;">之前</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding:15px 13px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;line-height:1.75;vertical-align:top;">{before}</p></section>'
            f'<section style="white-space:normal;"><span style="display:inline-block;width:48px;padding:16px 8px;color:{primary};font-size:12px;font-weight:750;vertical-align:top;">之后</span><p style="box-sizing:border-box;display:inline-block;width:84%;margin:0;padding:15px 13px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;line-height:1.75;vertical-align:top;">{after}</p></section></section>'
        )
    return (
        f'<section style="{timeline_margin(recipe, 28)}padding:3px 0 3px 13px;border-left:2px dotted {sky};">'
        '<section style="margin:0 0 20px;padding-left:13px;">'
        f'<span style="display:inline-block;margin:0 0 8px;padding:5px 11px;border-radius:4px 12px 12px 12px;background-color:{accent};color:#FFFFFF;font-size:11px;font-weight:750;">改革前</span>'
        f'<p style="margin:0;padding:12px 14px;border-radius:4px 14px 14px 14px;background-color:{accent_pale};color:{ink};font-size:15px;line-height:1.75;">{before}</p></section>'
        '<section style="padding-left:13px;">'
        f'<span style="display:inline-block;margin:0 0 8px;padding:5px 11px;border-radius:4px 12px 12px 12px;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:750;">改革后</span>'
        f'<p style="margin:0;padding:12px 14px;border-radius:4px 14px 14px 14px;background-color:{pale};color:{ink};font-size:15px;line-height:1.75;">{after}</p></section></section>'
    )
