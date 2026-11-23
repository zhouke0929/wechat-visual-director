"""A layout candidate may never consume a block explicitly reserved as plain."""
from visual_director.parser import parse_markdown
from visual_director.planner import supplement_component_coverage


def test_reserved_list_remains_available_to_ordinary_renderer():
    article = parse_markdown("# 核验事项\n\n## 行动清单\n\n- 复核文件。\n- 确认签名。")
    protected = next(block.id for block in article.blocks if block.type == "unordered_list")
    candidates, _, _ = supplement_component_coverage(article, [])
    assert any(protected in slot["consume_block_ids"] for slot in candidates)
    candidates, _, _ = supplement_component_coverage(article, [], plain_block_ids={protected})
    assert all(protected not in slot["consume_block_ids"] for slot in candidates)
