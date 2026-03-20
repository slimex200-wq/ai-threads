# AI Card News Generator

AI 최신 뉴스를 자동 수집하고 인스타그램 스타일 카드뉴스 이미지를 생성하는 CLI 앱

## 기능

- RSS 피드에서 AI 뉴스 자동 수집 (TechCrunch, The Verge, MIT Tech Review, Ars Technica)
- Claude API로 한국어 번역 + 요약 + 카드 문구 자동 생성
- 미니멀 화이트 디자인의 카드뉴스 이미지(PNG) 자동 생성
- 표지 → 뉴스 카드 → 마무리 카드 세트 구성

## 설치

```bash
git clone https://github.com/shjung1/ai-cardnews.git
cd ai-cardnews
pip install -r requirements.txt
```

## 사용법

```bash
# API 키 설정
export ANTHROPIC_API_KEY="sk-ant-..."

# 기본 실행 (뉴스 4개)
python cardnews.py

# 뉴스 개수 지정
python cardnews.py --count 3

# 출력 경로 지정
python cardnews.py --output ./my-cards/
```

## 출력 예시

```
[1/3] AI 뉴스 수집 중... (최대 4개)
  → 4개 기사 수집 완료
[2/3] 카드 문구 생성 중... (Claude API)
  → 4개 카드 문구 생성 완료
[3/3] 카드 이미지 생성 중...
  → 표지: card-01.png
  → 카드 2: card-02.png
  → 카드 3: card-03.png
  → 카드 4: card-04.png
  → 카드 5: card-05.png
  → 마무리: card-06.png

완료! 6장의 카드뉴스가 생성되었습니다.
저장 위치: ~/Desktop/ai-cardnews/2026-03-20/
```

## 카드 구성

| 카드 | 내용 |
|------|------|
| 1장 (표지) | AI Weekly + 날짜 |
| 2~N장 (뉴스) | 제목 + 부제 + 핵심 포인트 + 출처 |
| 마지막 (마무리) | 감사 메시지 |

## 디자인

- 1080 x 1080px (인스타 정사각형)
- 미니멀 화이트 + 블루 액센트
- 맑은 고딕 폰트

## 프로젝트 구조

```
ai-cardnews/
├── cardnews.py          # 메인 엔트리포인트 + CLI
├── rss_collector.py     # RSS 뉴스 수집
├── ai_writer.py         # Claude API 카드 문구 생성
├── card_renderer.py     # Pillow 이미지 생성
├── config.py            # 설정
├── requirements.txt     # 의존성
└── tests/               # 테스트
```

## 기술 스택

- Python 3.14
- feedparser (RSS 파싱)
- anthropic (Claude API)
- Pillow (이미지 생성)
