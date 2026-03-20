import json
import re
from datetime import date
import anthropic
from config import ANTHROPIC_API_KEY, MODEL

def build_prompt(articles, select_count=None):
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"\n### Article {i}\n"
        articles_text += f"Title: {a['title']}\n"
        articles_text += f"Summary: {a['summary']}\n"
        if a.get('body'):
            articles_text += f"Body (excerpt): {a['body']}\n"
        articles_text += f"Source: {a['source']}\n"
        articles_text += f"Link: {a.get('link', '')}\n"

    selection_instruction = ""
    if select_count and len(articles) > select_count:
        selection_instruction = f"""
먼저 아래 {len(articles)}개 기사 중 가장 중요하고 흥미로운 {select_count}개를 선별해주세요.
선별 기준: AI 업계에 미치는 영향력, 독자 관심도, 정보의 신선도
선별된 {select_count}개 기사만 카드뉴스로 변환해주세요.
"""

    return f"""{selection_instruction}당신은 AI/테크 업계 시니어 에디터입니다. 아래 기사들을 한국어 인스타그램 카드뉴스로 변환해주세요.

## 톤 & 스타일
- 업계 전문가가 동료에게 브리핑하는 느낌
- 반드시 구체적 수치, 금액, 날짜, 인물명을 포함할 것
- "폭발적 증가", "절호의 기회" 같은 빈 수식어 금지
- 마지막 포인트는 반드시 "왜 중요한지" 분석 (So What)으로 마무리

## 각 기사에 대해:
- title: 임팩트 있는 제목 (15자 이내, 한국어)
- subtitle: 핵심 맥락 한 줄 (25자 이내, 한국어)
- points: 핵심 포인트 5개 (각 35자 이내, 한국어)
  - 1~3번째: 구체적 팩트 (수치, 인물, 날짜 포함)
  - 4번째: 업계 영향 또는 파급 효과
  - 5번째: "왜 주목해야 하는가" 에디터 관점 분석
- insight: 에디터 한줄평 (30자 이내, 독자에게 시사점)
- source: 출처명
- link: 원문 URL (기사의 Link 필드 그대로 사용)
- keywords: 이 기사의 핵심 키워드 1~2개 (표지에 사용)
- original_title: 원본 기사의 Title 필드를 그대로 복사 (이미지 매칭에 사용, 절대 수정 금지)

## 추가 생성 항목:
- cover_headline: 이번 회차의 핵심 트렌드를 담은 표지 헤드라인 (20자 이내, 한국어, 예: "AI가 제조업을 삼킨다")
- trend_summary: 선별된 기사들을 관통하는 공통 트렌드 한 문장 (40자 이내)
- caption: Threads 메인 스레드용 텍스트 (요약 1~2문장 + 해시태그 5~8개, 원문 링크는 포함하지 말 것)

JSON 형식으로 응답해주세요:
{{
  "cover_headline": "표지 헤드라인",
  "cover_date": "{date.today().isoformat()}",
  "trend_summary": "이번 주 AI 트렌드 한 줄 요약",
  "cards": [
    {{
      "number": 1, "original_title": "원문 기사 Title 그대로 복사",
      "title": "...",
      "subtitle": "...",
      "points": ["팩트1", "팩트2", "팩트3", "영향", "So What"],
      "insight": "에디터 한줄평",
      "source": "...",
      "link": "https://...",
      "keywords": ["키워드1"]
    }}
  ],
  "closing_message": "읽어주셔서 감사합니다",
  "caption": "메인 스레드 캡션 (링크 없이, 해시태그 포함)"
}}

기사들:
{articles_text}"""

def parse_response(text):
    text = text.strip()
    # 마크다운 코드블록 추출
    code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    else:
        # JSON 객체 직접 추출
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    return json.loads(text)

def generate_card_content(articles, select_count=None):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = build_prompt(articles, select_count=select_count)

    message = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    try:
        return parse_response(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[경고] JSON 파싱 실패, 재시도 중... ({e})")
        message = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": "JSON 형식이 올바르지 않습니다. 올바른 JSON으로 다시 응답해주세요."},
            ],
        )
        return parse_response(message.content[0].text)
