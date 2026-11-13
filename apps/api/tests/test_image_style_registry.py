from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from visual_director import visual_dna
from visual_director.component_catalog import registered_visual_system_order
from visual_director.image_intent import apply_theme_to_image_slot, build_visual_intent
from visual_director.image_provider import (
    COMPOSITION_FAMILY_LABELS,
    build_cover_prompt,
    build_provider_prompt,
)
from visual_director.plan_schema import ArticleImageArtDirection, ImageVisualIntent
from visual_director.visual_dna import (
    IMAGE_STYLE_MANIFESTS,
    ImageStyleRecipe,
    resolve_article_image_direction,
    theme_manifest,
)


ARTICLE_TYPES = ("data_policy", "tutorial_steps", "viewpoint_trend", "lively_growth")
PROMPT_PROFILES = ("generic", "seedream", "openai", "gemini")
TITLE = "开放日路线"
ITEMS = ["先确认入口", "再找体验区", "最后抵达休息点"]


def _fixture_prompts(direction: dict, profile: str, candidate_index: int) -> dict[str, str]:
    article_type = direction["article_type"]
    subject = "社区开放日的小路连接入口、体验桌和休息区"
    prompts = {}
    for purpose in ("atmosphere", "structured_infographic"):
        intent = build_visual_intent(
            purpose=purpose,
            subject=subject,
            title=TITLE,
            fact_anchors=ITEMS if purpose == "structured_infographic" else [],
            article_type=article_type,
        )
        slot = apply_theme_to_image_slot(
            {"purpose": purpose, "aspect_ratio": "4:3" if purpose == "structured_infographic" else "16:9",
             "visual_intent": intent},
            direction["visual_system"],
            art_direction=direction,
        )
        prompts[purpose] = build_provider_prompt(
            slot,
            article_type,
            infographic_title=TITLE,
            infographic_items=ITEMS,
            prompt_profile=profile,
            candidate_index=candidate_index,
        )
    prompts["cover"] = build_cover_prompt(
        {"title": TITLE, "scene_anchor": subject, "article_type": article_type, "image_art_direction": direction},
        prompt_profile=profile,
        candidate_index=candidate_index,
    )
    return prompts


def _prompt_digest(style_id: str) -> str:
    style = IMAGE_STYLE_MANIFESTS[style_id]
    # Both the built-in and the official-pack cover material paths matter.
    prompts = []
    for visual_system in ("light_reading", "pixel_live"):
        for article_type in ARTICLE_TYPES:
            direction = resolve_article_image_direction(
                visual_system=visual_system, article_type=article_type, legacy_only=True
            )
            direction.update(
                style_family=style_id,
                style_treatment=style["style_treatment"],
                edge_treatment=style["edge_treatment"],
                decorative_motifs=style["decorative_motifs"],
            )
            if recipe := style.get("recipe"):
                direction["surface_treatment"] = recipe.surface_id
            for candidate_index, composition in enumerate(style["composition_families"], start=1):
                direction["composition_family"] = composition
                for profile in PROMPT_PROFILES:
                    prompts.extend(_fixture_prompts(direction, profile, candidate_index).values())
    return hashlib.sha256(json.dumps(prompts, ensure_ascii=False).encode("utf-8")).hexdigest()


# Captured before the recipe registry. These guard old host requests, whose
# IDs include the original prompt hash, not just its meaning.
LEGACY_PROMPT_DIGESTS = {
    "editorial_paper_cut": "673846624bc8a8c8cf0f69a52d734d35ea3defd8f3d22fe146056b82ac7b41e4",
    "soft_flat_illustration": "3e20e529719807387db307310352e09fbce298e0d840ac2aa0483b06e5643ee1",
    "clean_3d_geometry": "a1c256a6ff9d4d45c36f534888c200131003275f512c51ce1da97d42d36fcc95",
    "editorial_tech_collage": "099da2fd57732ec74876f02dc9f66229faad81134e24b41ba3baf6208ba12585",
    "oriental_ink_folio": "7e50ee4f34f68b767969f7703a310c72f91dbea7cfaf97e7ea0a4883ba0e8b67",
    "archival_halftone_collage": "d05b73511b31f6389dd5584e1e24e9cb84a12a629e6073a0829865d3624c46d3",
    "graphic_poster_collage": "49867cbeea20836cc9ba59fca9f0bc98d53b63a8c008c6581e1569451ddcb461",
    "botanical_field_illustration": "4106b6c1a96894bc986114b14426086aa99bff4ab9887267a2d7d889079ee0f3",
    "executive_signal_editorial": "f4d80bf30acafa183fa623f74812d39c9cdffe2776470029d6eda3ec8980beab",
    "cinematic_storyboard_collage": "70e2ed19ceb476e2a8d12fb8683df1942847f1336c2e2a1c8f62f3127cfa7ea0",
}


# Newly shipped recipes need the same stability for their own in-flight requests.
RECIPE_PROMPT_DIGESTS = {
    "pixel_editorial": "a05dcae390181d130f768d6cf070f01b57860cb49460ff737d80ec005ddb9c49",
}


@pytest.mark.parametrize(("style_id", "expected"), (LEGACY_PROMPT_DIGESTS | RECIPE_PROMPT_DIGESTS).items())
def test_prompt_hashes_stay_stable_for_issued_host_requests(style_id: str, expected: str) -> None:
    assert _prompt_digest(style_id) == expected


def test_all_new_style_entries_compile_in_every_image_path() -> None:
    # A new entry must not quietly fall through to the old, generic compiler.
    assert IMAGE_STYLE_MANIFESTS.keys() == LEGACY_PROMPT_DIGESTS.keys() | RECIPE_PROMPT_DIGESTS.keys()
    for style_id, style in IMAGE_STYLE_MANIFESTS.items():
        if style_id in LEGACY_PROMPT_DIGESTS:
            assert "recipe" not in style
            continue
        recipe = style.get("recipe")
        assert isinstance(recipe, ImageStyleRecipe), style_id
        assert all(value.strip() for value in (
            recipe.artwork_zh, recipe.artwork_en, recipe.surface_id, recipe.surface_zh, recipe.surface_en
        )), style_id
        assert style["composition_families"], style_id
        assert bool(recipe.cover_framing_zh) == bool(recipe.cover_framing_en), style_id
        assert set(style["composition_families"]) <= COMPOSITION_FAMILY_LABELS.keys(), style_id
        direction = resolve_article_image_direction(visual_system="light_reading", article_type="tutorial_steps")
        direction.update(
            style_family=style_id,
            style_treatment=style["style_treatment"],
            edge_treatment=style["edge_treatment"],
            decorative_motifs=style["decorative_motifs"],
            surface_treatment=recipe.surface_id,
            composition_family=style["composition_families"][0],
        )
        ArticleImageArtDirection.model_validate(direction)
        ImageVisualIntent.model_validate(
            build_visual_intent(purpose="atmosphere", subject=TITLE, article_type="tutorial_steps",
                                style_family=style_id, palette_roles=direction["palette_roles"], tone=direction["tone"])
            | {"article_art_direction": direction}
        )
        for profile in PROMPT_PROFILES:
            prompts = _fixture_prompts(direction, profile, 1)
            for purpose in ("atmosphere", "structured_infographic"):
                assert recipe.artwork_zh in prompts[purpose], (style_id, profile, purpose)
                assert recipe.surface_zh in prompts[purpose], (style_id, profile, purpose)
            expected_artwork = recipe.artwork_zh if profile == "seedream" else recipe.artwork_en
            expected_surface = recipe.surface_zh if profile == "seedream" else recipe.surface_en
            assert expected_artwork in prompts["cover"], (style_id, profile)
            assert expected_surface in prompts["cover"], (style_id, profile)


@pytest.mark.parametrize("profile", PROMPT_PROFILES)
def test_pixel_keeps_text_and_cropping_rules(profile: str) -> None:
    direction = resolve_article_image_direction(visual_system="pixel_live", article_type="tutorial_steps")
    prompts = _fixture_prompts(direction, profile, 1)
    assert "任何文字" in prompts["atmosphere"] or "不要出现文字" in prompts["atmosphere"]
    assert "不使用像素字体" in prompts["structured_infographic"]
    assert "严格文字白名单" in prompts["structured_infographic"]
    for item in ITEMS:
        assert f"“{item}”" in prompts["structured_infographic"]
    assert "5:4" in prompts["cover"]
    safe_area = "高度中央45%的横带" if profile == "seedream" else "middle 45 percent of canvas height"
    no_text = "不出现文字" if profile == "seedream" else "no text"
    assert safe_area in prompts["cover"]
    assert "2.35:1" in prompts["cover"]
    assert safe_area not in prompts["atmosphere"]
    assert safe_area not in prompts["structured_infographic"]
    assert no_text in prompts["cover"]


@pytest.mark.parametrize("profile", PROMPT_PROFILES)
def test_pixel_cover_framing_fits_prompt_budget_with_long_article_context(profile: str) -> None:
    direction = resolve_article_image_direction(visual_system="pixel_live", article_type="lively_growth")
    prompt = build_cover_prompt(
        {
            "article_type": "lively_growth",
            "scene_anchor": "维修桌上并排摆着完整的外壳与零件，手里的镊子指向正在检查的胶垫。" * 5,
            "narrative": "通过一件日常小事说明从发现问题到确认原因的过程。" * 5,
            "image_art_direction": direction,
        },
        prompt_profile=profile,
    )
    assert "2.35:1" in prompt


@pytest.mark.parametrize("article_type", ARTICLE_TYPES)
@pytest.mark.parametrize("profile", PROMPT_PROFILES)
def test_pixel_matches_by_visual_trait_and_does_not_change_other_themes(article_type: str, profile: str) -> None:
    baseline = resolve_article_image_direction(
        visual_system="pixel_live", article_type=article_type, provider_profile=profile, legacy_only=True
    )
    assert baseline["style_family"] in LEGACY_PROMPT_DIGESTS
    direction = resolve_article_image_direction(visual_system="pixel_live", article_type=article_type, provider_profile=profile)
    assert direction["style_family"] == "pixel_editorial"
    assert direction["palette_roles"] == baseline["palette_roles"]
    for theme_id in registered_visual_system_order():
        if "pixel_graphics" in theme_manifest(theme_id)["material_tags"]:
            continue
        old_style = resolve_article_image_direction(
            visual_system=theme_id, article_type=article_type, provider_profile=profile
        )["style_family"]
        recent = [{"visual_signature": {"image_style_family": old_style}}] * 5
        options = dict(visual_system=theme_id, article_type=article_type, provider_profile=profile, recent_summaries=recent)
        assert resolve_article_image_direction(**options) == resolve_article_image_direction(**options, legacy_only=True)


def test_saved_legacy_direction_is_reused_even_when_theme_now_matches_pixel() -> None:
    legacy = resolve_article_image_direction(visual_system="pixel_live", article_type="tutorial_steps", legacy_only=True)
    slot = {"purpose": "atmosphere", "aspect_ratio": "16:9", "visual_intent": {"subject": TITLE}}
    for art_direction in (legacy, None):
        revised = apply_theme_to_image_slot(slot, "pixel_live", article_type="tutorial_steps", art_direction=art_direction)
        assert revised["visual_intent"]["article_art_direction"] == legacy
        assert "阶梯轮廓" not in build_provider_prompt(revised, "tutorial_steps")
    assert slot["visual_intent"] == {"subject": TITLE}


def test_recipe_eligibility_uses_theme_traits_not_id_or_palette(monkeypatch: pytest.MonkeyPatch) -> None:
    theme = theme_manifest("pixel_live")
    theme["palette_family"] = "user_pack:custom_scene"
    theme["palette_variants"] = {"custom": ["#287455", "#F4CE62", "#FFFFFF"]}
    monkeypatch.setattr(visual_dna, "theme_manifest", lambda _: deepcopy(theme))
    with_trait = resolve_article_image_direction(visual_system="custom_scene", article_type="tutorial_steps")
    assert with_trait["style_family"] == "pixel_editorial"
    assert with_trait["palette_roles"] == theme["palette_variants"]["custom"]
    theme["material_tags"].remove("pixel_graphics")
    without_trait = resolve_article_image_direction(visual_system="custom_scene", article_type="tutorial_steps")
    assert without_trait["style_family"] != "pixel_editorial"
