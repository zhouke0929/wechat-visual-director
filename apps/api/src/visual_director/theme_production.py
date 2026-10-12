"""Probe declared theme layouts through production entry points, with no user data."""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

from .brief_compiler import visual_system_configuration, visual_system_variant
from .component_catalog import COMPONENT_CATALOG, CORE_THEME_COMPONENTS
from .parser import parse_markdown
from .planner import generate_plans
from .publication import _materialized_image_markup
from .renderer import _opening_highlight, render_preview
from .theme_layouts import ROLE_FIELDS


class _LayoutProbe(HTMLParser):
    def __init__(self, document: str):
        super().__init__()
        self.stack: list[tuple[str, dict]] = []
        self.roles: dict[str, list[list[dict]]] = {}
        self.feed(document)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        ancestors = [item[1] for item in self.stack] + [attributes]
        if attributes.get("data-theme-layout"):
            self.roles.setdefault(attributes["data-theme-layout"], []).append(ancestors)
        if tag not in {"img", "br", "hr", "meta", "link", "input", "source", "wbr"}:
            self.stack.append((tag, attributes))

    def handle_startendtag(self, tag, attributes):
        pass

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def owns(self, role, key=None, value=None):
        return any(key is None or any(node.get(key) == value for node in ancestors)
                   for ancestors in self.roles.get(role, []))


def _fixture(long: bool):
    phrase = "观察具体条件，再说明自己的判断，不补写不存在的事实。" * (5 if long else 1)
    return parse_markdown(f"""# 正式主题链路检查

本文从阅读顺序、正文层级与图文关系出发，说明怎样保持完整而清楚的表达。{phrase}

## 进入阅读阶段

### 为什么需要先判断再行动？

因为需要把观察与结论分开。{phrase}

> 引文保持原意。{phrase}

- 保存具体观察。{phrase}
- 说明判断依据。{phrase}

1. 先理解已有条件。{phrase}
2. 再确认下一步。{phrase}

### 什么是阅读节奏

阅读节奏是不同信息关系之间的停顿。{phrase}

### 案例：一份整理笔记

笔记保留了问题、过程与结果。{phrase}

原来的方式只保留结论。{phrase}

新的方式也保留判断依据。{phrase}

注意：这只是程序测试的公开合成内容。{phrase}

---

![公开图文测试](probe-image.png)
""")


def check_theme_production(manifest: dict[str, Any]) -> dict[str, Any]:
    layouts = manifest.get("design_system", {}).get("layouts", {})
    if not layouts:
        return {"status": "not_applicable", "scope": "declared_production_entrypoints", "cases": [], "checked_roles": []}
    config = visual_system_configuration(manifest["base_theme"])
    config.update(palette=manifest["palette"], accent=manifest["palette"]["primary"],
                  generated_design_system=manifest["design_system"], visual_system="production_probe")
    brand = {"standard_kicker": "阅读检查", "fixed_footer": {"enabled": True, "text": "保持完整表达。"}}
    cases = []
    for long in (False, True):
        length = "long" if long else "short"
        parsed = _fixture(long)
        plan = generate_plans(parsed, "tutorial_steps", 5)[0]
        plan.update(configuration=config, slots=[], image_slots=[])
        paragraphs = [block for block in parsed.blocks if block.type == "paragraph"]
        headings = [block for block in parsed.blocks if block.type == "heading" and block.level == 3]
        heading = next(block for block in parsed.blocks if block.type == "heading" and block.level == 2)
        quote = next(block for block in parsed.blocks if block.type == "quote")
        lists = [block for block in parsed.blocks if block.type in {"unordered_list", "ordered_list"}]
        refs = lambda block: [f"{block.id}:item:{index}" for index in range(len(block.content))]
        bindings = {
            "question_hook": {"title": headings[0].id},
            "faq_card": {"question": headings[0].id, "answer": paragraphs[1].id},
            "concept_explainer": {"title": headings[1].id, "definition": paragraphs[2].id},
            "case_card": {"title": headings[2].id, "body": paragraphs[3].id},
            "evidence_callout": {"evidence": quote.id},
            "warning_note": {"body": paragraphs[6].id},
            "before_after_timeline": {"before": paragraphs[4].id, "after": paragraphs[5].id},
            "comparison_card": {"left": paragraphs[4].id, "right": paragraphs[5].id},
            **{role: {"items": refs(lists[1] if role == "logic_path" else lists[0])}
               for role in ("numbered_insight", "logic_path", "action_checklist", "section_summary")},
        }
        lead_id, _ = _opening_highlight(parsed)
        try:
            plain = _LayoutProbe(render_preview(parsed, plan, brand_profile=brand))
            picture = _LayoutProbe(_materialized_image_markup(
                element_id="probe-image", anchor_class="source-image-anchor", content_url="asset://probe-image",
                width=600, height=400, alt="公开图文检查", frame_variant="neutral",
                caption_html="公开图文检查", theme_config=config))
            basic = {
                "hero": plain.owns("hero"),
                "heading": plain.owns("heading", "data-editor-block-ids", heading.id),
                "subheading": plain.owns("subheading", "data-editor-block-ids", headings[0].id),
                "lead": plain.owns("lead", "data-editor-block-ids", lead_id),
                "quote": plain.owns("quote", "data-editor-block-ids", quote.id),
                "list": all(plain.owns("list", "data-editor-block-ids", block.id) for block in lists),
                "divider": plain.owns("divider"),
                "closing_cta": plain.owns("closing_cta", "data-content-role", "brand-cta"),
                "image_caption": picture.owns("image_caption"),
            }
            for role, hit in basic.items():
                if role in layouts:
                    cases.append({"role": role, "length": length, "status": "pass" if hit else "blocking",
                                  **({} if hit else {"message": "已声明布局没有命中对应的正式渲染入口"})})
        except (ValueError, KeyError, OSError) as exc:
            cases.extend({"role": role, "length": length, "status": "blocking", "message": str(exc)}
                         for role in layouts if role not in CORE_THEME_COMPONENTS)
        for role in CORE_THEME_COMPONENTS:
            if role not in layouts:
                continue
            binding = bindings[role]
            consumed = {ref.split(":", 1)[0] for value in binding.values()
                        for ref in (value if isinstance(value, list) else [value])}
            consumed = [block.id for block in parsed.blocks if block.id in consumed]
            slot = {"slot_id": "slot-001", "anchor_block_id": consumed[0], "consume_block_ids": consumed,
                    "semantic_role": role, "component_type": role,
                    "variant": visual_system_variant(role, manifest["base_theme"]),
                    "fallback_variant": COMPONENT_CATALOG[role]["fallback_variant"],
                    "emphasis": "primary", "content_bindings": binding,
                    "selection_reason": "公开合成试样验证正式组件入口", "facts_locked": True}
            try:
                probe = _LayoutProbe(render_preview(parsed, {**plan, "slots": [slot]}, brand_profile=brand))
                hit = probe.owns(role, "data-component-type", role)
                cases.append({"role": role, "length": length, "status": "pass" if hit else "blocking",
                              **({} if hit else {"message": "已声明布局没有命中正式语义组件入口"})})
            except (ValueError, KeyError, OSError) as exc:
                cases.append({"role": role, "length": length, "status": "blocking", "message": str(exc)})
    checked = [role for role in ROLE_FIELDS if any(case["role"] == role for case in cases)]
    return {"status": "blocking" if any(case["status"] == "blocking" for case in cases) else "pass",
            "scope": "declared_production_entrypoints", "checked_roles": checked,
            "undeclared_roles": [role for role in ROLE_FIELDS if role not in layouts], "cases": cases,
            "visual_review": "not_verified", "wechat_saved_roundtrip": "not_verified"}
