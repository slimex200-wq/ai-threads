# AI Threads

## Commands
- `python main.py` - 수집 → 생성 → QA → 포스팅 (기본: informational)
- `python main.py --mode viral` - 바이럴 모드
- `python main.py --dry-run` - 포스팅 없이 생성+QA만
- `python main.py --collect-engagement` - engagement 수집만
- `python -m pytest tests/ -v` - 테스트

## Architecture
8개 소스 병렬 수집 → AI 키워드 필터 → Claude API 생성(Generator) → QA 평가(Evaluator) → Threads 포스팅

### 콘텐츠 모드
- **informational** (기본): 바이브코더 타겟, 정보성 톤, reply 4개 (background/impact/compare/summary)
- **viral**: 논쟁 유발 톤, reply 5개 (explain/important/action/counter/casual)

`--mode` 플래그 또는 `CONTENT_MODE` 환경변수로 전환. 수집/필터는 공유, 생성/평가/포스팅만 분기.

### Generator/Evaluator 패턴
- ai_writer.py = Generator (모드별 프롬프트)
- qa_evaluator.py = Evaluator (모드별 평가 기준, 별도 Claude 호출)
- QA 2회 실패 시 포스팅 스킵 (강제 진행 안 함)

| 파일 | 역할 |
|------|------|
| main.py | 메인 파이프라인 (7단계) |
| ai_writer.py | Generator — 모드별 프롬프트로 포스트 생성 |
| qa_evaluator.py | Evaluator — 모드별 규칙 검증 + AI 품질 평가 |
| threads_poster.py | Threads Graph API, 모드별 reply 구조 |
| engagement_tracker.py | Insights API 수집 + 모드별 패턴 분석 |
| social_collector.py | 8개 소스 병렬 수집 (last30days 스킬 활용) |
| rss_collector.py | RSS 피드 수집 (보충용) |
| news_filter.py | AI 키워드 필터링 |
| history.py | 중복 방지 히스토리 |
| telegram_notify.py | 텔레그램 프리뷰/결과 알림 |
| config.py | 환경변수, 모델, 키워드, 모드, 타이밍 설정 |

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
- output/{날짜}/post.json에 생성 결과 저장 (mode 필드 포함)
- output/history.json으로 최근 3일 기사 중복 방지
- output/engagement.json으로 모드별 성과 추적
- Claude 모델: claude-sonnet-4-20250514

## QA Evaluator
- 2단계 평가: 규칙 검증(무료) → AI 평가(별도 Claude 호출)
- viral 5축: hook_power(30%), debate_potential(30%), tone(20%), coherence(10%), compliance(10%)
- informational 5축: clarity(30%), usefulness(30%), accuracy(20%), tone(10%), structure(10%)
- 통과 기준: overall >= 0.65 AND 규칙 위반 0건
- 규칙 위반 3건 이상 시 AI 호출 없이 즉시 실패 (비용 절약)

## NEVER
- NEVER 해시태그(#) 사용 -- Threads가 스팸 처리
- NEVER 외부 링크 포함 -- 도달률 킬러
- NEVER "개인적으로"로 첫 댓글 시작 -- 반복되면 봇처럼 보임
- NEVER output/ 내 생성된 파일을 수동 편집 -- CI가 매일 자동 덮어씀
- NEVER qa_evaluator.py 평가 기준 변경 시 ai_writer.py 프롬프트도 함께 확인
- NEVER 모드 간 engagement 데이터 섞기 -- 모드별 패턴 분리 필수
