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
