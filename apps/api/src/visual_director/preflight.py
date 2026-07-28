from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .parser import MarkdownInputError, ParsedArticle, parse_markdown
from .planner import component_opportunity_diagnostics


PreflightStatus = Literal["PASS", "REVIEW", "BLOCK"]
ResolutionPolicy = Literal["ACKNOWLEDGE", "EDIT_SOURCE", "REPLACE_ASSET", "HARD_BLOCK"]

PREFLIGHT_SCHEMA_VERSION = "preflight_report.v0.1"
PREFLIGHT_RULESET_VERSION = "preflight_rules.v0.2-semantic-structure"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IMAGE_LINE_RE = re.compile(r"^!\[([^\]]*)]\(([^)]+)\)\s*$")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)\b(?:WECHAT_APP_SECRET|APP_SECRET|APPSECRET|API_KEY|ACCESS_TOKEN|SECRET_KEY)\b"
    r"\s*[:=]\s*['\"]?([A-Za-z0-9_./+\-=]{12,})"
)


@dataclass(frozen=True)
class AutoRepair:
    code: str
    message: str
    before: str | None = None
    after: str | None = None


@dataclass(frozen=True)
class PreflightFinding:
    code: str
    message: str
    resolution_policy: ResolutionPolicy
    planning_blocking: bool
    draft_blocking: bool
    block_id: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class PreflightReport:
    schema_version: str
    ruleset_version: str
    status: PreflightStatus
    source_hash: str
    normalized_hash: str
    canonical_title: str | None
    title_source: str | None
    auto_repairs: tuple[AutoRepair, ...]
    findings: tuple[PreflightFinding, ...]
    quality_dimensions: dict[str, str]
    planning_allowed: bool
    draft_creation_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreflightResult:
    original_markdown: str
    normalized_markdown: str
    parsed: ParsedArticle | None
    report: PreflightReport


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_markdown(markdown: str) -> tuple[str, tuple[AutoRepair, ...]]:
    """Apply only deterministic, semantics-preserving normalizations."""

    repairs: list[AutoRepair] = []
    normalized = markdown
    if normalized.startswith("\ufeff"):
        normalized = normalized[1:]
        repairs.append(AutoRepair("utf8_bom_removed", "已移除 UTF-8 BOM"))

    if "\r" in normalized:
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        repairs.append(AutoRepair("line_endings_normalized", "已将换行统一为 LF"))

    cleaned_lines: list[str] = []
    trimmed_count = 0
    for line in normalized.split("\n"):
        # Markdown 双空格、反斜杠和 <br> 都可能表达显式换行，不得清理。
        if line.endswith("  ") or line.endswith("\\") or re.search(r"<br\s*/?>\s*$", line, re.IGNORECASE):
            cleaned_lines.append(line)
            continue
        cleaned = line.rstrip(" \t")
        if cleaned != line:
            trimmed_count += 1
        cleaned_lines.append(cleaned)
    normalized = "\n".join(cleaned_lines)
    if trimmed_count:
        repairs.append(
            AutoRepair(
                "ordinary_trailing_space_removed",
                f"已清理 {trimmed_count} 行不承载 Markdown 语义的行尾空格",
            )
        )
    return normalized, tuple(repairs)


def _title_candidates(
    normalized_markdown: str,
    parsed: ParsedArticle | None,
    title_override: str | None,
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    override = (title_override or "").strip()
    if override:
        candidates.append(("override", override))
    if parsed:
        frontmatter_title = str(parsed.frontmatter.get("title", "")).strip()
        if frontmatter_title:
            candidates.append(("frontmatter", frontmatter_title))
    body = parsed.body if parsed else normalized_markdown
    h1 = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    if h1:
        candidates.append(("first_h1", h1.group(1).strip()))
    return candidates


def _heading_findings(parsed: ParsedArticle) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    headings = [block for block in parsed.blocks if block.type == "heading"]
    h1_blocks = [block for block in headings if block.level == 1]
    distinct_h1 = {str(block.content).strip() for block in h1_blocks}
    if len(distinct_h1) > 1:
        findings.append(
            PreflightFinding(
                code="multiple_distinct_h1",
                message="检测到多个内容不同的一级标题，请修改原稿后重新预检",
                resolution_policy="EDIT_SOURCE",
                planning_blocking=True,
                draft_blocking=True,
                details={"titles": sorted(distinct_h1)},
            )
        )

    previous_level: int | None = None
    for block in headings:
        level = block.level or 1
        if previous_level is not None and level > previous_level + 1:
            findings.append(
                PreflightFinding(
                    code="heading_level_jump",
                    message=f"标题层级从 H{previous_level} 跳到 H{level}，系统不会自动改级",
                    resolution_policy="EDIT_SOURCE",
                    planning_blocking=True,
                    draft_blocking=True,
                    block_id=block.id,
                    details={"from_level": previous_level, "to_level": level},
                )
            )
        previous_level = level
    return findings


def _asset_findings(parsed: ParsedArticle) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    cover = str(parsed.frontmatter.get("cover", "")).strip()
    if not cover:
        findings.append(
            PreflightFinding(
                code="missing_cover",
                message="未提供封面图；可以先生成视觉方案，但创建草稿前必须补齐",
                resolution_policy="REPLACE_ASSET",
                planning_blocking=False,
                draft_blocking=True,
            )
        )
    elif any(marker in cover.lower() for marker in ("picsum.photos", "placeholder", "placehold.co", "dummyimage.com")):
        findings.append(
            PreflightFinding(
                code="placeholder_cover",
                message="检测到占位封面；允许先看方案，但创建草稿前必须替换",
                resolution_policy="REPLACE_ASSET",
                planning_blocking=False,
                draft_blocking=True,
                details={"source": cover},
            )
        )
    else:
        findings.append(
            PreflightFinding(
                code="cover_requires_import",
                message="封面引用尚未进入受控资产库；允许先看方案，但冻结前必须上传真实文件",
                resolution_policy="REPLACE_ASSET",
                planning_blocking=False,
                draft_blocking=True,
                details={"source": cover},
            )
        )

    for block in parsed.blocks:
        if block.type != "image_reference" or not isinstance(block.content, dict):
            continue
        source = str(block.content.get("source", "")).strip()
        placeholder = bool(block.content.get("placeholder")) or any(
            marker in source.lower()
            for marker in ("placeholder", "placehold.co", "dummyimage.com", "example.com/image")
        )
        if placeholder:
            findings.append(
                PreflightFinding(
                    code="placeholder_image",
                    message="检测到占位图片；允许先看方案，但创建草稿前必须替换",
                    resolution_policy="REPLACE_ASSET",
                    planning_blocking=False,
                    draft_blocking=True,
                    block_id=block.id,
                    details={"source": source},
                )
            )
        elif source.lower().startswith(("javascript:", "data:text/html")):
            findings.append(
                PreflightFinding(
                    code="unsafe_image_source",
                    message="图片引用使用了不安全协议",
                    resolution_policy="HARD_BLOCK",
                    planning_blocking=True,
                    draft_blocking=True,
                    block_id=block.id,
                )
            )
        else:
            findings.append(
                PreflightFinding(
                    code="source_image_requires_import",
                    message="原稿图片引用尚未进入受控资产库；冻结前必须上传真实文件",
                    resolution_policy="REPLACE_ASSET",
                    planning_blocking=False,
                    draft_blocking=True,
                    block_id=block.id,
                    details={"source": source},
                )
            )
    return findings


def _semantic_structure_finding(
    parsed: ParsedArticle,
    requested_article_type: str | None,
) -> PreflightFinding | None:
    schema_version = str(parsed.frontmatter.get("schema_version", "")).strip()
    article_type = (
        (requested_article_type or "").strip()
        or str(parsed.frontmatter.get("article_type", "")).strip()
    )
    if schema_version != "wechat_article.v1" or article_type not in {
        "data_policy",
        "viewpoint_trend",
        "tutorial_steps",
    }:
        return None

    paragraphs = [block for block in parsed.blocks if block.type == "paragraph"]
    body_characters = sum(len(re.sub(r"\s+", "", str(block.content))) for block in paragraphs)
    h3_count = sum(
        1
        for block in parsed.blocks
        if block.type == "heading" and (block.level or 0) >= 3
    )
    list_count = sum(
        1
        for block in parsed.blocks
        if block.type in {"ordered_list", "unordered_list"}
    )
    table_count = sum(1 for block in parsed.blocks if block.type == "table")
    semantic_structure_count = h3_count + list_count + table_count
    opportunities = component_opportunity_diagnostics(parsed)
    eligible_component_types = opportunities["eligible_component_types"]
    grounded_role_count = len(eligible_component_types) + (1 if table_count else 0)

    if len(paragraphs) < 8 or body_characters < 900 or grounded_role_count >= 2:
        return None
    return PreflightFinding(
        code="source_structure_too_flat",
        message=(
            "长篇分析稿主要由连续段落组成，已有的并列因素、政策影响、顺序或真实二维数据"
            "需要先整理为 H3、列表或表格，再进入组件规划"
        ),
        resolution_policy="EDIT_SOURCE",
        planning_blocking=True,
        draft_blocking=False,
        details={
            "article_type": article_type,
            "paragraph_count": len(paragraphs),
            "body_characters": body_characters,
            "h3_count": h3_count,
            "list_count": list_count,
            "table_count": table_count,
            "semantic_structure_count": semantic_structure_count,
            "eligible_component_types": eligible_component_types,
            "grounded_role_count": grounded_role_count,
            "repair_boundary": (
                "只重排原稿已经存在的关系；不得补造概念、比较、结论、数字、来源或行动建议"
            ),
        },
    )


def _quality_dimensions(findings: list[PreflightFinding]) -> dict[str, str]:
    dimensions = {
        "transport_security": "pass",
        "title_hierarchy": "pass",
        "content_blocks": "pass",
        "semantic_risk": "pass",
        "publication_readiness": "pass",
    }
    mapping = {
        "sensitive_credentials": "transport_security",
        "invalid_markdown": "transport_security",
        "missing_title": "title_hierarchy",
        "title_source_conflict": "title_hierarchy",
        "multiple_distinct_h1": "title_hierarchy",
        "heading_level_jump": "title_hierarchy",
        "empty_body": "content_blocks",
        "no_sections": "semantic_risk",
        "source_structure_too_flat": "semantic_risk",
        "article_type_conflict": "semantic_risk",
        "missing_cover": "publication_readiness",
        "placeholder_cover": "publication_readiness",
        "cover_requires_import": "publication_readiness",
        "placeholder_image": "publication_readiness",
        "source_image_requires_import": "publication_readiness",
        "unsafe_image_source": "publication_readiness",
    }
    rank = {"pass": 0, "warning": 1, "blocking": 2}
    for finding in findings:
        dimension = mapping.get(finding.code, "semantic_risk")
        value = "blocking" if finding.resolution_policy == "HARD_BLOCK" else "warning"
        if rank[value] > rank[dimensions[dimension]]:
            dimensions[dimension] = value
    return dimensions


def run_preflight(
    markdown: str,
    *,
    title_override: str | None = None,
    requested_article_type: str | None = None,
) -> PreflightResult:
    normalized, repairs = normalize_markdown(markdown)
    findings: list[PreflightFinding] = []
    parsed: ParsedArticle | None = None

    if not normalized.strip():
        findings.append(
            PreflightFinding(
                code="empty_body",
                message="Markdown 文件为空",
                resolution_policy="HARD_BLOCK",
                planning_blocking=True,
                draft_blocking=True,
            )
        )
    if SECRET_ASSIGNMENT_RE.search(normalized):
        findings.append(
            PreflightFinding(
                code="sensitive_credentials",
                message="检测到疑似密钥或访问令牌，请从原稿中移除后重试",
                resolution_policy="HARD_BLOCK",
                planning_blocking=True,
                draft_blocking=True,
            )
        )

    if not findings or all(item.code != "empty_body" for item in findings):
        try:
            parsed = parse_markdown(normalized, title_override)
        except MarkdownInputError as exc:
            code = "missing_title" if "缺少标题" in str(exc) else "invalid_markdown"
            findings.append(
                PreflightFinding(
                    code=code,
                    message=str(exc),
                    resolution_policy="HARD_BLOCK",
                    planning_blocking=True,
                    draft_blocking=True,
                )
            )

    canonical_title: str | None = parsed.title if parsed else None
    title_source: str | None = parsed.title_source if parsed else None
    if parsed:
        candidates = _title_candidates(normalized, parsed, title_override)
        distinct_titles = {title for _, title in candidates}
        if len(distinct_titles) > 1:
            findings.append(
                PreflightFinding(
                    code="title_source_conflict",
                    message="后台标题与正文 H1 不一致；系统按上传参数 > frontmatter > 首个 H1 选择标题，并采用受限规划",
                    resolution_policy="ACKNOWLEDGE",
                    planning_blocking=False,
                    draft_blocking=False,
                    details={
                        "selected_source": parsed.title_source,
                        "candidates": [{"source": source, "title": title} for source, title in candidates],
                    },
                )
            )
        findings.extend(_heading_findings(parsed))
        if parsed.section_count == 0:
            findings.append(
                PreflightFinding(
                    code="no_sections",
                    message="未识别到二级章节标题，方案将采用受限的朴素层级",
                    resolution_policy="ACKNOWLEDGE",
                    planning_blocking=False,
                    draft_blocking=False,
                )
            )
        structure_finding = _semantic_structure_finding(parsed, requested_article_type)
        if structure_finding is not None:
            findings.append(structure_finding)
        findings.extend(_asset_findings(parsed))

        frontmatter_type = str(parsed.frontmatter.get("article_type", "")).strip()
        if requested_article_type and frontmatter_type and requested_article_type != frontmatter_type:
            findings.append(
                PreflightFinding(
                    code="article_type_conflict",
                    message="运营选择的文章类型与 frontmatter 不一致，将优先采用运营选择",
                    resolution_policy="ACKNOWLEDGE",
                    planning_blocking=False,
                    draft_blocking=False,
                    details={"requested": requested_article_type, "frontmatter": frontmatter_type},
                )
            )

    if any(item.resolution_policy == "HARD_BLOCK" for item in findings):
        status: PreflightStatus = "BLOCK"
    elif findings:
        status = "REVIEW"
    else:
        status = "PASS"

    planning_allowed = status != "BLOCK" and not any(item.planning_blocking for item in findings)
    # Fresh REVIEW reports have not yet collected acknowledgement/resolution evidence.
    draft_creation_allowed = status == "PASS" and not any(item.draft_blocking for item in findings)
    report = PreflightReport(
        schema_version=PREFLIGHT_SCHEMA_VERSION,
        ruleset_version=PREFLIGHT_RULESET_VERSION,
        status=status,
        source_hash=_sha256(markdown),
        normalized_hash=_sha256(normalized),
        canonical_title=canonical_title,
        title_source=title_source,
        auto_repairs=repairs,
        findings=tuple(findings),
        quality_dimensions=_quality_dimensions(findings),
        planning_allowed=planning_allowed,
        draft_creation_allowed=draft_creation_allowed,
    )
    return PreflightResult(
        original_markdown=markdown,
        normalized_markdown=normalized,
        parsed=parsed,
        report=report,
    )
