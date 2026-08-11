from __future__ import annotations

import copy
from collections import Counter
from typing import Any


VISUAL_DNA_SCHEMA_VERSION = "visual_dna.v0.1"
ARTICLE_IMAGE_DIRECTION_SCHEMA_VERSION = "article_image_art_direction.v0.1"
VISUAL_SIGNATURE_SCHEMA_VERSION = "article_visual_signature.v0.1"

DNA_DIMENSIONS = (
    "warmth",
    "saturation",
    "contrast",
    "geometry",
    "tactility",
    "dimensionality",
    "energy",
    "information_density",
    "brand_formality",
)


# Each article theme declares only its own visual character. It does not name
# compatible image styles, so adding a new theme never requires editing an
# existing style definition (D375/D380).
ARTICLE_THEME_MANIFESTS: dict[str, dict[str, Any]] = {
    "light_reading": {
        "dna": {
            "warmth": 0.62,
            "saturation": 0.34,
            "contrast": 0.30,
            "geometry": 0.24,
            "tactility": 0.34,
            "dimensionality": 0.12,
            "energy": 0.34,
            "information_density": 0.36,
            "brand_formality": 0.58,
        },
        "material_tags": ["open_page", "soft_ink", "light_paper"],
        "palette_family": "soft_balanced",
        "palette_variants": {
            "teal_sky": ["warm_ivory", "muted_teal", "soft_sky", "coral_accent"],
            "sky_coral": ["warm_ivory", "soft_sky", "muted_teal", "coral_accent"],
        },
        "surface_variants": ["airy_open_page", "soft_margin_paper"],
        "tone": ["轻盈", "清晰", "安静"],
    },
    "warm_humanist": {
        "dna": {
            "warmth": 0.88,
            "saturation": 0.48,
            "contrast": 0.44,
            "geometry": 0.22,
            "tactility": 0.92,
            "dimensionality": 0.18,
            "energy": 0.50,
            "information_density": 0.54,
            "brand_formality": 0.50,
        },
        "material_tags": ["handmade_paper", "watercolor", "editorial_collage"],
        "palette_family": "warm_editorial",
        "palette_variants": {
            "coral_teal": ["warm_ivory", "coral_accent", "muted_teal", "sunlit_yellow"],
            "teal_sunlit": ["warm_ivory", "muted_teal", "sunlit_yellow", "coral_accent"],
        },
        "surface_variants": ["warm_tactile_paper", "watercolor_note_paper"],
        "tone": ["温暖", "可信", "有人情味"],
    },
    "youth_campus": {
        "dna": {
            "warmth": 0.66,
            "saturation": 0.70,
            "contrast": 0.56,
            "geometry": 0.28,
            "tactility": 0.76,
            "dimensionality": 0.20,
            "energy": 0.82,
            "information_density": 0.54,
            "brand_formality": 0.36,
        },
        "material_tags": ["bulletin_paper", "paper_cut", "pencil_mark"],
        "palette_family": "bright_optimistic",
        "palette_variants": {
            "sky_coral": ["warm_ivory", "soft_sky", "coral_accent", "sunlit_yellow"],
            "teal_sunlit": ["warm_ivory", "muted_teal", "sunlit_yellow", "coral_accent"],
        },
        "surface_variants": ["campus_bulletin_paper", "sketchbook_paper"],
        "tone": ["青春", "明快", "有行动感"],
    },
    "editorial_contrast": {
        "dna": {
            "warmth": 0.56,
            "saturation": 0.50,
            "contrast": 0.88,
            "geometry": 0.42,
            "tactility": 0.84,
            "dimensionality": 0.14,
            "energy": 0.72,
            "information_density": 0.68,
            "brand_formality": 0.76,
        },
        "material_tags": ["magazine_paper", "editorial_collage", "ink_rule"],
        "palette_family": "warm_editorial",
        "palette_variants": {
            "navy_coral": ["warm_ivory", "deep_navy", "coral_accent", "sunlit_yellow"],
            "navy_teal": ["warm_ivory", "deep_navy", "muted_teal", "coral_accent"],
        },
        "surface_variants": ["independent_magazine_paper", "annotated_report_paper"],
        "tone": ["鲜明", "理性", "编辑感"],
    },
    "structured_grid": {
        "dna": {
            "warmth": 0.34,
            "saturation": 0.34,
            "contrast": 0.68,
            "geometry": 0.88,
            "tactility": 0.30,
            "dimensionality": 0.76,
            "energy": 0.44,
            "information_density": 0.80,
            "brand_formality": 0.88,
        },
        "material_tags": ["matte_geometry", "spatial_grid", "data_surface"],
        "palette_family": "cool_editorial",
        "palette_variants": {
            "teal_navy": ["warm_ivory", "muted_teal", "deep_navy", "sunlit_yellow"],
            "navy_sky": ["warm_ivory", "deep_navy", "soft_sky", "sunlit_yellow"],
        },
        "surface_variants": ["structured_spatial_surface", "precision_grid_surface"],
        "tone": ["精确", "克制", "有秩序"],
    },
    "future_tech": {
        "dna": {
            "warmth": 0.20,
            "saturation": 0.60,
            "contrast": 0.78,
            "geometry": 0.80,
            "tactility": 0.38,
            "dimensionality": 0.60,
            "energy": 0.74,
            "information_density": 0.66,
            "brand_formality": 0.78,
        },
        "material_tags": ["matte_geometry", "signal_light", "spatial_track"],
        "palette_family": "cool_editorial",
        "palette_variants": {
            "navy_sky": ["warm_ivory", "deep_navy", "soft_sky", "coral_accent"],
            "teal_signal": ["warm_ivory", "deep_navy", "muted_teal", "soft_sky"],
        },
        "surface_variants": ["future_signal_surface", "quiet_technology_surface"],
        "tone": ["未来", "清晰", "可信"],
    },
}


# Image styles are independent capability manifests. They describe what a
# medium is good at, not which article theme it is allowed to pair with.
IMAGE_STYLE_MANIFESTS: dict[str, dict[str, Any]] = {
    "editorial_paper_cut": {
        "dna": {
            "warmth": 0.68,
            "saturation": 0.52,
            "contrast": 0.62,
            "geometry": 0.30,
            "tactility": 0.90,
            "dimensionality": 0.18,
            "energy": 0.66,
            "information_density": 0.62,
            "brand_formality": 0.62,
        },
        "material_tags": ["handmade_paper", "paper_cut", "editorial_collage", "magazine_paper"],
        "style_treatment": "tactile_editorial_collage",
        "edge_treatment": "deckled_paper_frame",
        "decorative_motifs": ["自然纸张毛边", "铅笔批注", "小型索引签"],
        "composition_families": ["editorial_storyline", "open_diagonal", "layered_spread"],
        "content_fit": {
            "data_policy": 0.86,
            "tutorial_steps": 0.88,
            "viewpoint_trend": 1.00,
            "lively_growth": 0.94,
        },
        "provider_reliability": {"seedream": 0.92, "gemini": 0.90, "openai": 0.90, "generic": 0.90},
    },
    "soft_flat_illustration": {
        "dna": {
            "warmth": 0.62,
            "saturation": 0.42,
            "contrast": 0.32,
            "geometry": 0.22,
            "tactility": 0.34,
            "dimensionality": 0.10,
            "energy": 0.42,
            "information_density": 0.38,
            "brand_formality": 0.48,
        },
        "material_tags": ["soft_ink", "light_paper", "open_page", "pencil_mark"],
        "style_treatment": "soft_educational_illustration",
        "edge_treatment": "open_illustrated_edge",
        "decorative_motifs": ["手绘弧线", "微小星点", "轻盈植物或书页"],
        "composition_families": ["open_scene", "gentle_path", "balanced_focus"],
        "content_fit": {
            "data_policy": 0.66,
            "tutorial_steps": 0.92,
            "viewpoint_trend": 0.80,
            "lively_growth": 1.00,
        },
        "provider_reliability": {"seedream": 0.88, "gemini": 0.92, "openai": 0.90, "generic": 0.89},
    },
    "clean_3d_geometry": {
        "dna": {
            "warmth": 0.24,
            "saturation": 0.46,
            "contrast": 0.72,
            "geometry": 0.92,
            "tactility": 0.22,
            "dimensionality": 0.90,
            "energy": 0.58,
            "information_density": 0.70,
            "brand_formality": 0.84,
        },
        "material_tags": ["matte_geometry", "spatial_grid", "spatial_track", "data_surface"],
        "style_treatment": "clean_spatial_geometry",
        "edge_treatment": "clean_spatial_edge",
        "decorative_motifs": ["统一材质小模型", "柔和投影", "细小坐标点"],
        "composition_families": ["spatial_route", "miniature_stage", "axial_system"],
        "content_fit": {
            "data_policy": 1.00,
            "tutorial_steps": 0.80,
            "viewpoint_trend": 0.84,
            "lively_growth": 0.76,
        },
        "provider_reliability": {"seedream": 0.86, "gemini": 0.90, "openai": 0.92, "generic": 0.89},
    },
    "editorial_tech_collage": {
        "dna": {
            "warmth": 0.30,
            "saturation": 0.56,
            "contrast": 0.76,
            "geometry": 0.76,
            "tactility": 0.42,
            "dimensionality": 0.58,
            "energy": 0.74,
            "information_density": 0.66,
            "brand_formality": 0.78,
        },
        "material_tags": ["signal_light", "spatial_track", "editorial_collage", "data_surface"],
        "style_treatment": "editorial_spatial_collage",
        "edge_treatment": "layered_translucent_edge",
        "decorative_motifs": ["半透明信息薄片", "连续信号曲线", "克制的数据光晕"],
        "composition_families": ["asymmetric_editorial_field", "flowing_signal_path", "layered_horizon"],
        "content_fit": {
            "data_policy": 0.94,
            "tutorial_steps": 0.88,
            "viewpoint_trend": 0.92,
            "lively_growth": 0.78,
        },
        "provider_reliability": {"seedream": 0.93, "gemini": 0.91, "openai": 0.92, "generic": 0.92},
    },
}


SCENE_FAMILIES = {
    "data_policy": "evidence_navigation",
    "tutorial_steps": "action_path",
    "viewpoint_trend": "editorial_transition",
    "lively_growth": "growth_scene",
}


def _bounded(value: Any, fallback: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


def _dna_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    distances = [abs(_bounded(left.get(key)) - _bounded(right.get(key))) for key in DNA_DIMENSIONS]
    return 1.0 - (sum(distances) / len(distances))


def _tag_similarity(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set or not right_set:
        return 0.5
    return len(left_set & right_set) / len(left_set | right_set)


def _theme_fit(theme: dict[str, Any], style: dict[str, Any]) -> float:
    # Continuous attributes carry most of the decision. Material overlap is a
    # softer signal, allowing combinations the original hard matrix rejected.
    return 0.82 * _dna_similarity(theme["dna"], style["dna"]) + 0.18 * _tag_similarity(
        list(theme.get("material_tags") or []),
        list(style.get("material_tags") or []),
    )


def _recent_signatures(recent_summaries: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    return [
        summary["visual_signature"]
        for summary in recent_summaries[:limit]
        if isinstance(summary.get("visual_signature"), dict)
    ]


def _novelty_score(
    *,
    signatures: list[dict[str, Any]],
    style_family: str,
    palette_variant: str,
    surface_treatment: str,
    composition_family: str,
    scene_family: str,
) -> float:
    if not signatures:
        return 1.0
    counts: Counter[tuple[str, str]] = Counter()
    for signature in signatures:
        counts[("style", str(signature.get("image_style_family") or signature.get("style_family") or ""))] += 1
        counts[("palette", str(signature.get("palette_variant") or ""))] += 1
        counts[("surface", str(signature.get("surface_treatment") or ""))] += 1
        counts[("composition", str(signature.get("composition_family") or ""))] += 1
        counts[("scene", str(signature.get("scene_family") or ""))] += 1
    denominator = max(1, len(signatures))
    repetition = (
        0.30 * counts[("style", style_family)]
        + 0.20 * counts[("palette", palette_variant)]
        + 0.15 * counts[("surface", surface_treatment)]
        + 0.20 * counts[("composition", composition_family)]
        + 0.15 * counts[("scene", scene_family)]
    ) / denominator
    return max(0.0, 1.0 - repetition)


def resolve_article_image_direction(
    *,
    visual_system: str | None,
    article_type: str,
    recent_summaries: list[dict[str, Any]] | None = None,
    provider_profile: str = "generic",
) -> dict[str, Any]:
    """Resolve one shared art direction from independent Visual DNA manifests.

    The resolver evaluates every style against the current theme and article,
    then rotates palette, surface and composition with recent frozen visual
    signatures. It never stores a theme-to-style compatibility matrix.
    """
    theme_name = str(visual_system or "light_reading")
    theme = ARTICLE_THEME_MANIFESTS.get(theme_name, ARTICLE_THEME_MANIFESTS["light_reading"])
    signatures = _recent_signatures(recent_summaries or [])
    scene_family = SCENE_FAMILIES.get(article_type, "editorial_transition")
    candidates: list[dict[str, Any]] = []
    for style_index, (style_name, style) in enumerate(IMAGE_STYLE_MANIFESTS.items()):
        for palette_index, (palette_variant, palette_roles) in enumerate(theme["palette_variants"].items()):
            for surface_index, surface in enumerate(theme["surface_variants"]):
                for composition_index, composition in enumerate(style["composition_families"]):
                    content_fit = _bounded(style["content_fit"].get(article_type), 0.75)
                    theme_fit = _theme_fit(theme, style)
                    novelty = _novelty_score(
                        signatures=signatures,
                        style_family=style_name,
                        palette_variant=palette_variant,
                        surface_treatment=surface,
                        composition_family=composition,
                        scene_family=scene_family,
                    )
                    provider_reliability = _bounded(
                        style["provider_reliability"].get(
                            provider_profile,
                            style["provider_reliability"].get("generic"),
                        ),
                        0.85,
                    )
                    total = (
                        content_fit * 0.35
                        + theme_fit * 0.30
                        + novelty * 0.25
                        + provider_reliability * 0.10
                    )
                    candidates.append(
                        {
                            "style_family": style_name,
                            "palette_variant": palette_variant,
                            "palette_roles": list(palette_roles),
                            "surface_treatment": surface,
                            "composition_family": composition,
                            "content_fit": content_fit,
                            "theme_fit": theme_fit,
                            "novelty": novelty,
                            "provider_reliability": provider_reliability,
                            "total": total,
                            "stable_order": (style_index, palette_index, surface_index, composition_index),
                        }
                    )
    selected = max(candidates, key=lambda item: (round(item["total"], 8), tuple(-v for v in item["stable_order"])))
    style = IMAGE_STYLE_MANIFESTS[selected["style_family"]]
    return {
        "schema_version": ARTICLE_IMAGE_DIRECTION_SCHEMA_VERSION,
        "visual_dna_schema_version": VISUAL_DNA_SCHEMA_VERSION,
        "visual_system": theme_name,
        "article_type": article_type,
        "style_family": selected["style_family"],
        "style_treatment": style["style_treatment"],
        "palette_family": theme["palette_family"],
        "palette_variant": selected["palette_variant"],
        "palette_roles": list(selected["palette_roles"]),
        "surface_treatment": selected["surface_treatment"],
        "edge_treatment": style["edge_treatment"],
        "decorative_motifs": list(style["decorative_motifs"]),
        "composition_family": selected["composition_family"],
        "scene_family": scene_family,
        "tone": list(theme["tone"]),
        "visual_dna": copy.deepcopy(theme["dna"]),
        "score": round(selected["total"], 4),
        "score_breakdown": {
            "content_fit": round(selected["content_fit"], 4),
            "theme_fit": round(selected["theme_fit"], 4),
            "novelty": round(selected["novelty"], 4),
            "provider_reliability": round(selected["provider_reliability"], 4),
        },
        "history_window_used": min(5, len(signatures)),
    }


def theme_manifest(visual_system: str | None) -> dict[str, Any]:
    name = str(visual_system or "light_reading")
    return copy.deepcopy(ARTICLE_THEME_MANIFESTS.get(name, ARTICLE_THEME_MANIFESTS["light_reading"]))


def style_manifest(style_family: str | None) -> dict[str, Any]:
    name = str(style_family or "editorial_paper_cut")
    return copy.deepcopy(IMAGE_STYLE_MANIFESTS.get(name, IMAGE_STYLE_MANIFESTS["editorial_paper_cut"]))


def compatibility_score(snapshot: dict[str, Any], target_visual_system: str | None) -> float:
    target = theme_manifest(target_visual_system)
    style = style_manifest(str(snapshot.get("style_family") or ""))
    source_dna = snapshot.get("visual_dna")
    if isinstance(source_dna, dict):
        dna_fit = _dna_similarity(target["dna"], source_dna)
    else:
        dna_fit = _dna_similarity(target["dna"], style["dna"])
    material_fit = _tag_similarity(
        list(target.get("material_tags") or []),
        list(style.get("material_tags") or []),
    )
    palette_bonus = 1.0 if snapshot.get("palette_family") == target.get("palette_family") else 0.45
    return round(0.68 * dna_fit + 0.17 * material_fit + 0.15 * palette_bonus, 4)


def build_visual_signature(
    plan: dict[str, Any],
    *,
    selected_snapshots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a fact-free signature suitable for the recent-five history."""
    direction = copy.deepcopy(plan.get("image_art_direction") or {})
    snapshots = [item for item in (selected_snapshots or []) if isinstance(item, dict)]
    if not direction and snapshots:
        direction = copy.deepcopy(snapshots[0])
    if not direction:
        direction = resolve_article_image_direction(
            visual_system=plan.get("visual_system") or plan.get("style_mode"),
            article_type=str(plan.get("article_type") or "viewpoint_trend"),
        )
    layouts = [
        str(slot.get("visual_intent", {}).get("layout_family") or "")
        for slot in plan.get("image_slots", [])
        if slot.get("visual_intent", {}).get("layout_family")
    ]
    return {
        "schema_version": VISUAL_SIGNATURE_SCHEMA_VERSION,
        "article_theme": plan.get("visual_system") or plan.get("style_mode") or "light_reading",
        "image_style_family": direction.get("style_family"),
        "palette_variant": direction.get("palette_variant") or direction.get("palette_family"),
        "composition_family": direction.get("composition_family") or (layouts[0] if layouts else None),
        "surface_treatment": direction.get("surface_treatment"),
        "edge_treatment": direction.get("edge_treatment"),
        "scene_family": direction.get("scene_family") or str(plan.get("article_type") or "viewpoint_trend"),
        "layout_families": list(dict.fromkeys(layouts)),
    }
