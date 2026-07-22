from __future__ import annotations

import hashlib
import json
import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

from .brief_compiler import compile_editorial_brief
from .component_catalog import COMPONENT_CATALOG
from .editorial_brief import normalize_editorial_brief_for_article
from .parser import ContentBlock, parse_markdown
from .planner import generate_plans
from .renderer import render_preview
from .text_planner import TextPlannerRequest, build_rule_based_brief


BLIND_REVIEW_SCHEMA_VERSION = "blind_review.v0.1"
BLIND_REVIEW_DIMENSIONS = (
    ("article_understanding", "文章理解", "受众、读者任务与内容重点是否准确"),
    ("component_planning", "组件规划", "强调位置是否合理，是否存在刻意堆砌"),
    ("image_planning", "图片规划", "图片必要性、位置和用途是否符合阅读节奏"),
    ("style_direction", "风格方向", "色彩、装饰密度和文章主题是否协调"),
    ("history_freshness", "历史新鲜感", "是否避开最近文章的重复套路"),
    ("direct_adoption", "继续编辑意愿", "是否愿意以此方案继续编辑并走向发布"),
)


def _block_excerpt(block: ContentBlock | None) -> str:
    if block is None:
        return "正文位置"
    content = block.content
    if isinstance(content, list):
        text = " / ".join(str(item) for item in content[:2])
    else:
        text = str(content)
    text = " ".join(text.split())
    return text[:38] + ("…" if len(text) > 38 else "")


class BlindReviewDataset:
    """Build a source-hidden R/L comparison set from a frozen certification report."""

    def __init__(self, root: Path, manifest_path: Path) -> None:
        self.root = root
        self.manifest_path = manifest_path
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.eval_set_id = str(self.manifest["eval_set_id"])
        self.reviewers = {
            str(item["id"]): str(item["label"])
            for item in self.manifest["reviewers"]
        }
        catalog = json.loads(self._resolve(self.manifest["sample_catalog"]).read_text(encoding="utf-8"))
        history = json.loads(self._resolve(self.manifest["history_fixture"]).read_text(encoding="utf-8"))["summaries"]
        sample_by_id = {str(item["id"]): item for item in catalog["samples"]}
        report_results: dict[str, dict[str, Any]] = {}
        if self.manifest.get("source_report"):
            report = json.loads(self._resolve(self.manifest["source_report"]).read_text(encoding="utf-8"))
            report_results = {
                str(item["sample_id"]): item
                for item in report["results"]
                if item.get("model") == self.manifest.get("source_model")
            }
            if set(report_results) != set(sample_by_id):
                raise ValueError("盲评认证报告与开发样本集不完整或不一致")

        self.samples: list[dict[str, Any]] = []
        self.samples_by_id: dict[str, dict[str, Any]] = {}
        for index, sample_id in enumerate(sample_by_id, start=1):
            sample_meta = sample_by_id[sample_id]
            markdown = self._resolve(sample_meta["path"]).read_text(encoding="utf-8")
            parsed = parse_markdown(markdown)
            article_type = str(sample_meta["gold_article_type"])
            request = TextPlannerRequest(
                parsed=parsed,
                article_type=article_type,
                history_window=5,
                recent_summaries=history,
                brand_config={},
            )
            baseline_brief = build_rule_based_brief(request)
            baseline_plan = generate_plans(parsed, article_type, 5, history)[0]
            if sample_id in report_results:
                candidate_brief, _ = normalize_editorial_brief_for_article(
                    report_results[sample_id]["brief"], parsed
                )
            else:
                candidate_brief = baseline_brief.model_copy(deep=True)
                candidate_brief.art_direction.style_family = "editorial_paper_cut"
                candidate_brief.art_direction.palette_roles = [
                    "deep_navy",
                    "warm_ivory",
                    "coral_accent",
                ]
            candidate_plan = compile_editorial_brief(parsed, candidate_brief, 5, history)
            baseline_plan = self._source_hidden_plan(baseline_plan)
            candidate_plan = self._source_hidden_plan(candidate_plan)
            block_map = {block.id: block for block in parsed.blocks}
            sources = {
                "baseline": self._candidate_payload(
                    baseline_plan,
                    baseline_brief.model_dump(mode="json"),
                    block_map,
                    render_preview(parsed, baseline_plan),
                ),
                "candidate": self._candidate_payload(
                    candidate_plan,
                    candidate_brief.model_dump(mode="json"),
                    block_map,
                    render_preview(parsed, candidate_plan),
                ),
            }
            item = {
                "sample_id": sample_id,
                "index": index,
                "title": parsed.title,
                "article_type": article_type,
                "role": sample_meta["role"],
                "visual_scoring": bool(sample_meta["visual_scoring"]),
                "sources": sources,
            }
            self.samples.append(item)
            self.samples_by_id[sample_id] = item

    @staticmethod
    def _source_hidden_plan(plan: dict[str, Any]) -> dict[str, Any]:
        hidden = copy.deepcopy(plan)
        hidden["plan_name"] = "视觉校样"
        hidden["recommendation"] = "alternative"
        return hidden

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    @staticmethod
    def _candidate_payload(
        plan: dict[str, Any],
        brief: dict[str, Any],
        block_map: dict[str, ContentBlock],
        html: str,
    ) -> dict[str, Any]:
        components = []
        for slot in plan.get("slots", []):
            definition = COMPONENT_CATALOG.get(slot["component_type"], {})
            components.append(
                {
                    "label": definition.get("label", slot["component_type"]),
                    "anchor": _block_excerpt(block_map.get(slot["anchor_block_id"])),
                    "reason": slot.get("selection_reason", "用于突出当前段落"),
                }
            )
        images = []
        for slot in plan.get("image_slots", []):
            intent = slot.get("visual_intent", {})
            images.append(
                {
                    "anchor": _block_excerpt(block_map.get(slot["anchor_block_id"])),
                    "purpose": "结构信息图" if slot["purpose"] == "structured_infographic" else "氛围插图",
                    "reason": slot.get("reason", "辅助阅读节奏"),
                    "visual_intent": intent.get("subject", "围绕当前段落建立视觉意象"),
                }
            )
        return {
            "html": html,
            "summary": {
                "article": brief["article"],
                "art_direction": brief["art_direction"],
                "components": components,
                "images": images,
            },
        }

    def _ordered_sources(self, reviewer_id: str, sample_id: str) -> tuple[str, str]:
        if reviewer_id not in self.reviewers:
            raise KeyError("未知评审身份")
        if sample_id not in self.samples_by_id:
            raise KeyError("未知盲评样本")
        digest = hashlib.sha256(
            f"{self.eval_set_id}|{reviewer_id}|{sample_id}".encode("utf-8")
        ).digest()
        return ("baseline", "candidate") if digest[0] % 2 == 0 else ("candidate", "baseline")

    def assignment_token(self, reviewer_id: str, sample_id: str) -> str:
        ordered = self._ordered_sources(reviewer_id, sample_id)
        return hashlib.sha256(
            f"{self.eval_set_id}|{reviewer_id}|{sample_id}|{'|'.join(ordered)}".encode("utf-8")
        ).hexdigest()

    def public_set(self, reviewer_id: str, submitted_ids: set[str]) -> dict[str, Any]:
        if reviewer_id not in self.reviewers:
            raise KeyError("未知评审身份")
        public_samples = []
        for sample in self.samples:
            ordered = self._ordered_sources(reviewer_id, sample["sample_id"])
            candidates = []
            for position, source in zip(("left", "right"), ordered, strict=True):
                candidates.append(
                    {
                        "position": position,
                        "label": "方案 A" if position == "left" else "方案 B",
                        "summary": sample["sources"][source]["summary"],
                        "preview_url": (
                            f"/api/v1/blind-reviews/{self.eval_set_id}/reviewers/{reviewer_id}/"
                            f"samples/{sample['sample_id']}/candidates/{position}/preview"
                        ),
                    }
                )
            public_samples.append(
                {
                    "sample_id": sample["sample_id"],
                    "index": sample["index"],
                    "title": sample["title"],
                    "article_type": sample["article_type"],
                    "role": sample["role"],
                    "visual_scoring": sample["visual_scoring"],
                    "submitted": sample["sample_id"] in submitted_ids,
                    "assignment_token": self.assignment_token(reviewer_id, sample["sample_id"]),
                    "candidates": candidates,
                }
            )
        return {
            "schema_version": BLIND_REVIEW_SCHEMA_VERSION,
            "eval_set_id": self.eval_set_id,
            "mode": self.manifest["mode"],
            "formal_conclusion_allowed": bool(self.manifest["formal_conclusion_allowed"]),
            "note": self.manifest["note"],
            "reviewer": {"id": reviewer_id, "label": self.reviewers[reviewer_id]},
            "dimensions": [
                {"key": key, "label": label, "description": description}
                for key, label, description in BLIND_REVIEW_DIMENSIONS
            ],
            "progress": {"completed": len(submitted_ids), "total": len(self.samples)},
            "samples": public_samples,
        }

    def preview_html(self, reviewer_id: str, sample_id: str, position: str) -> str:
        ordered = self._ordered_sources(reviewer_id, sample_id)
        if position not in {"left", "right"}:
            raise KeyError("未知候选位置")
        source = ordered[0] if position == "left" else ordered[1]
        return str(self.samples_by_id[sample_id]["sources"][source]["html"])

    def source_for_position(self, reviewer_id: str, sample_id: str, position: str) -> str:
        ordered = self._ordered_sources(reviewer_id, sample_id)
        return ordered[0] if position == "left" else ordered[1]


@lru_cache(maxsize=4)
def load_blind_review_dataset(root: str, manifest_path: str) -> BlindReviewDataset:
    return BlindReviewDataset(Path(root), Path(manifest_path))
