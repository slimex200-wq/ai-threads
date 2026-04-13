"""Helpers for normalizing article links and attaching preview media."""

from __future__ import annotations

from urllib.parse import quote, urlparse, urlunparse


def normalize_source_link(raw_link: str | None) -> str:
    if not raw_link:
        return ""
    parsed = urlparse(raw_link)
    return urlunparse(parsed._replace(path=quote(parsed.path)))


def build_content_with_media(
    content: dict,
    *,
    source_link: str = "",
    og_image: str = "",
    video_url: str = "",
) -> dict:
    return {
        **content,
        "source_link": source_link,
        "og_image": og_image,
        "video_url": video_url,
    }
