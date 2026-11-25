import html
import re

import pytest
from bs4 import BeautifulSoup

from visual_director.logic_path_content import LogicPathField, step_field_text
from visual_director.reading_rules import STEP_TITLE, resolve_reading_profile
from visual_director.step_content import interpret_step


@pytest.fixture(autouse=True)
def enable_metric_trial(monkeypatch):
    monkeypatch.setenv("WVD_RENDERER_PILOT", "1")
    monkeypatch.setenv("WVD_READING_RULES_PILOT", "1")


def profile_for_trial():
    return resolve_reading_profile({"reading_overrides": {STEP_TITLE: {"weight": 750}}},
                                   official=True, theme_id="pop_poster")


def render(source, *, configured=True):
    profile = profile_for_trial() if configured else None
    field = LogicPathField("block-001:item:0", interpret_step(source), profile)
    return BeautifulSoup(step_field_text(field, lambda s: re.sub(
        r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(s))), "html.parser")


@pytest.mark.parametrize("sep", [" ", "  ", "\t", "\n"])
def test_step_title_presentation_keeps_editable_markdown_and_detail_emphasis(sep):
    source = f"**先核对基本信息。**{sep}分别确认**报名时间**。"
    out = render(source)
    assert out.strong.string == "先核对基本信息。"
    if sep != "\n":
        assert not out.find(["span", "br"])
        assert [s.string for s in out.find_all("strong")] == ["先核对基本信息。", "报名时间"]
        raw = step_field_text(LogicPathField("", interpret_step(source), profile_for_trial()), lambda s: s)
        assert raw == source
        return
    assert out.span.strong.string == "报名时间"
    assert "display:block" in out.span["style"]
    # Check the original HTML rather than a DOM library's whitespace normalization.
    raw = step_field_text(LogicPathField("", interpret_step(source), profile_for_trial()), lambda s: s)
    assert "</strong>" + sep + "<span" in raw


@pytest.mark.parametrize("source", [
    "先核对基本信息。 接下来读正文。", "**报名时间** 请再确认。", "**注意：** 时间有变。",
    "**先核对。**", "**这是强调。**下一句没有分隔。", "正文中**有重点。** 仍是正文。",
    "**第一句。第二句。** 后面还有说明。", "**先检查。**   ",
])
def test_keep_prose_and_short_items_inline(source):
    assert render(source).span is None


def test_unconfigured_theme_does_not_split_a_run_in_title():
    assert render("**先核对基本信息。** 阅读说明。", configured=False).span is None
