"""Prompt-building and generation helpers for AI Threads.

This module now prefers a freeform thread structure:
    - post_main
    - replies[]
    - media_plan

Legacy reply keys are still tolerated by downstream code, but new generations
should primarily use replies[].
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from llm_backend import request_structured_json


GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_article": {
            "type": "object",
            "properties": {
                "original_title": {"type": "string"},
                "link": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["original_title", "link", "reason"],
            "additionalProperties": True,
        },
        "post_main": {"type": "string"},
        "replies": {"type": "array", "items": {"type": "string"}},
        "media_plan": {
            "type": "object",
            "properties": {
                "preferred_type": {"type": "string"},
                "search_query": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["preferred_type", "search_query", "reason"],
            "additionalProperties": True,
        },
        "topic_tag": {"type": "string"},
    },
    "required": ["selected_article", "post_main", "replies", "media_plan", "topic_tag"],
    "additionalProperties": True,
}

WORTHINESS_SCHEMA = {
    "type": "object",
    "properties": {
        "worthy": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["worthy", "reason"],
    "additionalProperties": True,
}


def build_prompt(
    articles: list[dict[str, Any]],
    used_titles: list[str] | None = None,
    engagement_patterns: dict[str, Any] | None = None,
    mode: str = "informational",
) -> str:
    """Build the generation prompt."""
    articles_text = _format_articles(articles)
    history_instruction = _build_history_instruction(used_titles)
    engagement_instruction = _build_engagement_instruction(engagement_patterns)

    style_block = _build_style_block(mode)

    return f"""
{history_instruction}{engagement_instruction}
# ROLE
You write Korean Threads posts for a mixed audience:
- developers
- beginners
- vibe coders

Voice:
- like a smart close friend explaining what matters
- factual first, then interpretation
- useful before flashy
- optimized for shares and follows, not empty hype
- Korean only

{style_block}

# TASK
Pick exactly one article and write a freeform thread.

What "good" means:
1. The post teaches something useful right now.
2. It explains why the change matters in practice.
3. It gives readers at least one clear "so what / what to try next" takeaway.
4. It is interesting enough that someone would share it with a friend.

Avoid:
- bland news summaries
- empty hype
- repeated filler
- hashtags
- raw links in the prose
- "card news" framing
- do not invent facts. Stay grounded in the candidate article's Title, Summary, or Details fields below. If a fact is not in any of those fields, leave it out.
- if a detail would require guessing, leave it out

Use what's there:
- When Details contains specific numbers, mechanisms, before/after comparisons, quotes, or named components, surface them in the thread instead of paraphrasing them into generic claims.
- A concrete number or mechanism beats a generic adjective every time.

# OUTPUT FORMAT
Return JSON only.

{{
  "selected_article": {{
    "original_title": "exact title from candidate list",
    "link": "exact link from candidate list",
    "reason": "why this article is the best choice for a practical, shareable Threads post"
  }},
  "post_main": "main post in Korean",
  "replies": [
    "reply 1",
    "reply 2"
  ],
  "media_plan": {{
    "preferred_type": "video | image | none",
    "search_query": "best short query for finding a related demo / promo video",
    "reason": "why this media is relevant to the post"
  }},
  "topic_tag": "ai.threads"
}}

# STRUCTURE RULES
- `post_main`: 160~420 characters, usually 3~4 sentences
- `replies`: 2~4 items
- each reply: 80~280 characters
- replies do NOT need fixed roles
- the thread should naturally flow from fact -> interpretation -> practical takeaway
- if there is a strong practical angle, prioritize it over generic commentary
- if a useful comparison helps, include it naturally
- if there is no good media angle, set preferred_type to "none"
- if the article uses technical jargon or an acronym like VLM, explain it once in simple Korean
- include at least one concrete use case, workflow implication, or "what to try next" point across the thread

# CANDIDATE ARTICLES
{articles_text}
""".strip()


def _build_style_block(mode: str) -> str:
    if mode == "viral":
        return """
Mode: viral
- Start with a hook that makes people stop scrolling.
- Still stay grounded in facts.
- Make the share-worthy angle obvious.
- Replies can be sharper and more opinionated, but do not become ragebait.
""".strip()

    return """
Mode: informational
- Prioritize practical usefulness.
- Explain why the change matters to real workflows.
- Make it understandable even for non-experts.
- Interpretation is welcome, but facts come first.
""".strip()


def _format_articles(articles: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for index, article in enumerate(articles, start=1):
        chunks.append(
            "\n".join(
                [
                    f"## Article {index}",
                    f"Title: {article.get('title', '')}",
                    f"Summary: {article.get('summary', '')}",
                    f"Details: {article.get('details', '')}",
                    f"Source: {article.get('source', '')}",
                    f"Link: {article.get('link', '')}",
                    f"Engagement: {article.get('engagement', 0)}",
                ]
            )
        )
    return "\n\n".join(chunks)


def _build_history_instruction(used_titles: list[str] | None) -> str:
    if not used_titles:
        return ""

    titles_list = "\n".join(f"- {title}" for title in used_titles[:20])
    return f"""
## DUPLICATE AVOIDANCE
Do not pick the same story, same event, or same article angle as any recent title below.
If a new article is basically the same news item, skip it.
Recent titles:
{titles_list}

""".lstrip()


def _load_post_excerpts(
    date_str: str, *, max_post: int = 250, max_reply: int = 200
) -> tuple[str, str]:
    if not date_str:
        return "", ""
    path = Path("output") / date_str / "post.json"
    if not path.exists():
        return "", ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "", ""
    post_main = str(data.get("post_main", ""))[:max_post]
    first_reply = ""
    replies = data.get("replies")
    if isinstance(replies, list) and replies:
        first_reply = str(replies[0])[:max_reply]
    else:
        for legacy_key in (
            "reply_explain",
            "reply_background",
            "reply_important",
            "reply_impact",
            "reply_action",
            "reply_counter",
            "reply_casual",
        ):
            value = data.get(legacy_key)
            if value:
                first_reply = str(value)[:max_reply]
                break
    return post_main, first_reply


def _format_engagement_item(item: dict[str, Any]) -> list[str]:
    date_str = str(item.get("date", ""))
    post_main, first_reply = _load_post_excerpts(date_str)
    if not post_main:
        post_main = str(item.get("post_main", ""))
    title = str(item.get("title", ""))[:80]
    out = [f"- [{date_str}] score={item.get('score', 0)} title={title}"]
    if post_main:
        out.append(f"  post: {post_main}")
    if first_reply:
        out.append(f"  reply: {first_reply}")
    return out


def _build_engagement_instruction(patterns: dict[str, Any] | None) -> str:
    if not patterns or not patterns.get("top"):
        return ""

    lines = [
        "## WHAT HAS WORKED RECENTLY",
        "Use this only as a soft signal. Do not copy. Learn the pattern.",
        "",
        "Top performers:",
    ]

    for item in patterns.get("top", [])[:3]:
        lines.extend(_format_engagement_item(item))

    if patterns.get("bottom"):
        lines.append("")
        lines.append("Weak performers:")
        for item in patterns.get("bottom", [])[:3]:
            lines.extend(_format_engagement_item(item))

    lines.append("")
    lines.append("Favor threads that are practical, concrete, and easy to share.")
    lines.append("")
    return "\n".join(lines)


def _parse_response(text: str) -> dict[str, Any]:
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    return json.loads(text)


def _ensure_required_fields(content: dict[str, Any], mode: str = "informational") -> dict[str, Any]:
    selected_article = content.get("selected_article")
    if not isinstance(selected_article, dict):
        selected_article = {}

    replies = content.get("replies")
    if not isinstance(replies, list):
        replies = _legacy_replies_from_content(content, mode)

    cleaned_replies = [str(item).strip() for item in replies if str(item).strip()]

    media_plan = content.get("media_plan")
    if not isinstance(media_plan, dict):
        media_plan = {}

    normalized = {
        **content,
        "selected_article": {
            "original_title": str(selected_article.get("original_title", "")).strip(),
            "link": str(selected_article.get("link", "")).strip(),
            "reason": str(selected_article.get("reason", "")).strip(),
        },
        "post_main": str(content.get("post_main", "")).strip(),
        "replies": cleaned_replies,
        "media_plan": {
            "preferred_type": str(media_plan.get("preferred_type", "none")).strip() or "none",
            "search_query": str(media_plan.get("search_query", "")).strip(),
            "reason": str(media_plan.get("reason", "")).strip(),
        },
        "topic_tag": str(content.get("topic_tag", "ai.threads")).strip() or "ai.threads",
    }
    return normalized


def _legacy_replies_from_content(content: dict[str, Any], mode: str) -> list[str]:
    legacy_keys = {
        "viral": [
            "reply_explain",
            "reply_important",
            "reply_action",
            "reply_counter",
            "reply_casual",
        ],
        "informational": [
            "reply_background",
            "reply_impact",
            "reply_compare",
            "reply_summary",
        ],
    }
    return [content.get(key, "") for key in legacy_keys.get(mode, legacy_keys["informational"]) if content.get(key)]


def evaluate_worthiness(articles: list[dict[str, Any]], mode: str = "informational") -> tuple[bool, str]:
    """Decide whether today's article set is worth posting about."""
    if not articles:
        return False, "No articles available."

    articles_text = _format_articles(articles[:10])
    emphasis = (
        "practical usefulness, real workflow change, and share-worthy insight"
        if mode == "informational"
        else "share-worthy insight, practical relevance, and strong social hook"
    )
    prompt = f"""
You are filtering AI news for a Korean Threads account.

Decide if there is at least one article worth posting about today.

Priority:
- {emphasis}
- must matter to developers, beginners, or vibe coders
- should lead to a concrete takeaway, not just "news happened"

Reject if the batch is mostly:
- bland product updates
- funding / M&A with no workflow impact
- niche research without practical meaning
- repeat coverage of the same story

Return JSON only:
{{"worthy": true, "reason": "short reason"}}

{articles_text}
""".strip()

    try:
        result = request_structured_json(
            [{"role": "user", "content": prompt}],
            schema=WORTHINESS_SCHEMA,
            max_tokens=200,
        )
        return bool(result.get("worthy", True)), str(result.get("reason", "")).strip()
    except Exception:
        return True, "Worthiness parsing failed; proceeding by default."


def generate_post(
    articles: list[dict[str, Any]],
    used_titles: list[str] | None = None,
    engagement_patterns: dict[str, Any] | None = None,
    qa_feedback: dict[str, Any] | None = None,
    mode: str = "informational",
) -> dict[str, Any]:
    """Generate a Threads post and freeform reply chain."""
    prompt = build_prompt(articles, used_titles, engagement_patterns, mode)
    messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
    if qa_feedback:
        previous_json = json.dumps(qa_feedback["previous_post"], ensure_ascii=False, indent=2)
        feedback_text = _build_qa_feedback(qa_feedback)
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": previous_json},
            {"role": "user", "content": feedback_text},
        ]

    try:
        result = request_structured_json(
            messages,
            schema=GENERATION_SCHEMA,
            max_tokens=2200,
        )
        return _ensure_required_fields(result, mode=mode)
    except Exception:
        retry_messages = [
            *messages,
            {"role": "user", "content": "Return valid JSON only. Keep the same content quality."},
        ]
        result = request_structured_json(
            retry_messages,
            schema=GENERATION_SCHEMA,
            max_tokens=2200,
        )
        return _ensure_required_fields(result, mode=mode)


def _build_qa_feedback(qa_feedback: dict[str, Any]) -> str:
    lines = [
        "Your previous draft did not pass QA. Rewrite it.",
        "",
        "Problems to fix:",
    ]

    for issue in qa_feedback.get("issues", ()):
        lines.append(f"- {issue}")

    suggestions = list(qa_feedback.get("suggestions", ()))
    if suggestions:
        lines.append("")
        lines.append("Suggestions:")
        for suggestion in suggestions:
            lines.append(f"- {suggestion}")

    lines.extend(
        [
            "",
            f"Previous score: {qa_feedback.get('score', 0):.2f}",
            "Keep the same article only if it is still the best choice.",
            "You may change the article if another candidate is clearly more useful and shareable.",
            "Return JSON only.",
        ]
    )
    return "\n".join(lines)
