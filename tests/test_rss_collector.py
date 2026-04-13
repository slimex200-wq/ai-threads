from datetime import timezone

from rss_collector import _parse_published


def test_parse_published_handles_rfc2822_and_returns_utc():
    entry = {"published": "Sat, 12 Apr 2026 10:30:00 GMT"}

    parsed = _parse_published(entry)

    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert parsed.strftime("%Y-%m-%d") == "2026-04-12"
