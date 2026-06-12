"""Quality evaluation for generated Threads posts.

The new evaluator supports both:
- freeform `replies[]`
- legacy `reply_*` slot structures
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from llm_backend import request_structured_json


@dataclass(frozen=True)
class QAResult:
    passed: bool
    score: float
    issues: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()


_LEGACY_REPLY_KEYS = {
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

_POST_MAIN_LIMITS = {
    "viral": (180, 380),
    "informational": (60, 320),
}

_REPLY_LIMITS = {
    "viral": (40, 180),
    "informational": (35, 220),
}

_FREEFORM_REPLY_COUNT_LIMITS = {
    "viral": (2, 8),
    "informational": (2, 10),
}

_CONTENT_BRIEF_FIELDS = (
    "topic",
    "target_reader",
    "reader_problem",
    "promise",
    "angle",
    "why_now",
    "takeaway",
)

_BANNED_PATTERNS = (
    "#",
    "http://",
    "https://",
    "카드뉴스",
    "자세한 내용은",
)

_GENERIC_AI_HYPE_PATTERNS = (
    "AI 시대가 왔다",
    "AI 시대가 온다",
    "큰 변화가 예상된다",
    "우리 모두 주목해야 한다",
    "엄청난 혁신이다",
    "게임 체인저다",
)

QA_PASS_THRESHOLD = 0.72
QA_MIN_DIMENSION = 6.5


def _extract_replies(content: dict[str, Any], mode: str) -> list[str]:
    replies = content.get("replies")
    if isinstance(replies, list):
        return [str(item).strip() for item in replies if str(item).strip()]

    extracted: list[str] = []
    for key in _LEGACY_REPLY_KEYS.get(mode, _LEGACY_REPLY_KEYS["informational"]):
        value = str(content.get(key, "")).strip()
        if value:
            extracted.append(value)
    return extracted


def _non_empty_lines(texts: list[str]) -> list[str]:
    lines: list[str] = []
    for text in texts:
        for line in str(text or "").splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    return lines


def _has_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text))


def _ends_with_da_family(line: str) -> bool:
    cleaned = re.sub(r"[\s\"'“”‘’)\].,!?…]+$", "", line.strip())
    return cleaned.endswith("다") or cleaned.endswith("니다")


def _monotone_da_ratio(lines: list[str]) -> float:
    korean_lines = [line for line in lines if _has_korean(line)]
    if len(korean_lines) < 6:
        return 0.0
    return sum(1 for line in korean_lines if _ends_with_da_family(line)) / len(korean_lines)


def _is_dense_threads_block(text: str) -> bool:
    if not _has_korean(text):
        return False
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) < 70 or "\n\n" in normalized:
        return False
    non_empty_lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    return len(non_empty_lines) >= 3


def _has_long_threads_visual_line(text: str, limit: int = 38) -> bool:
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if _has_korean(line) and len(line) > limit:
            return True
    return False


def _has_too_many_threads_visual_lines(text: str, limit: int = 5) -> bool:
    if not _has_korean(text):
        return False
    non_empty_lines = [
        line.strip()
        for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    return len(non_empty_lines) > limit


def _check_rules(content: dict[str, Any], mode: str = "informational") -> list[str]:
    issues: list[str] = []

    post_main = str(content.get("post_main", "")).strip()
    replies = _extract_replies(content, mode)
    content_brief = content.get("content_brief", {})
    selected_article = content.get("selected_article", {})

    if not post_main:
        issues.append("missing required field: post_main")

    post_lo, post_hi = _POST_MAIN_LIMITS.get(mode, _POST_MAIN_LIMITS["informational"])
    if post_main:
        if len(post_main) < post_lo:
            issues.append(f"post_main too short ({len(post_main)} < {post_lo})")
        elif len(post_main) > post_hi:
            issues.append(f"post_main too long ({len(post_main)} > {post_hi})")

    uses_freeform_replies = isinstance(content.get("replies"), list)

    if not replies:
        issues.append("replies must contain at least two non-empty items")
    elif uses_freeform_replies:
        reply_min, reply_max = _FREEFORM_REPLY_COUNT_LIMITS.get(mode, _FREEFORM_REPLY_COUNT_LIMITS["informational"])
        if len(replies) < reply_min:
            issues.append(f"replies must contain at least {reply_min} items for the essay thread style")
        elif len(replies) > reply_max:
            issues.append(f"replies must contain at most {reply_max} items for the essay thread style")
    elif len(replies) < 2:
        issues.append("replies must contain at least two non-empty items")

    reply_lo, reply_hi = _REPLY_LIMITS.get(mode, _REPLY_LIMITS["informational"])
    for index, reply in enumerate(replies, start=1):
        if len(reply) < reply_lo:
            issues.append(f"reply {index} too short ({len(reply)} < {reply_lo})")
        elif len(reply) > reply_hi:
            issues.append(f"reply {index} too long ({len(reply)} > {reply_hi})")

    if not isinstance(selected_article, dict):
        issues.append("selected_article must be an object")
        selected_article = {}

    for key in ("original_title", "link", "reason"):
        if not str(selected_article.get(key, "")).strip():
            issues.append(f"selected_article.{key} is required")

    if not isinstance(content_brief, dict):
        issues.append("content_brief must be an object")
        content_brief = {}

    for key in _CONTENT_BRIEF_FIELDS:
        if not str(content_brief.get(key, "")).strip():
            issues.append(f"content_brief.{key} is required")

    if content.get("topic_tag") != "ai.threads":
        issues.append("topic_tag must be 'ai.threads'")

    texts_to_check = [post_main, *replies]
    for text_name, text in [("post_main", post_main), *[(f"reply {i}", r) for i, r in enumerate(replies, start=1)]]:
        for pattern in _BANNED_PATTERNS:
            if pattern and pattern in text:
                issues.append(f"{text_name} contains banned pattern: {pattern}")
        for pattern in _GENERIC_AI_HYPE_PATTERNS:
            if pattern in text:
                issues.append(f"{text_name} contains generic AI hype: {pattern}")
        if _is_dense_threads_block(text):
            issues.append(
                f"{text_name} is visually dense for Threads; use blank lines between short sentence blocks"
            )
        if _has_long_threads_visual_line(text):
            issues.append(
                f"{text_name} has a visual line that is too long for Threads; split it before the ending wraps alone"
            )
        if text_name.startswith("reply ") and _has_too_many_threads_visual_lines(text):
            issues.append(
                f"{text_name} has too many visual lines for one reply; keep replies to one small point"
            )

    da_ratio = _monotone_da_ratio(_non_empty_lines(texts_to_check))
    if da_ratio >= 0.72:
        issues.append(
            f"too many Korean lines end with '-다' ({da_ratio:.0%}); use a more explanatory, guided rhythm"
        )

    return issues


_EVAL_PROMPT = """
You are evaluating a Korean Threads draft for quality.

Audience:
- developers
- beginners
- vibe coders

Score 0-10 on:
1. clarity
2. usefulness
3. accuracy
4. shareability
5. thread_flow
6. hook_clarity
7. reader_fit
8. specificity
9. actionable_takeaway
10. grounding

Rubric:
- clarity: easy to follow, no jargon wall
- usefulness: gives a practical takeaway
- accuracy: grounded in the selected article, not exaggerated
- shareability: makes someone want to save, share, or follow because the idea is reusable
- thread_flow: replies feel coherent and right-sized for the idea, not random fragments, a short news recap, or padded filler
- reply_brevity: each reply is compact enough to scan in the Threads timeline, not a mini essay
- hook_clarity: first sentence works as a strong CTA or direction of attention, then the main post states one clean thesis in short lines
- reader_fit: it is obvious who this helps and why they should care
- specificity: uses concrete numbers, mechanisms, names, or contrasts from the article
- actionable_takeaway: final reply gives a useful decision rule, next step, or check to run
- grounding: claims stay inside the selected article title, summary, details, and source context
- explanatory_voice: the reader feels guided through why each point matters, not briefed by a stack of declarative facts

Fail aggressively when:
- the draft is only a bland news recap
- the first sentence is slow setup instead of a CTA, payoff, or direction of attention
- the main post hides the strongest point behind background context instead of using inverted pyramid order
- the final reply has no practical takeaway
- background context appears abruptly and breaks the thread
- it does not use the short-line essay rhythm
- it has dense paragraphs instead of one idea per line
- individual replies try to explain too many points at once
- it is padded to an arbitrary reply count instead of stopping when the idea is complete
- Korean endings feel monotonous because every line leans on the same polite ending
- too many lines end with "-다", making the draft feel like a bulletin or report instead of an explanation
- the draft reports facts accurately but does not guide the reader through the meaning
- it leans on generic AI hype like "AI 시대가 왔다" instead of a concrete mechanism or criterion
- a critical issue remains even if the numeric score is decent

Return JSON only:
{{
  "clarity": 0,
  "usefulness": 0,
  "accuracy": 0,
  "shareability": 0,
  "thread_flow": 0,
  "hook_clarity": 0,
  "reader_fit": 0,
  "specificity": 0,
  "actionable_takeaway": 0,
  "grounding": 0,
  "critical_issues": ["..."],
  "suggestions": ["..."]
}}

Content brief:
Topic: {brief_topic}
Target reader: {brief_target_reader}
Reader problem: {brief_reader_problem}
Promise: {brief_promise}
Angle: {brief_angle}
Why now: {brief_why_now}
Takeaway: {brief_takeaway}

Selected article:
Title: {article_title}
Reason: {article_reason}
Evidence: {article_evidence}
Summary: {article_summary}
Details: {article_details}

Main post:
{post_main}

Replies:
{replies_text}
""".strip()

EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "clarity": {"type": "number"},
        "usefulness": {"type": "number"},
        "accuracy": {"type": "number"},
        "shareability": {"type": "number"},
        "thread_flow": {"type": "number"},
        "hook_clarity": {"type": "number"},
        "reader_fit": {"type": "number"},
        "specificity": {"type": "number"},
        "actionable_takeaway": {"type": "number"},
        "grounding": {"type": "number"},
        "critical_issues": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "clarity",
        "usefulness",
        "accuracy",
        "shareability",
        "thread_flow",
        "hook_clarity",
        "reader_fit",
        "specificity",
        "actionable_takeaway",
        "grounding",
        "critical_issues",
        "suggestions",
    ],
    "additionalProperties": True,
}


def _parse_eval_json(text: str) -> dict[str, Any]:
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    return json.loads(text)


def _evaluate_with_ai(content: dict[str, Any], mode: str = "informational") -> dict[str, Any]:
    replies = _extract_replies(content, mode)
    article = content.get("selected_article", {}) or {}
    brief = content.get("content_brief", {}) or {}
    replies_text = "\n".join(f"{index}. {reply}" for index, reply in enumerate(replies, start=1))
    prompt = _EVAL_PROMPT.format(
        brief_topic=brief.get("topic", ""),
        brief_target_reader=brief.get("target_reader", ""),
        brief_reader_problem=brief.get("reader_problem", ""),
        brief_promise=brief.get("promise", ""),
        brief_angle=brief.get("angle", ""),
        brief_why_now=brief.get("why_now", ""),
        brief_takeaway=brief.get("takeaway", ""),
        article_title=article.get("original_title", ""),
        article_reason=article.get("reason", ""),
        article_evidence=_truncate(article.get("evidence", ""), 1200),
        article_summary=_truncate(article.get("summary", ""), 1200),
        article_details=_truncate(article.get("details", ""), 2400),
        post_main=content.get("post_main", ""),
        replies_text=replies_text or "(no replies)",
    )

    return request_structured_json(
        [{"role": "user", "content": prompt}],
        schema=EVAL_SCHEMA,
        max_tokens=900,
    )


def _truncate(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def evaluate(content: dict[str, Any], *, skip_ai: bool = False, mode: str = "informational") -> QAResult:
    rule_issues = _check_rules(content, mode=mode)

    if len(rule_issues) >= 3 and skip_ai:
        return QAResult(passed=False, score=0.0, issues=tuple(rule_issues))

    if skip_ai:
        passed = len(rule_issues) == 0
        return QAResult(
            passed=passed,
            score=1.0 if passed else 0.3,
            issues=tuple(rule_issues),
        )

    try:
        eval_result = _evaluate_with_ai(content, mode=mode)
    except Exception as exc:
        passed = len(rule_issues) == 0
        return QAResult(
            passed=passed,
            score=0.5 if passed else 0.2,
            issues=tuple(rule_issues),
            suggestions=(f"AI evaluation failed: {exc}",),
        )

    weights = {
        "clarity": 0.12,
        "usefulness": 0.16,
        "accuracy": 0.14,
        "shareability": 0.10,
        "thread_flow": 0.14,
        "hook_clarity": 0.10,
        "reader_fit": 0.08,
        "specificity": 0.08,
        "actionable_takeaway": 0.12,
        "grounding": 0.06,
    }
    weighted_sum = sum(float(eval_result.get(key, 0)) * weight for key, weight in weights.items())
    overall = round(weighted_sum / 10, 2)

    ai_issues = [f"[AI] {issue}" for issue in eval_result.get("critical_issues", []) if issue]
    dimension_issues = [
        f"[AI] {key} below threshold ({float(eval_result.get(key, 0)):.1f} < {QA_MIN_DIMENSION})"
        for key in weights
        if float(eval_result.get(key, 0)) < QA_MIN_DIMENSION
    ]
    suggestions = tuple(str(item) for item in eval_result.get("suggestions", []) if item)
    issues = tuple(rule_issues + ai_issues + dimension_issues)
    passed = overall >= QA_PASS_THRESHOLD and len(rule_issues) == 0 and not ai_issues and not dimension_issues

    return QAResult(
        passed=passed,
        score=overall,
        issues=issues,
        suggestions=suggestions,
    )
