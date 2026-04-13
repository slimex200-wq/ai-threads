"""Heuristics for ranking candidate articles before generation."""

from __future__ import annotations

import math
from datetime import datetime, timezone


POSITIVE_TITLE_SIGNALS = (
    "launch",
    "launches",
    "released",
    "release",
    "ships",
    "ship",
    "rollout",
    "open-source",
    "open source",
    "cli",
    "api",
    "sdk",
    "memory",
    "model",
    "update",
    "available",
)

NEGATIVE_TITLE_SIGNALS = (
    "what is",
    "explained",
    "brief history",
    "simple guide",
    "guide to common ai terms",
    "history of ai",
)

PREDICTION_SIGNALS = (
    "which company has",
    "before 2027",
    "prediction market",
    "market will resolve",
)


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def score_candidate(article: dict, *, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    title = str(article.get("title", "")).lower()
    summary = str(article.get("summary", "")).lower()
    source = str(article.get("source", "")).lower()
    engagement = float(article.get("engagement", 0) or 0)

    score = 0.0

    article_dt = _parse_date(article.get("date", ""))
    if article_dt:
        age_days = max(0.0, (now - article_dt).total_seconds() / 86400)
        score += max(0.0, 8.0 - min(age_days, 8.0))
    else:
        score += 1.0

    score += math.log1p(max(0.0, engagement)) * 0.35

    for signal in POSITIVE_TITLE_SIGNALS:
        if signal in title or signal in summary:
            score += 1.8

    for signal in NEGATIVE_TITLE_SIGNALS:
        if signal in title:
            score -= 4.0

    for signal in PREDICTION_SIGNALS:
        if signal in title or signal in summary:
            score -= 8.0

    if "youtube/" in source:
        score -= 2.0
    if "polymarket" in source:
        score -= 20.0
    if "techcrunch" in source or "the verge" in source or "google blog" in source or "openai" in source:
        score += 1.0

    return round(score, 3)
