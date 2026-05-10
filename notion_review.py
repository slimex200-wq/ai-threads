"""Optional Notion review handoff for generated Threads drafts."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from config import NOTION_API_KEY, NOTION_CONTENT_DATABASE_ID, NOTION_VERSION

NOTION_API_BASE = "https://api.notion.com/v1"
TEXT_CHUNK_LIMIT = 1900


class NotionReviewError(RuntimeError):
    """Raised when the Notion review handoff cannot be completed."""


def is_configured() -> bool:
    return bool(NOTION_API_KEY and NOTION_CONTENT_DATABASE_ID)


def submit_review_page(
    content: dict[str, Any],
    qa_result: Any,
    *,
    token: str | None = None,
    database_id: str | None = None,
) -> dict[str, Any]:
    """Create a Notion row/page for human review before publishing."""
    token = token or NOTION_API_KEY
    database_id = database_id or NOTION_CONTENT_DATABASE_ID
    if not token or not database_id:
        raise NotionReviewError("NOTION_API_KEY and NOTION_CONTENT_DATABASE_ID are required")

    payload = build_review_payload(content, qa_result, database_id=database_id)
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            f"{NOTION_API_BASE}/pages",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        raise NotionReviewError(f"Notion page create failed: {response.status_code} {response.text[:500]}")
    return response.json()


def list_approved_pages(
    *,
    token: str | None = None,
    database_id: str | None = None,
    limit: int = 1,
    status: str = "Approved",
) -> list[dict[str, Any]]:
    """Return Notion review rows that are ready to publish."""
    token = token or NOTION_API_KEY
    database_id = database_id or NOTION_CONTENT_DATABASE_ID
    if not token or not database_id:
        raise NotionReviewError("NOTION_API_KEY and NOTION_CONTENT_DATABASE_ID are required")

    payload = build_approved_query_payload(limit=limit, status=status)
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            f"{NOTION_API_BASE}/databases/{database_id}/query",
            headers=_headers(token),
            json=payload,
        )

    if response.status_code >= 400:
        raise NotionReviewError(f"Notion query failed: {response.status_code} {response.text[:500]}")
    return list(response.json().get("results", []))


def build_approved_query_payload(*, limit: int = 1, status: str = "Approved") -> dict[str, Any]:
    """Build the Notion query for publish-ready review rows."""
    return {
        "filter": {"property": "Status", "select": {"equals": status}},
        "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
        "page_size": max(1, min(limit, 100)),
    }


def review_page_to_content(page: dict[str, Any]) -> dict[str, Any]:
    """Convert one approved Notion row back into the post_thread content shape."""
    props = page.get("properties", {}) or {}

    media_type = _property_select(props.get("Media Type")).lower()
    media_publish_url = _property_url(props.get("Media Publish URL"))
    media_candidate_url = _property_url(props.get("Media Candidate URL"))
    media_url = media_publish_url or media_candidate_url
    media_approved = _property_checkbox(props.get("Media Approved"))

    if media_type == "video":
        _validate_video_review_media(
            media_publish_url=media_publish_url,
            media_candidate_url=media_candidate_url,
            media_approved=media_approved,
        )

    content = {
        "content_brief": {
            "topic": _property_text(props.get("Topic")),
            "target_reader": _property_text(props.get("Target Reader")),
            "reader_problem": _property_text(props.get("Reader Problem")),
            "promise": _property_text(props.get("Content Goal")),
            "angle": _property_text(props.get("Notes")),
            "why_now": "",
            "takeaway": _property_text(props.get("CTA")),
        },
        "selected_article": {
            "original_title": _property_text(props.get("Source Title")) or _property_text(props.get("Title")),
            "link": _property_url(props.get("Article URL")),
        },
        "post_main": _property_text(props.get("Post Main")),
        "replies": _split_replies(_property_text(props.get("Replies"))),
        "source_link": _property_url(props.get("Article URL")),
    }

    if media_approved and media_url:
        if media_type == "video":
            content["video_url"] = media_publish_url
        elif media_type == "image":
            content["og_image"] = media_url

    if not content["post_main"]:
        raise NotionReviewError("Approved Notion row is missing Post Main")
    if not content["replies"]:
        raise NotionReviewError("Approved Notion row is missing Replies")
    return content


def mark_review_published(
    page_id: str,
    posting_result: dict[str, Any],
    *,
    token: str | None = None,
) -> dict[str, Any]:
    """Mark a Notion review row as published after Threads succeeds."""
    token = token or NOTION_API_KEY
    if not token:
        raise NotionReviewError("NOTION_API_KEY is required")

    payload = build_published_update_payload(posting_result)
    with httpx.Client(timeout=20.0) as client:
        response = client.patch(
            f"{NOTION_API_BASE}/pages/{page_id}",
            headers=_headers(token),
            json=payload,
        )

    if response.status_code >= 400:
        raise NotionReviewError(f"Notion publish update failed: {response.status_code} {response.text[:500]}")
    return response.json()


def build_published_update_payload(posting_result: dict[str, Any], *, published_on: str | None = None) -> dict[str, Any]:
    post_id = str(posting_result.get("post_id") or "").strip()
    url = str(posting_result.get("permalink") or posting_result.get("url") or "").strip()
    properties: dict[str, Any] = {
        "Status": {"select": {"name": "Published"}},
        "Post ID": {"rich_text": _rich_text(post_id, max_total=300)},
        "Publish Date": {"date": {"start": published_on or date.today().isoformat()}},
    }
    if url:
        properties["Threads URL"] = _url_property(url)
    return {"properties": properties}


def build_review_payload(content: dict[str, Any], qa_result: Any, *, database_id: str) -> dict[str, Any]:
    article = content.get("selected_article", {}) or {}
    brief = content.get("content_brief", {}) or {}
    media_plan = content.get("media_plan", {}) or {}
    qa = _qa_dict(qa_result)

    title = str(article.get("original_title") or brief.get("topic") or "AI Threads draft").strip()
    post_main = str(content.get("post_main", "")).strip()
    replies = content.get("replies")
    reply_text = "\n\n".join(f"{index}. {reply}" for index, reply in enumerate(replies, start=1)) if isinstance(replies, list) else ""
    media_type = _media_type(content, media_plan)
    media_candidate_url = _review_media_candidate_url(content)
    media_publish_url = _review_media_publish_url(media_type, media_candidate_url)

    properties = {
        "Title": {"title": _rich_text(title, max_total=180)},
        "Status": {"select": {"name": "Review"}},
        "Channel": {"select": {"name": "Threads"}},
        "Topic": {"rich_text": _rich_text(brief.get("topic", ""), max_total=400)},
        "Target Reader": {"rich_text": _rich_text(brief.get("target_reader", ""), max_total=400)},
        "Reader Problem": {"rich_text": _rich_text(brief.get("reader_problem", ""), max_total=800)},
        "Content Goal": {"rich_text": _rich_text(brief.get("promise", ""), max_total=800)},
        "Tone": {"select": {"name": "clear practical"}},
        "CTA": {"rich_text": _rich_text(brief.get("takeaway", ""), max_total=800)},
        "Article URL": _url_property(article.get("link") or content.get("source_link", "")),
        "Source Title": {"rich_text": _rich_text(article.get("original_title", ""), max_total=800)},
        "Post Main": {"rich_text": _rich_text(post_main, max_total=1800)},
        "Replies": {"rich_text": _rich_text(reply_text, max_total=12000)},
        "Media Type": {"select": {"name": media_type}},
        "Media Candidate URL": _url_property(media_candidate_url),
        "Media Publish URL": _url_property(media_publish_url),
        "Media Approved": {"checkbox": False},
        "QA Score": {"number": float(qa.get("score") or 0)},
        "Notes": {"rich_text": _rich_text(_notes_text(qa, media_plan), max_total=1800)},
    }

    return {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": _review_blocks(content, qa),
    }


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _qa_dict(qa_result: Any) -> dict[str, Any]:
    if isinstance(qa_result, dict):
        return qa_result
    if is_dataclass(qa_result):
        return asdict(qa_result)
    return {
        "passed": getattr(qa_result, "passed", False),
        "score": getattr(qa_result, "score", None),
        "issues": list(getattr(qa_result, "issues", ()) or ()),
        "suggestions": list(getattr(qa_result, "suggestions", ()) or ()),
    }


def _media_type(content: dict[str, Any], media_plan: dict[str, Any]) -> str:
    if content.get("video_url"):
        return "video"
    if content.get("og_image"):
        return "image"
    preferred = str(media_plan.get("preferred_type", "none")).strip().lower()
    return preferred if preferred in {"none", "image", "video"} else "none"


def _review_media_candidate_url(content: dict[str, Any]) -> str:
    return str(content.get("video_url") or content.get("og_image") or "").strip()


def _review_media_publish_url(media_type: str, media_candidate_url: str) -> str:
    if media_type == "video" and _is_expiring_video_url(media_candidate_url):
        return ""
    return media_candidate_url


def _validate_video_review_media(
    *,
    media_publish_url: str,
    media_candidate_url: str,
    media_approved: bool,
) -> None:
    has_video_url = bool(media_publish_url or media_candidate_url)
    if not has_video_url:
        return
    if not media_approved:
        raise NotionReviewError(
            "Video media is present, but Media Approved is not checked. "
            "Approve a stable Media Publish URL before setting Status=Approved."
        )
    if not media_publish_url:
        raise NotionReviewError(
            "Approved video rows require Media Publish URL. "
            "Media Candidate URL is review-only; paste a stable public MP4/MOV URL into Media Publish URL."
        )
    if _is_expiring_video_url(media_publish_url):
        raise NotionReviewError(
            "Media Publish URL looks like an expiring video URL. "
            "Upload the video to stable public storage before approving."
        )


def _is_expiring_video_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    query = parse_qs(parsed.query)
    return "googlevideo.com" in host and "expire" in query


def _notes_text(qa: dict[str, Any], media_plan: dict[str, Any]) -> str:
    issues = "\n".join(f"- {issue}" for issue in qa.get("issues", []) if issue)
    suggestions = "\n".join(f"- {item}" for item in qa.get("suggestions", []) if item)
    return "\n\n".join(
        part
        for part in (
            f"QA passed: {qa.get('passed')}",
            f"Media rationale: {media_plan.get('reason', '')}",
            f"Issues:\n{issues}" if issues else "",
            f"Suggestions:\n{suggestions}" if suggestions else "",
        )
        if part
    )


def _review_blocks(content: dict[str, Any], qa: dict[str, Any]) -> list[dict[str, Any]]:
    brief = content.get("content_brief", {}) or {}
    article = content.get("selected_article", {}) or {}
    replies = content.get("replies") if isinstance(content.get("replies"), list) else []

    sections = [
        ("Content brief", _format_key_values(brief)),
        ("Selected article", _format_key_values(article)),
        ("Main post", str(content.get("post_main", ""))),
        ("Replies", "\n\n".join(f"{index}. {reply}" for index, reply in enumerate(replies, start=1))),
        ("QA", _format_key_values(qa)),
    ]

    blocks: list[dict[str, Any]] = []
    blocks.append(_review_checklist_block())
    for heading, text in sections:
        blocks.append(_heading_block(heading))
        blocks.extend(_paragraph_blocks(text or "(empty)"))
    return blocks


def _format_key_values(data: dict[str, Any]) -> str:
    lines = []
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            value = "\n".join(f"- {item}" for item in value)
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _heading_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": _rich_text(text, max_total=200)},
    }


def _review_checklist_block() -> dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rich_text(
                "\n".join(
                    [
                        "검토 체크리스트",
                        "- Post Main과 Replies를 읽고 어색한 부분을 수정한다.",
                        "- 이미지/영상이 적절하면 Media Publish URL을 확인하고 Media Approved를 체크한다.",
                        "- 게시해도 되면 Status를 Approved로 바꾼다.",
                        "- Rejected는 버릴 초안에 사용한다.",
                    ]
                )
            ),
        },
    }


def _paragraph_blocks(text: str) -> list[dict[str, Any]]:
    return [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _rich_text(chunk)},
        }
        for chunk in _chunks(str(text), TEXT_CHUNK_LIMIT)
    ]


def _url_property(value: Any) -> dict[str, Any]:
    text = str(value or "").strip()
    return {"url": text or None}


def _rich_text(value: Any, *, max_total: int | None = None) -> list[dict[str, Any]]:
    text = str(value or "").strip()
    if max_total is not None:
        text = text[:max_total]
    return [{"type": "text", "text": {"content": chunk}} for chunk in _chunks(text, TEXT_CHUNK_LIMIT)]


def _chunks(text: str, size: int) -> list[str]:
    if not text:
        return []
    return [text[index : index + size] for index in range(0, len(text), size)]


def _property_text(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    prop_type = prop.get("type")
    values = prop.get(prop_type or "", [])
    if not isinstance(values, list):
        return ""
    return "".join(str(item.get("plain_text", "")) for item in values).strip()


def _property_select(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    select = prop.get("select") or {}
    return str(select.get("name") or "").strip()


def _property_url(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    return str(prop.get("url") or "").strip()


def _property_checkbox(prop: dict[str, Any] | None) -> bool:
    if not prop:
        return False
    return bool(prop.get("checkbox"))


def _split_replies(value: str) -> list[str]:
    replies = []
    pattern = re.compile(r"(?ms)^\s*\d+[\.\)]\s*(.*?)(?=^\s*\d+[\.\)]\s*|\Z)")
    matches = pattern.findall(value)
    if matches:
        return [text.strip() for text in matches if text.strip()]

    for block in re.split(r"\n\s*\n", value):
        text = block.strip()
        if text:
            replies.append(text)
    return replies
