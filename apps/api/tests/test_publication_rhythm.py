import pytest

from visual_director.publication import (
    _materialized_image_markup,
    _placeholder_metadata,
    check_frozen_html,
    describe_html_compatibility_blockers,
    render_frozen_asset_urls,
    replace_asset_urls,
)
from visual_director.renderer import preserve_wechat_decorative_nodes


@pytest.mark.parametrize("caption", ["", "  ", "原图说明"])
def test_custom_image_layout_omits_only_absent_captions(caption: str) -> None:
    from visual_director.brief_compiler import visual_system_configuration

    theme = visual_system_configuration("light_reading")
    theme["palette"] = {"ink": "#222222"}
    theme["generated_design_system"] = {
        "typography": {"body_scale": 1, "heading_scale": 1, "letter_spacing": "normal", "heading_weight": 700},
        "rhythm": {"density": "balanced", "section_gap": 20, "component_gap": 14},
        "layouts": {
            "image_caption": {
                "type": "stack",
                "children": [
                    {"type": "media"},
                    {"type": "field", "bind": "caption", "style": {"size": "label", "align": "center"}},
                ],
            },
        },
    }
    markup = _materialized_image_markup(
        element_id="slot-01", anchor_class="image-slot-anchor",
        content_url="asset://candidate", width=1200, height=675, alt="原图",
        frame_variant="neutral", caption_html=caption, theme_config=theme,
    )
    assert 'src="asset://candidate"' in markup
    assert ('data-theme-field="caption"' in markup) == bool(caption.strip())
    if caption.strip():
        assert caption in markup
    assert check_frozen_html(markup).status == "pass"


def test_compatibility_blocker_explains_real_uncontrolled_image() -> None:
    report = check_frozen_html('<main><img src="https://example.com/uncontrolled.png"></main>')
    assert report.status == "blocking"
    assert "未进入本地资产库的图片" in describe_html_compatibility_blockers(report.messages)


def test_frozen_checks_distinguish_prose_from_actual_placeholders_and_tags() -> None:
    assert check_frozen_html("<main><p>标题用 Image Plan · 夏天，别放 Source Image · Waiting。</p>"
                             "<p>配置说明：onclick = 默认行为</p></main>").status == "pass"
    legacy = check_frozen_html(
        '<section id="photo" class="source-image-anchor" data-image-caption="">原稿图</section>'
        '<section id="slot" class="image-slot-anchor" data-image-caption="">计划配图</section>'
    )
    assert legacy.checks["no_waiting_source_images"] == "blocking"
    assert legacy.checks["no_waiting_planned_images"] == "blocking"
    assert check_frozen_html('<section class="image-slot-anchor"><img src="asset://photo"></section>').status == "pass"
    assert check_frozen_html("<p onclick='event'>测试</p>").checks["no_event_handlers"] == "blocking"
    assert check_frozen_html("<img src='https://example.com/uncontrolled.png'>").checks["controlled_image_sources"] == "blocking"


def test_placeholder_metadata_preserves_theme_frame_and_reliable_caption() -> None:
    frame, caption = _placeholder_metadata(
        '<section data-image-frame="warm_storybook" '
        'data-image-caption="志愿核对流程示意"></section>'
    )
    assert frame == "warm_storybook"
    assert caption == "志愿核对流程示意"


def test_generated_image_uses_theme_frame_without_inventing_caption() -> None:
    document = _materialized_image_markup(
        element_id="image-slot-01",
        anchor_class="image-slot-anchor",
        content_url="asset://candidate-01",
        width=1200,
        height=675,
        alt="运营已确认的文章配图",
        frame_variant="editorial_masthead",
    )
    assert 'data-image-frame="editorial_masthead"' in document
    assert "border-top:11px solid #202B33" in document
    assert 'data-content-role="image-caption"' not in document


def test_source_image_keeps_verified_alt_as_low_emphasis_caption() -> None:
    document = _materialized_image_markup(
        element_id="block-004",
        anchor_class="source-image-anchor",
        content_url="asset://source-01",
        width=1080,
        height=720,
        alt="志愿核对流程示意",
        frame_variant="airy_organic",
        caption_html="志愿核对流程示意",
    )
    assert 'data-content-role="image-caption"' in document
    assert "志愿核对流程示意" in document
    assert "font-size:11px" in document


def test_wechat_decorative_nodes_are_nonempty_before_publication() -> None:
    unsafe = (
        '<main><p style="margin:12px 0 0;">'
        '<span style="display:inline-block;width:42px;height:3px;background-color:#D98268;"></span>'
        '<span style="display:inline-block;width:10px;height:10px;background-color:#DDBD61;"></span>'
        "</p></main>"
    )
    assert check_frozen_html(unsafe).checks["no_empty_decorative_nodes"] == "blocking"

    preserved = preserve_wechat_decorative_nodes(unsafe)
    assert preserved.count("&#160;") == 2
    assert check_frozen_html(preserved).status == "pass"


def test_cleanup_omits_inert_fields_but_keeps_actual_geometry_and_text():
    document = (
        '<main><p>演示 src="asset://a" 与 &lt;span style="height:20px"&gt;&lt;/span&gt;。</p>'
        '<span style="max-width:100%;color:#333;"></span>'
        "<p data-theme-field='caption' style='border:0;width:auto;'></p>"
        '<span style="height:0;width:0;border-top:6px solid #234;"></span>'
        "<span style='height:8px;'></span>"
        '<span style="max-width:100%;">&#160;</span>'
        '<p style="width:0;margin:-10px 0;"></p>'
        '<!-- <span style="width:99px;"></span> -->'
        '</main>'
    )
    normalized = preserve_wechat_decorative_nodes(document)
    assert 'max-width:100%;color:#333' not in normalized
    assert 'border:0;width:auto;' not in normalized
    assert normalized.count("&#160;") == 4
    assert '演示 src="asset://a"' in normalized
    assert '<!-- <span style="width:99px;"></span> -->' in normalized
    assert preserve_wechat_decorative_nodes(normalized) == normalized
    assert check_frozen_html(normalized).status == "pass"


def test_media_validation_and_rewriting_only_consider_real_image_src():
    original = (
        '<main><p>参数示例 src="/api/example.png"；交付协议 asset://cover。</p>'
        '<span title=\'src="/api/example.png"\'>说明</span>'
        "<IMG alt='图片' SRC='/api/example.png' width='120' />"
        '</main>'
    )
    frozen = replace_asset_urls(original, {"/api/example.png": "body-one"})
    assert frozen.count('/api/example.png') == 2
    assert 'SRC="asset://body-one"' in frozen
    assert check_frozen_html(frozen, asset_tokens={"body-one"}).status == "pass"
    assert check_frozen_html(frozen, asset_tokens={"cover"}).checks["controlled_image_sources"] == "blocking"
    assert check_frozen_html('<img src="asset://body-one" src="asset://body-one">', asset_tokens={"body-one"}).status == "blocking"
    assert check_frozen_html('<img src="asset://">').status == "blocking"
    rendered = render_frozen_asset_urls(frozen, {"body-one": "https://example.test/p.png?x=1&y=2"})
    assert 'SRC="https://example.test/p.png?x=1&amp;y=2"' in rendered
    assert '交付协议 asset://cover' in rendered
