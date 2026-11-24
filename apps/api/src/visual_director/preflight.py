from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .parser import MarkdownInputError, ParsedArticle, parse_markdown


PreflightStatus = Literal["PASS", "REVIEW", "BLOCK"]
ResolutionPolicy = Literal["ACKNOWLEDGE", "EDIT_SOURCE", "REPLACE_ASSET", "HARD_BLOCK"]

PREFLIGHT_SCHEMA_VERSION = "preflight_report.v0.1"
PREFLIGHT_RULESET_VERSION = "preflight_rules.v0.3-host-structure-advice"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IMAGE_LINE_RE = re.compile(r"^!\[([^\]]*)]\(([^)]+)\)\s*$")
INLINE_IMAGE_RE = re.compile(r"(?<![\\`])!\[([^\]]*)]\(([^)]+)\)")
LINKED_IMAGE_RE = re.compile(r"(?<![\\`])!\[([^\]]*)]\[([^\]]*)]")
LINK_DEFINITION_RE = re.compile(r"^\s{0,3}\[([^\]]+)]:\s+<?([^\s>]+)>?(?:\s+.+)?$")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
NON_PARAGRAPH_RE = re.compile(r"^\s*(?:[#>|]|[-*+]\s|\d+[.)、]\s)|^ {4}|^\t")
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


def _promote_paragraph_images(markdown: str) -> tuple[str, int]:
    # Keep persisted block IDs stable by applying this only to new imports.
    prefix = ""
    if markdown.startswith("---\n"):
        closing = markdown.find("\n---\n", 4)
        if closing < 0:
            return markdown, 0
        prefix, markdown = markdown[:closing + 5], markdown[closing + 5:]
    lines = markdown.split("\n")
    fence = ""
    prose: set[int] = set()
    definitions: dict[str, tuple[int, str]] = {}
    for index, line in enumerate(lines):
        marker = FENCE_RE.match(line)
        if marker:
            token = marker[1]
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not line[marker.end():].strip():
                fence = ""
        elif not fence and not NON_PARAGRAPH_RE.match(line):
            definition = LINK_DEFINITION_RE.fullmatch(line)
            if definition:
                definitions.setdefault(" ".join(definition[1].split()).casefold(), (index, definition[2]))
            elif not line.lstrip().startswith("<!--"):
                prose.add(index)
    promoted = 0
    used: set[int] = set()
    for index in sorted(prose):
        line = lines[index]
        if IMAGE_LINE_RE.fullmatch(line.strip()) or "`" in line:
            continue
        def resolve(match: re.Match[str]) -> str:
            definition = definitions.get(" ".join((match[2] or match[1]).split()).casefold())
            if definition is None:
                return match[0]
            used.add(definition[0])
            return f"![{match[1]}]({definition[1]})"
        line = LINKED_IMAGE_RE.sub(resolve, line)
        lines[index], count = INLINE_IMAGE_RE.subn(lambda match: "\n\n" + match[0] + "\n\n", line)
        promoted += count
    for index in used:
        # A definition might also be used by an ordinary reference link.
        definition = LINK_DEFINITION_RE.fullmatch(lines[index])
        label = re.escape(definition[1]) if definition else ""
        if label and not any(re.search(rf"(?<!\!)\[[^\]]+\]\[{label}\]|(?<!\!)\[{label}\](?![(:])", line, re.I)
                             for number, line in enumerate(lines) if number != index):
            lines[index] = ""
    return prefix + "\n".join(lines), promoted


def normalize_markdown(markdown: str, *, promote_images: bool = True) -> tuple[str, tuple[AutoRepair, ...]]:
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
    if promote_images:
        normalized, promoted = _promote_paragraph_images(normalized)
        if promoted:
            repairs.append(AutoRepair("paragraph_images_promoted", f"已将 {promoted} 张正文图片保留为可补传的独立图块"))
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


def _quality_dimensions(findings: list[dict[str, Any]]) -> dict[str, str]:
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
        dimension = mapping.get(finding.get("code"), "semantic_risk")
        value = "blocking" if finding.get("resolution_policy") == "HARD_BLOCK" else "warning"
        if rank[value] > rank[dimensions[dimension]]:
            dimensions[dimension] = value
    return dimensions


def refresh_preflight_permissions(report: dict[str, Any]) -> None:
    unresolved = [item for item in report.get("findings", []) if not item.get("resolved_at")]
    report["planning_allowed"] = report.get("status") != "BLOCK" and not any(
        item.get("planning_blocking") for item in unresolved
    )
    report["draft_creation_allowed"] = report.get("status") != "BLOCK" and not any(
        item.get("draft_blocking") or item.get("resolution_policy") == "ACKNOWLEDGE"
        for item in unresolved
    )


def retire_flat_prose_blocker(summary: dict[str, Any]) -> bool:
    """Project pending legacy reports forward without re-parsing or erasing real decisions."""
    report = summary.get("preflight_report") or {}
    findings = report.get("findings") or []
    remaining = [f for f in findings if f.get("code") != "source_structure_too_flat"]
    if len(remaining) == len(findings):
        return False
    report["findings"] = remaining
    report["ruleset_version"] = PREFLIGHT_RULESET_VERSION
    if not remaining and report.get("status") == "REVIEW":
        report["status"] = "PASS"
    if isinstance(report.get("quality_dimensions"), dict):
        report["quality_dimensions"]["semantic_risk"] = _quality_dimensions(remaining)["semantic_risk"]
    refresh_preflight_permissions(report)
    if isinstance(summary.get("warnings"), list):
        summary["warnings"] = [
            w for w in summary["warnings"] if not isinstance(w, dict) or w.get("code") != "source_structure_too_flat"
        ]
    return True


def run_preflight(
    markdown: str,
    *,
    title_override: str | None = None,
    requested_article_type: str | None = None,
    promote_images: bool = True,
) -> PreflightResult:
    normalized, repairs = normalize_markdown(markdown, promote_images=promote_images)
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
        quality_dimensions=_quality_dimensions([asdict(item) for item in findings]),
        planning_allowed=planning_allowed,
        draft_creation_allowed=draft_creation_allowed,
    )
    return PreflightResult(
        original_markdown=markdown,
        normalized_markdown=normalized,
        parsed=parsed,
        report=report,
    )
