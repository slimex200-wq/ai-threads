from ai_writer import _ensure_required_fields, build_prompt


def test_build_prompt_includes_grounding_rules():
    prompt = build_prompt(
        articles=[{"title": "Test", "summary": "Summary", "source": "Source", "link": "https://example.com"}],
        mode="informational",
    )

    assert "do not" in prompt.lower()
    assert "do not invent facts" in prompt
    assert "Title, Summary, or Details" in prompt
    assert "60~260" in prompt
    assert "<br>" in prompt
    assert "STANDING INTERNET WRITING REFERENCE" in prompt
    assert "Internet readers usually decide before they read" in prompt
    assert "inverted pyramid" in prompt
    assert "first sentence" in prompt
    assert "CTA" in prompt
    assert "explanatory voice" in prompt
    assert "not bulletin voice" in prompt
    assert "<br><br>" in prompt
    assert "actual narrow Threads timeline" in prompt
    assert "one small point per reply" in prompt
    assert "compact article: 2~4 replies" in prompt
    assert "normal article: 4~6 replies" in prompt
    assert "deep article with real mechanisms, tradeoffs, or examples: 7~9 replies" in prompt


def test_build_prompt_requires_ship30_content_brief():
    prompt = build_prompt(
        articles=[{"title": "Agent marketplace", "summary": "Agents trade with each other"}],
        mode="informational",
    )

    assert '"content_brief"' in prompt
    assert '"target_reader"' in prompt
    assert '"reader_problem"' in prompt
    assert "first-line CTA -> thesis -> proof -> tradeoff -> criterion -> takeaway" in prompt
    assert "concrete decision rule" in prompt
    assert "unclejobs.ai" in prompt
    assert "prefer fewer replies" in prompt


def test_line_break_tokens_are_normalized():
    content = _ensure_required_fields(
        {
            "post_main": "첫 줄<br>둘째 줄",
            "replies": ["하나<br>둘"],
        }
    )

    assert content["post_main"] == "첫 줄\n둘째 줄"
    assert content["replies"] == ["하나\n둘"]


def test_blank_line_tokens_are_preserved():
    content = _ensure_required_fields(
        {
            "post_main": "First<br><br>Second",
            "replies": ["One<br><br>Two"],
        }
    )

    assert content["post_main"] == "First\n\nSecond"
    assert content["replies"] == ["One\n\nTwo"]


def test_prompt_uses_json_safe_candidate_titles():
    prompt = build_prompt(
        articles=[{"title": 'A launch with "quoted" text', "summary": "Summary"}],
        mode="informational",
    )

    assert "A launch with 'quoted' text" in prompt
    assert 'Title: A launch with "quoted" text' not in prompt
