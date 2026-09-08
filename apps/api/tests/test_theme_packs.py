from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from visual_director.brief_compiler import (
    apply_visual_system,
    visual_system_configuration,
    visual_system_variant,
)
from visual_director.component_catalog import COMPONENT_CATALOG, CORE_THEME_COMPONENTS, VISUAL_SYSTEM_ORDER
from visual_director.main import create_app
from visual_director.parser import parse_markdown
from visual_director.planner import generate_plans
from visual_director.renderer import render_preview
from visual_director.theme_packs import (
    THEME_PACK_MAX_BYTES,
    THEME_PACK_SCHEMA_VERSION,
    ThemePackError,
    configure_theme_packs,
    validate_theme_pack_bytes,
    validate_theme_pack_manifest,
)
from visual_director.theme_extensions import render_extended_list
from visual_director.theme_gallery import build_theme_gallery
from visual_director.visual_dna import resolve_article_image_direction, theme_manifest


@pytest.fixture(autouse=True)
def _reset_theme_pack_registry(tmp_path):
    configure_theme_packs(
        tmp_path / "initial-registry",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    yield
    configure_theme_packs(
        tmp_path / "final-registry",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )


def _manifest() -> dict:
    return {
        "schema_version": THEME_PACK_SCHEMA_VERSION,
        "id": "moonlit_archive",
        "name": "月下雅集",
        "english": "MOONLIT ARCHIVE",
        "description": "以月白、黛青和暖金构成克制的夜间东方阅读气质。",
        "version": "1.0.0",
        "author": "Theme Pack Test",
        "base_theme": "oriental_archive",
        "ideal_for": ["文化叙事", "品牌故事"],
        "personality": ["安静", "东方", "克制"],
        "palette": {
            "primary": "#263A4A",
            "secondary": "#B89A62",
            "accent": "#A24B43",
            "sky": "#738A96",
            "pale": "#EEF1F0",
            "secondary_pale": "#F5EEDC",
            "accent_pale": "#F3E6E3",
            "sky_pale": "#E8EEF0",
            "surface": "#FFFDF8",
            "ink": "#222A30",
        },
        "visual_dna": {
            "warmth": 0.45,
            "saturation": 0.28,
            "contrast": 0.64,
            "geometry": 0.31,
            "tactility": 0.74,
            "dimensionality": 0.12,
            "energy": 0.30,
            "information_density": 0.52,
            "brand_formality": 0.82,
        },
        "material_tags": ["rice_paper", "moonlit_ink", "aged_gold"],
        "tone": ["月白", "安静", "雅致"],
        "component_contract": {
            "mode": "inherit",
            "coverage": list(CORE_THEME_COMPONENTS),
            "edit_contract": "semantic_dom_v1",
        },
    }


def _manifest_with_recipe() -> dict:
    manifest = _manifest()
    manifest["base_theme"] = "light_reading"
    manifest["style_recipe"] = {
        "hero": "cinematic_story",
        "heading": "cinematic_story",
        "list": "natural_atlas",
        "quote": "vintage_press",
        "table": "business_review",
        "divider": "cinematic_story",
        "inline_emphasis": "oriental_archive",
        "image_frame": "cinematic_story",
        "component": "business_review",
    }
    return manifest


def _manifest_with_design() -> dict:
    manifest = _manifest()
    manifest["design_system"] = {
        "composition": "arched_editorial",
        "motifs": ["botanical_vine", "honeycomb"],
        "frame": "arched",
        "marker": "seed",
        "surface": "layered",
        "rhythm": {"density": "balanced", "section_gap": 48, "component_gap": 28, "inset": 17},
        "typography": {
            "heading_scale": 1.08,
            "body_scale": 1.0,
            "letter_spacing": "normal",
            "heading_weight": 720,
        },
        "ornament": {"density": 0.62, "border_width": 1, "corner_radius": 26},
    }
    return manifest


def test_manifest_rejects_structure_and_executable_overrides(tmp_path) -> None:
    configure_theme_packs(
        tmp_path / "packs",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    manifest = _manifest()
    manifest["css"] = ".evidence { display:none }"
    with pytest.raises(ThemePackError) as exc_info:
        validate_theme_pack_manifest(manifest)
    assert any(item["field"] == "manifest" for item in exc_info.value.field_errors)


def test_manifest_rejects_unreadable_body_contrast(tmp_path) -> None:
    configure_theme_packs(
        tmp_path / "packs",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    manifest = _manifest()
    manifest["palette"]["ink"] = "#DDDDDD"
    manifest["palette"]["surface"] = "#FFFFFF"
    with pytest.raises(ThemePackError) as exc_info:
        validate_theme_pack_manifest(manifest)
    assert any(item["field"] == "palette.ink" for item in exc_info.value.field_errors)


def test_manifest_rejects_incomplete_or_unverified_style_recipe(tmp_path) -> None:
    configure_theme_packs(
        tmp_path / "packs",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    manifest = _manifest_with_recipe()
    manifest["style_recipe"].pop("table")
    manifest["style_recipe"]["heading"] = "light_reading"
    with pytest.raises(ThemePackError) as exc_info:
        validate_theme_pack_manifest(manifest)
    fields = {item["field"] for item in exc_info.value.field_errors}
    assert "style_recipe" in fields
    assert "style_recipe.heading" in fields


def test_generated_design_rejects_unknown_tokens_and_recipe_ambiguity(tmp_path) -> None:
    configure_theme_packs(
        tmp_path / "packs",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    manifest = _manifest_with_design()
    manifest["design_system"]["composition"] = "arbitrary_css"
    manifest["style_recipe"] = _manifest_with_recipe()["style_recipe"]
    with pytest.raises(ThemePackError) as exc_info:
        validate_theme_pack_manifest(manifest)
    fields = {item["field"] for item in exc_info.value.field_errors}
    assert "design_system.composition" in fields
    assert "manifest" in fields


def test_zip_path_traversal_is_rejected(tmp_path) -> None:
    configure_theme_packs(
        tmp_path / "packs",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../theme.json", json.dumps(_manifest(), ensure_ascii=False))
    with pytest.raises(ThemePackError, match="不安全路径"):
        validate_theme_pack_bytes(buffer.getvalue(), "unsafe.vdtheme")


def test_zip_with_extra_file_is_rejected(tmp_path) -> None:
    configure_theme_packs(
        tmp_path / "packs",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("theme.json", json.dumps(_manifest(), ensure_ascii=False))
        archive.writestr("override.css", ".article { display: none; }")
    with pytest.raises(ThemePackError, match="不能包含 theme.json 之外的文件"):
        validate_theme_pack_bytes(buffer.getvalue(), "extra-file.vdtheme")


def test_oversized_json_is_rejected_before_parsing(tmp_path) -> None:
    configure_theme_packs(
        tmp_path / "packs",
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    content = b"{" + b" " * THEME_PACK_MAX_BYTES + b"}"
    with pytest.raises(ThemePackError, match="不能超过 2 MB"):
        validate_theme_pack_bytes(content, "oversized.json")


def test_theme_pack_install_gallery_render_contract_and_delete(tmp_path) -> None:
    app = create_app(str(tmp_path / "theme-packs.db"))
    headers = {"X-Local-Intent": "local-operator"}
    content = json.dumps(_manifest(), ensure_ascii=False).encode("utf-8")
    with TestClient(app) as client:
        installed = client.post(
            "/api/v1/theme-packs",
            headers=headers,
            files={"theme_file": ("theme.json", content, "application/json")},
        )
        assert installed.status_code == 200
        assert installed.json()["manifest"]["base_theme"] == "oriental_archive"

        themes = client.get("/api/v1/theme-gallery").json()["themes"]
        custom = next(item for item in themes if item["id"] == "moonlit_archive")
        assert custom["source"] == "custom"
        assert custom["base_theme"] == "oriental_archive"
        assert custom["core_component_count"] == len(CORE_THEME_COMPONENTS)
        assert custom["configuration"]["palette"]["primary"] == "#263A4A"
        assert "#263A4A" in custom["full_preview_html"]

        exported = client.get("/api/v1/theme-packs/moonlit_archive/export")
        assert exported.status_code == 200
        assert exported.headers["content-type"] == "application/zip"

        removed = client.delete("/api/v1/theme-packs/moonlit_archive", headers=headers)
        assert removed.status_code == 200
        assert not (tmp_path / "theme-packs" / "moonlit_archive").exists()

    configuration = visual_system_configuration("oriental_archive")
    assert configuration["heading_variant"] == "oriental_folio"


def test_installed_pack_inherits_component_variants_and_owns_visual_dna(tmp_path) -> None:
    pack_dir = tmp_path / "packs"
    configure_theme_packs(
        pack_dir,
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    (pack_dir / "moonlit_archive").mkdir(parents=True)
    (pack_dir / "moonlit_archive" / "theme.json").write_text(
        json.dumps(_manifest(), ensure_ascii=False),
        encoding="utf-8",
    )
    configure_theme_packs(
        pack_dir,
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    assert visual_system_variant("evidence_callout", "moonlit_archive") == visual_system_variant(
        "evidence_callout", "oriental_archive"
    )
    assert visual_system_configuration("moonlit_archive")["palette"]["primary"] == "#263A4A"
    assert theme_manifest("moonlit_archive")["dna"]["warmth"] == 0.45


def test_custom_pack_inherits_plain_block_grammar_and_drives_image_direction(tmp_path) -> None:
    pack_dir = tmp_path / "packs"
    configure_theme_packs(
        pack_dir,
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    (pack_dir / "moonlit_archive").mkdir(parents=True)
    (pack_dir / "moonlit_archive" / "theme.json").write_text(
        json.dumps(_manifest(), ensure_ascii=False),
        encoding="utf-8",
    )
    configure_theme_packs(
        pack_dir,
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )

    article = parse_markdown(
        """# 月下主题验收

## 第一步：确认文章结构

一段普通正文。

1. 识别读者任务
2. 保留事实证据
3. 检查手机阅读
"""
    )
    plan = apply_visual_system(
        generate_plans(article, "tutorial_steps", 5)[0],
        "moonlit_archive",
        recent_summaries=[],
    )
    document = render_preview(article, plan)

    assert 'data-theme-grammar="folio-heading"' in document
    assert 'data-theme-grammar="bound-folio"' in document
    assert "#263A4A" in document

    direction = plan["image_art_direction"]
    assert direction == resolve_article_image_direction(
        visual_system="moonlit_archive",
        article_type="tutorial_steps",
        recent_summaries=[],
    )
    assert direction["visual_dna"]["warmth"] == 0.45
    assert direction["palette_family"] == "user_pack:moonlit_archive"
    assert direction["palette_roles"] == ["#263A4A", "#B89A62", "#A24B43", "#FFFDF8"]
    assert direction["surface_treatment"] in theme_manifest("oriental_archive")["surface_variants"]


def test_custom_pack_composes_verified_visual_roles_without_changing_semantics(tmp_path) -> None:
    pack_dir = tmp_path / "packs"
    configure_theme_packs(
        pack_dir,
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    manifest = _manifest_with_recipe()
    (pack_dir / "moonlit_archive").mkdir(parents=True)
    (pack_dir / "moonlit_archive" / "theme.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    configure_theme_packs(
        pack_dir,
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )

    article = parse_markdown(
        """# 受控视觉配方验收

## 第一步：确认文章结构

> 一条证据摘录。

1. 识别读者任务
2. 保留事实证据
3. 检查手机阅读
"""
    )
    plan = apply_visual_system(
        generate_plans(article, "tutorial_steps", 5)[0],
        "moonlit_archive",
        recent_summaries=[],
    )
    document = render_preview(article, plan)

    assert plan["visual_system"] == "moonlit_archive"
    assert plan["configuration"]["render_theme_roles"] == manifest["style_recipe"]
    assert 'data-theme-grammar="opening-credit"' in document
    list_markup = render_extended_list(
        ["识别读者任务", "保留事实证据", "检查手机阅读"],
        True,
        plan["configuration"],
    )
    assert list_markup is not None
    assert 'data-theme-grammar="field-log"' in list_markup
    assert visual_system_variant("evidence_callout", "moonlit_archive") == visual_system_variant(
        "evidence_callout", "business_review"
    )
    assert "#263A4A" in document

    custom_gallery = next(
        item for item in build_theme_gallery() if item["id"] == "moonlit_archive"
    )
    assert 'data-theme-grammar="opening-credit"' in custom_gallery["full_preview_html"]
    assert custom_gallery["components"][0]["variant_label"] == (
        COMPONENT_CATALOG["question_hook"]["system_variants"]["business_review"]["label"]
    )


def test_generated_design_compiles_novel_wechat_safe_grammar(tmp_path) -> None:
    pack_dir = tmp_path / "packs"
    configure_theme_packs(
        pack_dir,
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    manifest = _manifest_with_design()
    (pack_dir / "moonlit_archive").mkdir(parents=True)
    (pack_dir / "moonlit_archive" / "theme.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    configure_theme_packs(
        pack_dir,
        reserved_ids=VISUAL_SYSTEM_ORDER,
        core_components=CORE_THEME_COMPONENTS,
    )
    article = parse_markdown(
        """# 植物工艺展主题验收

## 先观察材料，再理解工艺

> 手艺的价值来自时间留下的细节。

1. 看见材料
2. 理解步骤
3. 记住作者
"""
    )
    plan = apply_visual_system(
        generate_plans(article, "tutorial_steps", 5)[0],
        "moonlit_archive",
        recent_summaries=[],
    )
    document = render_preview(article, plan)
    assert plan["configuration"]["generated_design_system"] == manifest["design_system"]
    assert 'data-theme-grammar="generated-arched_editorial"' in document
    assert 'data-theme-motif="botanical-vine"' in document
    assert 'data-theme-motif="honeycomb"' in document
    assert 'data-theme-grammar="folio-heading"' not in document
    assert 'data-theme-grammar="field-log"' not in document
    assert "<script" not in document
    assert "javascript:" not in document

    custom_gallery = next(item for item in build_theme_gallery() if item["id"] == "moonlit_archive")
    assert 'data-generated-theme="moonlit_archive"' in custom_gallery["full_preview_html"]
    assert custom_gallery["components"][0]["variant_label"] == "自定义生成语法"
