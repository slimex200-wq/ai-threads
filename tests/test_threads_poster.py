"""threads_poster reply mapping tests."""

import pytest

import threads_poster
from threads_poster import REPLY_KEYS, REPLY_LABELS, format_threads_display_text, get_reply_sequence, post_thread


def test_viral_reply_keys():
    keys = REPLY_KEYS["viral"]
    assert len(keys) == 5
    assert "reply_explain" in keys
    assert "reply_casual" in keys


def test_informational_reply_keys():
    keys = REPLY_KEYS["informational"]
    assert len(keys) == 4
    assert "reply_background" in keys
    assert "reply_summary" in keys
    assert "reply_casual" not in keys


def test_reply_labels_match_keys():
    for mode in ("viral", "informational"):
        for key in REPLY_KEYS[mode]:
            assert key in REPLY_LABELS, f"{key} not in REPLY_LABELS"


def test_get_reply_sequence_prefers_freeform_replies():
    content = {
        "post_main": "main",
        "replies": ["first reply", "second reply", "third reply"],
    }

    sequence = get_reply_sequence(content, mode="informational")

    assert [item["text"] for item in sequence] == content["replies"]
    assert sequence[0]["label"] == "Reply 1"
    assert sequence[-1]["label"] == "Reply 3"


def test_get_reply_sequence_falls_back_to_legacy_keys():
    content = {
        "reply_background": "background",
        "reply_impact": "impact",
        "reply_compare": "compare",
        "reply_summary": "summary",
    }

    sequence = get_reply_sequence(content, mode="informational")

    assert [item["key"] for item in sequence] == REPLY_KEYS["informational"]
    assert [item["text"] for item in sequence] == [
        "background",
        "impact",
        "compare",
        "summary",
    ]


def test_format_threads_display_text_adds_visible_spacing():
    text = "첫 문장\n둘째 문장\n\n셋째 문장"

    assert format_threads_display_text(text) == "첫 문장\n\n둘째 문장\n\n셋째 문장"


def test_format_threads_display_text_wraps_long_lines_before_orphan_endings():
    text = "좋은 데모는 '무엇을 했는가'보다 '어디까지 사람이 개입했는가'를 보여줍니다."
    formatted = format_threads_display_text(text)

    assert "보여줍니\n다" not in formatted
    assert all(len(line) <= 38 for line in formatted.splitlines() if line)


def test_post_thread_strict_video_does_not_fallback_to_text(monkeypatch):
    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(threads_poster.httpx, "Client", lambda **kwargs: DummyClient())
    monkeypatch.setattr(
        threads_poster,
        "_create_video",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad video")),
    )

    def fail_text_fallback(*args, **kwargs):
        raise AssertionError("text fallback should not run in strict video mode")

    monkeypatch.setattr(threads_poster, "_create_text", fail_text_fallback)

    with pytest.raises(RuntimeError, match="strict mode"):
        post_thread(
            access_token="token",
            user_id="user",
            content={"post_main": "Main", "replies": []},
            source_link="https://example.com/article",
            video_url="https://cdn.example.com/video.mp4",
            strict_video=True,
        )
