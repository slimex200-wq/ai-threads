from datetime import datetime, timezone

from social_collector import (
    _build_date_window,
    _determine_refresh_mode,
    _filter_articles_to_window,
    _merge_cached_items,
)


def test_determine_refresh_mode_defaults_to_cold_without_cache():
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)

    assert _determine_refresh_mode("YouTube", None, now) == "cold"


def test_determine_refresh_mode_hot_source_uses_hot_between_cold_refreshes():
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    entry = {"last_refresh_at": "2026-04-13T08:00:00+00:00", "items": [{"title": "cached"}]}

    assert _determine_refresh_mode("YouTube", entry, now) == "hot"


def test_determine_refresh_mode_warm_source_uses_cache_when_fresh():
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    entry = {"last_refresh_at": "2026-04-13T10:30:00+00:00", "items": [{"title": "cached"}]}

    assert _determine_refresh_mode("Reddit", entry, now) == "cache"


def test_determine_refresh_mode_respects_negative_cache_for_empty_results():
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    entry = {"last_refresh_at": "2026-04-13T10:30:00+00:00", "items": []}

    assert _determine_refresh_mode("Reddit", entry, now) == "cache"


def test_filter_articles_to_window_removes_old_dated_items():
    articles = [
        {"title": "recent", "date": "2026-04-13"},
        {"title": "stale", "date": "2026-03-01"},
        {"title": "unknown-date", "date": ""},
    ]

    filtered = _filter_articles_to_window(articles, "2026-04-10")

    assert [article["title"] for article in filtered] == ["recent", "unknown-date"]


def test_merge_cached_items_dedupes_and_prunes_old_entries():
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    existing = [
        {"title": "old keep", "link": "https://a", "date": "2026-04-01", "cached_at": "2026-04-01T00:00:00+00:00"},
        {"title": "very old drop", "link": "https://b", "date": "2026-03-01", "cached_at": "2026-03-01T00:00:00+00:00"},
    ]
    fresh = [
        {"title": "old keep", "link": "https://a", "date": "2026-04-01"},
        {"title": "new item", "link": "https://c", "date": "2026-04-13"},
    ]

    merged = _merge_cached_items(existing, fresh, now=now)

    assert [item["title"] for item in merged] == ["new item", "old keep"]
