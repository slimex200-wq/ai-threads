import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, MODEL

def build_prompt(articles, select_count=None):
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"\n### Article {i}\n"
        articles_text += f"Title: {a['title']}\n"
        articles_text += f"Summary: {a['summary']}\n"
        articles_text += f"Source: {a['source']}\n"

    selection_instruction = ""
    if select_count and len(articles) > select_count:
        selection_instruction = f"""
먼저 아래 {len(articles)}개 기사 중 가장 중요하고 흥미로운 {select_count}개를 선별해주세요.
선별 기준: AI 업계에 미치는 영향력, 독자 관심도, 정보의 신선도
선별된 {select_count}개 기사만 카드뉴스로 변환해주세요.
"""

    return f"""{selection_instruction}아래 AI 관련 뉴스 기사들을 한국어 인스타그램 카드뉴스용 문구로 변환해주세요.

각 기사에 대해 다음을 생성해주세요:
- title: 카드 제목 (15자 이내, 한국어)
- subtitle: 부제 (20자 이내, 한국어)
- points: 핵심 포인트 2~3개 (각 30자 이내, 한국어)
- source: 출처명

JSON 형식으로 응답해주세요:
{{
  "cover_title": "AI Weekly",
  "cover_date": "YYYY-MM-DD",
  "cards": [
    {{
      "number": 1,
      "title": "...",
      "subtitle": "...",
      "points": ["...", "..."],
      "source": "..."
    }}
  ],
  "closing_message": "읽어주셔서 감사합니다"
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
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    return parse_response(response_text)
