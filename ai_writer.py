"""Threads 바이럴 텍스트 포스트 생성 모듈.

8개 소스에서 수집한 기사 중 가장 바이럴 가능성 높은 1개를 골라
Threads 텍스트 포스트 + 첫 댓글을 생성.
"""

import json
import re

import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from history import normalize_title


def build_prompt(articles, used_titles=None, recent_topics=None, hour=None,
                 top_posts=None, bottom_posts=None):
    """Threads 바이럴 텍스트 포스트 프롬프트."""
    articles_text = _format_articles(articles)
    history_instruction = _build_history_instruction(used_titles)
    diversity_instruction = _build_diversity_instruction(recent_topics)
    tone_instruction = _build_tone_instruction(hour)
    examples_section = _build_examples_section(top_posts, bottom_posts)

    return f"""{history_instruction}{diversity_instruction}{tone_instruction}당신은 한국 AI/테크 커뮤니티에서 활동하는 인플루언서입니다.
아래 기사들 중 **가장 논쟁적이거나 흥미로운 1개**를 골라, Threads 텍스트 포스트를 작성하세요.

## 핵심 목표
**댓글이 달리는 포스트**를 만드는 것. 정보 전달이 아님.
Threads 알고리즘은 포스팅 후 30분 내 댓글(reply)을 가장 중요한 신호로 봄.

## 기사 선별 기준 (우선순위)
1. 의견이 갈릴 수 있는 뉴스 (찬반 논쟁 가능)
2. "진짜?" 하고 놀랄 만한 팩트가 있는 뉴스
3. 개발자/직장인이 공감할 수 있는 뉴스
4. 단순 제품 업데이트나 기능 추가보다는 업계 판도를 바꾸는 뉴스

## 포스트 구조 (반드시 이 순서로)

### post_main: 메인 포스트 (200~350자)
1. **첫 줄 (Hook)**: 놀라운 팩트 또는 도발적 의견으로 시작. "더 보기" 누르기 전에 보이는 2줄이 승부처.
   - 좋은 예: "메타가 인간 없이 AI가 스스로 진화하는 시스템을 만들었는데..."
   - 나쁜 예: "메타가 새로운 AI 기술을 발표했습니다."
2. **본문 (2~4줄)**: 핵심 팩트 1~2개 + 본인 의견/해석. 수치가 있으면 반드시 포함.
3. **마지막 줄 (질문)**: 반드시 독자에게 의견을 묻는 질문으로 끝낼 것.
   - 좋은 예: "너희는 이런 자율 AI, 긍정적으로 봐 아니면 무섭다고 봐?"
   - 좋은 예: "솔직히 이거 개발자한테 좋은 소식이야 나쁜 소식이야?"
   - 나쁜 예: "여러분의 생각은 어떠신가요?" (너무 딱딱함)

### reply_explain: 쉽게 말하면... (80~150자)
비전문가도 이해할 수 있게 이 뉴스가 뭘 뜻하는지 풀어 설명.
- "쉽게 말하면", "한 줄로 요약하면" 등으로 시작 가능
- 전문 용어를 일상 언어로 번역하는 느낌

### reply_important: 왜 중요하냐면... (80~150자)
이 뉴스가 업계/개발자/일반인에게 미치는 실질적 영향.
- 구체적 수치나 비교가 있으면 포함
- "이게 왜 중요하냐면", "파급력이 큰 이유는" 등으로 시작 가능

### reply_action: 그래서 뭘 해야 하냐면... (80~150자)
독자가 취할 수 있는 구체적 행동 제안 또는 관점 제시.
- "지금 당장", "앞으로", "주목해야 할 건" 등으로 시작 가능
- 막연한 조언 금지 ("관심을 가져야 합니다" 같은 빈 말)

### reply_counter: 근데 반대 의견도 있음... (80~150자)
반대 시각이나 리스크를 짧게 제시. 토론 유발이 목적.
- 찬반 양쪽을 보여줘서 댓글에서 싸우게 만드는 것
- "근데", "다만", "반대로 보면" 등으로 시작 가능
- 좋은 예: "근데 이거 반대로 보면 스타트업한테는 오히려 기회일 수도..."
- 좋은 예: "다만 이게 진짜 실현되려면 아직 넘어야 할 산이..."

### reply_casual: 가벼운 한마디 (50~100자)
스레드 마무리용 가벼운 코멘트. 인게이지먼트 시드.
- 매번 다른 시작 패턴 사용할 것. "개인적으로"로 시작 금지.
- 좋은 시작 패턴 예시 (매번 다르게):
  - 반전/추가 정보: "근데 진짜 웃긴 건 이 회사가 작년에는..."
  - 경험 공유: "나도 써봤는데 솔직히..."
  - 도발적 의견: "ㄹㅇ 이러다 3년 안에..."
  - 비교/대조: "구글은 이미 이거 포기했는데..."

## 톤 & 스타일 규칙
- 반말 + 존댓말 자연스럽게 섞기 (한국 온라인 커뮤니티 톤)
- ~한다/~했다/~인듯 + 가끔 ~합니다 존댓말
- "ㅋㅋ", "ㄹㅇ", "솔직히" 같은 구어체 자연스럽게 사용 가능
- 이모지 1~2개 이하 (🤔, 🔥 정도)
- 해시태그(#) 절대 금지
- 맨 끝에 주제 태그 1개만 (예: "AI 뉴스")
- 외부 링크 절대 포함하지 말 것
- "카드뉴스", "자세한 내용은", "정리했습니다" 같은 표현 금지

## 금지 패턴 (이런 포스트는 조회수 0)
- 뉴스 요약 나열 (불릿 포인트로 여러 뉴스 나열)
- "~했습니다. ~했습니다." 반복되는 보도자료 톤
- 의견 없이 팩트만 전달
- 질문 없이 끝나는 포스트
- "여러분의 생각은?" 같은 형식적 질문

JSON 형식으로 응답:
{{
  "selected_article": {{
    "original_title": "선택한 기사의 Title 필드 그대로 복사",
    "link": "선택한 기사의 Link 필드 그대로 복사",
    "reason": "이 기사를 선택한 이유 (내부 참고용)"
  }},
  "post_main": "메인 포스트 (200~350자)",
  "reply_explain": "쉽게 말하면... (80~150자)",
  "reply_important": "왜 중요하냐면... (80~150자)",
  "reply_action": "그래서 뭘 해야 하냐면... (80~150자)",
  "reply_counter": "근데 반대 의견도 있음... (80~150자)",
  "reply_casual": "가벼운 한마디 (50~100자)",
  "topic_tag": "AI 뉴스"
}}

{examples_section}기사들:
{articles_text}"""


def _build_diversity_instruction(recent_topics):
    """최근 다룬 주제/회사 기반 다양성 지시."""
    if not recent_topics:
        return ""
    topics_str = ", ".join(recent_topics)
    return f"""
## 주제 다양성 (필수)
최근 포스팅한 회사/주제: {topics_str}
위 회사/주제와 동일한 기사는 가능한 피해주세요. 다양한 주제를 다루는 것이 팔로워 유지에 중요합니다.
"""


def _build_tone_instruction(hour):
    """시간대별 톤 조정 (KST 기준)."""
    if hour is None:
        return ""
    if 6 <= hour < 12:
        return """
## 시간대 톤: 아침 (뉴스 중심)
지금은 아침이라 출근길에 Threads를 보는 사람이 많음.
팩트 중심의 "이거 알아?" 톤으로, 뉴스 속보 느낌이 효과적.
"""
    elif 12 <= hour < 18:
        return """
## 시간대 톤: 오후 (분석 중심)
지금은 오후라 점심/휴식 시간에 보는 사람이 많음.
"근데 이게 왜 중요하냐면" 식의 분석/해석 톤이 효과적.
"""
    else:
        return """
## 시간대 톤: 저녁/밤 (의견 중심)
지금은 저녁/밤이라 여유롭게 스크롤하는 사람이 많음.
도발적 의견 + 논쟁 유발 톤이 효과적. "솔직히 나는 이렇게 생각하는데..." 식.
"""


def _build_examples_section(top_posts, bottom_posts):
    """성과 데이터 기반 few-shot 예시."""
    if not top_posts and not bottom_posts:
        return ""
    lines = ["\n## 성과 기반 학습 (과거 실제 데이터)\n"]
    if top_posts:
        lines.append("### 높은 성과 포스트 (이런 스타일로 써주세요)")
        for i, p in enumerate(top_posts, 1):
            lines.append(
                f"[Top {i}] 좋아요 {p.get('likes',0)} | 댓글 {p.get('replies',0)} | 조회 {p.get('views',0)}\n"
                f"메인: {p.get('post_main','')}\n"
                f"한마디: {p.get('reply_casual','')}"
            )
    if bottom_posts:
        lines.append("\n### 낮은 성과 포스트 (이런 스타일은 피해주세요)")
        for i, p in enumerate(bottom_posts, 1):
            lines.append(
                f"[Bottom {i}] 좋아요 {p.get('likes',0)} | 댓글 {p.get('replies',0)} | 조회 {p.get('views',0)}\n"
                f"메인: {p.get('post_main','')}"
            )
    lines.append("")
    return "\n".join(lines)


def _format_articles(articles):
    text = ""
    for i, a in enumerate(articles, 1):
        text += f"\n### Article {i}\n"
        text += f"Title: {a['title']}\n"
        text += f"Summary: {a['summary']}\n"
        text += f"Source: {a['source']}\n"
        text += f"Link: {a.get('link', '')}\n"
    return text


def _build_history_instruction(used_titles):
    if not used_titles:
        return ""
    titles_list = "\n".join(f"- {t}" for t in used_titles[:12])
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


def _filter_used_articles(articles, used_titles):
    """이미 포스팅한 기사를 후보에서 제거 (정규화 비교)."""
    if not used_titles:
        return articles
    used_set = {normalize_title(t) for t in used_titles}
    filtered = [a for a in articles if normalize_title(a.get("title", "")) not in used_set]
    if not filtered:
        return articles
    return filtered


def generate_post(articles, used_titles=None, recent_topics=None, hour=None,
                   top_posts=None, bottom_posts=None):
    """Threads 텍스트 포스트 생성."""
    articles = _filter_used_articles(articles, used_titles)
    prompt = build_prompt(articles, used_titles, recent_topics, hour,
                          top_posts, bottom_posts)
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
