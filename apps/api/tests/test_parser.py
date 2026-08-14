from visual_director.parser import classify_article, parse_markdown


def test_parser_extracts_frontmatter_sections_table_and_steps() -> None:
    article = parse_markdown(
        """---
title: 测试文章
article_type: tutorial_steps
---
# 测试文章

导语内容。

## 第一步

1. 核对数据
2. 保存结果

| 项目 | 结果 |
|---|---|
| 标题 | 通过 |
"""
    )
    assert article.title == "测试文章"
    assert article.section_count == 1
    assert {block.type for block in article.blocks} >= {"heading", "ordered_list", "table"}
    assert classify_article(article) == "tutorial_steps"


def test_horizontal_rules_become_thematic_breaks_and_images_are_structured() -> None:
    article = parse_markdown(
        """---
title: 真实稿件结构
---
# 真实稿件结构

---

![章节占位图](https://picsum.photos/800/400?random=1)

## 第一步

正文内容。
"""
    )
    assert article.image_reference_count == 1
    thematic_break = next(block for block in article.blocks if block.type == "thematic_break")
    assert thematic_break.content == "---"
    image_block = next(block for block in article.blocks if block.type == "image_reference")
    assert image_block.content == {
        "alt": "章节占位图",
        "source": "https://picsum.photos/800/400?random=1",
        "placeholder": True,
    }


def test_blockquoted_and_bold_source_lines_are_metadata_not_quotes() -> None:
    article = parse_markdown(
        """# 来源层级

正文内容。

> 数据来源：浙江省教育考试院

> 📊 **数据来源：** 教育部公开文件

> 政策来源：教育发展规划

> 核验来源：全国高等学校名单
"""
    )
    sources = [block for block in article.blocks if block.type == "source"]
    assert len(sources) == 4
    assert not [block for block in article.blocks if block.type == "quote"]


def test_reference_link_lists_have_source_semantics_instead_of_action_semantics() -> None:
    article = parse_markdown(
        """# 专业调整观察

## 可靠来源

- [教育部：本科专业目录](https://www.moe.gov.cn/example)
- [高校：专业培养方案](https://www.example.edu.cn/plan)
"""
    )
    references = [block for block in article.blocks if block.type == "reference_list"]
    assert len(references) == 1
    assert len(references[0].content) == 2
    assert not [block for block in article.blocks if block.type == "unordered_list"]


def test_decorative_emoji_lines_become_a_content_preserving_list() -> None:
    article = parse_markdown(
        """# 志愿核对

### 填报时怎么操作？

🟥 如果只想报本部，就填写本部代码
🟦 如果只想报医学，就填写医学院代码
🟧 如果两个都想报，可以分别排序

⚠️ 单独一条风险提示仍然保留为普通段落。
"""
    )

    lists = [block for block in article.blocks if block.type == "unordered_list"]
    assert len(lists) == 1
    assert lists[0].content == [
        "如果只想报本部，就填写本部代码",
        "如果只想报医学，就填写医学院代码",
        "如果两个都想报，可以分别排序",
    ]
    assert any(
        block.type == "paragraph" and "单独一条风险提示" in str(block.content)
        for block in article.blocks
    )


def test_article_structure_classification_is_not_limited_to_education_content() -> None:
    data_article = parse_markdown(
        """# 隐私新规落地后，企业需要核对哪些指标

监管部门发布最新政策与合规标准。报告列出了数据处理成本、统计口径和公开规则。
"""
    )
    story_article = parse_markdown(
        """# 一家社区咖啡店如何重新找到客人

这是一个真实品牌案例。主理人通过访谈复盘创业经历，并讲述门店从低谷到恢复的故事。
"""
    )

    assert classify_article(data_article) == "data_policy"
    assert classify_article(story_article) == "lively_growth"
