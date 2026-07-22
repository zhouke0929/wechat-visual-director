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


def test_horizontal_rules_are_not_paragraphs_and_images_are_structured() -> None:
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
    assert all(block.content != "---" for block in article.blocks)
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
"""
    )
    sources = [block for block in article.blocks if block.type == "source"]
    assert len(sources) == 2
    assert not [block for block in article.blocks if block.type == "quote"]


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
