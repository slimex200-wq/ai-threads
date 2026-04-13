from telegram_notify import _format_text_preview


def test_preview_includes_source_and_media_fields():
    text = _format_text_preview(
        {
            "mode": "informational",
            "selected_article": {
                "original_title": "Article title",
                "reason": "Because it matters",
            },
            "post_main": "Main body",
            "replies": ["Reply one"],
            "source_link": "https://example.com/article",
            "video_url": "https://example.com/video.mp4",
            "og_image": "https://example.com/image.jpg",
            "media_plan": {"preferred_type": "video", "search_query": "demo", "reason": "good fit"},
        }
    )

    assert "source link" in text
    assert "https://example.com/article" in text
    assert "Video" in text
    assert "OG image" in text


def test_preview_uses_compact_sections_for_readability():
    text = _format_text_preview(
        {
            "mode": "informational",
            "selected_article": {
                "original_title": "Article title",
                "reason": "Because it matters",
            },
            "post_main": "Main body",
            "replies": ["Reply one", "Reply two"],
            "source_link": "https://example.com/article",
            "media_plan": {"preferred_type": "video", "search_query": "demo", "reason": "good fit"},
        }
    )

    assert "Selected article" in text
    assert "Main post" in text
    assert "Replies" in text
