from visual_director.preflight import normalize_markdown, run_preflight


def test_normalization_preserves_markdown_hard_breaks() -> None:
    normalized, repairs = normalize_markdown("\ufeff# 标题\r\n第一行  \r\n第二行\\\r\n第三行   \r\n")

    assert normalized == "# 标题\n第一行  \n第二行\\\n第三行   \n"
    assert {repair.code for repair in repairs} == {"utf8_bom_removed", "line_endings_normalized"}


def test_preflight_requires_referenced_cover_to_be_imported_before_draft() -> None:
    result = run_preflight(
        """---
title: 三步核对志愿
cover: ./cover.jpg
article_type: tutorial_steps
---
# 三步核对志愿

先明确目标。

## 第一步

核对官方数据。
"""
    )

    assert result.report.status == "REVIEW"
    assert result.report.planning_allowed is True
    assert result.report.draft_creation_allowed is False
    assert {finding.code for finding in result.report.findings} == {"cover_requires_import"}
    assert result.parsed is not None
    assert result.report.source_hash == result.parsed.source_hash


def test_preflight_allows_constrained_planning_for_title_conflict_but_blocks_heading_jump() -> None:
    result = run_preflight(
        """---
title: Frontmatter 标题
cover: ./cover.jpg
---
# 正文标题

## 主章节

#### 跳级小节

正文。
"""
    )

    findings = {finding.code: finding for finding in result.report.findings}
    assert result.report.status == "REVIEW"
    assert findings["title_source_conflict"].resolution_policy == "ACKNOWLEDGE"
    assert findings["title_source_conflict"].planning_blocking is False
    assert findings["heading_level_jump"].planning_blocking is True
    assert result.report.planning_allowed is False


def test_placeholder_and_missing_cover_allow_planning_but_block_draft() -> None:
    result = run_preflight(
        """# 图片测试

## 第一节

![占位图](https://picsum.photos/800/400)
"""
    )

    assert result.report.status == "REVIEW"
    assert result.report.planning_allowed is True
    assert result.report.draft_creation_allowed is False
    assert {finding.code for finding in result.report.findings} >= {"missing_cover", "placeholder_image"}


def test_sensitive_credentials_are_hard_blocked_without_echoing_secret() -> None:
    secret = "sk-" + "this-value-must-never-be-returned"
    result = run_preflight(f"# 测试\n\nAPI_KEY={secret}\n")
    serialized = str(result.report.to_dict())

    assert result.report.status == "BLOCK"
    assert result.report.planning_allowed is False
    assert result.report.draft_creation_allowed is False
    assert "sensitive_credentials" in serialized
    assert secret not in serialized
