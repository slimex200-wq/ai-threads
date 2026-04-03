"""독립 QA 평가자 — Generator/Evaluator 패턴.

생성된 포스트를 별도 Claude 호출로 평가.
생성자(ai_writer)와 분리된 회의적 평가자 역할.

Ref: Anthropic "Harness Design for Long-Running Apps" (2026-03-24)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import anthropic
from config import ANTHROPIC_API_KEY, MODEL


@dataclass(frozen=True)
class QAResult:
    """QA 평가 결과."""

    passed: bool
    score: float  # 0.0 ~ 1.0
    issues: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()


# --- 규칙 기반 검증 (빠르고 저렴) ---

_CHAR_LIMITS_VIRAL: dict[str, tuple[int, int]] = {
    "post_main": (200, 350),
    "reply_explain": (80, 150),
    "reply_important": (80, 150),
    "reply_action": (80, 150),
    "reply_counter": (80, 150),
    "reply_casual": (50, 100),
}

_CHAR_LIMITS_INFORMATIONAL: dict[str, tuple[int, int]] = {
    "post_main": (200, 400),
    "reply_background": (100, 200),
    "reply_impact": (100, 200),
    "reply_compare": (100, 200),
    "reply_summary": (80, 150),
}

_REQUIRED_VIRAL: tuple[str, ...] = (
    "post_main", "reply_explain", "reply_important",
    "reply_action", "reply_counter", "reply_casual",
    "selected_article", "topic_tag",
)

_REQUIRED_INFORMATIONAL: tuple[str, ...] = (
    "post_main", "reply_background", "reply_impact",
    "reply_compare", "reply_summary",
    "selected_article", "topic_tag",
)

_BANNED_PATTERNS: tuple[str, ...] = (
    "#",            # 해시태그
    "http://",      # 외부 링크
    "https://",     # 외부 링크
    "카드뉴스",
    "자세한 내용은",
    "정리했습니다",
)


def _check_rules(content: dict, mode: str = "viral") -> list[str]:
    """규칙 기반 검증. 위반 사항 리스트 반환.

    Args:
        content: 생성된 포스트 딕셔너리
        mode: "viral" 또는 "informational"
    """
    issues: list[str] = []

    char_limits = _CHAR_LIMITS_VIRAL if mode == "viral" else _CHAR_LIMITS_INFORMATIONAL
    required = _REQUIRED_VIRAL if mode == "viral" else _REQUIRED_INFORMATIONAL

    # 필수 필드 존재
    for key in required:
        if key not in content or not content[key]:
            issues.append(f"필수 필드 누락: {key}")

    # 글자수 검증
    for key, (lo, hi) in char_limits.items():
        text = content.get(key, "")
        length = len(text)
        if length < lo:
            issues.append(f"{key}: {length}자 (최소 {lo}자 미달)")
        elif length > hi:
            issues.append(f"{key}: {length}자 (최대 {hi}자 초과)")

    # 금지 패턴 (char_limits의 reply 키들 대상)
    for key in char_limits:
        text = content.get(key, "")
        for pattern in _BANNED_PATTERNS:
            if pattern in text:
                issues.append(f"{key}에 금지 패턴 포함: '{pattern}'")

    # topic_tag 고정값 확인
    if content.get("topic_tag") != "ai.threads":
        issues.append(f"topic_tag가 'ai.threads'가 아님: {content.get('topic_tag')}")

    # post_main 질문 유도 — viral 전용
    if mode == "viral":
        post_main = content.get("post_main", "")
        if post_main and "?" not in post_main:
            issues.append("post_main이 질문으로 끝나지 않음 (댓글 유도 부족)")

    # selected_article 필수 하위 필드
    article = content.get("selected_article", {})
    if isinstance(article, dict):
        for sub_key in ("original_title", "link", "reason"):
            if not article.get(sub_key):
                issues.append(f"selected_article.{sub_key} 누락")

    return issues


# --- AI 기반 평가 (회의적 별도 Claude 호출) ---

_EVAL_PROMPT_VIRAL = """# ROLE
너는 Threads 바이럴 콘텐츠 전문 QA 심사관이다.
생성된 포스트를 **회의적으로** 평가하라. 관대하지 마라.

# TASK
아래 포스트를 5가지 기준으로 0~10점 평가하라.

## 평가 기준
1. **hook_power** (0~10): 첫 2줄만 보고 "더 보기"를 누를까? 도발적이고 구체적인가?
2. **debate_potential** (0~10): 댓글에서 찬반이 갈릴까? "이건 좀..." 하고 의견 쓸 만큼?
3. **tone_authenticity** (0~10): 진짜 사람이 쓴 것 같은가? 봇/보도자료 냄새 없는가?
4. **reply_coherence** (0~10): 5개 대댓글이 자연스럽게 이어지는가? 반복/모순 없는가?
5. **rule_compliance** (0~10): 해시태그, 링크, "카드뉴스" 등 금지 패턴 없는가?

## 심사 원칙
- 6점 이하는 "실패" 수준이다. 기준이 높아야 한다.
- "그럭저럭 괜찮다"는 7점이다. 8점부터가 "좋다".
- 10점은 거의 없다.
- 의심스러우면 낮게 준다.

## 포스트 내용
```
메인: {post_main}

대댓글1 (설명): {reply_explain}
대댓글2 (중요성): {reply_important}
대댓글3 (행동): {reply_action}
대댓글4 (반론): {reply_counter}
대댓글5 (가벼움): {reply_casual}
```

## 선택된 기사
제목: {article_title}
이유: {article_reason}

# FORMAT
JSON으로만 응답. 다른 텍스트 없이.
{{
  "hook_power": 0,
  "debate_potential": 0,
  "tone_authenticity": 0,
  "reply_coherence": 0,
  "rule_compliance": 0,
  "overall": 0.0,
  "critical_issues": ["있으면 적기"],
  "suggestions": ["개선 제안"]
}}
overall = 5개 점수의 가중 평균 (hook_power 30%, debate_potential 30%, tone 20%, coherence 10%, compliance 10%) / 10
"""

_EVAL_PROMPT_INFORMATIONAL = """# ROLE
너는 바이브코더 대상 AI 뉴스 콘텐츠 QA 심사관이다.
정보성 포스트를 **회의적으로** 평가하라. 관대하지 마라.

# TASK
아래 포스트를 5가지 기준으로 0~10점 평가하라.

## 평가 기준
1. **clarity** (0~10): 코딩 입문자가 읽고 이해할 수 있는가? 전문용어에 설명 없이 넘어가진 않는가?
2. **usefulness** (0~10): 바이브코더가 실제로 써먹을 수 있는 정보인가? "그래서 나한테 뭐가 달라지는데?"에 답하는가?
3. **accuracy** (0~10): 팩트가 정확하고 과장이 없는가? 클릭베이트 냄새 없는가?
4. **tone** (0~10): 자연스러운 구어체인가? 보도자료/번역투 아닌가? 종결어미가 단조롭지 않은가?
5. **structure** (0~10): 메인→배경→영향→비교→정리 흐름이 논리적인가? 각 파트가 제 역할을 하는가?

## 심사 원칙
- 6점 이하는 "실패" 수준이다. 기준이 높아야 한다.
- "그럭저럭 괜찮다"는 7점이다. 8점부터가 "좋다".
- 10점은 거의 없다.
- 의심스러우면 낮게 준다.

## 포스트 내용
```
메인: {post_main}

배경: {reply_background}
영향: {reply_impact}
비교: {reply_compare}
정리: {reply_summary}
```

## 선택된 기사
제목: {article_title}
이유: {article_reason}

# FORMAT
JSON으로만 응답. 다른 텍스트 없이.
{{
  "clarity": 0,
  "usefulness": 0,
  "accuracy": 0,
  "tone": 0,
  "structure": 0,
  "overall": 0.0,
  "critical_issues": ["있으면 적기"],
  "suggestions": ["개선 제안"]
}}
overall = 5개 점수의 가중 평균 (clarity 30%, usefulness 30%, accuracy 20%, tone 10%, structure 10%) / 10
"""


def _parse_eval_json(text: str) -> dict:
    """평가 응답에서 JSON 추출."""
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    return json.loads(text)


def _evaluate_with_ai(content: dict, mode: str = "viral") -> dict:
    """별도 Claude 호출로 포스트 품질 평가."""
    article = content.get("selected_article", {})
    if mode == "informational":
        prompt = _EVAL_PROMPT_INFORMATIONAL.format(
            post_main=content.get("post_main", ""),
            reply_background=content.get("reply_background", ""),
            reply_impact=content.get("reply_impact", ""),
            reply_compare=content.get("reply_compare", ""),
            reply_summary=content.get("reply_summary", ""),
            article_title=article.get("original_title", ""),
            article_reason=article.get("reason", ""),
        )
    else:
        prompt = _EVAL_PROMPT_VIRAL.format(
            post_main=content.get("post_main", ""),
            reply_explain=content.get("reply_explain", ""),
            reply_important=content.get("reply_important", ""),
            reply_action=content.get("reply_action", ""),
            reply_counter=content.get("reply_counter", ""),
            reply_casual=content.get("reply_casual", ""),
            article_title=article.get("original_title", ""),
            article_reason=article.get("reason", ""),
        )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_eval_json(message.content[0].text)


# --- 통합 평가 ---

QA_PASS_THRESHOLD = 0.65  # overall 0.65 이상이면 통과


def evaluate(content: dict, *, skip_ai: bool = False, mode: str = "viral") -> QAResult:
    """생성된 포스트를 규칙 + AI로 평가.

    Args:
        content: ai_writer.generate_post() 반환값
        skip_ai: True면 규칙 검증만 (비용 절약, 테스트용)
        mode: "viral" 또는 "informational"

    Returns:
        QAResult with pass/fail, score, issues, suggestions
    """
    # 1단계: 규칙 기반 (무료, 즉시)
    rule_issues = _check_rules(content, mode=mode)

    # 규칙 위반이 3개 이상이면 AI 호출 없이 바로 실패
    if len(rule_issues) >= 3:
        return QAResult(
            passed=False,
            score=0.0,
            issues=tuple(rule_issues),
            suggestions=("규칙 위반이 너무 많아 AI 평가 생략",),
        )

    if skip_ai:
        passed = len(rule_issues) == 0
        return QAResult(
            passed=passed,
            score=1.0 if passed else 0.3,
            issues=tuple(rule_issues),
        )

    # 2단계: AI 기반 (회의적 별도 호출)
    try:
        eval_result = _evaluate_with_ai(content, mode=mode)
    except Exception as e:
        # AI 평가 실패 시 규칙 검증만으로 판단
        print(f"  [QA] AI 평가 실패, 규칙만 적용: {e}")
        passed = len(rule_issues) == 0
        return QAResult(
            passed=passed,
            score=0.5 if passed else 0.2,
            issues=tuple(rule_issues),
            suggestions=("AI 평가 실패로 규칙 검증만 수행됨",),
        )

    # AI 반환 overall 무시, 개별 점수로 직접 계산
    ai_issues = eval_result.get("critical_issues", [])
    suggestions = eval_result.get("suggestions", [])

    if mode == "viral":
        weights = {"hook_power": 0.3, "debate_potential": 0.3, "tone_authenticity": 0.2,
                    "reply_coherence": 0.1, "rule_compliance": 0.1}
    else:
        weights = {"clarity": 0.3, "usefulness": 0.3, "accuracy": 0.2,
                    "tone": 0.1, "structure": 0.1}

    weighted_sum = sum(eval_result.get(k, 0) * w for k, w in weights.items())
    overall = round(weighted_sum / 10, 2)  # 0~1 스케일

    all_issues = rule_issues + [f"[AI] {i}" for i in ai_issues if i]
    passed = overall >= QA_PASS_THRESHOLD and len(rule_issues) == 0

    return QAResult(
        passed=passed,
        score=round(overall, 2),
        issues=tuple(all_issues),
        suggestions=tuple(s for s in suggestions if s),
    )
