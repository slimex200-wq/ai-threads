from llm_backend import build_backend_order, build_prompt_transcript, is_overloaded_error


def test_build_backend_order_prefers_api_then_clis():
    order = build_backend_order(
        preferred="auto",
        has_anthropic_api=True,
        has_claude_cli=True,
        has_codex_cli=True,
    )

    assert order == ["anthropic_api", "claude_cli", "codex_cli"]


def test_build_backend_order_claude_cli_is_cli_only():
    order = build_backend_order(
        preferred="claude_cli",
        has_anthropic_api=True,
        has_claude_cli=True,
        has_codex_cli=True,
    )

    assert order == ["claude_cli", "codex_cli"]


def test_build_backend_order_without_api_uses_clis():
    order = build_backend_order(
        preferred="auto",
        has_anthropic_api=False,
        has_claude_cli=True,
        has_codex_cli=True,
    )

    assert order == ["claude_cli", "codex_cli"]


def test_build_backend_order_api_mode_is_explicit_api_only():
    order = build_backend_order(
        preferred="anthropic_api",
        has_anthropic_api=True,
        has_claude_cli=True,
        has_codex_cli=True,
    )

    assert order == ["anthropic_api"]


def test_is_overloaded_error_matches_529_message():
    exc = RuntimeError("Error code: 529 overloaded")
    assert is_overloaded_error(exc) is True


def test_build_prompt_transcript_keeps_message_roles():
    transcript = build_prompt_transcript(
        [
            {"role": "user", "content": "First instruction"},
            {"role": "assistant", "content": "{\"ok\":false}"},
            {"role": "user", "content": "Try again"},
        ]
    )

    assert "[USER]" in transcript
    assert "[ASSISTANT]" in transcript
    assert "Try again" in transcript
