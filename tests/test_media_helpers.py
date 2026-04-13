from media_helpers import build_content_with_media, normalize_source_link


def test_normalize_source_link_quotes_path_but_keeps_query():
    raw = "https://example.com/news/article title?idxno=123&foo=bar"

    normalized = normalize_source_link(raw)

    assert "article%20title" in normalized
    assert "idxno=123" in normalized


def test_build_content_with_media_merges_preview_fields():
    content = {"post_main": "main", "replies": ["one"]}

    merged = build_content_with_media(
        content,
        source_link="https://example.com/a",
        og_image="https://example.com/image.jpg",
        video_url="https://example.com/video.mp4",
    )

    assert merged["source_link"] == "https://example.com/a"
    assert merged["og_image"] == "https://example.com/image.jpg"
    assert merged["video_url"] == "https://example.com/video.mp4"
