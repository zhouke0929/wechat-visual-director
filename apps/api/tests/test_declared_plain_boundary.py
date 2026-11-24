"""A host may decline an eligible opportunity without losing the original list."""
import json
from pathlib import Path

from visual_director.brief_compiler import compile_editorial_brief
from visual_director.component_opportunities import component_opportunity_diagnostics
from visual_director.parser import parse_markdown
from visual_director.renderer import render_preview


def test_reserved_list_remains_available_to_ordinary_renderer():
    article = parse_markdown("# 核验事项\n\n## 行动清单\n\n- 复核文件。\n- 确认签名。")
    protected = next(block.id for block in article.blocks if block.type == "unordered_list")
    candidates = component_opportunity_diagnostics(article)["candidate_anchors"]
    assert any(protected in candidate["consume_block_ids"] for candidate in candidates)
    fixture = Path(__file__).resolve().parents[3] / "samples/showcase/brief-01-campus-project-portfolio.json"
    brief = json.loads(fixture.read_text(encoding="utf-8"))
    brief.update(sections=[{"source_block_ids": [protected], "semantic_role": "plain_narrative",
                            "visual_priority": "low", "component_intent": "plain", "reasoning": "保留原文清单。"}],
                 image_intents=[])
    plan = compile_editorial_brief(article, brief, 5)
    assert plan["slots"] == []
    preview = render_preview(article, plan)
    assert "复核文件。" in preview and "确认签名。" in preview
