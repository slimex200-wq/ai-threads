"""QA evaluator tests for freeform and legacy thread structures."""

import qa_evaluator
from qa_evaluator import _EVAL_PROMPT, _check_rules, evaluate


def _make_freeform_content() -> dict:
    return {
        "content_brief": {
            "topic": "AI agent workflows",
            "target_reader": "developers and vibe coders",
            "reader_problem": "They do not know which agent update matters in practice.",
            "promise": "Show the one workflow implication worth trying.",
            "angle": "The update matters only if it changes daily work.",
            "why_now": "Teams are adopting agent tooling right now.",
            "takeaway": "Test the workflow on one bounded task before broad rollout.",
        },
        "post_main": "A" * 180,
        "replies": [chr(66 + index) * 90 for index in range(12)],
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
        "content_brief": {
            "topic": "AI agent workflows",
            "target_reader": "developers",
            "reader_problem": "They need a practical signal.",
            "promise": "Explain the useful implication.",
            "angle": "Workflow impact beats feature hype.",
            "why_now": "The feature just shipped.",
            "takeaway": "Try it on one small workflow.",
        },
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
        "content_brief": {
            "topic": "AI coding tools",
            "target_reader": "vibe coders",
            "reader_problem": "They need to know what is worth attention.",
            "promise": "Show why this update matters.",
            "angle": "The workflow change is the story.",
            "why_now": "The market is shifting quickly.",
            "takeaway": "Compare the tool on a real task.",
        },
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
    content["replies"] = ["Only one reply is not enough for a thread"]

    issues = _check_rules(content, mode="informational")

    assert any("at least 2" in issue for issue in issues)


def test_freeform_banned_pattern_detected():
    content = _make_freeform_content()
    content["replies"][1] = "Useful recap with #AI hashtag"

    issues = _check_rules(content, mode="informational")

    assert any("#" in issue for issue in issues)


def test_freeform_rejects_monotone_da_endings():
    content = _make_freeform_content()
    content["post_main"] = "이 글은 첫 줄에서 기준을 보여준다.\n독자는 여기서 읽을 이유를 찾는다."
    content["replies"] = [
        "첫 번째 답글은 사실을 설명한다.\n두 번째 줄도 같은 어미로 닫힌다.\n세 번째 줄 역시 보고서처럼 끝난다.",
        "다음 답글도 정보를 전달한다.\n중간 문장도 계속 같은 리듬이다.\n마지막 문장까지 모두 판정문처럼 들린다.",
    ]

    issues = _check_rules(content, mode="informational")

    assert any("too many Korean lines end with '-다'" in issue for issue in issues)


def test_freeform_allows_compact_but_valid_main_post():
    content = _make_freeform_content()
    content["post_main"] = "A" * 90

    issues = _check_rules(content, mode="informational")

    assert not any("post_main too short" in issue for issue in issues)


def test_freeform_rejects_dense_threads_formatting():
    content = _make_freeform_content()
    content["replies"][0] = (
        "\uc774 \uae00\uc740 \uccab \uc904\uc5d0\uc11c \uae30\uc900\uc744 \ubcf4\uc5ec\uc90d\ub2c8\ub2e4.\n"
        "\ub450 \ubc88\uc9f8 \uc904\uc740 \uadf8 \uc774\uc720\ub97c \uc124\uba85\ud569\ub2c8\ub2e4.\n"
        "\uc138 \ubc88\uc9f8 \uc904\uc740 \uc2e4\uc81c \uc791\uc5c5\uc5d0 \uc801\uc6a9\ud560 \uae30\uc900\uc744 \uc815\ub9ac\ud569\ub2c8\ub2e4."
    )

    issues = _check_rules(content, mode="informational")

    assert any("visually dense for Threads" in issue for issue in issues)


def test_freeform_rejects_overlong_visual_line():
    content = _make_freeform_content()
    content["replies"][0] = (
        "\uc88b\uc740 \ub370\ubaa8\ub294 '\ubb34\uc5c7\uc744 \ud588\ub294\uac00'\ubcf4\ub2e4 "
        "'\uc5b4\ub514\uae4c\uc9c0 \uc0ac\ub78c\uc774 \uac1c\uc785\ud588\ub294\uac00'\ub97c \ubcf4\uc5ec\uc90d\ub2c8\ub2e4."
    )

    issues = _check_rules(content, mode="informational")

    assert any("too long for Threads" in issue for issue in issues)


def test_legacy_informational_still_works():
    issues = _check_rules(_make_legacy_informational_content(), mode="informational")
    assert issues == []


def test_legacy_viral_still_works():
    issues = _check_rules(_make_legacy_viral_content(), mode="viral")
    assert issues == []


def test_content_brief_is_required():
    content = _make_freeform_content()
    content["content_brief"]["takeaway"] = ""

    issues = _check_rules(content, mode="informational")

    assert "content_brief.takeaway is required" in issues


def test_eval_prompt_template_formats_cleanly():
    rendered = _EVAL_PROMPT.format(
        brief_topic="Topic",
        brief_target_reader="Reader",
        brief_reader_problem="Problem",
        brief_promise="Promise",
        brief_angle="Angle",
        brief_why_now="Now",
        brief_takeaway="Takeaway",
        article_title="Title",
        article_reason="Reason",
        article_evidence="Evidence",
        article_summary="Summary",
        article_details="Details",
        post_main="Main body",
        replies_text="1. Reply",
    )

    assert '"clarity"' in rendered
    assert '"actionable_takeaway"' in rendered
    assert "Content brief" in rendered
    assert "short-line essay rhythm" in rendered
    assert "direction of attention" in rendered
    assert "inverted pyramid" in rendered
    assert "{article_title}" not in rendered


def test_ai_critical_issue_blocks_pass(monkeypatch):
    def fake_eval(content, mode="informational"):
        return {
            "clarity": 9,
            "usefulness": 9,
            "accuracy": 9,
            "shareability": 9,
            "thread_flow": 9,
            "hook_clarity": 9,
            "reader_fit": 9,
            "specificity": 9,
            "actionable_takeaway": 9,
            "grounding": 9,
            "critical_issues": ["final reply has no practical takeaway"],
            "suggestions": ["Add a concrete next step."],
        }

    monkeypatch.setattr(qa_evaluator, "_evaluate_with_ai", fake_eval)

    result = evaluate(_make_freeform_content(), mode="informational")

    assert not result.passed
    assert any("final reply" in issue for issue in result.issues)


def test_low_ship30_dimension_blocks_pass(monkeypatch):
    def fake_eval(content, mode="informational"):
        return {
            "clarity": 9,
            "usefulness": 9,
            "accuracy": 9,
            "shareability": 9,
            "thread_flow": 9,
            "hook_clarity": 9,
            "reader_fit": 9,
            "specificity": 9,
            "actionable_takeaway": 4,
            "grounding": 9,
            "critical_issues": [],
            "suggestions": ["Make the final reply useful."],
        }

    monkeypatch.setattr(qa_evaluator, "_evaluate_with_ai", fake_eval)

    result = evaluate(_make_freeform_content(), mode="informational")

    assert not result.passed
    assert any("actionable_takeaway below threshold" in issue for issue in result.issues)
