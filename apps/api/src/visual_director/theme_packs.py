from __future__ import annotations

import copy
import io
import json
import os
import re
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Any, Iterable

from .theme_layouts import validate_layouts


THEME_PACK_SCHEMA_VERSION = "visual_director.theme_pack.v1"
THEME_PACK_FILE_NAME = "theme.json"
THEME_PACK_MAX_BYTES = 2 * 1024 * 1024
THEME_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,47}$")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
PALETTE_KEYS = (
    "primary",
    "secondary",
    "accent",
    "sky",
    "pale",
    "secondary_pale",
    "accent_pale",
    "sky_pale",
    "surface",
    "ink",
)
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
STYLE_RECIPE_ROLES = (
    "hero",
    "heading",
    "list",
    "quote",
    "table",
    "divider",
    "inline_emphasis",
    "image_frame",
    "component",
)
COMPOSABLE_THEME_IDS = (
    "oriental_archive",
    "vintage_press",
    "pop_poster",
    "natural_atlas",
    "business_review",
    "cinematic_story",
)
GENERATED_DESIGN_ENUMS = {
    "composition": (
        "arched_editorial",
        "offset_journal",
        "modular_exhibit",
        "ribbon_story",
        "medallion_archive",
        "woven_catalog",
    ),
    "frame": ("arched", "double_rule", "offset_shadow", "stitched", "bracketed", "open_corner"),
    "marker": ("seed", "medallion", "ticket", "coordinate", "petal", "bar"),
    "surface": ("quiet", "tinted", "layered", "alternating"),
}
GENERATED_MOTIFS = (
    "botanical_vine",
    "honeycomb",
    "celestial_orbit",
    "paper_cut",
    "wave_ripple",
    "architectural_grid",
    "none",
)
GENERATED_DENSITIES = ("airy", "balanced", "compact")


class ThemePackError(ValueError):
    def __init__(self, message: str, *, field_errors: list[dict[str, str]] | None = None,
                 code: str = "theme_pack_invalid", delivery_report: dict[str, Any] | None = None):
        super().__init__(message)
        self.field_errors = field_errors or []
        self.code = code
        self.delivery_report = delivery_report


_lock = threading.RLock()
_pack_dir: Path | None = None
_reserved_ids: frozenset[str] = frozenset()
_core_components: tuple[str, ...] = ()
_installed: dict[str, dict[str, Any]] = {}
_load_errors: list[dict[str, Any]] = []


def configure_theme_packs(
    pack_dir: Path,
    *,
    reserved_ids: Iterable[str],
    core_components: Iterable[str],
) -> None:
    global _pack_dir, _reserved_ids, _core_components, _installed, _load_errors
    with _lock:
        _pack_dir = pack_dir.resolve()
        _reserved_ids = frozenset(str(value) for value in reserved_ids)
        _core_components = tuple(str(value) for value in core_components)
        _pack_dir.mkdir(parents=True, exist_ok=True)
        loaded: dict[str, dict[str, Any]] = {}
        errors = []
        for manifest_path in sorted(_pack_dir.glob(f"*/{THEME_PACK_FILE_NAME}")):
            if manifest_path.parent.name.startswith("."):
                continue  # Never register transaction staging or backup folders.
            try:
                manifest = validate_theme_pack_manifest(
                    json.loads(manifest_path.read_text(encoding="utf-8-sig"))
                )
            except (OSError, UnicodeError, json.JSONDecodeError, ThemePackError) as exc:
                errors.append({"id": f"unavailable:{manifest_path.parent.name}", "label": manifest_path.parent.name,
                               "code": "theme_pack_load_failed", "message": "主题文件无法加载，请修复后重新导入。原文件未删除。",
                               "field_errors": getattr(exc, "field_errors", [])})
                continue
            loaded[manifest["id"]] = manifest
        _installed = loaded
        _load_errors = errors


def theme_pack_directory() -> Path:
    if _pack_dir is None:
        raise ThemePackError("主题扩展包目录尚未初始化")
    return _pack_dir


def _field_error(errors: list[dict[str, str]], field: str, message: str) -> None:
    errors.append({"field": field, "message": message})


def _short_text(
    manifest: dict[str, Any],
    key: str,
    errors: list[dict[str, str]],
    *,
    maximum: int,
) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value.strip():
        _field_error(errors, key, "必须是非空文本")
        return ""
    normalized = value.strip()
    if len(normalized) > maximum:
        _field_error(errors, key, f"不能超过 {maximum} 个字符")
    return normalized


def _text_list(
    manifest: dict[str, Any],
    key: str,
    errors: list[dict[str, str]],
    *,
    minimum: int = 1,
    maximum: int = 8,
) -> list[str]:
    value = manifest.get(key)
    if not isinstance(value, list):
        _field_error(errors, key, "必须是文本数组")
        return []
    normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if len(normalized) != len(value):
        _field_error(errors, key, "只能包含非空文本")
    if not minimum <= len(normalized) <= maximum:
        _field_error(errors, key, f"需要 {minimum} 到 {maximum} 项")
    if any(len(item) > 40 for item in normalized):
        _field_error(errors, key, "单项不能超过 40 个字符")
    return normalized


def _contrast_ratio(foreground: str, background: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _validate_generated_design_system(
    value: Any,
    errors: list[dict[str, str]],
) -> dict[str, Any] | None:
    """Validate the declarative visual language compiled by the safe renderer."""
    if not isinstance(value, dict):
        _field_error(errors, "design_system", "必须是完整的受控设计系统对象")
        return None
    required = {"composition", "motifs", "frame", "marker", "surface", "rhythm", "typography", "ornament"}
    unknown = sorted(set(value) - required - {"layouts"})
    missing = sorted(required - set(value))
    if unknown:
        _field_error(errors, "design_system", f"包含未知字段：{', '.join(unknown)}")
    if missing:
        _field_error(errors, "design_system", f"缺少字段：{', '.join(missing)}")

    normalized: dict[str, Any] = {}
    for key, options in GENERATED_DESIGN_ENUMS.items():
        item = value.get(key)
        if not isinstance(item, str) or item not in options:
            _field_error(errors, f"design_system.{key}", f"必须是：{', '.join(options)}")
        else:
            normalized[key] = item

    motifs = value.get("motifs")
    if (
        not isinstance(motifs, list)
        or not 1 <= len(motifs) <= 2
        or any(not isinstance(item, str) or item not in GENERATED_MOTIFS for item in motifs)
        or len(set(motifs)) != len(motifs)
        or ("none" in motifs and len(motifs) > 1)
    ):
        _field_error(errors, "design_system.motifs", "必须包含 1–2 个不重复的受控纹样；none 不能与其他纹样并用")
    else:
        normalized["motifs"] = list(motifs)

    rhythm = value.get("rhythm")
    if not isinstance(rhythm, dict) or set(rhythm) != {"density", "section_gap", "component_gap", "inset"}:
        _field_error(errors, "design_system.rhythm", "必须完整声明 density、section_gap、component_gap 和 inset")
    else:
        if rhythm.get("density") not in GENERATED_DENSITIES:
            _field_error(errors, "design_system.rhythm.density", f"必须是：{', '.join(GENERATED_DENSITIES)}")
        number_limits = {"section_gap": (30, 64), "component_gap": (18, 44), "inset": (10, 28)}
        normalized_rhythm: dict[str, Any] = {"density": rhythm.get("density")}
        for key, (minimum, maximum) in number_limits.items():
            item = rhythm.get(key)
            if not isinstance(item, int) or isinstance(item, bool) or not minimum <= item <= maximum:
                _field_error(errors, f"design_system.rhythm.{key}", f"必须是 {minimum}–{maximum} 的整数")
            else:
                normalized_rhythm[key] = item
        normalized["rhythm"] = normalized_rhythm

    typography = value.get("typography")
    if not isinstance(typography, dict) or set(typography) != {"heading_scale", "body_scale", "letter_spacing", "heading_weight"}:
        _field_error(errors, "design_system.typography", "必须完整声明 heading_scale、body_scale、letter_spacing 和 heading_weight")
    else:
        normalized_typography: dict[str, Any] = {}
        ranges = {"heading_scale": (0.9, 1.3), "body_scale": (0.95, 1.1)}
        for key, (minimum, maximum) in ranges.items():
            item = typography.get(key)
            if not isinstance(item, (int, float)) or isinstance(item, bool) or not minimum <= float(item) <= maximum:
                _field_error(errors, f"design_system.typography.{key}", f"必须是 {minimum}–{maximum} 的数字")
            else:
                normalized_typography[key] = round(float(item), 3)
        spacing = typography.get("letter_spacing")
        if not isinstance(spacing, str) or spacing not in {"tight", "normal", "relaxed"}:
            _field_error(errors, "design_system.typography.letter_spacing", "必须是 tight、normal 或 relaxed")
        else:
            normalized_typography["letter_spacing"] = spacing
        weight = typography.get("heading_weight")
        if not isinstance(weight, int) or isinstance(weight, bool) or not 500 <= weight <= 900:
            _field_error(errors, "design_system.typography.heading_weight", "必须是 500–900 的整数")
        else:
            normalized_typography["heading_weight"] = weight
        normalized["typography"] = normalized_typography

    ornament = value.get("ornament")
    if not isinstance(ornament, dict) or set(ornament) != {"density", "border_width", "corner_radius"}:
        _field_error(errors, "design_system.ornament", "必须完整声明 density、border_width 和 corner_radius")
    else:
        normalized_ornament: dict[str, Any] = {}
        density = ornament.get("density")
        if not isinstance(density, (int, float)) or isinstance(density, bool) or not 0 <= float(density) <= 1:
            _field_error(errors, "design_system.ornament.density", "必须是 0–1 的数字")
        else:
            normalized_ornament["density"] = round(float(density), 3)
        for key, minimum, maximum in (("border_width", 1, 4), ("corner_radius", 0, 36)):
            item = ornament.get(key)
            if not isinstance(item, int) or isinstance(item, bool) or not minimum <= item <= maximum:
                _field_error(errors, f"design_system.ornament.{key}", f"必须是 {minimum}–{maximum} 的整数")
            else:
                normalized_ornament[key] = item
        normalized["ornament"] = normalized_ornament

    if "layouts" in value:
        errors.extend(validate_layouts(value["layouts"]))
        normalized["layouts"] = value["layouts"]
    return normalized if not any(item["field"].startswith("design_system") for item in errors) else None


def validate_theme_pack_manifest(payload: Any, *, reserved_ids: Iterable[str] | None = None,
                                 core_components: Iterable[str] | None = None) -> dict[str, Any]:
    # Offline tools validate against the official catalog without initializing
    # or mutating the user's installed-theme registry.
    reserved = _reserved_ids if reserved_ids is None else frozenset(reserved_ids)
    components = _core_components if core_components is None else tuple(core_components)
    if not isinstance(payload, dict):
        raise ThemePackError("主题扩展包清单必须是 JSON 对象")
    manifest = copy.deepcopy(payload)
    errors: list[dict[str, str]] = []
    allowed_fields = {
        "schema_version",
        "id",
        "name",
        "english",
        "description",
        "version",
        "author",
        "base_theme",
        "ideal_for",
        "personality",
        "palette",
        "visual_dna",
        "material_tags",
        "tone",
        "style_recipe",
        "design_system",
        "component_contract",
    }
    unknown_fields = sorted(set(manifest) - allowed_fields)
    if unknown_fields:
        _field_error(errors, "manifest", f"包含未知字段：{', '.join(unknown_fields)}")

    if manifest.get("schema_version") != THEME_PACK_SCHEMA_VERSION:
        _field_error(errors, "schema_version", f"必须是 {THEME_PACK_SCHEMA_VERSION}")
    theme_id = _short_text(manifest, "id", errors, maximum=48)
    if theme_id and not THEME_PACK_ID_RE.fullmatch(theme_id):
        _field_error(errors, "id", "只能使用小写字母、数字和下划线，并以字母开头")
    if theme_id in reserved:
        _field_error(errors, "id", "不能覆盖官方主题")

    name = _short_text(manifest, "name", errors, maximum=32)
    english = _short_text(manifest, "english", errors, maximum=60)
    description = _short_text(manifest, "description", errors, maximum=180)
    version = _short_text(manifest, "version", errors, maximum=32)
    author = _short_text(manifest, "author", errors, maximum=60)
    base_theme = _short_text(manifest, "base_theme", errors, maximum=48)
    if base_theme and base_theme not in reserved:
        _field_error(errors, "base_theme", "必须继承一套现有官方主题")

    ideal_for = _text_list(manifest, "ideal_for", errors, maximum=6)
    personality = _text_list(manifest, "personality", errors, maximum=6)
    material_tags = _text_list(manifest, "material_tags", errors, maximum=12)
    tone = _text_list(manifest, "tone", errors, maximum=6)

    style_recipe_value = manifest.get("style_recipe")
    style_recipe: dict[str, str] | None = None
    if style_recipe_value is not None:
        if not isinstance(style_recipe_value, dict):
            _field_error(errors, "style_recipe", "必须是完整的受控视觉配方对象")
        else:
            unknown_roles = sorted(set(style_recipe_value) - set(STYLE_RECIPE_ROLES))
            missing_roles = sorted(set(STYLE_RECIPE_ROLES) - set(style_recipe_value))
            if unknown_roles:
                _field_error(errors, "style_recipe", f"包含未知视觉角色：{', '.join(unknown_roles)}")
            if missing_roles:
                _field_error(errors, "style_recipe", f"缺少视觉角色：{', '.join(missing_roles)}")
            normalized_recipe: dict[str, str] = {}
            for role in STYLE_RECIPE_ROLES:
                source = style_recipe_value.get(role)
                if not isinstance(source, str) or source not in COMPOSABLE_THEME_IDS:
                    _field_error(
                        errors,
                        f"style_recipe.{role}",
                        f"必须选用已验证的可组合主题：{', '.join(COMPOSABLE_THEME_IDS)}",
                    )
                else:
                    normalized_recipe[role] = source
            if len(normalized_recipe) == len(STYLE_RECIPE_ROLES):
                style_recipe = normalized_recipe

    design_system_value = manifest.get("design_system")
    design_system: dict[str, Any] | None = None
    if design_system_value is not None:
        design_system = _validate_generated_design_system(design_system_value, errors)
    if style_recipe_value is not None and design_system_value is not None:
        _field_error(errors, "manifest", "style_recipe 与 design_system 只能选择一种主题生成方式")

    palette_value = manifest.get("palette")
    palette: dict[str, str] = {}
    if not isinstance(palette_value, dict):
        _field_error(errors, "palette", "必须是完整色板对象")
    else:
        unknown = sorted(set(palette_value) - set(PALETTE_KEYS))
        missing = sorted(set(PALETTE_KEYS) - set(palette_value))
        if unknown:
            _field_error(errors, "palette", f"包含未知颜色角色：{', '.join(unknown)}")
        if missing:
            _field_error(errors, "palette", f"缺少颜色角色：{', '.join(missing)}")
        for key in PALETTE_KEYS:
            value = palette_value.get(key)
            if not isinstance(value, str) or not HEX_COLOR_RE.fullmatch(value):
                _field_error(errors, f"palette.{key}", "必须是 #RRGGBB 颜色")
            else:
                palette[key] = value.upper()
        if set(palette) == set(PALETTE_KEYS) and _contrast_ratio(palette["ink"], palette["surface"]) < 4.5:
            _field_error(errors, "palette.ink", "正文色与页面色的对比度必须至少为 4.5:1")

    visual_dna_value = manifest.get("visual_dna")
    dna: dict[str, float] = {}
    if not isinstance(visual_dna_value, dict):
        _field_error(errors, "visual_dna", "必须是九维视觉 DNA 对象")
    else:
        if set(visual_dna_value) != set(DNA_DIMENSIONS):
            _field_error(errors, "visual_dna", "必须完整声明九个标准维度")
        for key in DNA_DIMENSIONS:
            value = visual_dna_value.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
                _field_error(errors, f"visual_dna.{key}", "必须是 0 到 1 之间的数字")
            else:
                dna[key] = round(float(value), 3)

    component_contract = manifest.get("component_contract")
    if not isinstance(component_contract, dict):
        _field_error(errors, "component_contract", "必须声明组件继承契约")
    else:
        unknown_contract_fields = sorted(
            set(component_contract) - {"mode", "coverage", "edit_contract"}
        )
        if unknown_contract_fields:
            _field_error(
                errors,
                "component_contract",
                f"包含未知字段：{', '.join(unknown_contract_fields)}",
            )
        if component_contract.get("mode") != "inherit":
            _field_error(errors, "component_contract.mode", "v1 只允许 inherit")
        coverage = component_contract.get("coverage")
        if coverage != list(components):
            _field_error(errors, "component_contract.coverage", "必须覆盖全部标准语义组件且顺序一致")
        if component_contract.get("edit_contract") != "semantic_dom_v1":
            _field_error(errors, "component_contract.edit_contract", "必须是 semantic_dom_v1")

    forbidden = set(manifest).intersection({"html", "css", "javascript", "script", "renderer"})
    if forbidden:
        _field_error(errors, "manifest", f"不允许可执行或结构覆盖字段：{', '.join(sorted(forbidden))}")
    if errors:
        raise ThemePackError("主题扩展包未通过校验", field_errors=errors)

    normalized_manifest = {
        "schema_version": THEME_PACK_SCHEMA_VERSION,
        "id": theme_id,
        "name": name,
        "english": english.upper(),
        "description": description,
        "version": version,
        "author": author,
        "base_theme": base_theme,
        "ideal_for": ideal_for,
        "personality": personality,
        "palette": palette,
        "visual_dna": dna,
        "material_tags": material_tags,
        "tone": tone,
        "component_contract": {
            "mode": "inherit",
            "coverage": list(components),
            "edit_contract": "semantic_dom_v1",
        },
    }
    if style_recipe is not None:
        normalized_manifest["style_recipe"] = style_recipe
    if design_system is not None:
        normalized_manifest["design_system"] = design_system
    return normalized_manifest


def installed_theme_packs() -> list[dict[str, Any]]:
    with _lock:
        return [copy.deepcopy(_installed[key]) for key in sorted(_installed)]


def theme_pack_load_errors() -> list[dict[str, Any]]:
    with _lock:
        return copy.deepcopy(_load_errors)


def theme_pack(theme_id: str) -> dict[str, Any] | None:
    with _lock:
        manifest = _installed.get(theme_id)
        return copy.deepcopy(manifest) if manifest else None


def resolve_theme_base(theme_id: str) -> str:
    manifest = theme_pack(theme_id)
    return str(manifest["base_theme"]) if manifest else theme_id


def theme_pack_catalog_entry(theme_id: str) -> dict[str, Any] | None:
    from .theme_delivery import theme_layout_coverage

    manifest = theme_pack(theme_id)
    if not manifest:
        return None
    palette = manifest["palette"]
    return {
        "label": manifest["name"],
        "english": manifest["english"],
        "description": manifest["description"],
        "ideal_for": list(manifest["ideal_for"]),
        "personality": list(manifest["personality"]),
        "palette": [palette["primary"], palette["secondary"], palette["accent"], palette["surface"]],
        "status": "user_theme_pack",
        "source": "custom",
        "base_theme": manifest["base_theme"],
        "pack_version": manifest["version"],
        "layout_coverage": theme_layout_coverage(manifest),
        "author": manifest["author"],
    }


def theme_pack_visual_dna(theme_id: str) -> dict[str, Any] | None:
    manifest = theme_pack(theme_id)
    if not manifest:
        return None
    palette = manifest["palette"]
    return {
        "dna": copy.deepcopy(manifest["visual_dna"]),
        "material_tags": list(manifest["material_tags"]),
        "palette_family": f"user_pack:{theme_id}",
        "palette_variants": {
            "custom": [
                palette["primary"],
                palette["secondary"],
                palette["accent"],
                palette["surface"],
            ]
        },
        "surface_variants": [],
        "tone": list(manifest["tone"]),
        "base_theme": manifest["base_theme"],
        "style_recipe": copy.deepcopy(manifest.get("style_recipe")),
        "design_system": copy.deepcopy(manifest.get("design_system")),
    }


def _read_pack_bytes(content: bytes, filename: str) -> dict[str, Any]:
    if len(content) > THEME_PACK_MAX_BYTES:
        raise ThemePackError("主题扩展包不能超过 2 MB")
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        try:
            return json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ThemePackError("主题 JSON 无法解析") from exc
    if suffix not in {".zip", ".vdtheme"}:
        raise ThemePackError("只支持 .json、.zip 或 .vdtheme 主题扩展包")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = [(info, info.filename.replace("\\", "/")) for info in archive.infolist()]
            names = [name for _, name in entries]
            unsafe = [name for name in names if name.startswith("/") or ".." in Path(name).parts]
            if unsafe:
                raise ThemePackError("主题扩展包包含不安全路径")
            candidates = [
                (info, name)
                for info, name in entries
                if name.rstrip("/").endswith(f"/{THEME_PACK_FILE_NAME}") or name == THEME_PACK_FILE_NAME
            ]
            if len(candidates) != 1:
                raise ThemePackError("主题扩展包必须且只能包含一个 theme.json")
            files = [info for info in archive.infolist() if not info.is_dir()]
            if len(files) != 1:
                raise ThemePackError("v1 主题扩展包不能包含 theme.json 之外的文件")
            candidate_info, candidate_name = candidates[0]
            if len(Path(candidate_name).parts) > 2:
                raise ThemePackError("theme.json 只能位于压缩包根目录或单层目录")
            if candidate_info.file_size > 512 * 1024:
                raise ThemePackError("theme.json 不能超过 512 KB")
            return json.loads(archive.read(candidate_info).decode("utf-8-sig"))
    except zipfile.BadZipFile as exc:
        raise ThemePackError("主题扩展包不是有效压缩文件") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ThemePackError("theme.json 无法解析") from exc


def validate_theme_pack_bytes(content: bytes, filename: str, *, reserved_ids: Iterable[str] | None = None,
                              core_components: Iterable[str] | None = None) -> dict[str, Any]:
    return validate_theme_pack_manifest(_read_pack_bytes(content, filename), reserved_ids=reserved_ids, core_components=core_components)


def check_theme_pack_delivery(manifest: dict[str, Any]) -> dict[str, Any]:
    from .theme_delivery import theme_delivery_report

    try:
        report = theme_delivery_report(manifest)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
        raise ThemePackError("主题渲染检查未完成，请修复后重试。", code="theme_pack_delivery_blocked",
                             delivery_report={"local_delivery": "blocking", "next_action": "fix_delivery",
                                              "rehearsal": {"status": "blocking"}, "cause": type(exc).__name__}) from exc
    if report.get("local_delivery") == "blocking" or report.get("rehearsal", {}).get("status") == "blocking":
        raise ThemePackError("主题存在编译、资产或正式渲染阻断，请修复后重新导入。", code="theme_pack_delivery_blocked", delivery_report=report)
    return report


def validate_theme_pack_delivery_bytes(content: bytes, filename: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = validate_theme_pack_bytes(content, filename)
    return manifest, check_theme_pack_delivery(manifest)


def install_theme_pack_bytes(content: bytes, filename: str, *, with_report: bool = False) -> dict[str, Any]:
    # All checks finish before any filesystem/cache mutation, including updates.
    manifest, report = validate_theme_pack_delivery_bytes(content, filename)
    with _lock:
        destination = theme_pack_directory() / manifest["id"]
        temporary = None
        backup = destination.with_name(f".{destination.name}.backup")
        try:
            temporary = Path(tempfile.mkdtemp(prefix=f".{manifest['id']}.", dir=theme_pack_directory()))
            (temporary / THEME_PACK_FILE_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if backup.exists() and not destination.exists():
                # An interrupted rollback left the old theme in its backup.
                os.replace(backup, destination)
            if backup.exists():
                shutil.rmtree(backup)
            if destination.exists():
                os.replace(destination, backup)
            try:
                os.replace(temporary, destination)
            except OSError:
                if backup.exists() and not destination.exists():
                    os.replace(backup, destination)
                raise
            _installed[manifest["id"]] = manifest
            _load_errors[:] = [item for item in _load_errors if item["id"] != f"unavailable:{manifest['id']}"]
            if backup.exists():
                try:
                    shutil.rmtree(backup)
                except OSError:
                    report["installation_warnings"] = ["old_theme_backup_retained"]
        except OSError as exc:
            raise ThemePackError("主题写入未完成，未确认安装成功；已有主题或其备份保持保留。", code="theme_pack_install_failed") from exc
        finally:
            if temporary is not None and temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
    result = {"manifest": manifest, "delivery_report": report} if with_report else manifest
    return copy.deepcopy(result)


def delete_theme_pack(theme_id: str) -> bool:
    if theme_id in _reserved_ids:
        raise ThemePackError("官方主题不能删除")
    destination = theme_pack_directory() / theme_id
    if not destination.is_dir():
        return False
    shutil.rmtree(destination)
    with _lock:
        _installed.pop(theme_id, None)
        _load_errors[:] = [item for item in _load_errors if item["id"] != f"unavailable:{theme_id}"]
    return True


def export_theme_pack(theme_id: str) -> bytes:
    manifest = theme_pack(theme_id)
    if not manifest:
        raise ThemePackError("主题扩展包不存在")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            THEME_PACK_FILE_NAME,
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
    return buffer.getvalue()
