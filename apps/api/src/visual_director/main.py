from __future__ import annotations

import os
import copy
import html
import hashlib
import json
import re
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from .component_catalog import COMPONENT_CATALOG, allowed_variants, component_options
from .brand import brand_asset_path, load_brand_profile, public_brand_profile
from .blind_review import BLIND_REVIEW_DIMENSIONS, BlindReviewDataset, load_blind_review_dataset
from .parser import classify_article, parse_markdown
from .preflight import PREFLIGHT_RULESET_VERSION, PREFLIGHT_SCHEMA_VERSION, run_preflight
from .image_provider import (
    DEFAULT_AGNES_ENDPOINT,
    DEFAULT_AGNES_MODEL,
    DEFAULT_GEMINI_IMAGE_ENDPOINT,
    DEFAULT_GEMINI_IMAGE_MODEL,
    DEFAULT_IMAGES_API_ENDPOINT,
    DEFAULT_IMAGES_API_MODEL,
    DEFAULT_IMAGES_API_PROTOCOL,
    IMAGE_PROVIDER_SETTINGS_SCHEMA_VERSION,
    IMAGE_PROMPT_VERSION,
    GeneratedImage,
    ImageProvider,
    ImageProviderError,
    build_cover_prompt,
    build_provider_prompt,
    build_theme_fallback_cover,
    create_image_provider_from_env,
    image_prompt_profile,
)
from .planner import generate_plans, structural_difference_count
from .brief_compiler import (
    EditorialBriefCompileError,
    apply_visual_system,
    compile_editorial_brief,
    compile_editorial_brief_recommended,
    compile_editorial_brief_variants,
)
from .editorial_brief import EDITORIAL_BRIEF_NORMALIZER_VERSION, EDITORIAL_BRIEF_SCHEMA_VERSION
from .text_planner import (
    HOST_AGENT_PROMPT_VERSION,
    TEXT_PLANNER_PROMPT_VERSION,
    TextPlannerProvider,
    TextPlannerRequest,
    TextPlannerResult,
    adopt_host_agent_editorial_brief,
    build_host_agent_planner_context,
    build_rule_based_brief,
    create_text_planner_provider_from_env,
    generate_editorial_brief,
)
from .infographic_overlay import (
    InfographicOverlayError,
    compose_structured_infographic,
    resolve_overlay_copy,
)
from .ocr_verifier import verify_locked_copy
from .image_intent import (
    apply_theme_to_image_slot,
    build_art_direction_snapshot,
    evaluate_theme_compatibility,
    resolve_display_copy,
)
from .plan_schema import validate_plan_for_article
from .renderer import render_preview
from .theme_gallery import THEME_GALLERY_SCHEMA_VERSION, build_theme_gallery
from .theme_assets import referenced_theme_assets, theme_asset_metadata, theme_asset_path
from .publication import (
    PUBLICATION_SCHEMA_VERSION,
    canonical_json,
    check_frozen_html,
    hash_json,
    materialize_preview_document,
    render_frozen_asset_urls,
    replace_asset_urls,
    sha256_text,
    structure_hash,
)
from .settings import load_runtime_settings, read_env_file, update_env_file
from .onboarding import (
    CAPABILITY_SETTINGS_SCHEMA_VERSION,
    PublicIpProbe,
    WechatConnectionProbe,
    read_setup_preferences,
    write_probe_status,
    write_setup_preferences,
)
from .delivery import (
    build_clipboard_payload,
    build_delivery_files,
    build_delivery_zip,
)
from .wechat_publisher import WechatDraftPublisher
from .repository import NotFoundError, PublicationLockedError, Repository, VersionConflictError
from .version import application_version, runtime_identity


class GeneratePlansRequest(BaseModel):
    mode: str = Field(pattern="^(start|retry)$")
    expected_task_version: int = Field(ge=1)
    planner: str = Field(default="rule", pattern="^(rule|intelligent|host_agent)$")
    editorial_brief: dict[str, Any] | None = None
    host_model: str = Field(default="host_managed", max_length=120)


class ImageProviderSettingsRequest(BaseModel):
    mode: str = Field(pattern="^(manual|mock|images_api|gemini)$")
    api_key: str | None = Field(default=None, max_length=512)
    clear_api_key: bool = False
    endpoint: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=160)
    protocol: str | None = Field(default=None, pattern="^(openai|ark|ark_plan|extended)$")
    size: str | None = Field(default=None, max_length=40)


class SetupPreferencesRequest(BaseModel):
    target_mode: str = Field(pattern="^(typeset_only|images|full_delivery)$")


class BatchDeleteTasksRequest(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=100)


class WechatPublisherSettingsRequest(BaseModel):
    app_id: str | None = Field(default=None, min_length=1, max_length=128)
    app_secret: str | None = Field(default=None, min_length=1, max_length=512)
    clear_credentials: bool = False


class SelectPlanRequest(BaseModel):
    plan_id: str
    expected_task_version: int = Field(ge=1)


class UpdateSlotRequest(BaseModel):
    variant: str
    expected_plan_revision: int = Field(ge=1)
    reason: str = Field(default="operator_manual_switch", pattern="^(operator_manual_switch|product_review|compatibility_fallback)$")


class UpdateThemeRequest(BaseModel):
    visual_system: str = Field(
        pattern="^(light_reading|warm_humanist|youth_campus|editorial_contrast|structured_grid|future_tech|oriental_archive|vintage_press|pop_poster|natural_atlas|business_review|cinematic_story)$"
    )
    expected_plan_revision: int = Field(ge=1)
    reason: str = Field(default="operator_theme_switch", pattern="^(operator_theme_switch|history_rotation|product_review)$")


class RestoreRevisionRequest(BaseModel):
    expected_plan_revision: int = Field(ge=1)


class UndoPlanRequest(BaseModel):
    expected_plan_revision: int = Field(ge=1)


class GenerateImageRequest(BaseModel):
    mode: str = Field(pattern="^(start|regenerate|fallback)$")
    expected_image_revision: int = Field(ge=1)


class GenerateCoverRequest(BaseModel):
    expected_task_version: int = Field(ge=1)


class ReuseCoverRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    source_type: str = Field(pattern="^(accepted_body_image|controlled_source_image)$")
    source_id: str


class SelectCoverRequest(BaseModel):
    expected_task_version: int = Field(ge=1)


class CropCoverRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    scale: float = Field(ge=1.0, le=3.0)
    offset_x: float = Field(ge=-1.0, le=1.0)
    offset_y: float = Field(ge=-1.0, le=1.0)


class ImageDecisionRequest(BaseModel):
    expected_image_revision: int = Field(ge=1)
    text_verified: bool = False


class GenerateEditorialBriefRequest(BaseModel):
    expected_task_version: int = Field(ge=1)


class AcknowledgePreflightFindingRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    block_id: str | None = None


class PublicationMetadataRequest(BaseModel):
    author: str = Field(default="", max_length=8)
    digest: str = Field(default="", max_length=120)
    content_source_url: str = Field(default="", max_length=500)
    show_cover_pic: bool = True


class FreezePublicationRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    metadata: PublicationMetadataRequest = Field(default_factory=PublicationMetadataRequest)


class ContinueEditingRequest(BaseModel):
    expected_task_version: int = Field(ge=1)


class CreateMockDraftRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    draft_slot: str = Field(pattern=r"^(primary|draft-[2-9][0-9]*)$")
    simulation_mode: str = Field(default="success", pattern="^(success|fail_once|unknown)$")


class CreateWechatDraftRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    draft_slot: str = Field(pattern=r"^(primary|draft-[2-9][0-9]*)$")


class RetryMockDraftRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    expected_operation_version: int = Field(ge=1)


class ResolveUnknownDraftRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    expected_operation_version: int = Field(ge=1)
    outcome: str = Field(pattern="^(confirmed_succeeded|confirmed_not_created)$")
    evidence: str = Field(min_length=8, max_length=500)


class BlindDimensionRating(BaseModel):
    left: int = Field(ge=1, le=5)
    right: int = Field(ge=1, le=5)
    reason: str = Field(min_length=2, max_length=240)


class BlindReviewScores(BaseModel):
    article_understanding: BlindDimensionRating
    component_planning: BlindDimensionRating
    image_planning: BlindDimensionRating
    style_direction: BlindDimensionRating
    history_freshness: BlindDimensionRating
    direct_adoption: BlindDimensionRating


class BlindReviewSubmissionRequest(BaseModel):
    reviewer_id: str = Field(pattern="^(product_owner|operator)$")
    assignment_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    scores: BlindReviewScores
    preferred_candidate: str = Field(pattern="^(left|right|tie)$")
    preference_reason: str = Field(min_length=2, max_length=300)


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in task.items()
        if key
        not in {
            "markdown",
            "source_hash",
            "normalized_markdown",
            "normalized_hash",
            "progress",
            "input_summary",
            "last_error",
            "selection_change_count",
        }
    } | {"publication_mode": "local"}


def _fit_cover(content: bytes) -> bytes:
    try:
        with Image.open(BytesIO(content)) as source:
            converted = source.convert("RGB")
            target_size = (1080, 864)
            # Reused article images are commonly 16:9 while WeChat cover assets
            # use a 5:4 canvas. Keep the full source visible instead of silently
            # deleting the left/right information with a center crop. A softened
            # backdrop fills the remaining bands so the result still reads as a
            # deliberate cover rather than a letterboxed screenshot.
            backdrop = ImageOps.fit(
                converted,
                target_size,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            ).filter(ImageFilter.GaussianBlur(radius=28))
            backdrop = Image.blend(
                backdrop,
                Image.new("RGB", target_size, "#F7F5EF"),
                0.34,
            )
            fitted = ImageOps.contain(
                converted,
                target_size,
                method=Image.Resampling.LANCZOS,
            )
            offset = (
                (target_size[0] - fitted.width) // 2,
                (target_size[1] - fitted.height) // 2,
            )
            backdrop.paste(fitted, offset)
            output = BytesIO()
            backdrop.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("封面来源不是有效图片") from error


def _crop_cover(content: bytes, *, scale: float, offset_x: float, offset_y: float) -> bytes:
    """Apply the same fixed-frame transform used by the browser crop editor."""
    try:
        with Image.open(BytesIO(content)) as source:
            converted = source.convert("RGB")
            target_width, target_height = 1080, 864
            base = ImageOps.fit(
                converted,
                (target_width, target_height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            scaled_width = max(target_width, round(target_width * scale))
            scaled_height = max(target_height, round(target_height * scale))
            scaled = base.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
            max_x = max(0.0, (scale - 1.0) / 2.0)
            max_y = max(0.0, (scale - 1.0) / 2.0)
            safe_offset_x = max(-max_x, min(max_x, offset_x))
            safe_offset_y = max(-max_y, min(max_y, offset_y))
            left = round((scaled_width - target_width) / 2 - safe_offset_x * target_width)
            top = round((scaled_height - target_height) / 2 - safe_offset_y * target_height)
            left = max(0, min(scaled_width - target_width, left))
            top = max(0, min(scaled_height - target_height, top))
            cropped = scaled.crop((left, top, left + target_width, top + target_height))
            output = BytesIO()
            cropped.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("封面来源不是有效图片") from error


def _public_publication_revision(revision: dict[str, Any], *, suggested_draft_slot: str) -> dict[str, Any]:
    manifest = revision["asset_manifest"]
    roles = [item["asset_role"] for item in manifest.get("items", [])]
    preflight_status = revision["compatibility_report"].get("preflight_status", "PASS")
    return {
        key: value
        for key, value in revision.items()
        if key not in {"frozen_html", "visual_plan", "asset_manifest"}
    } | {
        "title": revision["metadata"]["title"],
        "preflight_status": preflight_status,
        "compatibility_status": revision["compatibility_report"]["status"],
        "asset_summary": {
            "cover_count": roles.count("cover"),
            "source_image_count": roles.count("source_body_image"),
            "planned_image_count": roles.count("planned_image"),
            "brand_asset_count": roles.count("brand_cta"),
        },
        "preview_url": f'/api/v1/publication-revisions/{revision["id"]}/content',
        "is_mock": False,
        "suggested_draft_slot": suggested_draft_slot,
    }


def _error(
    status: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "stage": None,
                "task_id": None,
                "field_errors": [],
                "request_id": str(uuid.uuid4()),
                "details": details,
            }
        },
    )


def _local_settings_request(request: Request, intent: str | None) -> bool:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return False
    if intent != "local-operator":
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed = urlparse(origin)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}


def create_app(
    database_path: str | None = None,
    image_provider: ImageProvider | None = None,
    text_planner_provider: TextPlannerProvider | None = None,
    blind_review_manifest_path: str | None = None,
    wechat_publisher: WechatDraftPublisher | None = None,
    wechat_connection_probe: WechatConnectionProbe | None = None,
    public_ip_probe: PublicIpProbe | None = None,
) -> FastAPI:
    root = Path(__file__).resolve().parents[4]
    runtime_settings, runtime_env_path = load_runtime_settings(root)
    db_path = database_path or os.environ.get("VISUAL_DIRECTOR_DB", str(root / "apps" / "api" / "data" / "visual-director.db"))
    repository = Repository(db_path)
    app = FastAPI(title="公众号视觉主编 API", version="0.1.0")
    app.state.repository = repository
    app.state.runtime_identity = runtime_identity(
        project_root=root,
        database_path=db_path,
    )
    app.state.image_provider = image_provider or create_image_provider_from_env(runtime_settings)
    app.state.text_planner_provider = text_planner_provider or create_text_planner_provider_from_env(runtime_settings)
    configured_env_path = os.environ.get("VISUAL_DIRECTOR_ENV_FILE")
    app.state.runtime_env_path = runtime_env_path or (
        Path(configured_env_path).expanduser().resolve()
        if configured_env_path
        else root / ".env.local"
    )
    app.state.runtime_settings = runtime_settings
    app.state.root = root
    app.state.brand_profile = load_brand_profile(root)
    app.state.brand_asset_path = brand_asset_path(root, app.state.brand_profile)
    app.state.wechat_publisher = wechat_publisher or WechatDraftPublisher(
        root,
        env_file=app.state.runtime_env_path,
        token_endpoint=runtime_settings.get("VISUAL_DIRECTOR_WECHAT_TOKEN_ENDPOINT"),
        api_base=runtime_settings.get("VISUAL_DIRECTOR_WECHAT_API_BASE"),
    )
    app.state.wechat_connection_probe = wechat_connection_probe or WechatConnectionProbe(
        endpoint=runtime_settings.get(
            "VISUAL_DIRECTOR_WECHAT_TOKEN_ENDPOINT",
            "https://api.weixin.qq.com/cgi-bin/token",
        )
    )
    app.state.public_ip_probe = public_ip_probe or PublicIpProbe()
    app.state.setup_preferences_path = app.state.runtime_env_path.parent / "setup-preferences.json"
    app.state.provider_status_path = app.state.runtime_env_path.parent / "provider-status.json"
    blind_manifest = Path(
        blind_review_manifest_path
        or os.environ.get(
            "VISUAL_DIRECTOR_BLIND_REVIEW_MANIFEST",
            str(root / "samples" / "evaluation" / "v0.6-public-blind-manifest.json"),
        )
    )
    app.state.blind_review_dataset = load_blind_review_dataset(str(root), str(blind_manifest))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3100",
        ],
        allow_origin_regex=r"^http://(?:localhost|127\.0\.0\.1):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return _error(404, "not_found", str(exc))

    @app.exception_handler(PublicationLockedError)
    async def publication_locked_handler(_: Request, exc: PublicationLockedError) -> JSONResponse:
        return _error(409, "publication_revision_locked", str(exc), retryable=False)

    @app.exception_handler(VersionConflictError)
    async def conflict_handler(_: Request, exc: VersionConflictError) -> JSONResponse:
        return _error(409, "version_conflict", str(exc), retryable=True)

    def publication_readiness(task_id: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
        task = repository.get_task(task_id)
        blockers: list[dict[str, Any]] = []
        checks = {
            "plan_selected": "pending",
            "preflight_resolved": "pending",
            "assets_complete": "pending",
            "image_slots_decided": "pending",
            "compatibility": "pending",
            "draft_operation_clear": "pending",
        }

        def block(code: str, message: str, resource_type: str, resource_id: str | None, action: str) -> None:
            blockers.append(
                {
                    "code": code,
                    "message": message,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "action": action,
                }
            )

        if task.get("active_publication_revision_id"):
            block(
                "active_revision_exists",
                "当前任务已有有效冻结版本",
                "publication_revision",
                task["active_publication_revision_id"],
                "view_frozen_revision",
            )

        plan: dict[str, Any] | None = None
        if not task.get("selected_plan_id"):
            checks["plan_selected"] = "blocking"
            block("plan_not_selected", "请先选择一套视觉方案", "task", task_id, "select_plan")
        else:
            checks["plan_selected"] = "pass"
            plan = repository.get_plan(task_id, task["selected_plan_id"])

        report = task["input_summary"].get("preflight_report") or {}
        unresolved_preflight_findings = [
            item
            for item in report.get("findings") or []
            if not item.get("resolved_at")
        ]
        asset_preflight_codes = {
            "missing_cover",
            "placeholder_cover",
            "cover_requires_import",
            "placeholder_image",
            "source_image_requires_import",
        }
        if not report.get("draft_creation_allowed"):
            checks["preflight_resolved"] = "blocking"
            unresolved_non_asset_findings = [
                item
                for item in unresolved_preflight_findings
                if item.get("code") not in asset_preflight_codes
            ]
            for finding in unresolved_non_asset_findings:
                policy = str(finding.get("resolution_policy") or "")
                block(
                    "preflight_finding_unresolved",
                    str(finding.get("message") or "存在未处理的内容检查项"),
                    "preflight_finding",
                    str(finding.get("block_id") or finding.get("code") or "root"),
                    "acknowledge_preflight" if policy == "ACKNOWLEDGE" else "edit_source",
                )
            if not unresolved_preflight_findings:
                block(
                    "preflight_not_ready",
                    "输入检查状态尚未就绪，请刷新任务后重试",
                    "preflight_report",
                    task_id,
                    "refresh_preflight",
                )
        else:
            checks["preflight_resolved"] = "pass"

        replacements = repository.list_preflight_asset_replacements(task_id)
        cover_asset = next((item for item in replacements if item["asset_role"] == "cover"), None)
        if cover_asset is None:
            block(
                "cover_asset_not_controlled",
                "封面尚未进入受控资产库",
                "preflight_finding",
                "cover",
                "replace_asset",
            )
        parsed = parse_markdown(task["normalized_markdown"], task["title"])
        source_blocks = [item for item in parsed.blocks if item.type == "image_reference"]
        replacement_by_block = {
            str(item["block_id"]): item
            for item in replacements
            if item["asset_role"] == "body_image" and item.get("block_id")
        }
        for source_block in source_blocks:
            if source_block.id not in replacement_by_block:
                block(
                    "source_image_not_controlled",
                    "原稿图片尚未进入受控资产库",
                    "content_block",
                    source_block.id,
                    "replace_asset",
                )

        def verify_asset_hash(
            *,
            path: Path,
            expected_sha256: str,
            resource_type: str,
            resource_id: str,
        ) -> None:
            actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_sha256 != expected_sha256:
                block(
                    "selected_asset_hash_mismatch",
                    "已确认资产与登记哈希不一致，请重新上传或生成",
                    resource_type,
                    resource_id,
                    "replace_asset",
                )

        if cover_asset is not None:
            try:
                cover_path_for_check, _ = repository.get_preflight_asset(cover_asset["id"])
                verify_asset_hash(
                    path=cover_path_for_check,
                    expected_sha256=cover_asset["output_sha256"],
                    resource_type="preflight_asset",
                    resource_id=cover_asset["id"],
                )
            except NotFoundError:
                block("selected_asset_missing", "已确认封面文件不存在", "preflight_asset", cover_asset["id"], "replace_asset")
        for asset in replacement_by_block.values():
            try:
                source_path_for_check, _ = repository.get_preflight_asset(asset["id"])
                verify_asset_hash(
                    path=source_path_for_check,
                    expected_sha256=asset["output_sha256"],
                    resource_type="preflight_asset",
                    resource_id=asset["id"],
                )
            except NotFoundError:
                block("selected_asset_missing", "已确认原稿图片文件不存在", "preflight_asset", asset["id"], "replace_asset")

        selected_states: list[dict[str, Any]] = []
        if plan is not None:
            repository.ensure_image_slot_states(task_id, plan["id"], plan.get("image_slots", []))
            selected_states = repository.list_image_slot_states(task_id, plan["id"])
            for state in selected_states:
                if state["decision"] not in {"accepted", "replaced", "skipped"}:
                    block(
                        "image_slot_pending",
                        "规划图片槽尚未做出采用、替换或跳过决定",
                        "image_slot",
                        state["image_slot_id"],
                        "review_image_slot",
                    )
                if state["decision"] in {"accepted", "replaced"}:
                    selected = next(
                        (candidate for candidate in state["candidates"] if candidate["id"] == state["selected_candidate_id"]),
                        None,
                    )
                    if selected is None:
                        block(
                            "selected_asset_missing",
                            "已采用的规划图片文件不存在",
                            "image_slot",
                            state["image_slot_id"],
                            "review_image_slot",
                        )
                    else:
                        try:
                            selected_path_for_check, _ = repository.get_image_candidate_asset(selected["id"])
                            verify_asset_hash(
                                path=selected_path_for_check,
                                expected_sha256=selected["output_sha256"],
                                resource_type="image_candidate",
                                resource_id=selected["id"],
                            )
                        except NotFoundError:
                            block(
                                "selected_asset_missing",
                                "已采用的规划图片文件不存在",
                                "image_candidate",
                                selected["id"],
                                "review_image_slot",
                            )
        checks["image_slots_decided"] = (
            "blocking"
            if any(item["code"] in {"image_slot_pending", "selected_asset_missing", "selected_asset_hash_mismatch"} for item in blockers)
            else "pass"
        )

        cta_path = app.state.brand_asset_path
        if cta_path is not None and not cta_path.is_file():
            block("cta_asset_missing", "固定 CTA 资产不存在", "brand_asset", "brand-cta", "restore_brand_asset")
        checks["assets_complete"] = (
            "blocking"
            if any(
                item["code"]
                in {
                    "cover_asset_not_controlled",
                    "source_image_not_controlled",
                    "selected_asset_missing",
                    "selected_asset_hash_mismatch",
                    "cta_asset_missing",
                }
                for item in blockers
            )
            else "pass"
        )

        operation_status = repository.has_blocking_draft_operation(task_id)
        if operation_status:
            code = "draft_operation_unknown" if operation_status == "unknown" else "draft_operation_in_progress"
            block(code, "存在未完成的草稿操作", "draft_operation", None, "resolve_draft_operation")
            checks["draft_operation_clear"] = "blocking"
        else:
            checks["draft_operation_clear"] = "pass"

        prepared: dict[str, Any] | None = None
        if not blockers and plan is not None and cover_asset is not None:
            document = materialize_preview_document(repository, plan["preview_artifact_id"])
            asset_sources: list[dict[str, Any]] = []

            def add_path_asset(
                *,
                token: str,
                role: str,
                resource_type: str,
                resource_id: str,
                path: Path,
                content_type: str,
                width: int,
                height: int,
                source_url: str | None = None,
                block_id: str | None = None,
                image_slot_id: str | None = None,
            ) -> None:
                content = path.read_bytes()
                asset_sources.append(
                    {
                        "asset_token": token,
                        "asset_role": role,
                        "source_resource_type": resource_type,
                        "source_resource_id": resource_id,
                        "source_url": source_url,
                        "block_id": block_id,
                        "image_slot_id": image_slot_id,
                        "path": path,
                        "content": content,
                        "content_type": content_type,
                        "output_sha256": hashlib.sha256(content).hexdigest(),
                        "width": width,
                        "height": height,
                    }
                )

            cover_path, cover_type = repository.get_preflight_asset(cover_asset["id"])
            add_path_asset(
                token="cover",
                role="cover",
                resource_type="preflight_asset",
                resource_id=cover_asset["id"],
                path=cover_path,
                content_type=cover_type,
                width=int(cover_asset["width"]),
                height=int(cover_asset["height"]),
            )
            for block_id, asset in replacement_by_block.items():
                path, content_type = repository.get_preflight_asset(asset["id"])
                add_path_asset(
                    token=f"source-{block_id}",
                    role="source_body_image",
                    resource_type="preflight_asset",
                    resource_id=asset["id"],
                    path=path,
                    content_type=content_type,
                    width=int(asset["width"]),
                    height=int(asset["height"]),
                    source_url=asset["content_url"],
                    block_id=block_id,
                )
            for state in selected_states:
                if state["decision"] not in {"accepted", "replaced"}:
                    continue
                selected = next(item for item in state["candidates"] if item["id"] == state["selected_candidate_id"])
                path, content_type = repository.get_image_candidate_asset(selected["id"])
                add_path_asset(
                    token=f'planned-{state["image_slot_id"]}',
                    role="planned_image",
                    resource_type="image_candidate",
                    resource_id=selected["id"],
                    path=path,
                    content_type=content_type,
                    width=int(selected["width"]),
                    height=int(selected["height"]),
                    source_url=selected["content_url"],
                    image_slot_id=state["image_slot_id"],
                )
            if cta_path is not None:
                with Image.open(cta_path) as cta_image:
                    cta_width, cta_height = cta_image.size
                    cta_content_type = Image.MIME.get(cta_image.format, "application/octet-stream")
                add_path_asset(
                    token="brand-cta",
                    role="brand_cta",
                    resource_type="brand_asset",
                    resource_id=task["fixed_footer_asset_version"],
                    path=cta_path,
                    content_type=cta_content_type,
                    width=cta_width,
                    height=cta_height,
                    source_url="/api/v1/brand-assets/current/content",
                )
            for source_url, asset_name in referenced_theme_assets(document):
                metadata = theme_asset_metadata(root, asset_name)
                if metadata is None:
                    block(
                        "theme_asset_missing",
                        f"主题装饰资产不存在：{asset_name}",
                        "theme_asset",
                        asset_name,
                        "restore_theme_asset",
                    )
                    checks["assets_complete"] = "blocking"
                    continue
                asset_path, asset_width, asset_height, asset_content_type = metadata
                add_path_asset(
                    token=f"theme-{asset_name.removesuffix('.png')}",
                    role="theme_decoration",
                    resource_type="theme_asset",
                    resource_id=asset_name,
                    path=asset_path,
                    content_type=asset_content_type,
                    width=asset_width,
                    height=asset_height,
                    source_url=source_url,
                )
            url_to_token = {
                item["source_url"]: item["asset_token"]
                for item in asset_sources
                if item.get("source_url")
            }
            frozen_html = replace_asset_urls(document, url_to_token)
            compatibility = check_frozen_html(frozen_html).to_dict()
            compatibility["preflight_status"] = (
                "REVIEW_RESOLVED" if report.get("status") == "REVIEW" else str(report.get("status") or "PASS")
            )
            if compatibility["status"] != "pass":
                block(
                    "compatibility_failed",
                    "最终 HTML 未通过兼容性检查",
                    "compatibility_report",
                    task_id,
                    "review_compatibility",
                )
                checks["compatibility"] = "blocking"
            else:
                checks["compatibility"] = "pass"
                prepared = {
                    "task": task,
                    "plan": plan,
                    "report": report,
                    "frozen_html": frozen_html,
                    "compatibility_report": compatibility,
                    "assets": asset_sources,
                }

        return (
            {
                "task_id": task_id,
                "ready": not blockers,
                "publication_mode": "local",
                "suggested_draft_slot": repository.suggested_draft_slot(task_id),
                "blockers": blockers,
                "checks": checks,
            },
            prepared if not blockers else None,
        )

    def image_provider_settings_snapshot() -> dict[str, Any]:
        env_path: Path = app.state.runtime_env_path
        file_values = read_env_file(env_path)
        image_setting_keys = (
            "VISUAL_DIRECTOR_IMAGE_PROVIDER",
            "IMAGE_API_KEY",
            "IMAGE_API_ENDPOINT",
            "IMAGE_API_MODEL",
            "IMAGE_API_PROTOCOL",
            "IMAGE_API_SIZE",
            "GEMINI_API_KEY",
            "GEMINI_IMAGE_ENDPOINT",
            "GEMINI_IMAGE_MODEL",
            "GEMINI_IMAGE_SIZE",
            # Legacy Agnes keys remain readable for a lossless upgrade.
            "AGNES_API_KEY",
            "AGNES_IMAGE_ENDPOINT",
            "AGNES_IMAGE_MODEL",
            "AGNES_IMAGE_SIZE",
        )
        process_keys = {
            key
            for key in image_setting_keys
            if key in os.environ
        }
        raw_mode = str(
            os.environ.get("VISUAL_DIRECTOR_IMAGE_PROVIDER")
            or file_values.get("VISUAL_DIRECTOR_IMAGE_PROVIDER")
            or "mock"
        ).strip().lower()
        legacy_agnes = raw_mode == "agnes"
        mode = "images_api" if legacy_agnes else raw_mode
        active_key_name = "GEMINI_API_KEY" if mode == "gemini" else "IMAGE_API_KEY"
        active_legacy_key_name = "AGNES_API_KEY" if mode == "images_api" else ""
        process_has_primary_key = active_key_name in os.environ
        file_has_primary_key = active_key_name in file_values
        process_api_key = str(
            os.environ.get(active_key_name, "")
            if process_has_primary_key
            else os.environ.get(active_legacy_key_name, "")
            if active_legacy_key_name
            else ""
        ).strip()
        file_api_key = str(
            file_values.get(active_key_name, "")
            if file_has_primary_key
            else file_values.get(active_legacy_key_name, "")
            if active_legacy_key_name
            else ""
        ).strip()
        api_key_configured = bool(
            process_api_key or file_api_key
        )
        credential_source = (
            "process_environment"
            if process_api_key
            else "local_env_file"
            if file_api_key
            else "missing"
        )
        active_provider = app.state.image_provider
        warnings: list[str] = []
        if mode == "manual":
            warnings.append("manual_upload_only")
        elif mode == "mock":
            warnings.append("mock_images_are_not_production_assets")
        elif mode in {"images_api", "gemini"} and not active_provider.configured:
            warnings.append("image_api_key_missing")
        if legacy_agnes:
            warnings.append("legacy_agnes_settings_mapped_to_images_api")
        images_endpoint = str(
            os.environ.get("IMAGE_API_ENDPOINT")
            or file_values.get("IMAGE_API_ENDPOINT")
            or os.environ.get("AGNES_IMAGE_ENDPOINT")
            or file_values.get("AGNES_IMAGE_ENDPOINT")
            or (DEFAULT_AGNES_ENDPOINT if legacy_agnes else DEFAULT_IMAGES_API_ENDPOINT)
        )
        images_model = str(
            os.environ.get("IMAGE_API_MODEL")
            or file_values.get("IMAGE_API_MODEL")
            or os.environ.get("AGNES_IMAGE_MODEL")
            or file_values.get("AGNES_IMAGE_MODEL")
            or (DEFAULT_AGNES_MODEL if legacy_agnes else DEFAULT_IMAGES_API_MODEL)
        )
        return {
            "schema_version": IMAGE_PROVIDER_SETTINGS_SCHEMA_VERSION,
            "mode": mode,
            "active_provider": active_provider.provider,
            "active_model": active_provider.model,
            "real_generation_available": (
                active_provider.provider in {"images_api", "gemini"} and active_provider.configured
            ),
            "api_key_configured": api_key_configured,
            "credential_source": credential_source,
            "managed_by_environment": bool(process_keys),
            "managed_fields": sorted(process_keys),
            "config_file": str(env_path),
            "providers": {
                "images_api": {
                    "endpoint": images_endpoint,
                    "model": images_model,
                    "protocol": str(
                        os.environ.get("IMAGE_API_PROTOCOL")
                        or file_values.get("IMAGE_API_PROTOCOL")
                        or ("extended" if legacy_agnes else DEFAULT_IMAGES_API_PROTOCOL)
                    ),
                    "size": str(
                        os.environ.get("IMAGE_API_SIZE")
                        or file_values.get("IMAGE_API_SIZE")
                        or os.environ.get("AGNES_IMAGE_SIZE")
                        or file_values.get("AGNES_IMAGE_SIZE")
                        or ("1K" if legacy_agnes else "auto")
                    ),
                    "api_key_configured": bool(
                        str(
                            os.environ.get("IMAGE_API_KEY", "")
                            if "IMAGE_API_KEY" in os.environ
                            else file_values.get("IMAGE_API_KEY", "")
                            if "IMAGE_API_KEY" in file_values
                            else os.environ.get("AGNES_API_KEY", "")
                            or file_values.get("AGNES_API_KEY", "")
                        ).strip()
                    ),
                },
                "gemini": {
                    "endpoint": str(
                        os.environ.get("GEMINI_IMAGE_ENDPOINT")
                        or file_values.get("GEMINI_IMAGE_ENDPOINT")
                        or DEFAULT_GEMINI_IMAGE_ENDPOINT
                    ),
                    "model": str(
                        os.environ.get("GEMINI_IMAGE_MODEL")
                        or file_values.get("GEMINI_IMAGE_MODEL")
                        or DEFAULT_GEMINI_IMAGE_MODEL
                    ),
                    "protocol": "gemini_interactions",
                    "size": str(
                        os.environ.get("GEMINI_IMAGE_SIZE")
                        or file_values.get("GEMINI_IMAGE_SIZE")
                        or "1K"
                    ),
                    "api_key_configured": bool(
                        str(
                            os.environ.get("GEMINI_API_KEY")
                            or file_values.get("GEMINI_API_KEY")
                            or ""
                        ).strip()
                    ),
                },
            },
            "legacy_agnes": {
                "detected": legacy_agnes,
                "size": str(
                    os.environ.get("AGNES_IMAGE_SIZE")
                    or file_values.get("AGNES_IMAGE_SIZE")
                    or "1K"
                ),
            },
            "prompt_strategy": "visual_director_managed",
            "external_connection_tested": False,
            "restart_required": False,
            "warnings": warnings,
        }

    @app.get("/api/v1/settings/image-provider")
    def get_image_provider_settings() -> dict[str, Any]:
        return {"settings": image_provider_settings_snapshot()}

    @app.put("/api/v1/settings/image-provider")
    def update_image_provider_settings(
        payload: ImageProviderSettingsRequest,
        request: Request,
        x_settings_intent: str | None = Header(default=None, alias="X-Settings-Intent"),
    ) -> Any:
        if not _local_settings_request(request, x_settings_intent):
            return _error(
                403,
                "local_settings_required",
                "生图配置只允许从本机工作台修改。",
            )
        current = image_provider_settings_snapshot()
        if current["managed_by_environment"]:
            return _error(
                409,
                "image_settings_environment_managed",
                "当前生图配置由进程环境变量托管，请在启动环境中修改后重启。",
                details={"managed_fields": current["managed_fields"]},
            )
        api_key = payload.api_key.strip() if payload.api_key is not None else None
        if payload.clear_api_key and api_key:
            return _error(
                422,
                "image_api_key_conflict",
                "不能同时填写新 Key 和清除 Key。",
            )

        env_path: Path = app.state.runtime_env_path
        file_values = read_env_file(env_path)
        updates = {"VISUAL_DIRECTOR_IMAGE_PROVIDER": payload.mode}
        if payload.mode == "images_api":
            updates.update(
                {
                    "IMAGE_API_ENDPOINT": (payload.endpoint or current["providers"]["images_api"]["endpoint"]).strip(),
                    "IMAGE_API_MODEL": (payload.model or current["providers"]["images_api"]["model"]).strip(),
                    "IMAGE_API_PROTOCOL": payload.protocol or current["providers"]["images_api"]["protocol"],
                    "IMAGE_API_SIZE": (payload.size or current["providers"]["images_api"]["size"]).strip(),
                }
            )
            if payload.clear_api_key:
                updates["IMAGE_API_KEY"] = ""
            elif api_key is not None:
                updates["IMAGE_API_KEY"] = api_key
        elif payload.mode == "gemini":
            updates.update(
                {
                    "GEMINI_IMAGE_ENDPOINT": (payload.endpoint or current["providers"]["gemini"]["endpoint"]).strip(),
                    "GEMINI_IMAGE_MODEL": (payload.model or current["providers"]["gemini"]["model"]).strip(),
                    "GEMINI_IMAGE_SIZE": (payload.size or current["providers"]["gemini"]["size"]).strip(),
                }
            )
            if payload.clear_api_key:
                updates["GEMINI_API_KEY"] = ""
            elif api_key is not None:
                updates["GEMINI_API_KEY"] = api_key
        elif api_key is not None or payload.clear_api_key:
            return _error(
                422,
                "image_api_key_mode_invalid",
                "人工上传和 Mock 模式不接收 API Key 修改。",
            )
        prospective_settings = {**file_values, **updates, **os.environ}
        try:
            provider = create_image_provider_from_env(prospective_settings)
            update_env_file(env_path, updates)
        except (OSError, ValueError) as error:
            return _error(
                422,
                "image_settings_invalid",
                str(error),
            )
        app.state.image_provider = provider
        app.state.runtime_settings = prospective_settings
        return {
            "saved": True,
            "validation_scope": "local_configuration",
            "settings": image_provider_settings_snapshot(),
        }

    def provider_probe_status() -> dict[str, Any]:
        path: Path = app.state.provider_status_path
        if not path.is_file():
            return {"schema_version": "provider_probe_status.v0.1"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": "provider_probe_status.v0.1"}
        return payload if isinstance(payload, dict) else {"schema_version": "provider_probe_status.v0.1"}

    def wechat_publisher_settings_snapshot() -> dict[str, Any]:
        env_path: Path = app.state.runtime_env_path
        file_values = read_env_file(env_path)
        managed_fields = sorted(
            key
            for key in (
                "WECHAT_APP_ID",
                "WECHAT_APP_SECRET",
            )
            if key in os.environ
        )
        app_id = str(
            os.environ.get("WECHAT_APP_ID")
            if "WECHAT_APP_ID" in os.environ
            else file_values.get("WECHAT_APP_ID", "")
        ).strip()
        app_secret = str(
            os.environ.get("WECHAT_APP_SECRET")
            if "WECHAT_APP_SECRET" in os.environ
            else file_values.get("WECHAT_APP_SECRET", "")
        ).strip()
        probe = provider_probe_status().get("wechat_connection")
        return {
            "schema_version": "wechat_publisher_settings.v0.2",
            "credentials_configured": bool(app_id and app_secret),
            "app_id_configured": bool(app_id),
            "app_secret_configured": bool(app_secret),
            "credential_source": (
                "process_environment"
                if app_id and app_secret and {
                    "WECHAT_APP_ID",
                    "WECHAT_APP_SECRET",
                }.issubset(os.environ)
                else "local_env_file"
                if app_id and app_secret
                else "missing"
            ),
            "managed_by_environment": bool(managed_fields),
            "managed_fields": managed_fields,
            "connection_probe": probe if isinstance(probe, dict) else None,
            "config_file": str(env_path),
            "secrets_returned": False,
            "restart_required": False,
        }

    def capability_settings_snapshot() -> dict[str, Any]:
        preferences = read_setup_preferences(app.state.setup_preferences_path)
        image_settings = image_provider_settings_snapshot()
        wechat_settings = wechat_publisher_settings_snapshot()
        publisher_status = (
            app.state.wechat_publisher.quick_status()
            if hasattr(app.state.wechat_publisher, "quick_status")
            else app.state.wechat_publisher.status()
        )
        target_mode = preferences["target_mode"]
        image_ready = bool(image_settings["real_generation_available"])
        wechat_probe = wechat_settings.get("connection_probe") or {}
        publisher_ready = bool(
            publisher_status.get("ready_for_connection_probe", publisher_status.get("ready", False))
        )
        wechat_ready = bool(publisher_ready and wechat_probe.get("ok"))
        required = {
            "typesetting": True,
            "image_generation": target_mode in {"images", "full_delivery"},
            "wechat_draft": target_mode == "full_delivery",
        }
        complete = (
            (not required["image_generation"] or image_ready)
            and (not required["wechat_draft"] or wechat_ready)
        )
        if required["image_generation"] and not image_ready:
            next_action = "configure_image_provider"
        elif required["wechat_draft"] and not wechat_settings["credentials_configured"]:
            next_action = "configure_wechat_credentials"
        elif required["wechat_draft"] and not wechat_ready:
            next_action = "test_wechat_connection"
        else:
            next_action = "create_article"
        return {
            "schema_version": CAPABILITY_SETTINGS_SCHEMA_VERSION,
            "target_mode": target_mode,
            "complete_for_target": complete,
            "next_action": next_action,
            "preferences": preferences,
            "capabilities": {
                "typesetting": {
                    "state": "ready",
                    "required": required["typesetting"],
                },
                "image_generation": {
                    "state": "ready" if image_ready else "configuration",
                    "required": required["image_generation"],
                    "mode": image_settings["mode"],
                },
                "wechat_draft": {
                    "state": (
                        "ready"
                        if wechat_ready
                        else "configuration"
                        if not wechat_settings["credentials_configured"]
                        else "review_required"
                    ),
                    "required": required["wechat_draft"],
                    "publisher_ready": publisher_ready,
                    "connection_tested": bool(
                        wechat_probe.get("checked_at")
                        and wechat_probe.get("code") != "not_checked"
                    ),
                    "connection_ok": bool(wechat_probe.get("ok")),
                },
                "rich_copy": {"state": "ready", "required": False},
                "bundle_export": {"state": "ready", "required": False},
            },
        }

    @app.get("/api/v1/settings/capabilities")
    def get_capability_settings() -> dict[str, Any]:
        return {"settings": capability_settings_snapshot()}

    @app.get("/api/v1/settings/setup-preferences")
    def get_setup_preferences() -> dict[str, Any]:
        return {"settings": read_setup_preferences(app.state.setup_preferences_path)}

    @app.put("/api/v1/settings/setup-preferences")
    def update_setup_preferences(
        payload: SetupPreferencesRequest,
        request: Request,
        x_settings_intent: str | None = Header(default=None, alias="X-Settings-Intent"),
    ) -> Any:
        if not _local_settings_request(request, x_settings_intent):
            return _error(403, "local_settings_required", "本机能力设置只允许从本机工作台修改。")
        try:
            settings = write_setup_preferences(
                app.state.setup_preferences_path,
                payload.target_mode,
            )
        except (OSError, ValueError) as error:
            return _error(422, "setup_preferences_invalid", str(error))
        return {"saved": True, "settings": settings, "capability_settings": capability_settings_snapshot()}

    @app.get("/api/v1/settings/wechat-publisher")
    def get_wechat_publisher_settings() -> dict[str, Any]:
        return {"settings": wechat_publisher_settings_snapshot()}

    @app.put("/api/v1/settings/wechat-publisher")
    def update_wechat_publisher_settings(
        payload: WechatPublisherSettingsRequest,
        request: Request,
        x_settings_intent: str | None = Header(default=None, alias="X-Settings-Intent"),
    ) -> Any:
        if not _local_settings_request(request, x_settings_intent):
            return _error(403, "local_settings_required", "微信公众号配置只允许从本机工作台修改。")
        current = wechat_publisher_settings_snapshot()
        if current["managed_by_environment"]:
            return _error(
                409,
                "wechat_settings_environment_managed",
                "当前微信公众号配置由进程环境变量托管，请在启动环境中修改后重启。",
                details={"managed_fields": current["managed_fields"]},
            )
        if payload.clear_credentials and (payload.app_id or payload.app_secret):
            return _error(422, "wechat_credentials_conflict", "不能同时填写新凭据和清除凭据。")
        updates: dict[str, str] = {}
        if payload.clear_credentials:
            updates.update({"WECHAT_APP_ID": "", "WECHAT_APP_SECRET": ""})
        else:
            if payload.app_id is not None:
                updates["WECHAT_APP_ID"] = payload.app_id.strip()
            if payload.app_secret is not None:
                updates["WECHAT_APP_SECRET"] = payload.app_secret.strip()
        if not updates:
            return _error(422, "wechat_settings_empty", "没有需要保存的微信公众号配置。")
        try:
            update_env_file(app.state.runtime_env_path, updates)
            write_probe_status(
                app.state.provider_status_path,
                "wechat_connection",
                {"ok": False, "code": "not_checked", "checked_at": None},
            )
        except (OSError, ValueError) as error:
            return _error(422, "wechat_settings_invalid", str(error))
        app.state.runtime_settings = {
            **read_env_file(app.state.runtime_env_path),
            **os.environ,
        }
        return {"saved": True, "settings": wechat_publisher_settings_snapshot()}

    @app.post("/api/v1/settings/wechat-publisher/probe")
    def probe_wechat_publisher(
        request: Request,
        x_settings_intent: str | None = Header(default=None, alias="X-Settings-Intent"),
    ) -> Any:
        if not _local_settings_request(request, x_settings_intent):
            return _error(403, "local_settings_required", "微信公众号连通性检测只允许从本机发起。")
        values = {**read_env_file(app.state.runtime_env_path), **os.environ}
        result = app.state.wechat_connection_probe.probe(
            str(values.get("WECHAT_APP_ID") or "").strip(),
            str(values.get("WECHAT_APP_SECRET") or "").strip(),
        )
        try:
            write_probe_status(app.state.provider_status_path, "wechat_connection", result)
        except OSError:
            pass
        return result

    @app.post("/api/v1/settings/network/public-ip-probe")
    def probe_public_ip(
        request: Request,
        x_settings_intent: str | None = Header(default=None, alias="X-Settings-Intent"),
    ) -> Any:
        if not _local_settings_request(request, x_settings_intent):
            return _error(403, "local_settings_required", "公网 IP 检测只允许从本机显式发起。")
        result = app.state.public_ip_probe.probe()
        try:
            write_probe_status(app.state.provider_status_path, "public_ip", result)
        except OSError:
            pass
        return result

    @app.get("/api/health")
    @app.get("/health")
    def health() -> dict[str, Any]:
        runtime = {
            **app.state.runtime_identity,
            "task_count": int(repository.list_tasks_page(page=1, page_size=1)["total"]),
        }
        return {
            "status": "ok",
            "application": "wechat_visual_director_workbench",
            "application_version": application_version(),
            "planner": "editorial_brief",
            "image_provider": app.state.image_provider.provider,
            "image_provider_configured": app.state.image_provider.configured,
            "image_provider_settings_schema_version": IMAGE_PROVIDER_SETTINGS_SCHEMA_VERSION,
            "capability_settings_schema_version": CAPABILITY_SETTINGS_SCHEMA_VERSION,
            "image_prompt_version": IMAGE_PROMPT_VERSION,
            "text_planner_provider": app.state.text_planner_provider.provider,
            "text_planner_model": app.state.text_planner_provider.model,
            "text_planner_configured": app.state.text_planner_provider.configured,
            "text_planner_prompt_version": TEXT_PLANNER_PROMPT_VERSION,
            "editorial_brief_schema_version": EDITORIAL_BRIEF_SCHEMA_VERSION,
            "editorial_brief_normalizer_version": EDITORIAL_BRIEF_NORMALIZER_VERSION,
            "preflight_schema_version": PREFLIGHT_SCHEMA_VERSION,
            "preflight_ruleset_version": PREFLIGHT_RULESET_VERSION,
            "publication_schema_version": PUBLICATION_SCHEMA_VERSION,
            "publication_mode": "local",
            "runtime_identity": runtime,
        }

    @app.get("/api/v1/theme-gallery")
    def theme_gallery() -> dict[str, Any]:
        return {
            "schema_version": THEME_GALLERY_SCHEMA_VERSION,
            "themes": build_theme_gallery(),
        }

    @app.get("/api/v1/article-tasks")
    def list_tasks(
        page: int | None = Query(default=None, ge=1),
        page_size: int | None = Query(default=None, ge=1, le=50),
    ) -> dict[str, Any]:
        # Calls without pagination parameters retain the original full-list response.
        if page is None and page_size is None:
            items = [_public_task(task) for task in repository.list_tasks()]
            return {"items": items, "next_cursor": None}
        resolved_page = page or 1
        resolved_page_size = page_size or 8
        result = repository.list_tasks_page(page=resolved_page, page_size=resolved_page_size)
        total = int(result["total"])
        total_pages = max(1, (total + resolved_page_size - 1) // resolved_page_size)
        return {
            "schema_version": "article_task_page.v0.1",
            "items": [_public_task(task) for task in result["items"]],
            "page": resolved_page,
            "page_size": resolved_page_size,
            "total": total,
            "total_pages": total_pages,
            "has_previous": resolved_page > 1,
            "has_next": resolved_page < total_pages,
            "next_cursor": None,
        }

    @app.post("/api/v1/article-tasks/batch-delete")
    def batch_delete_tasks(payload: BatchDeleteTasksRequest) -> dict[str, Any]:
        result = repository.delete_tasks(payload.task_ids)
        return {
            "schema_version": "task_batch_delete_result.v0.1",
            "deleted_count": len(result["deleted_task_ids"]),
            **result,
        }

    @app.get("/api/v1/blind-reviews/{eval_set_id}")
    def get_blind_review_set(eval_set_id: str, reviewer_id: str) -> Any:
        dataset: BlindReviewDataset = app.state.blind_review_dataset
        if eval_set_id != dataset.eval_set_id:
            raise NotFoundError("盲评集合不存在")
        if reviewer_id not in dataset.reviewers:
            return _error(422, "unknown_reviewer", "请选择有效的评审身份")
        submitted = {
            item["sample_id"]
            for item in repository.list_blind_review_submissions(eval_set_id, reviewer_id)
        }
        return dataset.public_set(reviewer_id, submitted)

    @app.get(
        "/api/v1/blind-reviews/{eval_set_id}/reviewers/{reviewer_id}/samples/{sample_id}/candidates/{position}/preview",
        response_class=HTMLResponse,
    )
    def get_blind_candidate_preview(
        eval_set_id: str,
        reviewer_id: str,
        sample_id: str,
        position: str,
    ) -> Any:
        dataset: BlindReviewDataset = app.state.blind_review_dataset
        if eval_set_id != dataset.eval_set_id:
            raise NotFoundError("盲评集合不存在")
        try:
            return HTMLResponse(dataset.preview_html(reviewer_id, sample_id, position))
        except KeyError as exc:
            raise NotFoundError(str(exc)) from exc

    @app.post(
        "/api/v1/blind-reviews/{eval_set_id}/samples/{sample_id}/submissions",
        status_code=201,
    )
    def submit_blind_review(
        eval_set_id: str,
        sample_id: str,
        payload: BlindReviewSubmissionRequest,
    ) -> Any:
        dataset: BlindReviewDataset = app.state.blind_review_dataset
        if eval_set_id != dataset.eval_set_id or sample_id not in dataset.samples_by_id:
            raise NotFoundError("盲评样本不存在")
        if payload.reviewer_id not in dataset.reviewers:
            return _error(422, "unknown_reviewer", "请选择有效的评审身份")
        expected_token = dataset.assignment_token(payload.reviewer_id, sample_id)
        if payload.assignment_token != expected_token:
            return _error(409, "assignment_changed", "候选顺序已变化，请刷新页面后重新评分", retryable=True)
        response = payload.model_dump(mode="json")
        repository.create_blind_review_submission(
            eval_set_id=eval_set_id,
            reviewer_id=payload.reviewer_id,
            sample_id=sample_id,
            assignment_token=payload.assignment_token,
            response=response,
        )
        completed = len(repository.list_blind_review_submissions(eval_set_id, payload.reviewer_id))
        return {
            "submitted": True,
            "sample_id": sample_id,
            "locked": True,
            "progress": {"completed": completed, "total": len(dataset.samples)},
        }

    @app.get("/api/v1/blind-reviews/{eval_set_id}/results")
    def get_blind_review_results(eval_set_id: str) -> Any:
        dataset: BlindReviewDataset = app.state.blind_review_dataset
        if eval_set_id != dataset.eval_set_id:
            raise NotFoundError("盲评集合不存在")
        submissions = repository.list_blind_review_submissions(eval_set_id)
        expected = len(dataset.samples) * len(dataset.reviewers)
        if len(submissions) < expected:
            return _error(
                409,
                "review_incomplete",
                "两位评审者全部提交后才能统一揭盲",
                details={"completed": len(submissions), "total": expected},
            )
        totals = {
            "baseline": {key: [] for key, _, _ in BLIND_REVIEW_DIMENSIONS},
            "candidate": {key: [] for key, _, _ in BLIND_REVIEW_DIMENSIONS},
        }
        preferences = {"baseline": 0, "candidate": 0, "tie": 0}
        for submission in submissions:
            reviewer_id = submission["reviewer_id"]
            sample_id = submission["sample_id"]
            response = submission["response"]
            for key, _, _ in BLIND_REVIEW_DIMENSIONS:
                rating = response["scores"][key]
                left_source = dataset.source_for_position(reviewer_id, sample_id, "left")
                right_source = dataset.source_for_position(reviewer_id, sample_id, "right")
                totals[left_source][key].append(rating["left"])
                totals[right_source][key].append(rating["right"])
            preferred = response["preferred_candidate"]
            if preferred == "tie":
                preferences["tie"] += 1
            else:
                preferences[dataset.source_for_position(reviewer_id, sample_id, preferred)] += 1
        averages = {
            source: {
                key: round(sum(values) / len(values), 2)
                for key, values in dimensions.items()
            }
            for source, dimensions in totals.items()
        }
        return {
            "eval_set_id": eval_set_id,
            "revealed": True,
            "formal_conclusion_allowed": False,
            "sources": {
                "baseline": "R · 确定性规则方案",
                "candidate": "L · 固定快照文本规划方案",
            },
            "average_scores": averages,
            "preferences": preferences,
            "note": dataset.manifest["note"],
        }

    @app.post("/api/v1/article-tasks", status_code=201)
    async def create_task(
        account_id: str = Form("default"),
        markdown_file: UploadFile = File(...),
        article_type: str | None = Form(None),
        title_override: str | None = Form(None),
        idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ) -> Any:
        if idempotency_key is not None and (not idempotency_key.strip() or len(idempotency_key) > 200):
            return _error(422, "invalid_idempotency_key", "Idempotency-Key must contain 1 to 200 characters")
        if not markdown_file.filename or not markdown_file.filename.lower().endswith((".md", ".markdown")):
            return _error(415, "unsupported_media_type", "只支持 .md 或 .markdown 文件")
        raw = await markdown_file.read()
        if len(raw) > 2 * 1024 * 1024:
            return _error(413, "file_too_large", "Markdown 文件不能超过 2MB")
        try:
            markdown = raw.decode("utf-8")
        except UnicodeDecodeError:
            return _error(422, "invalid_encoding", "Markdown 必须使用 UTF-8 编码")
        preflight = run_preflight(
            markdown,
            title_override=title_override,
            requested_article_type=article_type,
        )
        preflight_report = preflight.report.to_dict()
        if preflight.report.status == "BLOCK" or preflight.parsed is None:
            return _error(
                422,
                "preflight_blocked",
                "Markdown 预检未通过，请修复阻断项后重试",
                details={"preflight_report": preflight_report},
            )
        parsed = preflight.parsed
        resolved_type = classify_article(parsed, article_type)
        warnings = [
            {"code": finding.code, "message": finding.message}
            for finding in preflight.report.findings
        ]
        if parsed.image_reference_count:
            warnings.append(
                {
                    "code": "source_images_deferred",
                    "message": f"识别到 {parsed.image_reference_count} 个原稿图片引用；V0.7 试点不加载来源图片，只评估系统规划的图片槽位置",
                }
            )
        input_summary = {
            "title_source": parsed.title_source if parsed.title_source != "override" else "frontmatter",
            "section_count": parsed.section_count,
            "image_reference_count": parsed.image_reference_count,
            "warnings": warnings,
            "preflight_report": preflight_report,
        }
        request_hash = hash_json(
            {
                "account_id": account_id,
                "article_type": resolved_type,
                "title": parsed.title,
                "normalized_hash": preflight.report.normalized_hash,
            }
        )
        task, idempotency_replayed = repository.create_task(
            account_id=account_id,
            title=parsed.title,
            article_type=resolved_type,
            markdown=markdown,
            source_hash=preflight.report.source_hash,
            normalized_markdown=preflight.normalized_markdown,
            normalized_hash=preflight.report.normalized_hash,
            input_summary=input_summary,
            idempotency_key=idempotency_key,
            request_hash=request_hash if idempotency_key else None,
        )
        return {
            "task": _public_task(task),
            "input_summary": input_summary,
            "review_path": f'/tasks/{task["id"]}',
            "idempotency_replayed": idempotency_replayed,
        }

    @app.get("/api/v1/article-tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task = repository.get_task(task_id)
        actions = {
            "created": ["start_plan_generation"],
            "analyzing": [],
            "plans_ready": ["view_plans", "select_plan"],
            "plan_selected": ["view_plans", "change_selection", "view_publication_readiness"],
            "publication_frozen": ["view_frozen_revision", "create_mock_draft", "continue_editing"],
            "mock_draft_created": ["view_mock_draft", "continue_editing"],
            "mock_draft_failed": ["retry_mock_draft", "continue_editing"],
            "mock_draft_unknown": ["resolve_mock_unknown"],
            "wechat_draft_syncing": ["view_draft_operation"],
            "wechat_draft_created": ["view_wechat_draft", "continue_editing"],
            "wechat_draft_failed": ["view_draft_error", "continue_editing"],
            "wechat_draft_unknown": ["verify_wechat_backend"],
            "failed": ["retry_plan_generation"],
        }[task["status"]]
        return {
            "task": _public_task(task),
            "progress": task["progress"],
            "input_summary": task["input_summary"],
            "available_actions": actions,
            "last_error": task["last_error"],
        }

    @app.patch("/api/v1/article-tasks/{task_id}/publication-draft")
    def save_publication_draft(
        task_id: str,
        payload: PublicationMetadataRequest,
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> dict[str, Any]:
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的操作身份")
        return repository.save_publication_draft_metadata(
            task_id=task_id,
            metadata=payload.model_dump(),
            operator_id=operator_id,
        )

    @app.get("/api/v1/article-tasks/{task_id}/publication-readiness")
    def get_publication_readiness(task_id: str) -> dict[str, Any]:
        readiness, _ = publication_readiness(task_id)
        return readiness

    @app.get("/api/v1/article-tasks/{task_id}/publication-revisions")
    def get_publication_revisions(task_id: str) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "items": [
                _public_publication_revision(
                    item,
                    suggested_draft_slot=repository.suggested_draft_slot(task_id),
                )
                for item in repository.list_publication_revisions(task_id)
            ],
        }

    @app.post("/api/v1/article-tasks/{task_id}/publication-revisions", status_code=201)
    def freeze_publication_revision(
        task_id: str,
        payload: FreezePublicationRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> Any:
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的操作身份")
        request_value = {
            "task_id": task_id,
            "expected_task_version": payload.expected_task_version,
            "metadata": payload.metadata.model_dump(mode="json"),
        }
        request_hash = hash_json(request_value)
        replay = repository.get_idempotent_resource(
            scope="freeze",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay:
            revision = repository.get_publication_revision(replay[1])
            task = repository.get_task(task_id)
            return {
                "revision": _public_publication_revision(
                    revision,
                    suggested_draft_slot=repository.suggested_draft_slot(task_id),
                ),
                "task": _public_task(task),
            }
        readiness, prepared = publication_readiness(task_id)
        if not readiness["ready"] or prepared is None:
            return _error(
                409,
                "publication_gate_blocked",
                "当前工作版本尚未满足冻结条件",
                details={"blockers": readiness["blockers"], "checks": readiness["checks"]},
            )
        task = prepared["task"]
        if task["version"] != payload.expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        revision_id = str(uuid.uuid4())
        extension_by_type = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
        stored_assets: list[dict[str, Any]] = []
        manifest_items: list[dict[str, Any]] = []
        for source in prepared["assets"]:
            asset_id = str(uuid.uuid4())
            extension = extension_by_type.get(source["content_type"], Path(source["path"]).suffix.lower())
            relative_filename = f"{asset_id}{extension}"
            stored = {
                **source,
                "id": asset_id,
                "relative_filename": relative_filename,
            }
            stored_assets.append(stored)
            manifest_items.append(
                {
                    key: value
                    for key, value in stored.items()
                    if key not in {"content", "path", "source_url"}
                }
            )
        metadata = {
            "title": task["title"],
            **payload.metadata.model_dump(mode="json"),
        }
        manifest = {"schema_version": "publication_asset_manifest.v0.1", "items": manifest_items}
        revision_payload = {
            "id": revision_id,
            "plan_id": prepared["plan"]["id"],
            "plan_revision": prepared["plan"]["revision"],
            "normalized_hash": task["normalized_hash"],
            "preflight_report_hash": hash_json(prepared["report"]),
            "visual_plan": prepared["plan"],
            "visual_plan_hash": hash_json(prepared["plan"]),
            "frozen_html": prepared["frozen_html"],
            "frozen_html_hash": sha256_text(prepared["frozen_html"]),
            "structure_hash": structure_hash(prepared["frozen_html"]),
            "metadata": metadata,
            "metadata_hash": hash_json(metadata),
            "asset_manifest": manifest,
            "asset_manifest_hash": hash_json(manifest),
            "compatibility_report": prepared["compatibility_report"],
            "compatibility_report_hash": hash_json(prepared["compatibility_report"]),
            "frozen_by": operator_id,
        }
        revision, updated_task = repository.create_publication_revision(
            task_id=task_id,
            expected_task_version=payload.expected_task_version,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            revision=revision_payload,
            assets=stored_assets,
        )
        return {
            "revision": _public_publication_revision(
                revision,
                suggested_draft_slot=repository.suggested_draft_slot(task_id),
            ),
            "task": _public_task(updated_task),
        }

    @app.get("/api/v1/publication-revisions/{revision_id}")
    def get_publication_revision(revision_id: str) -> dict[str, Any]:
        revision = repository.get_publication_revision(revision_id)
        return _public_publication_revision(
            revision,
            suggested_draft_slot=repository.suggested_draft_slot(revision["task_id"]),
        )

    @app.get("/api/v1/publication-revisions/{revision_id}/content", response_class=HTMLResponse)
    def publication_revision_content(revision_id: str) -> HTMLResponse:
        revision = repository.get_publication_revision(revision_id)
        assets = repository.list_publication_assets(revision_id)
        document = render_frozen_asset_urls(
            revision["frozen_html"],
            {item["asset_token"]: item["content_url"] for item in assets},
        )
        return HTMLResponse(
            content=document,
            headers={
                "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline';",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/api/v1/publishers/wechat/status")
    def wechat_publisher_status() -> dict[str, Any]:
        return app.state.wechat_publisher.status()

    @app.get("/api/v1/publication-revisions/{revision_id}/clipboard")
    def publication_clipboard_payload(revision_id: str, request: Request) -> dict[str, Any]:
        revision = repository.get_publication_revision(revision_id)
        assets = repository.list_publication_assets(revision_id)
        base_url = str(request.base_url).rstrip("/")
        return build_clipboard_payload(
            revision,
            assets,
            lambda asset_id: f"{base_url}/api/v1/publication-assets/{asset_id}/content",
        )

    @app.get("/api/v1/publication-revisions/{revision_id}/bundle")
    def download_publication_bundle(revision_id: str) -> Response:
        revision = repository.get_publication_revision(revision_id)
        assets = repository.list_publication_assets(revision_id)
        files = build_delivery_files(revision, assets, repository.get_publication_asset)
        archive = build_delivery_zip(files)
        return Response(
            content=archive,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="wechat-visual-director-{revision_id}.zip"',
                "Cache-Control": "private, no-store",
            },
        )

    @app.get("/api/v1/publication-assets/{asset_id}/content")
    def publication_asset_content(asset_id: str) -> FileResponse:
        path, content_type = repository.get_publication_asset(asset_id)
        return FileResponse(path, media_type=content_type, filename=path.name)

    @app.post("/api/v1/publication-revisions/{revision_id}/continue-editing")
    def continue_editing_publication(
        revision_id: str,
        payload: ContinueEditingRequest,
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> dict[str, Any]:
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的操作身份")
        task = repository.continue_editing_publication(
            revision_id=revision_id,
            expected_task_version=payload.expected_task_version,
            operator_id=operator_id,
        )
        return {"task": _public_task(task)}

    @app.post("/api/v1/publication-revisions/{revision_id}/draft-operations")
    def create_mock_draft_operation(
        revision_id: str,
        payload: CreateMockDraftRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> Any:
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的操作身份")
        if payload.simulation_mode != "success" and os.environ.get("VISUAL_DIRECTOR_ENABLE_MOCK_FAILURES") != "1":
            return _error(422, "mock_failure_injection_disabled", "当前环境未开启 Mock 故障注入")
        request_hash = hash_json(
            {"revision_id": revision_id, **payload.model_dump(mode="json"), "operator_id": operator_id}
        )
        operation, task = repository.create_mock_draft_operation(
            revision_id=revision_id,
            draft_slot=payload.draft_slot,
            expected_task_version=payload.expected_task_version,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            simulation_mode=payload.simulation_mode,
            confirmed_by=operator_id,
        )
        return {"operation": operation, "task": _public_task(task)}

    @app.post("/api/v1/publication-revisions/{revision_id}/wechat-draft")
    def create_wechat_draft_operation(
        revision_id: str,
        payload: CreateWechatDraftRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> Any:
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的操作身份")
        publisher_status = app.state.wechat_publisher.status()
        if not publisher_status["ready"]:
            return _error(
                409,
                "wechat_publisher_not_ready",
                "请先在本地设置中配置微信公众号 AppID 和 AppSecret，并检测连接。",
                retryable=True,
                details={"publisher": publisher_status},
            )
        request_hash = hash_json(
            {"revision_id": revision_id, **payload.model_dump(mode="json"), "operator_id": operator_id}
        )
        operation, started_task, replayed = repository.begin_wechat_draft_operation(
            revision_id=revision_id,
            draft_slot=payload.draft_slot,
            expected_task_version=payload.expected_task_version,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            confirmed_by=operator_id,
        )
        if replayed:
            return {"operation": operation, "task": _public_task(started_task), "idempotency_replayed": True}

        revision = repository.get_publication_revision(revision_id)
        try:
            result = app.state.wechat_publisher.publish(
                revision,
                repository.list_publication_assets(revision_id),
                repository.get_publication_asset,
            )
        except (OSError, ValueError) as error:
            result_status = "failed"
            result_media_id = None
            result_error = {
                "code": "delivery_bundle_invalid",
                "message": str(error),
                "retryable": True,
            }
        else:
            result_status = result.status
            result_media_id = result.media_id
            result_error = result.error
        operation, finished_task = repository.finish_wechat_draft_operation(
            operation_id=operation["id"],
            expected_task_version=started_task["version"],
            status=result_status,
            media_id=result_media_id,
            error=result_error,
        )
        return {"operation": operation, "task": _public_task(finished_task), "idempotency_replayed": False}

    @app.get("/api/v1/draft-operations/{operation_id}")
    def get_draft_operation(operation_id: str) -> dict[str, Any]:
        return {"operation": repository.get_draft_operation(operation_id)}

    @app.get("/api/v1/article-tasks/{task_id}/draft-operations")
    def get_task_draft_operations(task_id: str) -> dict[str, Any]:
        repository.get_task(task_id)
        return {"items": repository.list_draft_operations(task_id)}

    @app.post("/api/v1/draft-operations/{operation_id}/wechat-retry")
    def retry_wechat_draft_operation(
        operation_id: str,
        payload: RetryMockDraftRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> Any:
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的操作身份")
        publisher_status = app.state.wechat_publisher.status()
        if not publisher_status["ready"]:
            return _error(
                409,
                "wechat_publisher_not_ready",
                "请先完成微信公众号 AppID、AppSecret 与 IP 白名单配置。",
                retryable=True,
                details={"publisher": publisher_status},
            )
        request_hash = hash_json(
            {"operation_id": operation_id, **payload.model_dump(mode="json"), "operator_id": operator_id}
        )
        operation, started_task, replayed = repository.retry_wechat_draft_operation(
            operation_id=operation_id,
            expected_task_version=payload.expected_task_version,
            expected_operation_version=payload.expected_operation_version,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            operator_id=operator_id,
        )
        if replayed:
            return {"operation": operation, "task": _public_task(started_task), "idempotency_replayed": True}

        revision = repository.get_publication_revision(operation["revision_id"])
        try:
            result = app.state.wechat_publisher.publish(
                revision,
                repository.list_publication_assets(revision["id"]),
                repository.get_publication_asset,
            )
        except (OSError, ValueError) as error:
            result_status = "failed"
            result_media_id = None
            result_error = {
                "code": "delivery_bundle_invalid",
                "message": str(error),
                "retryable": True,
            }
        else:
            result_status = result.status
            result_media_id = result.media_id
            result_error = result.error
        operation, finished_task = repository.finish_wechat_draft_operation(
            operation_id=operation["id"],
            expected_task_version=started_task["version"],
            status=result_status,
            media_id=result_media_id,
            error=result_error,
        )
        return {"operation": operation, "task": _public_task(finished_task), "idempotency_replayed": False}

    @app.post("/api/v1/draft-operations/{operation_id}/retry")
    def retry_mock_draft_operation(
        operation_id: str,
        payload: RetryMockDraftRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> dict[str, Any]:
        request_hash = hash_json(
            {"operation_id": operation_id, **payload.model_dump(mode="json"), "operator_id": operator_id}
        )
        operation, task = repository.retry_mock_draft_operation(
            operation_id=operation_id,
            expected_task_version=payload.expected_task_version,
            expected_operation_version=payload.expected_operation_version,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            operator_id=operator_id,
        )
        return {"operation": operation, "task": _public_task(task)}

    @app.post("/api/v1/draft-operations/{operation_id}/resolve-unknown")
    def resolve_unknown_draft_operation(
        operation_id: str,
        payload: ResolveUnknownDraftRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> Any:
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的核对身份")
        request_hash = hash_json(
            {"operation_id": operation_id, **payload.model_dump(mode="json"), "operator_id": operator_id}
        )
        operation, task = repository.resolve_unknown_draft_operation(
            operation_id=operation_id,
            expected_task_version=payload.expected_task_version,
            expected_operation_version=payload.expected_operation_version,
            outcome=payload.outcome,
            evidence=payload.evidence,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            operator_id=operator_id,
        )
        return {"operation": operation, "task": _public_task(task)}

    @app.post("/api/v1/article-tasks/{task_id}/preflight/findings/{finding_code}/acknowledge")
    def acknowledge_preflight_finding(
        task_id: str,
        finding_code: str,
        payload: AcknowledgePreflightFindingRequest,
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> Any:
        repository.assert_task_editable(task_id)
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的确认身份")
        try:
            task = repository.acknowledge_preflight_finding(
                task_id=task_id,
                finding_code=finding_code,
                block_id=payload.block_id,
                expected_version=payload.expected_task_version,
                resolved_by=operator_id,
            )
        except ValueError as exc:
            return _error(422, "finding_not_acknowledgeable", str(exc))
        return {
            "task": _public_task(task),
            "progress": task["progress"],
            "input_summary": task["input_summary"],
            "last_error": task["last_error"],
        }

    @app.post("/api/v1/article-tasks/{task_id}/preflight/findings/{finding_code}/replace-asset")
    async def replace_preflight_asset(
        task_id: str,
        finding_code: str,
        expected_task_version: int = Form(...),
        image_file: UploadFile = File(...),
        block_id: str | None = Form(None),
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> Any:
        repository.assert_task_editable(task_id)
        if operator_id not in {"operator", "product_owner"}:
            return _error(422, "invalid_operator", "请选择有效的确认身份")
        content = await image_file.read()
        if not content:
            return _error(422, "empty_image", "上传图片为空")
        if len(content) > 10 * 1024 * 1024:
            return _error(413, "image_too_large", "单张图片不能超过 10MB")
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                image_format = (image.format or "").upper()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            return _error(422, "invalid_image", "上传文件不是有效图片")
        if width < 480 or height < 240:
            return _error(
                422,
                "image_too_small",
                "图片尺寸过小，宽度至少 480px、高度至少 240px",
                details={"width": width, "height": height},
            )
        format_map = {
            "PNG": ("image/png", ".png"),
            "JPEG": ("image/jpeg", ".jpg"),
            "WEBP": ("image/webp", ".webp"),
        }
        if image_format not in format_map:
            return _error(415, "unsupported_image_type", "只支持 PNG、JPEG 和 WEBP")
        content_type, extension = format_map[image_format]
        try:
            task = repository.replace_preflight_asset(
                task_id=task_id,
                finding_code=finding_code,
                block_id=block_id,
                expected_version=expected_task_version,
                content=content,
                content_type=content_type,
                extension=extension,
                width=width,
                height=height,
                replaced_by=operator_id,
            )
        except ValueError as exc:
            return _error(422, "finding_not_replaceable", str(exc))
        return {
            "task": _public_task(task),
            "progress": task["progress"],
            "input_summary": task["input_summary"],
            "last_error": task["last_error"],
        }

    @app.post("/api/v1/article-tasks/{task_id}/generate-plans", status_code=202)
    def start_plan_generation(task_id: str, payload: GeneratePlansRequest) -> dict[str, Any]:
        repository.assert_task_editable(task_id)
        current = repository.get_task(task_id)
        preflight_report = current["input_summary"].get("preflight_report", {})
        pending_planning_findings = [
            finding
            for finding in preflight_report.get("findings", [])
            if finding.get("planning_blocking") and not finding.get("resolved_at")
        ]
        if preflight_report.get("status") == "BLOCK" or pending_planning_findings:
            return _error(
                409,
                "preflight_confirmation_required",
                "存在必须在生成方案前解决的 Markdown 结构问题",
                details={"findings": pending_planning_findings},
            )
        analyzing = repository.start_generation(task_id, payload.expected_task_version)
        parsed = parse_markdown(analyzing["normalized_markdown"], analyzing["title"])
        recent_summaries = repository.list_recent_component_summaries(analyzing["account_id"], analyzing["history_window"])
        brand_config = public_brand_profile(app.state.brand_profile)
        request = TextPlannerRequest(
            parsed=parsed,
            article_type=analyzing["article_type"],
            history_window=analyzing["history_window"],
            recent_summaries=recent_summaries,
            brand_config=brand_config,
        )
        planner_call_count = 0
        if payload.planner in {"intelligent", "host_agent"}:
            if payload.planner == "host_agent":
                result = adopt_host_agent_editorial_brief(
                    payload.editorial_brief,
                    request,
                    host_model=payload.host_model,
                )
                prompt_version = HOST_AGENT_PROMPT_VERSION
            else:
                result = generate_editorial_brief(app.state.text_planner_provider, request)
                planner_call_count = 1
                prompt_version = TEXT_PLANNER_PROMPT_VERSION
            try:
                plans = [compile_editorial_brief_recommended(
                    parsed, result.brief, analyzing["history_window"], recent_summaries
                )]
            except EditorialBriefCompileError as exc:
                fallback_brief = build_rule_based_brief(request)
                plans = [compile_editorial_brief_recommended(
                    parsed, fallback_brief, analyzing["history_window"], recent_summaries
                )]
                result = TextPlannerResult(
                    brief=fallback_brief,
                    provider=result.provider,
                    model=result.model,
                    latency_ms=result.latency_ms,
                    repair_count=result.repair_count,
                    fallback_used=True,
                    fallback_reason=f"{type(exc).__name__}: {exc}",
                    estimated_cost_yuan=result.estimated_cost_yuan,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    provider_error_code=result.provider_error_code,
                    normalization_count=result.normalization_count,
                    normalization_adjustments=result.normalization_adjustments,
                    diagnostics=result.diagnostics,
                )
            planner_metadata = {
                "mode": payload.planner,
                "provider": result.provider,
                "model": result.model,
                "prompt_version": prompt_version,
                "planner_call_count": planner_call_count,
                "latency_ms": result.latency_ms,
                "fallback_used": result.fallback_used,
                "fallback_reason": result.fallback_reason,
                "estimated_cost_yuan": result.estimated_cost_yuan,
                "repair_count": result.repair_count,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "normalization_count": result.normalization_count,
                "normalization_adjustments": result.normalization_adjustments or [],
                "provider_error_code": result.provider_error_code,
            }
        else:
            plans = [compile_editorial_brief_recommended(
                parsed,
                build_rule_based_brief(request),
                analyzing["history_window"],
                recent_summaries,
            )]
            planner_metadata = {
                "mode": "rule",
                "provider": "deterministic_baseline",
                "model": "none",
                "prompt_version": None,
                "planner_call_count": 0,
                "fallback_used": False,
            }
        for plan in plans:
            plan["planner_metadata"] = planner_metadata
        documents = [render_preview(parsed, plan, brand_profile=app.state.brand_profile) for plan in plans]
        repository.save_plans(task_id, plans, documents)
        return {
            "task_id": task_id,
            "status": "analyzing",
            "planner": payload.planner,
            "planner_call_count": planner_call_count,
            "planner_metadata": planner_metadata,
            "poll_after_ms": 500,
            "version": analyzing["version"],
        }

    @app.get("/api/v1/article-tasks/{task_id}/editorial-brief/context")
    def get_editorial_brief_context(task_id: str) -> dict[str, Any]:
        task = repository.get_task(task_id)
        parsed = parse_markdown(task["normalized_markdown"], task["title"])
        recent_summaries = repository.list_recent_component_summaries(
            task["account_id"],
            task["history_window"],
        )
        request = TextPlannerRequest(
            parsed=parsed,
            article_type=task["article_type"],
            history_window=task["history_window"],
            recent_summaries=recent_summaries,
            brand_config=public_brand_profile(app.state.brand_profile),
        )
        return {
            "task_id": task_id,
            "expected_task_version": task["version"],
            "context": build_host_agent_planner_context(request),
        }

    @app.post("/api/v1/article-tasks/{task_id}/editorial-brief/generate")
    def create_editorial_brief(task_id: str, payload: GenerateEditorialBriefRequest) -> Any:
        repository.assert_task_editable(task_id)
        task = repository.get_task(task_id)
        if task["version"] != payload.expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        parsed = parse_markdown(task["normalized_markdown"], task["title"])
        recent_summaries = repository.list_recent_component_summaries(task["account_id"], task["history_window"])
        brand_config = public_brand_profile(app.state.brand_profile)
        request = TextPlannerRequest(
            parsed=parsed,
            article_type=task["article_type"],
            history_window=task["history_window"],
            recent_summaries=recent_summaries,
            brand_config=brand_config,
        )
        result = generate_editorial_brief(app.state.text_planner_provider, request)
        try:
            experimental_plan = compile_editorial_brief(
                parsed,
                result.brief,
                task["history_window"],
                recent_summaries,
            )
            experimental_plans = compile_editorial_brief_variants(
                parsed,
                result.brief,
                task["history_window"],
                recent_summaries,
            )
        except EditorialBriefCompileError as exc:
            fallback_brief = build_rule_based_brief(request)
            experimental_plan = compile_editorial_brief(
                parsed,
                fallback_brief,
                task["history_window"],
                recent_summaries,
            )
            experimental_plans = compile_editorial_brief_variants(
                parsed,
                fallback_brief,
                task["history_window"],
                recent_summaries,
            )
            result = TextPlannerResult(
                brief=fallback_brief,
                provider=result.provider,
                model=result.model,
                latency_ms=result.latency_ms,
                repair_count=result.repair_count,
                fallback_used=True,
                fallback_reason=f"{type(exc).__name__}: {exc}",
                estimated_cost_yuan=result.estimated_cost_yuan,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                provider_error_code=result.provider_error_code,
                normalization_count=result.normalization_count,
                normalization_adjustments=result.normalization_adjustments,
                diagnostics=result.diagnostics,
            )
        baseline_plan = generate_plans(
            parsed,
            task["article_type"],
            task["history_window"],
            recent_summaries,
        )[0]
        return {
            "task_id": task_id,
            "brief": result.brief.model_dump(mode="json"),
            "experimental_plan": experimental_plan,
            "experimental_plans": experimental_plans,
            "baseline_plan": baseline_plan,
            "planner_run": {
                "provider": result.provider,
                "model": result.model,
                "prompt_version": TEXT_PLANNER_PROMPT_VERSION,
                "latency_ms": result.latency_ms,
                "repair_count": result.repair_count,
                "fallback_used": result.fallback_used,
                "fallback_reason": result.fallback_reason,
                "estimated_cost_yuan": result.estimated_cost_yuan,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "provider_error_code": result.provider_error_code,
                "normalization_count": result.normalization_count,
                "normalization_adjustments": result.normalization_adjustments,
            },
        }

    def plan_for_workbench(plan: dict[str, Any]) -> dict[str, Any]:
        slots = []
        for slot in plan.get("slots", []):
            definition = COMPONENT_CATALOG[slot["component_type"]]
            slots.append(
                {
                    **slot,
                    "component_label": definition["label"],
                    "variant_options": component_options(slot["component_type"]),
                }
            )
        return {
            key: value
            for key, value in plan.items()
            if key not in {"configuration", "slots"}
        } | {
            "slots": slots,
            "preview_url": f'/api/v1/render-artifacts/{plan["preview_artifact_id"]}/content',
        }

    @app.get("/api/v1/article-tasks/{task_id}/plans")
    def list_plans(task_id: str) -> dict[str, Any]:
        task = repository.get_task(task_id)
        plans = repository.list_plans(task_id)
        summaries = [plan_for_workbench(plan) for plan in plans]
        structure_fingerprints = {
            plan.get("structure_fingerprint")
            for plan in plans
            if plan.get("structure_fingerprint")
        }
        shared_structure = len(structure_fingerprints) == 1
        return {
            "task_id": task_id,
            "selected_plan_id": task["selected_plan_id"],
            "plans": summaries,
            "comparison": {
                "structural_difference_count": structural_difference_count(plans),
                "shared_structure": shared_structure,
                "mode": "single_recommendation",
                "summary": "已推荐一套完整主题；可在不改变正文、图片和组件锚点的前提下即时换主题并回退。",
            },
        }

    @app.get("/api/v1/article-tasks/{task_id}/plans/{plan_id}")
    def get_plan(task_id: str, plan_id: str) -> dict[str, Any]:
        plan = repository.get_plan(task_id, plan_id)
        return {
            "plan": plan,
            "preview_url": f'/api/v1/render-artifacts/{plan["preview_artifact_id"]}/content',
        }

    @app.patch("/api/v1/article-tasks/{task_id}/plans/{plan_id}/slots/{slot_id}")
    def update_plan_slot(task_id: str, plan_id: str, slot_id: str, payload: UpdateSlotRequest) -> Any:
        repository.assert_task_editable(task_id)
        current = repository.get_plan(task_id, plan_id)
        if current["revision"] != payload.expected_plan_revision:
            raise VersionConflictError("方案已被更新，请刷新后重试")
        slot = next((item for item in current.get("slots", []) if item["slot_id"] == slot_id), None)
        if slot is None:
            raise NotFoundError("组件插槽不存在")
        if payload.variant not in allowed_variants(slot["component_type"]):
            return _error(422, "unknown_component_variant", "该变体未获准用于当前组件")
        if payload.variant == slot["variant"]:
            return _error(409, "variant_unchanged", "当前插槽已经使用该变体")

        revised = copy.deepcopy(current)
        revised["revision"] = current["revision"] + 1
        revised["undo_stack"] = [*current.get("undo_stack", []), current["revision"]]
        revised_slot = next(item for item in revised["slots"] if item["slot_id"] == slot_id)
        previous_variant = revised_slot["variant"]
        revised_slot["variant"] = payload.variant
        task = repository.get_task(task_id)
        parsed = parse_markdown(task["normalized_markdown"], task["title"])
        revised = validate_plan_for_article(revised, parsed)
        document = render_preview(parsed, revised, brand_profile=app.state.brand_profile)
        saved = repository.save_plan_revision(
            task_id=task_id,
            plan_id=plan_id,
            plan=revised,
            html_document=document,
            change_reason=payload.reason,
            event_type="component_variant_switched",
            event_payload={
                "slot_id": slot_id,
                "component_type": slot["component_type"],
                "from_variant": previous_variant,
                "to_variant": payload.variant,
            },
        )
        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "slot_id": slot_id,
            "revision": saved["revision"],
            "preview_url": f'/api/v1/render-artifacts/{saved["preview_artifact_id"]}/content',
            "preview_content_hash": saved["preview_content_hash"],
            "planner_called": False,
            "plan": plan_for_workbench(saved),
        }

    @app.patch("/api/v1/article-tasks/{task_id}/plans/{plan_id}/theme")
    def update_plan_theme(task_id: str, plan_id: str, payload: UpdateThemeRequest) -> Any:
        repository.assert_task_editable(task_id)
        current = repository.get_plan(task_id, plan_id)
        if current["revision"] != payload.expected_plan_revision:
            raise VersionConflictError("方案已被更新，请刷新后重试")
        if payload.visual_system == (current.get("visual_system") or current.get("style_mode")):
            return _error(409, "theme_unchanged", "当前文章已经使用该主题")

        previous_visual_system = current.get("visual_system") or current.get("style_mode")
        task = repository.get_task(task_id)
        recent_summaries = repository.list_recent_component_summaries(
            task["account_id"],
            task["history_window"],
        )
        revised = apply_visual_system(
            current,
            payload.visual_system,
            previous_visual_system=current.get("visual_system_metadata", {}).get("previous_visual_system"),
            recommended_visual_system=current.get("visual_system_metadata", {}).get("recommended_visual_system"),
            history_window=task["history_window"],
            recent_summaries=recent_summaries,
        )
        revised["revision"] = current["revision"] + 1
        revised["undo_stack"] = [*current.get("undo_stack", []), current["revision"]]
        parsed = parse_markdown(task["normalized_markdown"], task["title"])
        revised = validate_plan_for_article(revised, parsed)
        document = render_preview(parsed, revised, brand_profile=app.state.brand_profile)
        saved = repository.save_plan_revision(
            task_id=task_id,
            plan_id=plan_id,
            plan=revised,
            html_document=document,
            change_reason=payload.reason,
            event_type="visual_theme_switched",
            event_payload={
                "from_visual_system": previous_visual_system,
                "to_visual_system": payload.visual_system,
                "planner_called": False,
                "images_regenerated": False,
            },
        )
        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "revision": saved["revision"],
            "preview_url": f'/api/v1/render-artifacts/{saved["preview_artifact_id"]}/content',
            "preview_content_hash": saved["preview_content_hash"],
            "planner_called": False,
            "images_regenerated": False,
            "plan": plan_for_workbench(saved),
        }

    @app.get("/api/v1/article-tasks/{task_id}/plans/{plan_id}/revisions")
    def list_plan_revisions(task_id: str, plan_id: str) -> dict[str, Any]:
        return {"items": repository.list_plan_revisions(task_id, plan_id)}

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/undo")
    def undo_plan_change(task_id: str, plan_id: str, payload: UndoPlanRequest) -> Any:
        repository.assert_task_editable(task_id)
        current = repository.get_plan(task_id, plan_id)
        if current["revision"] != payload.expected_plan_revision:
            raise VersionConflictError("方案已被更新，请刷新后重试")
        undo_stack = current.get("undo_stack", [])
        if not undo_stack:
            return _error(409, "nothing_to_undo", "没有可撤回的主题或方案修改")
        target_revision = undo_stack[-1]
        target = repository.get_plan_revision(task_id, plan_id, target_revision)
        restored = copy.deepcopy(target)
        restored["revision"] = current["revision"] + 1
        restored["undo_stack"] = undo_stack[:-1]
        task = repository.get_task(task_id)
        parsed = parse_markdown(task["normalized_markdown"], task["title"])
        restored = validate_plan_for_article(restored, parsed)
        document = render_preview(parsed, restored, brand_profile=app.state.brand_profile)
        saved = repository.save_plan_revision(
            task_id=task_id,
            plan_id=plan_id,
            plan=restored,
            html_document=document,
            change_reason=f"undo_revision_{target_revision}",
            event_type="plan_change_undone",
            event_payload={"undone_to_revision": target_revision},
        )
        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "undone_to_revision": target_revision,
            "revision": saved["revision"],
            "can_undo": bool(saved.get("undo_stack")),
            "preview_url": f'/api/v1/render-artifacts/{saved["preview_artifact_id"]}/content',
            "preview_content_hash": saved["preview_content_hash"],
            "plan": plan_for_workbench(saved),
        }

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/revisions/{revision}/restore")
    def restore_plan_revision(
        task_id: str,
        plan_id: str,
        revision: int,
        payload: RestoreRevisionRequest,
    ) -> dict[str, Any]:
        repository.assert_task_editable(task_id)
        current = repository.get_plan(task_id, plan_id)
        if current["revision"] != payload.expected_plan_revision:
            raise VersionConflictError("方案已被更新，请刷新后重试")
        target = repository.get_plan_revision(task_id, plan_id, revision)
        restored = copy.deepcopy(target)
        restored["revision"] = current["revision"] + 1
        restored["undo_stack"] = [*current.get("undo_stack", []), current["revision"]]
        task = repository.get_task(task_id)
        parsed = parse_markdown(task["normalized_markdown"], task["title"])
        restored = validate_plan_for_article(restored, parsed)
        document = render_preview(parsed, restored, brand_profile=app.state.brand_profile)
        saved = repository.save_plan_revision(
            task_id=task_id,
            plan_id=plan_id,
            plan=restored,
            html_document=document,
            change_reason=f"restore_revision_{revision}",
            event_type="plan_revision_restored",
            event_payload={"restored_from_revision": revision},
        )
        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "restored_from_revision": revision,
            "revision": saved["revision"],
            "preview_url": f'/api/v1/render-artifacts/{saved["preview_artifact_id"]}/content',
            "preview_content_hash": saved["preview_content_hash"],
        }

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/select")
    def select_plan(task_id: str, plan_id: str, payload: SelectPlanRequest) -> dict[str, Any]:
        repository.assert_task_editable(task_id)
        if payload.plan_id != plan_id:
            return _error(422, "plan_id_mismatch", "路径与请求体的 plan_id 不一致")
        task = repository.select_plan(task_id, plan_id, payload.expected_task_version)
        return {
            "task_id": task_id,
            "selected_plan_id": plan_id,
            "status": "plan_selected",
            "selection_change_count": task["selection_change_count"],
            "version": task["version"],
            "updated_at": task["updated_at"],
        }

    def image_slot_for_plan(task_id: str, plan_id: str, image_slot_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        task = repository.get_task(task_id)
        if task["selected_plan_id"] != plan_id:
            raise VersionConflictError("只有当前选中的方案可以生成或修改图片")
        plan = repository.get_plan(task_id, plan_id)
        image_slot = next(
            (item for item in plan.get("image_slots", []) if item["image_slot_id"] == image_slot_id),
            None,
        )
        if image_slot is None:
            raise NotFoundError("图片槽不存在")
        repository.ensure_image_slot_states(task_id, plan_id, plan.get("image_slots", []))
        return plan, image_slot

    def cover_workspace(task_id: str, plan_id: str) -> dict[str, Any]:
        task = repository.get_task(task_id)
        if task["selected_plan_id"] != plan_id:
            raise VersionConflictError("只有当前选中的方案可以规划封面")
        plan = repository.get_plan(task_id, plan_id)
        metadata = plan.get("editorial_brief_metadata") or {}
        candidates = repository.list_cover_candidates(task_id, plan_id)
        replacements = repository.list_preflight_asset_replacements(task_id)
        selected_cover = next((item for item in replacements if item["asset_role"] == "cover"), None)
        selected_sha = selected_cover["output_sha256"] if selected_cover else None
        reuse_sources: list[dict[str, Any]] = []
        for item in replacements:
            if item["asset_role"] != "body_image":
                continue
            reuse_sources.append(
                {
                    "source_type": "controlled_source_image",
                    "source_id": item["id"],
                    "label": "原稿受控图片",
                    "content_url": item["content_url"],
                }
            )
        repository.ensure_image_slot_states(task_id, plan_id, plan.get("image_slots", []))
        for state in repository.list_image_slot_states(task_id, plan_id):
            selected_id = state.get("selected_candidate_id")
            if not selected_id or state.get("decision") not in {"accepted", "replaced"}:
                continue
            candidate = next((item for item in state["candidates"] if item["id"] == selected_id), None)
            if candidate:
                reuse_sources.append(
                    {
                        "source_type": "accepted_body_image",
                        "source_id": candidate["id"],
                        "label": f'已采纳正文配图 · {state["image_slot_id"]}',
                        "content_url": candidate["content_url"],
                    }
                )
        brief = {
            "title": task["title"],
            "article_type": task["article_type"],
            "audience": metadata.get("audience") or [],
            "reader_task": metadata.get("reader_task") or "帮助读者快速理解文章核心价值",
            "narrative": plan.get("summary") or "提炼文章核心判断与行动方向",
            "visual_system": plan.get("visual_system") or plan.get("style_mode"),
            "image_art_direction": plan.get("image_art_direction"),
            "output_size": "1080x864",
            "text_policy": "image_only",
            "recommended_source": "reuse_body_image" if reuse_sources else "ai_generated",
        }
        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "provider_mode": app.state.image_provider.provider,
            "cover_brief": brief,
            "selected_cover": selected_cover,
            "candidates": [
                {**candidate, "selected": candidate["output_sha256"] == selected_sha}
                for candidate in candidates
            ],
            "reuse_sources": reuse_sources,
        }

    @app.get("/api/v1/article-tasks/{task_id}/plans/{plan_id}/cover-candidates")
    def list_cover_candidates(task_id: str, plan_id: str) -> dict[str, Any]:
        return cover_workspace(task_id, plan_id)

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/cover-candidates/generate")
    def generate_cover_candidate(task_id: str, plan_id: str, payload: GenerateCoverRequest) -> Any:
        repository.assert_task_editable(task_id)
        workspace = cover_workspace(task_id, plan_id)
        task = repository.get_task(task_id)
        if task["version"] != payload.expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        candidate_index = len(workspace["candidates"]) + 1
        prompt = build_cover_prompt(
            workspace["cover_brief"],
            prompt_profile=image_prompt_profile(app.state.image_provider),
            candidate_index=candidate_index,
        )
        try:
            generated = app.state.image_provider.generate(
                prompt=prompt,
                aspect_ratio="4:3",
                candidate_index=candidate_index,
            )
            fitted = _fit_cover(generated.content)
        except ImageProviderError as error:
            return _error(
                error.http_status,
                error.code,
                error.public_message,
                retryable=error.retryable,
                details=error.details,
            )
        candidate = repository.add_cover_candidate(
            task_id=task_id,
            plan_id=plan_id,
            source_type="ai_generated",
            source_resource_id=None,
            provider=generated.provider,
            model=generated.model,
            provider_prompt=generated.prompt,
            content=fitted,
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            latency_ms=generated.latency_ms,
            machine_checks={
                **generated.machine_checks,
                "cover_fit": "1080x864_contain_over_soft_backdrop",
                "ratio_valid": True,
            },
        )
        return {"candidate": candidate, "workspace": cover_workspace(task_id, plan_id)}

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/cover-candidates/reuse")
    def reuse_cover_candidate(task_id: str, plan_id: str, payload: ReuseCoverRequest) -> dict[str, Any]:
        repository.assert_task_editable(task_id)
        workspace = cover_workspace(task_id, plan_id)
        task = repository.get_task(task_id)
        if task["version"] != payload.expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        source = next(
            (
                item
                for item in workspace["reuse_sources"]
                if item["source_type"] == payload.source_type and item["source_id"] == payload.source_id
            ),
            None,
        )
        if source is None:
            raise NotFoundError("可复用正文图片不存在")
        if payload.source_type == "accepted_body_image":
            path, _ = repository.get_image_candidate_asset(payload.source_id)
        else:
            path, _ = repository.get_preflight_asset(payload.source_id)
        fitted = _fit_cover(path.read_bytes())
        candidate = repository.add_cover_candidate(
            task_id=task_id,
            plan_id=plan_id,
            source_type=payload.source_type,
            source_resource_id=payload.source_id,
            provider="reuse",
            model="deterministic_cover_fit_v2",
            provider_prompt="reuse accepted article image; deterministic 1080x864 contain fit",
            content=fitted,
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            latency_ms=0,
            machine_checks={
                "file_valid": True,
                "ratio_valid": True,
                "cover_fit": "1080x864_contain_over_soft_backdrop",
            },
        )
        return {"candidate": candidate, "workspace": cover_workspace(task_id, plan_id)}

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/cover-candidates/{candidate_id}/select")
    def select_cover_candidate(
        task_id: str,
        plan_id: str,
        candidate_id: str,
        payload: SelectCoverRequest,
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> dict[str, Any]:
        repository.assert_task_editable(task_id)
        cover_workspace(task_id, plan_id)
        candidate = repository.get_cover_candidate(candidate_id)
        if candidate["task_id"] != task_id or candidate["plan_id"] != plan_id:
            raise NotFoundError("封面候选不属于当前方案")
        task = repository.get_task(task_id)
        report = task["input_summary"].get("preflight_report") or {}
        cover_finding = next(
            (
                item
                for item in report.get("findings", [])
                if item.get("code") in {"missing_cover", "placeholder_cover", "cover_requires_import"}
            ),
            None,
        )
        if cover_finding is None:
            raise NotFoundError("当前任务没有可替换的封面预检项")
        path, _ = repository.get_cover_candidate_asset(candidate_id)
        updated = repository.replace_preflight_asset(
            task_id=task_id,
            finding_code=cover_finding["code"],
            block_id=cover_finding.get("block_id"),
            expected_version=payload.expected_task_version,
            content=path.read_bytes(),
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            replaced_by=operator_id,
        )
        return {"task": _public_task(updated), "workspace": cover_workspace(task_id, plan_id)}

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/cover-candidates/fallback")
    def use_theme_fallback_cover(
        task_id: str,
        plan_id: str,
        payload: GenerateCoverRequest,
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> dict[str, Any]:
        """Skip model/upload while still satisfying WeChat's required cover asset."""
        repository.assert_task_editable(task_id)
        workspace = cover_workspace(task_id, plan_id)
        task = repository.get_task(task_id)
        if task["version"] != payload.expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        report = task["input_summary"].get("preflight_report") or {}
        cover_finding = next(
            (
                item
                for item in report.get("findings", [])
                if item.get("code") in {"missing_cover", "placeholder_cover", "cover_requires_import"}
            ),
            None,
        )
        if cover_finding is None:
            raise NotFoundError("当前任务没有可替换的封面预检项")
        content = build_theme_fallback_cover(workspace["cover_brief"])
        candidate = repository.add_cover_candidate(
            task_id=task_id,
            plan_id=plan_id,
            source_type="theme_fallback",
            source_resource_id=None,
            provider="deterministic_fallback",
            model="theme-cover-v1",
            provider_prompt="local image-only theme fallback cover; no model request",
            content=content,
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            latency_ms=0,
            machine_checks={
                "file_valid": True,
                "ratio_valid": True,
                "qr_risk": "none",
                "text_risk": "none",
                "logo_risk": "none",
                "person_risk": "none",
                "generation_mode": "deterministic_theme_fallback",
            },
        )
        updated = repository.replace_preflight_asset(
            task_id=task_id,
            finding_code=cover_finding["code"],
            block_id=cover_finding.get("block_id"),
            expected_version=payload.expected_task_version,
            content=content,
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            replaced_by=operator_id,
        )
        return {
            "candidate": candidate,
            "task": _public_task(updated),
            "workspace": cover_workspace(task_id, plan_id),
        }

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/cover-candidates/{candidate_id}/crop")
    def crop_cover_candidate(
        task_id: str,
        plan_id: str,
        candidate_id: str,
        payload: CropCoverRequest,
        operator_id: str = Header("operator", alias="X-Operator-Id"),
    ) -> dict[str, Any]:
        repository.assert_task_editable(task_id)
        workspace = cover_workspace(task_id, plan_id)
        task = repository.get_task(task_id)
        if task["version"] != payload.expected_task_version:
            raise VersionConflictError("任务已被更新，请刷新后重试")
        source_candidate = repository.get_cover_candidate(candidate_id)
        if source_candidate["task_id"] != task_id or source_candidate["plan_id"] != plan_id:
            raise NotFoundError("封面候选不属于当前方案")
        report = task["input_summary"].get("preflight_report") or {}
        cover_finding = next(
            (
                item
                for item in report.get("findings", [])
                if item.get("code") in {"missing_cover", "placeholder_cover", "cover_requires_import"}
            ),
            None,
        )
        if cover_finding is None:
            raise NotFoundError("当前任务没有可替换的封面预检项")
        source_path, _ = repository.get_cover_candidate_asset(candidate_id)
        content = _crop_cover(
            source_path.read_bytes(),
            scale=payload.scale,
            offset_x=payload.offset_x,
            offset_y=payload.offset_y,
        )
        candidate = repository.add_cover_candidate(
            task_id=task_id,
            plan_id=plan_id,
            source_type="custom_crop",
            source_resource_id=candidate_id,
            provider="deterministic_crop",
            model="fixed-frame-cover-crop-v1",
            provider_prompt=(
                f"fixed 5:4 crop; scale={payload.scale:.4f}; "
                f"offset_x={payload.offset_x:.4f}; offset_y={payload.offset_y:.4f}"
            ),
            content=content,
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            latency_ms=0,
            machine_checks={
                "file_valid": True,
                "ratio_valid": True,
                "generation_mode": "operator_fixed_frame_crop",
                "source_candidate_id": candidate_id,
                "crop_transform": {
                    "scale": payload.scale,
                    "offset_x": payload.offset_x,
                    "offset_y": payload.offset_y,
                },
            },
        )
        updated = repository.replace_preflight_asset(
            task_id=task_id,
            finding_code=cover_finding["code"],
            block_id=cover_finding.get("block_id"),
            expected_version=payload.expected_task_version,
            content=content,
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            replaced_by=operator_id,
        )
        return {
            "candidate": candidate,
            "task": _public_task(updated),
            "workspace": cover_workspace(task_id, plan_id),
        }

    @app.get("/api/v1/cover-candidates/{candidate_id}/content")
    def cover_candidate_content(candidate_id: str) -> FileResponse:
        path, content_type = repository.get_cover_candidate_asset(candidate_id)
        return FileResponse(path, media_type=content_type, filename=path.name)

    @app.get("/api/v1/article-tasks/{task_id}/plans/{plan_id}/image-slots")
    def list_image_slots(task_id: str, plan_id: str) -> dict[str, Any]:
        task = repository.get_task(task_id)
        if task["selected_plan_id"] != plan_id:
            raise VersionConflictError("只有当前选中的方案可以进入配图确认")
        plan = repository.get_plan(task_id, plan_id)
        repository.ensure_image_slot_states(task_id, plan_id, plan.get("image_slots", []))
        states = {item["image_slot_id"]: item for item in repository.list_image_slot_states(task_id, plan_id)}
        visual_system = plan.get("visual_system") or plan.get("style_mode")
        for state in states.values():
            state["candidates"] = [
                {
                    **candidate,
                    "theme_compatibility": evaluate_theme_compatibility(
                        candidate.get("machine_checks", {}).get("art_direction_snapshot"),
                        visual_system,
                    ),
                }
                for candidate in state.get("candidates", [])
            ]
        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "provider_mode": app.state.image_provider.provider,
            "visual_system": visual_system,
            "items": [
                {**slot, "state": states[slot["image_slot_id"]]}
                for slot in plan.get("image_slots", [])
            ],
        }

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/image-slots/{image_slot_id}/generate")
    def generate_image_candidate(
        task_id: str,
        plan_id: str,
        image_slot_id: str,
        payload: GenerateImageRequest,
    ) -> Any:
        repository.assert_task_editable(task_id)
        plan, image_slot = image_slot_for_plan(task_id, plan_id, image_slot_id)
        visual_system = plan.get("visual_system") or plan.get("style_mode")
        task = repository.get_task(task_id)
        recent_summaries = repository.list_recent_component_summaries(
            task["account_id"],
            task["history_window"],
        )
        generation_slot = apply_theme_to_image_slot(
            image_slot,
            visual_system,
            article_type=str(plan.get("article_type") or "viewpoint_trend"),
            recent_summaries=recent_summaries,
            art_direction=plan.get("image_art_direction"),
        )
        art_direction_snapshot = build_art_direction_snapshot(
            visual_system=visual_system,
            visual_intent=generation_slot["visual_intent"],
            plan_revision=int(plan.get("revision") or 1),
        )
        state = repository.get_image_slot_state(task_id, plan_id, image_slot_id)
        if payload.mode == "start" and state["candidates"]:
            return _error(409, "image_already_generated", "该图片槽已有候选，请使用重生成")
        try:
            locked_copy: list[str] = []
            infographic_title: str | None = None
            infographic_items: list[str] | None = None
            if image_slot["purpose"] == "structured_infographic":
                parsed = parse_markdown(task["normalized_markdown"], task["title"])
                infographic_title, infographic_items = resolve_overlay_copy(
                    parsed,
                    image_slot["fact_bindings"],
                )
                display_title, display_items = resolve_display_copy(
                    generation_slot["visual_intent"],
                    infographic_title,
                    infographic_items,
                )
                locked_copy = [display_title, *display_items]
            if payload.mode == "fallback":
                if image_slot["purpose"] != "structured_infographic":
                    return _error(422, "fallback_not_supported", "确定性保底图只适用于结构信息图")
                fallback_size = (1600, 1200) if image_slot["aspect_ratio"] == "4:3" else (1600, 900)
                fallback_source = BytesIO()
                Image.new("RGB", fallback_size, "#fffaf0").save(fallback_source, format="PNG")
                raw_content = fallback_source.getvalue()
                fallback_content = compose_structured_infographic(
                    raw_content,
                    title=display_title or "关键步骤",
                    items=display_items or [],
                )
                generated = GeneratedImage(
                    provider="deterministic_fallback",
                    model="infographic-fallback-v2",
                    prompt="deterministic locked-copy infographic fallback",
                    content=fallback_content,
                    content_type="image/png",
                    width=fallback_size[0],
                    height=fallback_size[1],
                    latency_ms=1,
                    machine_checks={
                        "file_valid": True,
                        "ratio_valid": True,
                        "qr_risk": "none",
                        "text_risk": "deterministic_locked_copy",
                        "logo_risk": "none",
                        "person_risk": "none",
                        "generation_mode": "deterministic_infographic_fallback",
                        "locked_copy": locked_copy,
                        "text_consistency": {
                            "status": "passed",
                            "engine": "deterministic_source_copy",
                            "expected_count": len(locked_copy),
                            "matched_count": len(locked_copy),
                            "human_confirmation_required": False,
                            "reason": None,
                        },
                    },
                )
            else:
                candidate_index = len(state["candidates"]) + 1
                prompt = build_provider_prompt(
                    generation_slot,
                    str(plan.get("article_type", "viewpoint_trend")),
                    infographic_title=infographic_title,
                    infographic_items=infographic_items,
                    prompt_profile=image_prompt_profile(app.state.image_provider),
                    candidate_index=candidate_index,
                )
                generated = app.state.image_provider.generate(
                    prompt=prompt,
                    aspect_ratio=image_slot["aspect_ratio"],
                    candidate_index=candidate_index,
                )
                raw_content = generated.content
            if image_slot["purpose"] == "structured_infographic" and payload.mode != "fallback":
                text_consistency = verify_locked_copy(generated.content, locked_copy)
                generated = type(generated)(
                    provider=generated.provider,
                    model=generated.model,
                    prompt=generated.prompt,
                    content=generated.content,
                    content_type=generated.content_type,
                    width=generated.width,
                    height=generated.height,
                    latency_ms=generated.latency_ms,
                    machine_checks={
                        **generated.machine_checks,
                        "generation_mode": "model_end_to_end_infographic",
                        "art_direction_snapshot": art_direction_snapshot,
                        "locked_copy": locked_copy,
                        "text_consistency": text_consistency.as_dict(),
                    },
                )
            elif image_slot["purpose"] != "structured_infographic":
                generated = type(generated)(
                    provider=generated.provider,
                    model=generated.model,
                    prompt=generated.prompt,
                    content=generated.content,
                    content_type=generated.content_type,
                    width=generated.width,
                    height=generated.height,
                    latency_ms=generated.latency_ms,
                    machine_checks={
                        **generated.machine_checks,
                        "generation_mode": "semantic_illustration",
                        "art_direction_snapshot": art_direction_snapshot,
                        "text_consistency": {
                            "status": "not_applicable",
                            "human_confirmation_required": False,
                        },
                    },
                )
        except InfographicOverlayError as error:
            failed_state = repository.mark_image_slot_failed(
                task_id=task_id,
                plan_id=plan_id,
                image_slot_id=image_slot_id,
                expected_image_revision=payload.expected_image_revision,
                error={
                    "code": "infographic_copy_resolution_failed",
                    "message": str(error),
                    "retryable": False,
                },
            )
            return _error(
                422,
                "infographic_copy_resolution_failed",
                str(error),
                details={
                    "image_slot_id": image_slot_id,
                    "image_revision": failed_state["image_revision"],
                },
            )
        except ImageProviderError as error:
            failed_state = repository.mark_image_slot_failed(
                task_id=task_id,
                plan_id=plan_id,
                image_slot_id=image_slot_id,
                expected_image_revision=payload.expected_image_revision,
                error={
                    "code": error.code,
                    "message": error.public_message,
                    "retryable": error.retryable,
                },
            )
            return _error(
                error.http_status,
                error.code,
                error.public_message,
                retryable=error.retryable,
                details={
                    **error.details,
                    "image_slot_id": image_slot_id,
                    "image_revision": failed_state["image_revision"],
                },
            )
        extension_by_type = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
        }
        updated = repository.add_image_candidate(
            task_id=task_id,
            plan_id=plan_id,
            image_slot_id=image_slot_id,
            expected_image_revision=payload.expected_image_revision,
            provider=generated.provider,
            model=generated.model,
            provider_prompt=generated.prompt,
            content=generated.content,
            content_type=generated.content_type,
            extension=extension_by_type[generated.content_type],
            width=generated.width,
            height=generated.height,
            latency_ms=generated.latency_ms,
            machine_checks={
                **generated.machine_checks,
                "art_direction_snapshot": generated.machine_checks.get(
                    "art_direction_snapshot",
                    art_direction_snapshot,
                ),
            },
            raw_content=raw_content,
        )
        return {"image_slot": updated, "provider_mode": app.state.image_provider.provider}

    @app.post(
        "/api/v1/article-tasks/{task_id}/plans/{plan_id}/image-slots/{image_slot_id}/candidates/{candidate_id}/accept"
    )
    def accept_image_candidate(
        task_id: str,
        plan_id: str,
        image_slot_id: str,
        candidate_id: str,
        payload: ImageDecisionRequest,
    ) -> dict[str, Any]:
        repository.assert_task_editable(task_id)
        _, image_slot = image_slot_for_plan(task_id, plan_id, image_slot_id)
        candidate = repository.get_image_candidate(candidate_id)
        if (
            candidate["task_id"] != task_id
            or candidate["plan_id"] != plan_id
            or candidate["image_slot_id"] != image_slot_id
        ):
            return _error(404, "image_candidate_not_found", "图片候选不存在")
        if image_slot["purpose"] == "structured_infographic":
            text_check = candidate["machine_checks"].get("text_consistency", {})
            if text_check.get("status") != "passed" and not payload.text_verified:
                return _error(
                    422,
                    "image_text_verification_required",
                    "自动 OCR 未能证明图片文字与原文完全一致，请逐项人工核对后再确认。",
                )
        updated = repository.decide_image_slot(
            task_id=task_id,
            plan_id=plan_id,
            image_slot_id=image_slot_id,
            expected_image_revision=payload.expected_image_revision,
            decision="accepted",
            candidate_id=candidate_id,
        )
        return {"image_slot": updated}

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/image-slots/{image_slot_id}/skip")
    def skip_image_slot(
        task_id: str,
        plan_id: str,
        image_slot_id: str,
        payload: ImageDecisionRequest,
    ) -> dict[str, Any]:
        repository.assert_task_editable(task_id)
        image_slot_for_plan(task_id, plan_id, image_slot_id)
        updated = repository.decide_image_slot(
            task_id=task_id,
            plan_id=plan_id,
            image_slot_id=image_slot_id,
            expected_image_revision=payload.expected_image_revision,
            decision="skipped",
        )
        return {"image_slot": updated}

    @app.post("/api/v1/article-tasks/{task_id}/plans/{plan_id}/image-slots/{image_slot_id}/replace")
    async def replace_image_slot(
        task_id: str,
        plan_id: str,
        image_slot_id: str,
        expected_image_revision: int = Form(..., ge=1),
        image_file: UploadFile = File(...),
    ) -> Any:
        repository.assert_task_editable(task_id)
        _, image_slot = image_slot_for_plan(task_id, plan_id, image_slot_id)
        content = await image_file.read()
        if len(content) > 8 * 1024 * 1024:
            return _error(413, "image_too_large", "替换图片不能超过 8MB")
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                image_format = (image.format or "").upper()
        except (UnidentifiedImageError, OSError):
            return _error(422, "invalid_image", "上传文件不是有效图片")
        format_map = {
            "PNG": ("image/png", ".png"),
            "JPEG": ("image/jpeg", ".jpg"),
            "WEBP": ("image/webp", ".webp"),
        }
        if image_format not in format_map:
            return _error(415, "unsupported_image_type", "只支持 PNG、JPEG 和 WEBP")
        content_type, extension = format_map[image_format]
        expected_ratio = 4 / 3 if image_slot["aspect_ratio"] == "4:3" else 16 / 9
        actual_ratio = width / height
        ratio_valid = abs(actual_ratio - expected_ratio) / expected_ratio <= 0.08
        updated = repository.add_image_candidate(
            task_id=task_id,
            plan_id=plan_id,
            image_slot_id=image_slot_id,
            expected_image_revision=expected_image_revision,
            provider="manual_upload",
            model="operator_asset",
            provider_prompt="manual upload",
            content=content,
            content_type=content_type,
            extension=extension,
            width=width,
            height=height,
            latency_ms=0,
            machine_checks={
                "file_valid": True,
                "ratio_valid": ratio_valid,
                "qr_risk": "unknown",
                "text_risk": "unknown",
                "logo_risk": "unknown",
                "person_risk": "unknown",
            },
            auto_select=True,
        )
        return {"image_slot": updated}

    @app.get("/api/v1/image-candidates/{candidate_id}/content")
    def image_candidate_content(candidate_id: str) -> FileResponse:
        path, content_type = repository.get_image_candidate_asset(candidate_id)
        return FileResponse(path, media_type=content_type, filename=path.name)

    @app.get("/api/v1/image-candidates/{candidate_id}/raw-content")
    def raw_image_candidate_content(candidate_id: str) -> FileResponse:
        path, content_type = repository.get_raw_image_candidate_asset(candidate_id)
        return FileResponse(path, media_type=content_type, filename=path.name)

    @app.get("/api/v1/render-artifacts/{artifact_id}/content", response_class=HTMLResponse)
    def preview_content(artifact_id: str) -> HTMLResponse:
        document = materialize_preview_document(repository, artifact_id)
        return HTMLResponse(
            content=document,
            headers={
                "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline';",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/api/v1/preflight-assets/{asset_id}/content")
    def preflight_asset_content(asset_id: str) -> FileResponse:
        path, content_type = repository.get_preflight_asset(asset_id)
        return FileResponse(path, media_type=content_type, filename=path.name)

    @app.get("/api/v1/brand-assets/current/content")
    def current_brand_asset() -> Any:
        asset = app.state.brand_asset_path
        if asset is None or not asset.is_file():
            return _error(404, "brand_asset_not_configured", "The current brand has no fixed footer asset")
        return FileResponse(asset, filename=asset.name)

    @app.get("/api/v1/theme-assets/{asset_name}")
    def current_theme_asset(asset_name: str) -> Any:
        asset = theme_asset_path(root, asset_name)
        if asset is None:
            return _error(404, "theme_asset_not_found", "Theme decoration asset not found")
        return FileResponse(asset, media_type="image/png", filename=asset.name)

    web_dist = Path(
        os.environ.get("VISUAL_DIRECTOR_WEB_DIST", str(root / "apps" / "web" / "dist"))
    ).expanduser().resolve()
    app.state.web_dist = web_dist

    @app.get("/{full_path:path}", include_in_schema=False)
    def workbench_static(full_path: str) -> Any:
        if full_path == "api" or full_path.startswith("api/"):
            return _error(404, "not_found", "API endpoint not found")
        candidate = (web_dist / full_path).resolve()
        if candidate.is_relative_to(web_dist) and candidate.is_file():
            return FileResponse(candidate)
        index_file = web_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file, media_type="text/html")
        return _error(
            503,
            "workbench_build_missing",
            "本地工作台静态文件尚未构建",
            details={"expected": str(index_file)},
        )

    return app


app = create_app()
