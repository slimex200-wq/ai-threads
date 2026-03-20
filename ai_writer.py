import json
import anthropic
from config import ANTHROPIC_API_KEY, MODEL

def build_prompt(articles):
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"\n### Article {i}\n"
        articles_text += f"Title: {a['title']}\n"
        articles_text += f"Summary: {a['summary']}\n"
        articles_text += f"Source: {a['source']}\n"

    return f"""아래 AI 관련 영문 뉴스 기사들을 한국어 인스타그램 카드뉴스용 문구로 변환해주세요.

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
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return json.loads(text)

def generate_card_content(articles):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = build_prompt(articles)

    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    return parse_response(response_text)
