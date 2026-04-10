"""Threads 바이럴/정보성 텍스트 포스트 생성 모듈.

8개 소스에서 수집한 기사 중 가장 적합한 1개를 골라
Threads 텍스트 포스트 + 첫 댓글을 생성.
"""

import json
import re

import anthropic
from config import ANTHROPIC_API_KEY, MODEL


def build_prompt(articles, used_titles=None, engagement_patterns=None, mode="informational"):
    """Threads 포스트 프롬프트. mode='viral' 또는 'informational'."""
    if mode == "viral":
        return _build_viral_prompt(articles, used_titles, engagement_patterns)
    return _build_informational_prompt(articles, used_titles, engagement_patterns)


def _build_viral_prompt(articles, used_titles=None, engagement_patterns=None):
    """Threads 바이럴 텍스트 포스트 프롬프트."""
    articles_text = _format_articles(articles)
    history_instruction = _build_history_instruction(used_titles)
    engagement_instruction = _build_engagement_instruction(engagement_patterns)

    return f"""{history_instruction}{engagement_instruction}
# ROLE
한국 AI/테크 Threads 인플루언서. 반말+존댓말 자연스럽게 섞는 온라인 커뮤니티 톤.
- "ㅋㅋ", "ㄹㅇ", "솔직히" 같은 구어체 OK
- ~한다/~했다/~인듯 + 가끔 ~합니다
- 이모지 1~2개 이하 (🤔, 🔥 정도)

# TASK
아래 기사 중 **가장 논쟁적인 1개**를 골라 Threads 바이럴 포스트를 작성하라.
핵심 KPI: **포스팅 후 30분 내 댓글 수**. 정보 전달이 아니라 토론 유발이 목적.

## 기사 선별 필수 테스트 (2개 모두 통과해야 선택 가능)
1. **대중 인지도 테스트** — "비개발자 직장인이 제목만 보고 관심 가질까?" No면 탈락.
   - O: 코카콜라, 구글, 삼성, 오픈AI, 메타 등 누구나 아는 브랜드/인물
   - X: 얀 르쿤, 사카나AI, 특정 연구자 이름 (대중이 모름)
2. **위협 근접성 테스트** — "읽는 사람이 '나도 해당되네'라고 느낄까?" No면 후순위.
   - O: CEO도 AI 때문에 교체, 채용 동결, 일자리 위협
   - X: 벤치마크 점수 갱신, 모델 아키텍처 변경 (전문가만 관심)

## 기사 선별 기준 (우선순위, 위 테스트 통과 전제)
1. **내 직업/삶에 직접 위협** — "나도 잘릴 수 있겠다", "내 일이 바뀌겠다" 위기감
   - 예: CEO 교체, 대량 해고, 채용 동결, AI가 인간 능가
2. **찬반 논쟁** — "이거 좋은 거야 나쁜 거야?" 싸움이 붙는 뉴스
3. **충격적 숫자** — "진짜?" 하고 놀랄 수치 (매출, 시총 증발, % 감축 등)
4. **빅테크 내부 이야기** — 일반인이 못 보는 내부 사정 (비밀 도구, 내부 갈등)

Engagement 점수 높은 기사 = 이미 사람들이 반응 중 = 우선 고려.

## 반드시 피할 기사
- 단순 제품 업데이트/버전 출시
- 파트너십/투자 발표 (의견 붙일 거리 없음)
- 며칠 된 뉴스의 후속 보도
- 특정 국가/기업에만 해당하는 로컬 뉴스
- 순수 학술/연구 뉴스 (논문, 벤치마크, 모델 구조). 단, "이 기술이 나오면 OO가 바뀐다"가 명확한 기술 뉴스는 OK.

## 포스트 작성 규칙

### post_main (200~350자)
1. **Hook (첫 2줄)** — 놀라운 팩트 또는 도발적 의견. "더 보기" 전에 보이는 승부처.
   - O: "메타가 인간 없이 AI가 스스로 진화하는 시스템을 만들었는데..."
   - X: "메타가 새로운 AI 기술을 발표했습니다."
2. **본문 (2~4줄)** — 핵심 팩트 1~2개 + 본인 의견. 수치 필수 포함.
3. **질문 (마지막 줄)** — 독자에게 의견을 묻는 질문으로 반드시 끝낼 것.
   - O: "솔직히 이거 개발자한테 좋은 소식이야 나쁜 소식이야?"
   - X: "여러분의 생각은 어떠신가요?" (딱딱함)

### reply_explain (80~150자)
비전문가용 풀어쓰기. "쉽게 말하면", "한 줄로 요약하면" 등으로 시작.

### reply_important (80~150자)
실질적 영향. 수치/비교 포함. "이게 왜 중요하냐면", "파급력이 큰 이유는" 등.

### reply_action (80~150자)
구체적 행동 제안. "지금 당장", "주목해야 할 건" 등. 막연한 조언 금지.

### reply_counter (80~150자)
반대 시각/리스크. 토론 유발용. "근데", "다만", "반대로 보면" 등.
- O: "근데 이거 반대로 보면 스타트업한테는 오히려 기회일 수도..."

### reply_casual (50~100자)
가벼운 마무리. 매번 다른 패턴. "개인적으로" 시작 금지.
- 반전: "근데 진짜 웃긴 건 이 회사가 작년에는..."
- 경험: "나도 써봤는데 솔직히..."
- 도발: "ㄹㅇ 이러다 3년 안에..."
- 비교: "구글은 이미 이거 포기했는데..."

## 금지 패턴
- 해시태그(#), 외부 링크, "카드뉴스", "자세한 내용은", "정리했습니다"
- topic_tag는 항상 "ai.threads" 고정. 변경 금지.
- 불릿 포인트 뉴스 나열, 보도자료 톤, 의견 없는 팩트 전달, 질문 없는 마무리

# FORMAT
JSON으로 응답. 다른 텍스트 없이 JSON만 출력.
{{
  "selected_article": {{
    "original_title": "선택한 기사의 Title 필드 그대로 복사",
    "link": "선택한 기사의 Link 필드 그대로 복사",
    "reason": "이 기사를 선택한 이유 (논쟁 포텐셜 중심)"
  }},
  "post_main": "메인 포스트 (200~350자)",
  "reply_explain": "쉽게 말하면... (80~150자)",
  "reply_important": "왜 중요하냐면... (80~150자)",
  "reply_action": "그래서 뭘 해야 하냐면... (80~150자)",
  "reply_counter": "근데 반대 의견도 있음... (80~150자)",
  "reply_casual": "가벼운 한마디 (50~100자)",
  "topic_tag": "ai.threads"
}}

# 기사들
{articles_text}"""


def _build_informational_prompt(articles, used_titles=None, engagement_patterns=None):
    """바이브코더 대상 정보성 포스트 프롬프트."""
    articles_text = _format_articles(articles)
    history_instruction = _build_history_instruction(used_titles)
    engagement_instruction = _build_engagement_instruction(engagement_patterns)

    return f"""{history_instruction}{engagement_instruction}
# ROLE
바이브코더 대상 AI 뉴스를 정리해주는 사람. "뉴스 기자"와 "개발 선배" 사이 포지셔닝.
- 구어체 유지하되 슬랭("ㅋㅋ", "ㄹㅇ") 최소화
- 3문장 연속 같은 종결어미 금지
- 종결 패턴 로테이션: ~다(팩트) / ~거든(설명) / 명사종결(리듬) / ~인 셈이다(정리) / 질문형(참여)
- 문장 리듬: 짧은 팩트(3-5단어) → 맥락 설명 → 풀어주는 문장 → 다시 짧게
- 강한 의견 > 애매한 중립
- 구체적 숫자 > 모호한 형용사

# TASK
아래 기사 중 **바이브코더에게 가장 실용적인 1개**를 골라 정보성 포스트를 작성하라.
핵심 KPI: 읽는 사람이 "이거 나한테도 해당되네"라고 느끼는 것. 정보 전달 + 실용적 인사이트가 목적.

## 기사 선별 필수 테스트 (2개 모두 통과해야 선택 가능)
1. **실용성 테스트** — "바이브코더가 이걸 알면 뭔가 달라지나?" No면 탈락.
   - O: 새 AI 코딩 도구 출시, API 변경, 가격 변동, 성능 벤치마크
   - X: 순수 비즈니스 뉴스, 투자/인수, 정치적 규제
2. **대중성 테스트** — "코딩 입문자도 관심 가질 만한가?" No면 후순위.
   - O: ChatGPT, Claude, Cursor, GitHub Copilot 관련
   - X: 특정 프레임워크 내부 구현, 학술 논문

## 기사 선별 기준 (우선순위, 위 테스트 통과 전제)
1. AI 코딩 도구 변화 (출시/업데이트/가격)
2. 바이브코딩 워크플로우에 영향 주는 뉴스
3. AI 시장 변화 중 개발자에게 직접 영향 있는 것
4. 충격적 숫자/트렌드

Engagement 점수 높은 기사 = 이미 사람들이 반응 중 = 우선 고려.

## 반드시 피할 기사
- 순수 비즈니스 뉴스 (투자, 인수, 파트너십)
- 정치/규제 뉴스 (바이브코더 행동에 영향 없는 것)
- 며칠 된 뉴스의 후속 보도
- 순수 학술/연구 뉴스. 단, "이 기술이 나오면 바이브코딩이 바뀐다"가 명확한 기술 뉴스는 OK.

## 포스트 작성 규칙

### post_main (200~400자)
1. **Hook (첫 1~2문장)** — 구체적 숫자, 반상식, 비하인드, 시간 투자 중 택1.
   - O: "Google이 Gemini CLI를 오픈소스로 풀었다. 무료."
   - O: "바이브코딩이 개발자를 대체한다? 정반대다."
   - X: "오늘은 X에 대해 이야기해보겠습니다." (약한 시작)
2. **본문 (2~4줄)** — 핵심 팩트 + "바이브코더에게 왜 중요한지" (So What). 수치 포함.
3. **마무리** — 강한 의견 또는 질문. 어느 쪽이든 OK.

### reply_background (100~200자)
이 뉴스가 나온 맥락/배경. "이게 갑자기 나온 게 아니거든", "나온 이유가 있는데" 등.

### reply_impact (100~200자)
바이브코더에게 구체적 영향. "달라지는 건 하나", "입장에서 보면" 등. 막연한 일반론 금지.

### reply_compare (100~200자)
기존 도구/방식과 비교. 객관적 분석. "A는 ~형, B는 ~형, C는 ~인데" 등.

### reply_summary (80~150자)
핵심 한줄 정리 + 본인 의견. "정리하면", "결론은" 등.

## 톤 레퍼런스 (이 수준을 목표로)
```
[메인]
Google이 Gemini CLI를 오픈소스로 풀었다. 무료.

터미널에서 Gemini 2.5 Pro를 바로 쓸 수 있는 도구인데, Claude Code가 개발자 시장을 먹기 시작하니까 Google이 무료 카드를 꺼낸 거다. 바이브코딩 입문하려는데 월 구독료가 걸렸던 사람들한테는 진입장벽이 사라진 셈.

유료 도구 없이도 AI 코딩을 시작할 수 있는 시대가 된 건데, 문제는 뭘 골라야 하느냐는 거다.

[reply_background]
이게 갑자기 나온 게 아니거든. MS는 Copilot, Anthropic은 Claude Code, Cursor는 독자 노선 — 근데 Google만 CLI 도구가 없었다. 오픈소스로 낸 건 "일단 써보게 하자"는 생태계 선점 전략.

[reply_impact]
바이브코더 입장에서 달라지는 건 하나. 선택지가 늘었다는 거다. 프로젝트 초기 세팅이나 간단한 자동화 스크립트 정도는 무료 티어로 충분히 되니까, 유료 도구는 진짜 복잡한 작업에만 쓰면 된다.

[reply_compare]
Claude Code는 에이전트형. 파일 읽고 수정까지 알아서 해준다. Cursor는 에디터 통합형. 코드 쓰면서 실시간 보조를 받는 방식이고. Gemini CLI는 그 중간인데, 1M 컨텍스트가 강점이라 큰 코드베이스를 한번에 넘길 때 유리할 수 있다. 만능은 없고 용도가 다른 거다.

[reply_summary]
도구 경쟁이 붙으면 결국 사용자가 이득. 하나에 올인하기보다 용도별로 써보고 자기한테 맞는 조합을 찾는 게 맞는 방향이라고 본다.
```

## 금지 패턴
- 해시태그(#), 외부 링크, "카드뉴스", "자세한 내용은", "정리했습니다"
- topic_tag는 항상 "ai.threads" 고정. 변경 금지.
- 클릭베이트 ("인생이 바뀝니다", "비밀 공개", "충격")
- 의견 없는 뉴스 나열, 보도자료 톤 ("~라고 밝혔다", "~를 발표했다"로 끝나는 문장)

# FORMAT
JSON으로 응답. 다른 텍스트 없이 JSON만 출력.
{{
  "selected_article": {{
    "original_title": "선택한 기사의 Title 필드 그대로 복사",
    "link": "선택한 기사의 Link 필드 그대로 복사",
    "reason": "이 기사를 선택한 이유 (실용성 중심)"
  }},
  "post_main": "메인 포스트 (200~400자)",
  "reply_background": "배경/맥락 (100~200자)",
  "reply_impact": "바이브코더 영향 (100~200자)",
  "reply_compare": "비교/분석 (100~200자)",
  "reply_summary": "핵심 정리 + 의견 (80~150자)",
  "topic_tag": "ai.threads"
}}

# 기사들
{articles_text}"""


def _format_articles(articles):
    text = ""
    for i, a in enumerate(articles, 1):
        text += f"\n### Article {i}\n"
        text += f"Title: {a['title']}\n"
        text += f"Summary: {a['summary']}\n"
        text += f"Source: {a['source']}\n"
        text += f"Link: {a.get('link', '')}\n"
        eng = a.get("engagement", 0)
        if eng:
            text += f"Engagement: {eng}\n"
    return text


def _build_history_instruction(used_titles):
    if not used_titles:
        return ""
    titles_list = "\n".join(f"- {t}" for t in used_titles)
    return f"""
## 중복 방지 (필수)
아래는 최근 며칠간 이미 다룬 기사 제목입니다. **같은 주제, 같은 사건, 같은 인물/회사에 대한 기사는 반드시 제외**해주세요.
URL이 다르더라도 동일한 이벤트를 다룬 기사는 중복입니다.
{titles_list}
"""


def _build_engagement_instruction(patterns):
    if not patterns:
        return ""

    top = patterns.get("top", [])
    bottom = patterns.get("bottom", [])
    avg = patterns.get("avg", {})

    if not top:
        return ""

    lines = ["\n## 과거 포스트 성과 분석 (자가학습 데이터)"]
    lines.append("아래 데이터를 참고하여 engagement가 높은 패턴을 따르고, 낮은 패턴은 피하라.\n")

    lines.append("### 잘 된 포스트 (이 패턴을 따라라)")
    for i, p in enumerate(top, 1):
        lines.append(f"{i}. [{p['date']}] \"{p.get('title', '')[:50]}\"")
        lines.append(f"   views={p.get('views',0)}, likes={p.get('likes',0)}, replies={p.get('replies',0)}, reposts={p.get('reposts',0)} (score={p.get('score',0)})")
        if p.get("post_main"):
            lines.append(f"   메인: {p['post_main'][:60]}...")
        if p.get("reply_casual"):
            lines.append(f"   한마디: {p['reply_casual'][:50]}...")

    if bottom:
        lines.append("\n### 안 된 포스트 (이 패턴을 피하라)")
        for i, p in enumerate(bottom, 1):
            lines.append(f"{i}. [{p['date']}] \"{p.get('title', '')[:50]}\"")
            lines.append(f"   views={p.get('views',0)}, likes={p.get('likes',0)}, replies={p.get('replies',0)}, reposts={p.get('reposts',0)} (score={p.get('score',0)})")
            if p.get("post_main"):
                lines.append(f"   메인: {p['post_main'][:60]}...")

    if avg:
        lines.append(f"\n### 평균 수치")
        lines.append(f"views={avg.get('views',0)}, likes={avg.get('likes',0)}, replies={avg.get('replies',0)}, reposts={avg.get('reposts',0)} (score={avg.get('score',0)})")

    return "\n".join(lines) + "\n"


def _parse_response(text):
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    return json.loads(text)


def evaluate_worthiness(articles, mode="informational"):
    """Evaluate whether articles are worth posting. Returns (bool, reason)."""
    if not articles:
        return False, "기사가 없음"

    articles_text = _format_articles(articles[:10])

    if mode == "viral":
        prompt = f"""아래 기사들을 보고 Threads에 바이럴 포스트로 올릴 만한 기사가 있는지 판단해.

판단 기준:
1. 대중 인지도 — 비개발자도 관심 가질 만한 브랜드/인물인가?
2. 위협 근접성 — 읽는 사람이 "나도 해당되네"라고 느낄까?
3. 논쟁성 — 찬반이 갈리는가?
4. 신선도 — 이미 다 아는 뉴스가 아닌가?

반드시 피할 기사: 단순 업데이트, 파트너십 발표, 순수 학술 연구

JSON으로만 응답:
{{"worthy": true/false, "reason": "판단 이유 한 줄"}}

{articles_text}"""
    else:
        prompt = f"""아래 기사들을 보고 바이브코더에게 실용적인 기사가 있는지 판단해.

판단 기준:
1. 실용성 — AI 코딩 도구, API, 가격, 워크플로우 변화가 있는가?
2. 대중성 — 코딩 입문자도 관심 가질 만한가?
3. 신선도 — 이미 다 아는 뉴스가 아닌가?

피할 기사: 순수 비즈니스 뉴스, 정치/규제, 학술 논문

JSON으로만 응답:
{{"worthy": true/false, "reason": "판단 이유 한 줄"}}

{articles_text}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        result = _parse_response(message.content[0].text)
        return result.get("worthy", True), result.get("reason", "")
    except Exception:
        # Parsing failed — default to posting
        return True, "가치 판단 파싱 실패, 기본 포스팅 진행"


def generate_post(articles, used_titles=None, engagement_patterns=None,
                  qa_feedback=None, mode="informational"):
    """Threads 텍스트 포스트 생성.

    Args:
        articles: 필터링된 기사 리스트
        used_titles: 최근 사용한 기사 제목 (중복 방지)
        engagement_patterns: engagement 분석 패턴 (자가학습)
        qa_feedback: QA 실패 시 피드백 dict (issues, suggestions, previous_post)
        mode: "viral" 또는 "informational"
    """
    prompt = build_prompt(articles, used_titles, engagement_patterns, mode)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    messages = [{"role": "user", "content": prompt}]

    # QA 피드백이 있으면 이전 결과 + 피드백을 대화에 주입
    if qa_feedback:
        prev_json = json.dumps(qa_feedback["previous_post"], ensure_ascii=False, indent=2)
        feedback_text = _build_qa_feedback(qa_feedback)
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": prev_json},
            {"role": "user", "content": feedback_text},
        ]

    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=messages,
    )
    response_text = message.content[0].text
    try:
        result = _parse_response(response_text)
        return _ensure_required_fields(result)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[경고] JSON 파싱 실패, 재시도 중... ({e})")
        message = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[
                *messages,
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": "JSON 형식이 올바르지 않습니다. 올바른 JSON으로 다시 응답해주세요."},
            ],
        )
        return _ensure_required_fields(_parse_response(message.content[0].text))


def _ensure_required_fields(content: dict) -> dict:
    """LLM이 누락시키는 필수 필드를 강제 보정."""
    if not content.get("topic_tag"):
        content = {**content, "topic_tag": "ai.threads"}
    return content


def _build_qa_feedback(qa_feedback):
    """QA 평가 결과를 Generator 재생성용 피드백 텍스트로 변환."""
    lines = ["# QA 평가 결과: 불합격. 아래 피드백을 반영해서 다시 작성하라.\n"]

    issues = qa_feedback.get("issues", ())
    if issues:
        lines.append("## 문제점 (반드시 수정)")
        for issue in issues:
            lines.append(f"- {issue}")

    suggestions = qa_feedback.get("suggestions", ())
    if suggestions:
        lines.append("\n## 개선 제안")
        for s in suggestions:
            lines.append(f"- {s}")

    score = qa_feedback.get("score", 0)
    lines.append(f"\n## 점수: {score:.2f} / 1.00 (0.65 이상 필요)")
    lines.append("\n같은 기사를 선택해도 좋지만, 글의 톤/구조/표현을 개선하라.")
    lines.append("다른 기사가 더 적합하다면 기사 변경도 가능하다.")
    lines.append('반드시 "topic_tag": "ai.threads"를 포함하라. 모든 필드를 빠짐없이 채워라.')
    lines.append("JSON으로만 응답하라.")

    return "\n".join(lines)
