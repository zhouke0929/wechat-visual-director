import pytest

from visual_director.brief_compiler import compile_editorial_brief
from visual_director.editorial_brief import normalize_editorial_brief_for_article
from visual_director.parser import parse_markdown
from visual_director.rule_baseline import MockTextPlannerProvider
from visual_director.text_planner import TextPlannerRequest


@pytest.mark.parametrize("separated", [False, True], ids=["one-glossary", "separate-cards"])
@pytest.mark.parametrize("plain_first", [False, True], ids=["plain-last", "plain-first"])
def test_inferred_concept_series_does_not_take_a_reserved_sibling(separated, plain_first):
    between = "\n\n值班的人又翻过一页，继续往下读。" if separated else ""
    article = parse_markdown("# 手册\n\n## 纸张\n\n" + "\n\n".join(
        f"### {name}\n\n{name}是指{description}。{between}"
        for name, description in (("定量", "每平方米纸的质量"), ("厚度", "两面之间的距离"), ("幅宽", "纸张横向的宽度"))
    ))
    pairs = [(b.id, article.blocks[i+1].id) for i, b in enumerate(article.blocks) if b.level == 3]
    first, middle, _ = pairs
    req = TextPlannerRequest(article, "viewpoint_trend", 5, [], {})
    raw = MockTextPlannerProvider().generate(req).model_dump(mode="json")
    concept = dict(source_block_ids=list(first), semantic_role="concept", visual_priority="high",
                   component_intent="concept_explainer", reasoning="第一个术语用卡片解释。")
    plain = dict(source_block_ids=[middle[1]], semantic_role="plain_narrative", visual_priority="medium",
                 component_intent="plain", reasoning="第二个术语的说明保持普通正文。")
    raw.update(image_intents=[], sections=[plain, concept] if plain_first else [concept, plain])
    brief, _ = normalize_editorial_brief_for_article(raw, article)
    plan = compile_editorial_brief(article, brief, 5)
    assert any(set(first) <= set(s["consume_block_ids"]) for s in plan["slots"])
    assert all(middle[1] not in s["consume_block_ids"] for s in plan["slots"])
