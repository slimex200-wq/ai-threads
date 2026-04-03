"""QA Evaluator — informational 모드 규칙 검증 테스트."""

from qa_evaluator import _check_rules, QAResult


def _make_informational_content() -> dict:
    return {
        "post_main": "A" * 250,
        "reply_background": "B" * 120,
        "reply_impact": "C" * 120,
        "reply_compare": "D" * 120,
        "reply_summary": "E" * 100,
        "selected_article": {
            "original_title": "Test Article",
            "link": "https://example.com",
            "reason": "테스트",
        },
        "topic_tag": "ai.threads",
    }


def _make_viral_content() -> dict:
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
            "reason": "테스트",
        },
        "topic_tag": "ai.threads",
    }


def test_informational_valid():
    issues = _check_rules(_make_informational_content(), mode="informational")
    assert issues == []


def test_informational_missing_reply_background():
    content = _make_informational_content()
    del content["reply_background"]
    issues = _check_rules(content, mode="informational")
    assert any("reply_background" in i for i in issues)


def test_informational_post_main_too_short():
    content = _make_informational_content()
    content["post_main"] = "A" * 150
    issues = _check_rules(content, mode="informational")
    assert any("post_main" in i and "미달" in i for i in issues)


def test_informational_post_main_too_long():
    content = _make_informational_content()
    content["post_main"] = "A" * 450
    issues = _check_rules(content, mode="informational")
    assert any("post_main" in i and "초과" in i for i in issues)


def test_informational_banned_pattern():
    content = _make_informational_content()
    content["post_main"] = "A" * 250 + "#AI"
    issues = _check_rules(content, mode="informational")
    assert any("#" in i for i in issues)


def test_viral_still_works():
    issues = _check_rules(_make_viral_content(), mode="viral")
    assert issues == []


def test_viral_missing_reply_casual():
    content = _make_viral_content()
    del content["reply_casual"]
    issues = _check_rules(content, mode="viral")
    assert any("reply_casual" in i for i in issues)


def test_informational_no_question_required():
    content = _make_informational_content()
    content["post_main"] = "A" * 250  # no question mark
    issues = _check_rules(content, mode="informational")
    assert not any("질문" in i for i in issues)
