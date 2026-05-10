from ai_writer import build_prompt


def test_build_prompt_includes_grounding_rules():
    prompt = build_prompt(
        articles=[{"title": "Test", "summary": "Summary", "source": "Source", "link": "https://example.com"}],
        mode="informational",
    )

    assert "do not" in prompt.lower()
    assert "do not invent facts" in prompt
    assert "Title, Summary, or Details" in prompt
    assert "160~420" in prompt


def test_build_prompt_requires_ship30_content_brief():
    prompt = build_prompt(
        articles=[{"title": "Agent marketplace", "summary": "Agents trade with each other"}],
        mode="informational",
    )

    assert '"content_brief"' in prompt
    assert '"target_reader"' in prompt
    assert '"reader_problem"' in prompt
    assert "fact -> interpretation -> practical takeaway" in prompt
    assert "Ship 30-style" in prompt
