from visual_director.publication import _materialized_image_markup, _placeholder_metadata


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
