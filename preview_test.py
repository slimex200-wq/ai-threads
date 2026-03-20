"""Generate sample cards for design preview."""
from pathlib import Path
from card_renderer import render_cover, render_news_card, render_closing

output = Path(__file__).parent / "design-preview-v3"
output.mkdir(exist_ok=True)

# Cover
render_cover("AI Weekly", "2026.03.20", output, total_cards=4)

# News cards
samples = [
    {
        "number": 1,
        "title": "GPT-5 공개 임박",
        "subtitle": "OpenAI, 차세대 모델 발표 예고",
        "points": ["멀티모달 성능 대폭 향상", "추론 속도 3배 개선", "기업용 API 동시 출시 예정"],
        "source": "TechCrunch",
    },
    {
        "number": 2,
        "title": "구글, 제미나이 2.0 업데이트",
        "subtitle": "AI 검색 통합 강화 발표",
        "points": ["실시간 웹 검색 연동", "코드 생성 정확도 향상", "무료 사용자 확대"],
        "source": "The Verge",
    },
]

for i, s in enumerate(samples):
    render_news_card(s, i + 2, output, total_cards=4)

# Closing
render_closing("다음 주에 또 만나요", len(samples) + 2, output, total_cards=4)

print(f"Preview saved to {output}")
