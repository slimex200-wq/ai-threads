"""QA evaluator tests for freeform and legacy thread structures."""

from qa_evaluator import _EVAL_PROMPT, _check_rules


def _make_freeform_content() -> dict:
    return {
        "post_main": "A" * 240,
        "replies": [
            "B" * 100,
            "C" * 120,
            "D" * 90,
        ],
        "selected_article": {
            "original_title": "Test Article",
            "link": "https://example.com",
            "reason": "Useful because it changes a real workflow.",
        },
        "media_plan": {
            "preferred_type": "video",
            "search_query": "Gemini CLI demo",
            "reason": "The article is about Gemini CLI and a short demo helps shares.",
        },
        "topic_tag": "ai.threads",
    }


def _make_legacy_informational_content() -> dict:
    return {
        "post_main": "A" * 250,
        "reply_background": "B" * 120,
        "reply_impact": "C" * 120,
        "reply_compare": "D" * 120,
        "reply_summary": "E" * 100,
        "selected_article": {
            "original_title": "Test Article",
            "link": "https://example.com",
            "reason": "Useful because it changes a real workflow.",
        },
        "topic_tag": "ai.threads",
    }


def _make_legacy_viral_content() -> dict:
    return {
        "post_main": "A" * 250 + "?",
        "reply_explain": "B" * 100,
        "reply_important": "C" * 100,
        "reply_action": "D" * 100,
        "reply_counter": "E" * 100,
        "reply_casual": "F" * 60,
        "selected_article": {
            "original_title": "Test Article",
            "link": "https://example.com",
            "reason": "Useful because it changes a real workflow.",
        },
        "topic_tag": "ai.threads",
    }


def test_freeform_valid():
    issues = _check_rules(_make_freeform_content(), mode="informational")
    assert issues == []


def test_freeform_requires_replies():
    content = _make_freeform_content()
    content["replies"] = []

    issues = _check_rules(content, mode="informational")

    assert any("replies" in issue for issue in issues)


def test_freeform_banned_pattern_detected():
    content = _make_freeform_content()
    content["replies"][1] = "Useful recap with #AI hashtag"

    issues = _check_rules(content, mode="informational")

    assert any("#" in issue for issue in issues)


def test_freeform_allows_compact_but_valid_main_post():
    content = _make_freeform_content()
    content["post_main"] = "A" * 165

    issues = _check_rules(content, mode="informational")

    assert not any("post_main too short" in issue for issue in issues)


def test_legacy_informational_still_works():
    issues = _check_rules(_make_legacy_informational_content(), mode="informational")
    assert issues == []


def test_legacy_viral_still_works():
    issues = _check_rules(_make_legacy_viral_content(), mode="viral")
    assert issues == []


def test_eval_prompt_template_formats_cleanly():
    rendered = _EVAL_PROMPT.format(
        article_title="Title",
        article_reason="Reason",
        post_main="Main body",
        replies_text="1. Reply",
    )

    assert '"clarity"' in rendered
    assert "{article_title}" not in rendered
