"""threads_poster 모드별 reply 매핑 테스트."""

from threads_poster import REPLY_KEYS, REPLY_LABELS


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
