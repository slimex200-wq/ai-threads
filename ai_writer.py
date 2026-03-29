"""Threads 바이럴 텍스트 포스트 생성 모듈.

8개 소스에서 수집한 기사 중 가장 바이럴 가능성 높은 1개를 골라
Threads 텍스트 포스트 + 첫 댓글을 생성.
"""

import json
import re

import anthropic
from config import ANTHROPIC_API_KEY, MODEL


def build_prompt(articles, used_titles=None):
    """Threads 바이럴 텍스트 포스트 프롬프트."""
    articles_text = _format_articles(articles)
    history_instruction = _build_history_instruction(used_titles)

    return f"""{history_instruction}
# ROLE
한국 AI/테크 Threads 인플루언서. 반말+존댓말 자연스럽게 섞는 온라인 커뮤니티 톤.
- "ㅋㅋ", "ㄹㅇ", "솔직히" 같은 구어체 OK
- ~한다/~했다/~인듯 + 가끔 ~합니다
- 이모지 1~2개 이하 (🤔, 🔥 정도)

# TASK
아래 기사 중 **가장 논쟁적인 1개**를 골라 Threads 바이럴 포스트를 작성하라.
핵심 KPI: **포스팅 후 30분 내 댓글 수**. 정보 전달이 아니라 토론 유발이 목적.

## 기사 선별 기준 (우선순위)
1. **찬반 논쟁** — "이거 좋은 거야 나쁜 거야?" 싸움이 붙는 뉴스
   - 예: AI 일자리 대체, 윤리 논란, 규제 vs 혁신
2. **충격적 팩트** — "진짜?" 하고 놀랄 수치/사건
   - 예: 매출 1조 돌파, 대량 해고, 예상 못한 실패
3. **내 일에 직접 영향** — 개발자/직장인이 "나도 해당되네" 하는 뉴스
4. **판도 변화** — 업계 구도를 바꾸는 대형 이벤트

Engagement 점수 높은 기사 = 이미 사람들이 반응 중 = 우선 고려.

## 반드시 피할 기사
- 단순 제품 업데이트/버전 출시
- 파트너십/투자 발표 (의견 붙일 거리 없음)
- 며칠 된 뉴스의 후속 보도
- 특정 국가/기업에만 해당하는 로컬 뉴스

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


def generate_post(articles, used_titles=None):
    """Threads 텍스트 포스트 생성."""
    prompt = build_prompt(articles, used_titles)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = message.content[0].text
    try:
        return _parse_response(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[경고] JSON 파싱 실패, 재시도 중... ({e})")
        message = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": "JSON 형식이 올바르지 않습니다. 올바른 JSON으로 다시 응답해주세요."},
            ],
        )
        return _parse_response(message.content[0].text)
