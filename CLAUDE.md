# AI Threads

## Commands
- `python main.py` - 수집 → 생성 → QA 평가 → Threads 포스팅
- `python main.py --dry-run` - 포스팅 없이 생성+QA만

## Architecture
8개 소스 병렬 수집 → AI 키워드 필터 → Claude API 생성(Generator) → QA 평가(Evaluator) → Threads 포스팅

Generator/Evaluator 패턴 적용 (Anthropic "Harness Design for Long-Running Apps" 참조):
- ai_writer.py = Generator (포스트 생성)
- qa_evaluator.py = Evaluator (별도 Claude 호출로 회의적 평가)
- QA 실패 시 최대 2회 재생성

| 파일 | 역할 |
|------|------|
| main.py | 메인 파이프라인 (6단계) |
| ai_writer.py | Generator — Claude API 바이럴 포스트 생성 |
| qa_evaluator.py | Evaluator — 규칙 검증 + AI 품질 평가 (별도 호출) |
| threads_poster.py | Threads Graph API 텍스트 포스트 + 첫 댓글 |
| social_collector.py | 8개 소스 병렬 수집 (last30days 스킬 활용) |
| rss_collector.py | RSS 피드 수집 (보충용) |
| news_filter.py | AI 키워드 필터링 |
| history.py | 중복 방지 히스토리 |
| telegram_notify.py | 텔레그램 프리뷰/결과 알림 |
| config.py | 환경변수, 모델, 키워드 설정 |

## 수집 소스 (social_collector.py)
| 소스 | API | 키 |
|------|-----|-----|
| Reddit | ScrapeCreators | SCRAPECREATORS_API_KEY |
| Hacker News | Algolia | 불필요 |
| YouTube | yt-dlp | 불필요 |
| TikTok | ScrapeCreators | SCRAPECREATORS_API_KEY |
| Instagram | ScrapeCreators | SCRAPECREATORS_API_KEY |
| Bluesky | AT Protocol | BSKY_HANDLE + BSKY_APP_PASSWORD |
| Truth Social | Mastodon API | TRUTHSOCIAL_TOKEN |
| Polymarket | Gamma API | 불필요 |

## Conventions
- output/{날짜}/post.json에 생성 결과 저장
- output/history.json으로 최근 3일 기사 중복 방지
- Claude 모델: claude-sonnet-4-20250514

## QA Evaluator
- 2단계 평가: 규칙 검증(무료) → AI 평가(별도 Claude 호출)
- AI 평가 5축: hook_power(30%), debate_potential(30%), tone(20%), coherence(10%), compliance(10%)
- 통과 기준: overall >= 0.65 AND 규칙 위반 0건
- 규칙 위반 3건 이상 시 AI 호출 없이 즉시 실패 (비용 절약)

## NEVER
- NEVER 해시태그(#) 사용 -- Threads가 스팸 처리
- NEVER 외부 링크 포함 -- 도달률 킬러
- NEVER "개인적으로"로 첫 댓글 시작 -- 반복되면 봇처럼 보임
- NEVER output/ 내 생성된 파일을 수동 편집 -- CI가 매일 자동 덮어씀
- NEVER qa_evaluator.py 평가 기준 변경 시 ai_writer.py 프롬프트도 함께 확인
