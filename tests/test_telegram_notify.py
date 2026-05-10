from telegram_notify import _format_text_preview


def test_preview_includes_source_and_media_fields():
    text = _format_text_preview(
        {
            "mode": "informational",
            "content_brief": {
                "target_reader": "developers",
                "reader_problem": "They need a practical signal",
                "angle": "Workflow impact beats hype",
                "takeaway": "Try it on one bounded task",
            },
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
    assert "Content brief" in text
    assert "Workflow impact beats hype" in text
    assert "https://example.com/article" in text
    assert "Video" in text
    assert "OG image" in text


def test_preview_uses_compact_sections_for_readability():
    text = _format_text_preview(
        {
            "mode": "informational",
            "content_brief": {
                "target_reader": "beginners",
                "reader_problem": "Too many announcements",
                "angle": "Explain the one useful difference",
                "takeaway": "Use the update only where it saves a step",
            },
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
