from dataclasses import dataclass

from notion_review import build_approved_query_payload, build_published_update_payload, build_review_payload, review_page_to_content


@dataclass(frozen=True)
class FakeQA:
    passed: bool
    score: float
    issues: tuple[str, ...]
    suggestions: tuple[str, ...]


def _content() -> dict:
    return {
        "content_brief": {
            "topic": "AI agent workflows",
            "target_reader": "developers",
            "reader_problem": "They need to know what is worth trying.",
            "promise": "Explain the useful workflow implication.",
            "angle": "The workflow change is the story.",
            "why_now": "Teams are adopting these tools now.",
            "takeaway": "Try it on one bounded task before rollout.",
        },
        "selected_article": {
            "original_title": "Useful AI launch",
            "link": "https://example.com/article",
            "reason": "It changes a real workflow.",
        },
        "post_main": "Main post body",
        "replies": ["Reply one", "Reply two"],
        "media_plan": {"preferred_type": "video", "reason": "A demo helps review."},
        "video_url": "https://cdn.example.com/demo.mp4",
    }


def test_build_review_payload_maps_core_properties():
    payload = build_review_payload(
        _content(),
        FakeQA(passed=True, score=0.86, issues=(), suggestions=()),
        database_id="database-id",
    )

    assert payload["parent"] == {"database_id": "database-id"}
    props = payload["properties"]
    assert props["Status"]["select"]["name"] == "Review"
    assert props["Channel"]["select"]["name"] == "Threads"
    assert props["Media Type"]["select"]["name"] == "video"
    assert props["Media Approved"]["checkbox"] is False
    assert props["QA Score"]["number"] == 0.86
    assert props["Article URL"]["url"] == "https://example.com/article"
    assert payload["children"]
    assert payload["children"][0]["type"] == "callout"
    checklist = payload["children"][0]["callout"]["rich_text"][0]["text"]["content"]
    assert "Post Main" in checklist
    assert "Status" in checklist


def test_review_page_to_content_converts_approved_row():
    page = {
        "id": "page-id",
        "properties": {
            "Title": {"type": "title", "title": [{"plain_text": "Useful AI launch"}]},
            "Topic": {"type": "rich_text", "rich_text": [{"plain_text": "AI agent workflows"}]},
            "Target Reader": {"type": "rich_text", "rich_text": [{"plain_text": "developers"}]},
            "Reader Problem": {"type": "rich_text", "rich_text": [{"plain_text": "They need signal."}]},
            "Content Goal": {"type": "rich_text", "rich_text": [{"plain_text": "Show the useful implication."}]},
            "CTA": {"type": "rich_text", "rich_text": [{"plain_text": "Try one bounded task."}]},
            "Source Title": {"type": "rich_text", "rich_text": [{"plain_text": "Source title"}]},
            "Article URL": {"type": "url", "url": "https://example.com/article"},
            "Post Main": {"type": "rich_text", "rich_text": [{"plain_text": "Main post"}]},
            "Replies": {"type": "rich_text", "rich_text": [{"plain_text": "1. First line\nstill first\n\n2. Second"}]},
            "Media Type": {"type": "select", "select": {"name": "video"}},
            "Media Publish URL": {"type": "url", "url": "https://cdn.example.com/demo.mp4"},
            "Media Approved": {"type": "checkbox", "checkbox": True},
            "Notes": {"type": "rich_text", "rich_text": [{"plain_text": "Angle notes"}]},
        },
    }

    content = review_page_to_content(page)

    assert content["post_main"] == "Main post"
    assert content["replies"] == ["First line\nstill first", "Second"]
    assert content["selected_article"]["link"] == "https://example.com/article"
    assert content["content_brief"]["target_reader"] == "developers"
    assert content["video_url"] == "https://cdn.example.com/demo.mp4"


def test_review_page_to_content_requires_media_approval_for_media_url():
    page = {
        "properties": {
            "Post Main": {"type": "rich_text", "rich_text": [{"plain_text": "Main post"}]},
            "Replies": {"type": "rich_text", "rich_text": [{"plain_text": "1. First"}]},
            "Media Type": {"type": "select", "select": {"name": "image"}},
            "Media Publish URL": {"type": "url", "url": "https://cdn.example.com/image.png"},
            "Media Approved": {"type": "checkbox", "checkbox": False},
        },
    }

    content = review_page_to_content(page)

    assert "og_image" not in content


def test_build_published_update_payload_sets_status_and_post_id():
    payload = build_published_update_payload(
        {"post_id": "threads-post-id", "permalink": "https://threads.net/post/threads-post-id"},
        published_on="2026-05-10",
    )

    props = payload["properties"]
    assert props["Status"]["select"]["name"] == "Published"
    assert props["Post ID"]["rich_text"][0]["text"]["content"] == "threads-post-id"
    assert props["Threads URL"]["url"] == "https://threads.net/post/threads-post-id"
    assert props["Publish Date"]["date"]["start"] == "2026-05-10"


def test_build_approved_query_payload_sorts_recently_approved_first():
    payload = build_approved_query_payload(limit=150)

    assert payload["filter"] == {"property": "Status", "select": {"equals": "Approved"}}
    assert payload["sorts"] == [{"timestamp": "last_edited_time", "direction": "descending"}]
    assert payload["page_size"] == 100
