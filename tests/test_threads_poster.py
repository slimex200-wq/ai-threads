"""threads_poster reply mapping tests."""

from threads_poster import REPLY_KEYS, REPLY_LABELS, get_reply_sequence


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
