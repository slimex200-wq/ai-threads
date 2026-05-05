"""Lightweight article body enrichment for better grounded generation."""

from __future__ import annotations

import html
import re
from typing import Any

import httpx


def extract_article_text(raw_html: str, *, max_chars: int = 1600) -> str:
    """Extract readable text from article HTML without extra dependencies."""
    source = raw_html
    for match in re.finditer(r"<article\b[^>]*>(.*?)</article>", raw_html, re.IGNORECASE | re.DOTALL):
        candidate = match.group(1)
        if len(re.findall(r"<p\b[^>]*>", candidate, re.IGNORECASE)) >= 3:
            source = candidate
            break

    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", source, re.IGNORECASE | re.DOTALL)
    cleaned_parts: list[str] = []
    for paragraph in paragraphs:
        text = re.sub(r"<[^>]+>", " ", paragraph)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) >= 30:
            cleaned_parts.append(text)

    return " ".join(cleaned_parts)[:max_chars].strip()


def enrich_articles(articles: list[dict[str, Any]], *, max_articles: int = 5) -> list[dict[str, Any]]:
    """Fetch article bodies for the top-ranked HTTP candidates.

    This is intentionally lightweight:
    - skip known low-value / non-article sources
    - only enrich a small top slice
    """
    enriched: list[dict[str, Any]] = []
    for index, article in enumerate(articles):
        item = dict(article)
        if index < max_articles:
            link = str(item.get("link", "")).strip()
            source = str(item.get("source", "")).lower()
            if link.startswith("http") and "youtube/" not in source and "polymarket" not in source:
                details = fetch_article_details(link)
                if details:
                    item["details"] = details
        enriched.append(item)
    return enriched


def fetch_article_details(url: str, *, timeout: float = 10.0) -> str:
    try:
        response = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if response.status_code >= 400:
            return ""
        return extract_article_text(response.text)
    except Exception:
        return ""
