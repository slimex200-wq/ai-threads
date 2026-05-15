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


WRITING_REFERENCE_PATH = Path(__file__).resolve().parent / "reference_corpus" / "internet_writing_principles.md"

GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "content_brief": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "target_reader": {"type": "string"},
                "reader_problem": {"type": "string"},
                "promise": {"type": "string"},
                "angle": {"type": "string"},
                "why_now": {"type": "string"},
                "takeaway": {"type": "string"},
            },
            "required": [
                "topic",
                "target_reader",
                "reader_problem",
                "promise",
                "angle",
                "why_now",
                "takeaway",
            ],
            "additionalProperties": True,
        },
        "selected_article": {
            "type": "object",
            "properties": {
                "original_title": {"type": "string"},
                "link": {"type": "string"},
                "reason": {"type": "string"},
                "evidence": {"type": "string"},
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
    "required": ["content_brief", "selected_article", "post_main", "replies", "media_plan", "topic_tag"],
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
    writing_reference = _build_writing_reference()

    style_block = _build_style_block(mode)

    return f"""
{history_instruction}{engagement_instruction}{writing_reference}
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
Pick exactly one article, create a short content brief, then write a right-sized freeform Threads post.

Think like a calm technical essayist in the style of unclejobs.ai:
1. Choose one strong thesis.
2. Open with an inverted-pyramid first sentence: payoff or CTA first, context later.
3. Make the first sentence tell the reader what to notice, rethink, check, stop doing, or try.
4. Turn the article into a broader idea about how AI work changes.
5. Explain the idea through short, sparse Korean lines.
6. Use the article as proof, not as the whole post.
7. End with a practical criterion the reader can use.

What "good" means:
1. The first sentence is a strong CTA or direction of attention, not slow setup.
2. The main post states a clean thesis in 2~4 short lines.
3. Replies read like a connected essay, not a list of news bullets.
4. Each reply develops exactly one move: problem, contrast, example, caveat, criterion, or close.
5. The article supplies proof points, but the thread teaches a reusable lens.
6. The thread is interesting enough that someone would save it as a way to think.

Avoid:
- bland news summaries
- empty hype
- repeated filler
- hashtags
- raw links in the prose
- "card news" framing
- opening with "X announced Y" unless it is immediately turned into a thesis
- dense paragraphs that look like a blog post pasted into Threads
- do not invent facts. Stay grounded in the candidate article's Title, Summary, or Details fields below. If a fact is not in any of those fields, leave it out.
- if a detail would require guessing, leave it out

Style target:
- Korean only, except proper nouns and product names
- short declarative sentences
- visible blank lines between sentences or micro-paragraphs
- one idea per line
- calm, precise, slightly opinionated
- no forced jokes
- explanatory voice, not bulletin voice: the reader should feel guided, not briefed
- do not stack "-다" endings line after line; mix claim, explanation, question, contrast, and small aside
- use connective explanatory moves naturally: "쉽게 말하면", "이게 중요한 이유는", "여기서 봐야 할 건", "반대로", "그래서"
- avoid repetitive polite endings like "-요", "-죠", "-습니다", and "-합니다"
- use polite endings only when they are the cleanest sentence; otherwise vary with compact written Korean
- do not make every line end the same way
- no generic "AI 시대가 왔다" endings
- no more than one emoji, preferably none
- write with sparse rhythm: thesis, pause, concrete proof, implication, criterion
- optimize for the actual narrow Threads timeline, not a Markdown preview
- avoid 3~4 consecutive non-empty lines with no blank line; it looks cramped on Threads
- keep each visual line short enough that the final ending does not wrap alone on mobile
- keep replies compact: one small point per reply, not a mini essay

Use what's there:
- When Details contains specific numbers, mechanisms, before/after comparisons, quotes, or named components, surface them in the thread instead of paraphrasing them into generic claims.
- A concrete number or mechanism beats a generic adjective every time.

# OUTPUT FORMAT
Return JSON only.
Important JSON safety rule: when post_main or a reply needs line breaks, use the literal token `<br>` inside the JSON string.
Use `<br><br>` for visible paragraph gaps between sparse lines.
Do not put raw newline characters inside JSON string values.
The pipeline will convert `<br>` into real line breaks after parsing.

{{
  "content_brief": {{
    "topic": "specific topic, not a broad category",
    "target_reader": "who this is for, e.g. developers / beginners / vibe coders / solo founders",
    "reader_problem": "what this reader is confused about or deciding now",
    "promise": "what the thread will help the reader understand or do",
    "angle": "the sharp point of view for this article",
    "why_now": "why this matters today",
    "takeaway": "the practical final takeaway"
  }},
  "selected_article": {{
    "original_title": "title from candidate list, with any double quotation marks replaced by single quotation marks",
    "link": "exact link from candidate list",
    "reason": "why this article is the best choice for a practical, shareable Threads post",
    "evidence": "exact article facts used in the thread; no guesses"
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
- `post_main`: 60~260 Korean characters, usually 2~4 short lines
- first sentence: a CTA-like line that gives the reader an action or attention direction
- use inverted pyramid order: payoff or criterion first, proof second, background later
- `replies`: choose the count from the idea density, not from a fixed template
- compact article: 2~4 replies
- normal article: 4~6 replies
- deep article with real mechanisms, tradeoffs, or examples: 7~9 replies
- use 10~12 replies only when the article truly has multiple useful mechanisms or examples
- each reply: 40~200 Korean characters
- use `<br><br>` inside post_main and replies to create actual breathing room on Threads
- most replies should read as 1~2 short visual paragraphs, not one compact block
- if one sentence is long, split it into two visual lines at a natural phrase boundary
- every reply must be readable as its own post in the chain
- each reply should explain, not just report; avoid turning the thread into a stack of verdict sentences
- prefer fewer replies; if the idea is clear in 5 replies, stop there
- do not expand one reply into background, caveat, and takeaway at once; keep one move and move on
- suggested reply arc, scaled to length:
  - open: name the real problem or tension
  - middle: show proof, mechanism, example, or tradeoff
  - close: practical takeaway for the target reader, framed as a concrete decision rule, next step, or check to run
- the thread must naturally flow from first-line CTA -> thesis -> proof -> tradeoff -> criterion -> takeaway
- if the idea is already clear, stop; never pad the thread to look more substantial
- the content_brief.takeaway and final reply must point in the same direction
- if there is a strong practical angle, prioritize it over generic commentary
- if a useful comparison helps, include it naturally
- if there is no good media angle, set preferred_type to "none"
- if the article uses technical jargon or an acronym like VLM, explain it once in simple Korean
- include at least one concrete use case, workflow implication, or "what to try next" point across the thread
- if you cannot ground a technical detail in the article fields, remove it instead of making the thread sound smarter
- do not add background facts just because they are interesting. Use only context that strengthens the angle.

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
                    f"Title: {_safe_prompt_text(article.get('title', ''))}",
                    f"Summary: {_safe_prompt_text(article.get('summary', ''))}",
                    f"Details: {_safe_prompt_text(article.get('details', ''))}",
                    f"Source: {_safe_prompt_text(article.get('source', ''))}",
                    f"Link: {_safe_prompt_text(article.get('link', ''))}",
                    f"Engagement: {article.get('engagement', 0)}",
                ]
            )
        )
    return "\n\n".join(chunks)


def _safe_prompt_text(value: Any) -> str:
    text = str(value or "")
    return text.replace('"', "'")


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


def _build_writing_reference() -> str:
    try:
        text = WRITING_REFERENCE_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""

    if not text:
        return ""

    return f"""
## STANDING INTERNET WRITING REFERENCE
Use this as editorial guidance. Do not quote or mention the sources in the post.

{text}

""".lstrip()


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
    content_brief = content.get("content_brief")
    if not isinstance(content_brief, dict):
        content_brief = {}

    selected_article = content.get("selected_article")
    if not isinstance(selected_article, dict):
        selected_article = {}

    replies = content.get("replies")
    if not isinstance(replies, list):
        replies = _legacy_replies_from_content(content, mode)

    cleaned_replies = [_normalize_line_break_tokens(item) for item in replies if str(item).strip()]

    media_plan = content.get("media_plan")
    if not isinstance(media_plan, dict):
        media_plan = {}

    takeaway = str(content_brief.get("takeaway", "")).strip()
    promise = str(
        content_brief.get("promise", "")
        or content_brief.get("content_goal", "")
        or content_brief.get("goal", "")
        or takeaway
    ).strip()

    normalized = {
        **content,
        "content_brief": {
            "topic": str(content_brief.get("topic", "")).strip(),
            "target_reader": str(content_brief.get("target_reader", "")).strip(),
            "reader_problem": str(content_brief.get("reader_problem", "")).strip(),
            "promise": promise,
            "angle": str(content_brief.get("angle", "")).strip(),
            "why_now": str(content_brief.get("why_now", "")).strip(),
            "takeaway": takeaway,
        },
        "selected_article": {
            "original_title": str(selected_article.get("original_title", "")).strip(),
            "link": str(selected_article.get("link", "")).strip(),
            "reason": str(selected_article.get("reason", "")).strip(),
            "evidence": _normalize_line_break_tokens(selected_article.get("evidence", "")),
            "summary": str(selected_article.get("summary", "")).strip(),
            "details": str(selected_article.get("details", "")).strip(),
        },
        "post_main": _normalize_line_break_tokens(content.get("post_main", "")),
        "replies": cleaned_replies,
        "media_plan": {
            "preferred_type": str(media_plan.get("preferred_type", "none")).strip() or "none",
            "search_query": str(media_plan.get("search_query", "")).strip(),
            "reason": str(media_plan.get("reason", "")).strip(),
        },
        "topic_tag": str(content.get("topic_tag", "ai.threads")).strip() or "ai.threads",
    }
    return normalized


def _normalize_line_break_tokens(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s*<br\s*/?>\s*", "\n", text, flags=re.IGNORECASE)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if cleaned and not previous_blank:
                cleaned.append("")
                previous_blank = True
            continue
        cleaned.append(line)
        previous_blank = False

    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned)


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
            max_tokens=4200,
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
            max_tokens=4200,
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
            "Make the thread match the unclejobs.ai short-line essay rhythm.",
            "Choose the reply count from the idea density: 2~4 compact, 4~6 normal, 7~9 deep; never pad.",
            "Keep replies compact: one small point per reply, not a mini essay.",
            "Rewrite from bulletin voice into explanatory voice: guide the reader through why each point matters.",
            "Do not stack '-다' endings line after line; mix claim, explanation, question, contrast, and small aside.",
            "Avoid repeating polite Korean endings like '-요', '-죠', '-습니다', and '-합니다' on every line.",
            "Make the first sentence a CTA-like line: tell the reader what to notice, rethink, check, stop doing, or try.",
            "Use inverted pyramid order in post_main: payoff or criterion first, proof second, background later.",
            "Make post_main a clean thesis in 2~4 short lines.",
            "Make the final reply actionable: a concrete decision rule, next step, or check to run.",
            "If grounding was criticized, remove any fact that is not explicit in the candidate Title, Summary, or Details.",
            "Return JSON only.",
        ]
    )
    return "\n".join(lines)
