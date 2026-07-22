from __future__ import annotations

import os
import copy
import html
import hashlib
import json
import re
import uuid
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from PIL import Image, ImageOps, UnidentifiedImageError

from .component_catalog import COMPONENT_CATALOG, allowed_variants, component_options
from .brand import brand_asset_path, load_brand_profile, public_brand_profile
from .blind_review import BLIND_REVIEW_DIMENSIONS, BlindReviewDataset, load_blind_review_dataset
from .parser import classify_article, parse_markdown
from .preflight import PREFLIGHT_RULESET_VERSION, PREFLIGHT_SCHEMA_VERSION, run_preflight
from .image_provider import (
    IMAGE_PROMPT_VERSION,
    ImageProvider,
    ImageProviderError,
    build_cover_prompt,
    build_provider_prompt,
    create_image_provider_from_env,
)
from .planner import generate_plans, structural_difference_count
from .brief_compiler import (
    EditorialBriefCompileError,
    compile_editorial_brief,
    compile_editorial_brief_variants,
)
from .editorial_brief import EDITORIAL_BRIEF_NORMALIZER_VERSION, EDITORIAL_BRIEF_SCHEMA_VERSION
from .text_planner import (
    TEXT_PLANNER_PROMPT_VERSION,
    TextPlannerProvider,
    TextPlannerRequest,
    TextPlannerResult,
    build_rule_based_brief,
    create_text_planner_provider_from_env,
    generate_editorial_brief,
)
from .infographic_overlay import (
    InfographicOverlayError,
    compose_structured_infographic,
    resolve_overlay_copy,
)
from .plan_schema import validate_plan_for_article
from .renderer import render_preview
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
from .repository import NotFoundError, PublicationLockedError, Repository, VersionConflictError


class GeneratePlansRequest(BaseModel):
    mode: str = Field(pattern="^(start|retry)$")
    expected_task_version: int = Field(ge=1)
    planner: str = Field(default="rule", pattern="^(rule|intelligent)$")


class SelectPlanRequest(BaseModel):
    plan_id: str
    expected_task_version: int = Field(ge=1)


class UpdateSlotRequest(BaseModel):
    variant: str
    expected_plan_revision: int = Field(ge=1)
    reason: str = Field(default="operator_manual_switch", pattern="^(operator_manual_switch|product_review|compatibility_fallback)$")


class RestoreRevisionRequest(BaseModel):
    expected_plan_revision: int = Field(ge=1)


class UndoPlanRequest(BaseModel):
    expected_plan_revision: int = Field(ge=1)


class GenerateImageRequest(BaseModel):
    mode: str = Field(pattern="^(start|regenerate)$")
    expected_image_revision: int = Field(ge=1)


class GenerateCoverRequest(BaseModel):
    expected_task_version: int = Field(ge=1)


class ReuseCoverRequest(BaseModel):
    expected_task_version: int = Field(ge=1)
    source_type: str = Field(pattern="^(accepted_body_image|controlled_source_image)$")
    source_id: str


class SelectCoverRequest(BaseModel):
    expected_task_version: int = Field(ge=1)


class ImageDecisionRequest(BaseModel):
    expected_image_revision: int = Field(ge=1)


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
    } | {"publication_mode": "mock"}


def _crop_cover(content: bytes) -> bytes:
    try:
        with Image.open(BytesIO(content)) as source:
            converted = source.convert("RGB")
            fitted = ImageOps.fit(
                converted,
                (1080, 864),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            output = BytesIO()
            fitted.save(output, format="PNG", optimize=True)
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
        "is_mock": True,
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


def create_app(
    database_path: str | None = None,
    image_provider: ImageProvider | None = None,
    text_planner_provider: TextPlannerProvider | None = None,
    blind_review_manifest_path: str | None = None,
) -> FastAPI:
    root = Path(__file__).resolve().parents[4]
    db_path = database_path or os.environ.get("VISUAL_DIRECTOR_DB", str(root / "apps" / "api" / "data" / "visual-director.db"))
    repository = Repository(db_path)
    app = FastAPI(title="公众号视觉主编 API", version="0.1.0")
    app.state.repository = repository
    app.state.image_provider = image_provider or create_image_provider_from_env()
    app.state.text_planner_provider = text_planner_provider or create_text_planner_provider_from_env()
    app.state.root = root
    app.state.brand_profile = load_brand_profile(root)
    app.state.brand_asset_path = brand_asset_path(root, app.state.brand_profile)
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
        if not report.get("draft_creation_allowed"):
            checks["preflight_resolved"] = "blocking"
            block(
                "preflight_not_ready",
                "仍有未处理的预检发布阻断项",
                "preflight_report",
                task_id,
                "resolve_preflight",
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
                "publication_mode": "mock",
                "suggested_draft_slot": repository.suggested_draft_slot(task_id),
                "blockers": blockers,
                "checks": checks,
            },
            prepared if not blockers else None,
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "planner": "deterministic_baseline",
            "image_provider": app.state.image_provider.provider,
            "image_provider_configured": app.state.image_provider.configured,
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
            "publication_mode": "mock",
        }

    @app.get("/api/v1/article-tasks")
    def list_tasks() -> dict[str, Any]:
        return {"items": [_public_task(task) for task in repository.list_tasks()], "next_cursor": None}

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

    @app.get("/api/v1/draft-operations/{operation_id}")
    def get_draft_operation(operation_id: str) -> dict[str, Any]:
        return {"operation": repository.get_draft_operation(operation_id)}

    @app.get("/api/v1/article-tasks/{task_id}/draft-operations")
    def get_task_draft_operations(task_id: str) -> dict[str, Any]:
        repository.get_task(task_id)
        return {"items": repository.list_draft_operations(task_id)}

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
    def resolve_unknown_mock_draft_operation(
        operation_id: str,
        payload: ResolveUnknownDraftRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
        operator_id: str = Header("product_owner", alias="X-Operator-Id"),
    ) -> Any:
        if operator_id != "product_owner":
            return _error(403, "product_owner_required", "只有产品负责人可以处置结果未知状态")
        request_hash = hash_json(
            {"operation_id": operation_id, **payload.model_dump(mode="json"), "operator_id": operator_id}
        )
        operation, task = repository.resolve_unknown_mock_draft_operation(
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
        planner_call_count = 0
        if payload.planner == "intelligent":
            brand_config = public_brand_profile(app.state.brand_profile)
            request = TextPlannerRequest(
                parsed=parsed,
                article_type=analyzing["article_type"],
                history_window=analyzing["history_window"],
                recent_summaries=recent_summaries,
                brand_config=brand_config,
            )
            result = generate_editorial_brief(app.state.text_planner_provider, request)
            planner_call_count = 1
            try:
                plans = compile_editorial_brief_variants(
                    parsed,
                    result.brief,
                    analyzing["history_window"],
                    recent_summaries,
                )
            except EditorialBriefCompileError as exc:
                fallback_brief = build_rule_based_brief(request)
                plans = compile_editorial_brief_variants(
                    parsed,
                    fallback_brief,
                    analyzing["history_window"],
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
            planner_metadata = {
                "mode": "intelligent",
                "provider": result.provider,
                "model": result.model,
                "prompt_version": TEXT_PLANNER_PROMPT_VERSION,
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
            plans = generate_plans(
                parsed,
                analyzing["article_type"],
                analyzing["history_window"],
                recent_summaries,
            )
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
        if payload.planner == "intelligent":
            fingerprints = {plan.get("structure_fingerprint") for plan in plans}
            if None in fingerprints or len(fingerprints) != 1:
                raise RuntimeError("双视觉系统没有共享同一份智能结构")
            if len(set(documents)) != len(documents):
                raise RuntimeError("双视觉系统渲染结果没有形成可见差异")
        elif structural_difference_count(plans) < 2:
            raise RuntimeError("候选方案结构差异不足")
        repository.save_plans(task_id, plans, documents)
        return {
            "task_id": task_id,
            "status": "analyzing",
            "planner": payload.planner,
            "planner_call_count": planner_call_count,
            "poll_after_ms": 500,
            "version": analyzing["version"],
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

    @app.get("/api/v1/article-tasks/{task_id}/plans")
    def list_plans(task_id: str) -> dict[str, Any]:
        task = repository.get_task(task_id)
        plans = repository.list_plans(task_id)
        summaries = []
        for plan in plans:
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
            summaries.append(
                {
                    key: value
                    for key, value in plan.items()
                    if key not in {"configuration", "slots"}
                }
                | {
                    "slots": slots,
                    "preview_url": f'/api/v1/render-artifacts/{plan["preview_artifact_id"]}/content',
                }
            )
        structure_fingerprints = {
            plan.get("structure_fingerprint")
            for plan in plans
            if plan.get("structure_fingerprint")
        }
        shared_structure = len(plans) == 2 and len(structure_fingerprints) == 1
        return {
            "task_id": task_id,
            "selected_plan_id": task["selected_plan_id"],
            "plans": summaries,
            "comparison": {
                "structural_difference_count": structural_difference_count(plans),
                "shared_structure": shared_structure,
                "summary": (
                    "共享同一份智能结构，只比较轻盈阅读与编辑对比两套视觉系统。"
                    if shared_structure
                    else "两套方案在组件组合、出现位置、密度与基础阅读节奏上存在结构差异。"
                ),
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
            return _error(409, "nothing_to_undo", "没有可撤回的局部换型")
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
        prompt = build_cover_prompt(workspace["cover_brief"])
        try:
            generated = app.state.image_provider.generate(
                prompt=prompt,
                aspect_ratio="4:3",
                candidate_index=len(workspace["candidates"]) + 1,
            )
            cropped = _crop_cover(generated.content)
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
            content=cropped,
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            latency_ms=generated.latency_ms,
            machine_checks={
                **generated.machine_checks,
                "cover_crop": "1080x864_center_safe",
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
        cropped = _crop_cover(path.read_bytes())
        candidate = repository.add_cover_candidate(
            task_id=task_id,
            plan_id=plan_id,
            source_type=payload.source_type,
            source_resource_id=payload.source_id,
            provider="reuse",
            model="deterministic_center_crop_v1",
            provider_prompt="reuse accepted article image; deterministic 1080x864 center crop",
            content=cropped,
            content_type="image/png",
            extension=".png",
            width=1080,
            height=864,
            latency_ms=0,
            machine_checks={"file_valid": True, "ratio_valid": True, "cover_crop": "1080x864_center_safe"},
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
        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "provider_mode": app.state.image_provider.provider,
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
        state = repository.get_image_slot_state(task_id, plan_id, image_slot_id)
        if payload.mode == "start" and state["candidates"]:
            return _error(409, "image_already_generated", "该图片槽已有候选，请使用重生成")
        prompt = build_provider_prompt(image_slot, str(plan.get("article_type", "viewpoint_trend")))
        try:
            generated = app.state.image_provider.generate(
                prompt=prompt,
                aspect_ratio=image_slot["aspect_ratio"],
                candidate_index=len(state["candidates"]) + 1,
            )
            if image_slot["purpose"] == "structured_infographic":
                task = repository.get_task(task_id)
                parsed = parse_markdown(task["normalized_markdown"], task["title"])
                overlay_title, overlay_items = resolve_overlay_copy(parsed, image_slot["fact_bindings"])
                overlaid = compose_structured_infographic(
                    generated.content,
                    title=overlay_title,
                    items=overlay_items,
                )
                generated = replace(
                    generated,
                    content=overlaid,
                    content_type="image/png",
                    machine_checks={
                        **generated.machine_checks,
                        "deterministic_overlay": "applied",
                        "overlay_item_count": len(overlay_items),
                    },
                )
        except InfographicOverlayError as error:
            failed_state = repository.mark_image_slot_failed(
                task_id=task_id,
                plan_id=plan_id,
                image_slot_id=image_slot_id,
                expected_image_revision=payload.expected_image_revision,
                error={
                    "code": "infographic_overlay_failed",
                    "message": str(error),
                    "retryable": False,
                },
            )
            return _error(
                422,
                "infographic_overlay_failed",
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
            machine_checks=generated.machine_checks,
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
        image_slot_for_plan(task_id, plan_id, image_slot_id)
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

    return app


app = create_app()
