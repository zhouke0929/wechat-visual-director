from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .component_catalog import COMPONENT_CATALOG, PLAN_SCHEMA_VERSION, allowed_variants
from .parser import ParsedArticle


BLOCK_REF_RE = re.compile(r"^(block-\d{3})(?::item:(\d+))?$")


class HistoryEvidence(BaseModel):
    recent_use_count: int = Field(default=0, ge=0)
    penalty_applied: bool = False
    component_use_count: int = Field(default=0, ge=0)
    selected_variant: str | None = None
    avoided_variant: str | None = None


class ComponentSlot(BaseModel):
    slot_id: str = Field(pattern=r"^slot-\d{3}$")
    anchor_block_id: str = Field(pattern=r"^block-\d{3}$")
    consume_block_ids: list[str] = Field(min_length=1)
    semantic_role: str
    component_type: str
    variant: str
    fallback_variant: str
    emphasis: str = Field(pattern=r"^(primary|secondary|subtle)$")
    content_bindings: dict[str, str | list[str]]
    selection_reason: str = Field(min_length=1)
    history_evidence: HistoryEvidence = Field(default_factory=HistoryEvidence)
    facts_locked: bool = True

    @model_validator(mode="after")
    def validate_component_contract(self) -> "ComponentSlot":
        if self.component_type not in COMPONENT_CATALOG:
            raise ValueError(f"未知组件类型：{self.component_type}")
        definition = COMPONENT_CATALOG[self.component_type]
        if self.variant not in allowed_variants(self.component_type):
            raise ValueError(f"未知组件变体：{self.component_type}.{self.variant}")
        if self.fallback_variant != definition["fallback_variant"]:
            raise ValueError(f"安全朴素版不匹配：{self.component_type}.{self.fallback_variant}")
        if self.semantic_role != self.component_type:
            raise ValueError("V0.3 中 semantic_role 必须与 component_type 一致")
        for role, cardinality in definition["required_bindings"].items():
            value = self.content_bindings.get(role)
            if value is None:
                raise ValueError(f"缺少内容绑定：{role}")
            if cardinality == "one" and not isinstance(value, str):
                raise ValueError(f"内容绑定 {role} 必须为单个引用")
            if cardinality == "many" and (not isinstance(value, list) or not value):
                raise ValueError(f"内容绑定 {role} 必须为非空引用数组")
        if not self.facts_locked:
            raise ValueError("V0.3 组件必须锁定原文事实")
        return self


class ImageVisualIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=160)
    composition: str = Field(pattern=r"^(branching|layered|wide_scene|centered)$")
    style_family: str = Field(pattern=r"^(editorial_paper_cut|soft_flat_illustration|clean_3d_geometry)$")
    palette_role: str = Field(default="plan_palette", pattern=r"^plan_palette$")
    palette_roles: list[str] = Field(default_factory=list, max_length=5)
    tone: list[str] = Field(default_factory=list, max_length=4)
    negative_space: str = Field(pattern=r"^(none|lower_right|lower_third)$")


class ImageFactBindings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_ref: str | None = None
    item_refs: list[str] = Field(default_factory=list, max_length=4)
    facts_locked: bool = True


class ImageHistoryEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent_use_count: int = Field(default=0, ge=0)
    avoided_style_family: str | None = None
    penalty_applied: bool = False


class ImageSlotPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_slot_id: str = Field(pattern=r"^image-slot-\d{3}$")
    anchor_block_id: str = Field(pattern=r"^block-\d{3}$")
    source_block_ids: list[str] = Field(min_length=1)
    placement: str = Field(default="after_anchor", pattern=r"^after_anchor$")
    purpose: str = Field(pattern=r"^(atmosphere|structured_infographic)$")
    required: bool = False
    reason: str = Field(min_length=1, max_length=240)
    aspect_ratio: str = Field(pattern=r"^(4:3|16:9)$")
    visual_intent: ImageVisualIntent
    fact_bindings: ImageFactBindings = Field(default_factory=ImageFactBindings)
    history_evidence: ImageHistoryEvidence = Field(default_factory=ImageHistoryEvidence)

    @model_validator(mode="after")
    def validate_image_contract(self) -> "ImageSlotPlan":
        if self.required:
            raise ValueError("V0.5 自动图片必须允许跳过")
        if self.anchor_block_id not in self.source_block_ids:
            raise ValueError("图片锚点必须包含在 source_block_ids 中")
        if not self.fact_bindings.facts_locked:
            raise ValueError("图片事实绑定必须锁定原文")
        if self.purpose == "structured_infographic":
            if not 2 <= len(self.fact_bindings.item_refs) <= 4:
                raise ValueError("结构信息图必须绑定 2–4 个原文节点")
        elif self.fact_bindings.item_refs or self.fact_bindings.title_ref:
            raise ValueError("氛围图不得绑定需要叠加的关键事实")
        return self


class VisualPlanContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = PLAN_SCHEMA_VERSION
    revision: int = Field(default=1, ge=1)
    undo_stack: list[int] = Field(default_factory=list)
    task_id: str | None = None
    component_library_version: str
    renderer_version: str
    history_window: int = Field(ge=1, le=20)
    slots: list[ComponentSlot] = Field(default_factory=list)
    image_slots: list[ImageSlotPlan] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_slots(self) -> "VisualPlanContract":
        if self.schema_version not in {"visual_plan.v0.4", PLAN_SCHEMA_VERSION}:
            raise ValueError(f"不支持的 VisualPlan 版本：{self.schema_version}")
        slot_ids = [slot.slot_id for slot in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("slot_id 不能重复")
        consumed: set[str] = set()
        for slot in self.slots:
            overlap = consumed.intersection(slot.consume_block_ids)
            if overlap:
                raise ValueError(f"内容块被多个组件重复消费：{sorted(overlap)}")
            consumed.update(slot.consume_block_ids)
        image_slot_ids = [slot.image_slot_id for slot in self.image_slots]
        if len(image_slot_ids) != len(set(image_slot_ids)):
            raise ValueError("image_slot_id 不能重复")
        for image_slot in self.image_slots:
            for component_slot in self.slots:
                if image_slot.anchor_block_id in component_slot.consume_block_ids:
                    if image_slot.anchor_block_id != component_slot.consume_block_ids[-1]:
                        raise ValueError("图片不得插入组件消费内容的中间")
        return self


def _binding_refs(slot: ComponentSlot) -> list[str]:
    refs: list[str] = []
    for value in slot.content_bindings.values():
        refs.extend(value if isinstance(value, list) else [value])
    return refs


def validate_plan_for_article(plan: dict[str, Any], parsed: ParsedArticle) -> dict[str, Any]:
    contract = VisualPlanContract.model_validate(plan)
    blocks = {block.id: block for block in parsed.blocks}
    for slot in contract.slots:
        if slot.anchor_block_id not in blocks:
            raise ValueError(f"锚点内容块不存在：{slot.anchor_block_id}")
        if slot.anchor_block_id != slot.consume_block_ids[0]:
            raise ValueError("anchor_block_id 必须是第一个消费块")
        for block_id in slot.consume_block_ids:
            if block_id not in blocks:
                raise ValueError(f"消费内容块不存在：{block_id}")
            block = blocks[block_id]
            if (
                contract.schema_version == PLAN_SCHEMA_VERSION
                and block.type == "heading"
                and (block.level or 0) <= 2
            ):
                raise ValueError(
                    f"文章 H1/H2 属于受保护结构，不得被组件消费：{block_id}"
                )
        for reference in _binding_refs(slot):
            match = BLOCK_REF_RE.fullmatch(reference)
            if not match:
                raise ValueError(f"内容绑定引用格式错误：{reference}")
            block_id, item_index = match.groups()
            if block_id not in blocks:
                raise ValueError(f"内容绑定跨出当前任务：{reference}")
            if block_id not in slot.consume_block_ids:
                raise ValueError(f"内容绑定未包含在消费块中：{reference}")
            if item_index is not None:
                block = blocks[block_id]
                if block.type not in {"ordered_list", "unordered_list"}:
                    raise ValueError(f"非列表内容不能使用 item 引用：{reference}")
                if int(item_index) >= len(block.content):
                    raise ValueError(f"列表项不存在：{reference}")
    for image_slot in contract.image_slots:
        for block_id in image_slot.source_block_ids:
            if block_id not in blocks:
                raise ValueError(f"图片来源内容块不存在：{block_id}")
        references = [
            reference
            for reference in [image_slot.fact_bindings.title_ref, *image_slot.fact_bindings.item_refs]
            if reference is not None
        ]
        for reference in references:
            match = BLOCK_REF_RE.fullmatch(reference)
            if not match:
                raise ValueError(f"图片事实引用格式错误：{reference}")
            block_id, item_index = match.groups()
            if block_id not in blocks:
                raise ValueError(f"图片事实引用跨出当前任务：{reference}")
            if block_id not in image_slot.source_block_ids:
                raise ValueError(f"图片事实引用未包含在来源块中：{reference}")
            if item_index is not None:
                block = blocks[block_id]
                if block.type not in {"ordered_list", "unordered_list"}:
                    raise ValueError(f"图片非列表内容不能使用 item 引用：{reference}")
                if int(item_index) >= len(block.content):
                    raise ValueError(f"图片列表项不存在：{reference}")
    return contract.model_dump(mode="json")
