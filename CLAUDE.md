# AI Threads

AI 뉴스를 자동 수집하여 Threads 바이럴 포스트를 생성·게시하는 봇.

## Commands
- `python main.py` — 수집 → 생성 → Threads 포스팅 (전체 파이프라인)
- `python main.py --dry-run` — 포스팅 없이 생성만 (테스트용)

## Pipeline (5단계)
1. **수집**: 8개 소셜 소스 병렬 수집 + RSS 보충
2. **필터링**: AI 키워드 매칭 (최대 15개 선별)
3. **생성**: Claude API로 바이럴 포스트 생성 (중복 기사 자동 제외)
4. **이미지**: 원문 URL에서 og:image 추출
5. **포스팅**: Threads Graph API로 메인 + 5단 대댓글 + 이미지/링크

## Architecture

| 파일 | 역할 |
|------|------|
| main.py | 메인 파이프라인 오케스트레이션, CLI, og:image 추출 |
| social_collector.py | 8개 소스 ThreadPoolExecutor 병렬 수집 (last30days 스킬 활용) |
| ai_writer.py | Claude API 바이럴 포스트 생성, JSON 파싱/재시도 |
| threads_poster.py | Threads Graph API 포스팅 — 메인 + 5 대댓글 + 이미지 |
| rss_collector.py | RSS 피드 수집 (36시간 이내, 보충용) |
| news_filter.py | AI 키워드 필터링 (단어 경계 매칭) |
| history.py | 중복 방지 히스토리 (정규화 비교, 최근 3일) |
| telegram_notify.py | 텔레그램 프리뷰/결과 알림 (선택사항) |
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

## 포스트 구조 (Threads 대댓글 체인)
```
메인 포스트 (post_main, 200~350자)
├─ reply_explain: 쉽게 말하면 (80~150자)
├─ reply_important: 왜 중요 (80~150자)
├─ reply_action: 뭘 해야 (80~150자)
├─ reply_counter: 반대 의견 (80~150자)
├─ reply_casual: 가벼운 한마디 (50~100자)
└─ 이미지 + 원문 링크
```

## 중복 방지 (history.py)
- `output/history.json`에 최근 3일 포스팅 기사 제목 저장
- **정규화 비교**: 따옴표(`'`, `"`, `\u2018` 등) 제거 + 공백 통일 후 비교
- `save_title()`: 정규화 중복 체크 후 저장 (같은 기사 이중 저장 방지)
- `_filter_used_articles()`: Claude에게 보내기 전에 이미 사용한 기사를 후보에서 프로그래밍적으로 제거
- Claude 프롬프트에도 히스토리 전달 (이중 안전장치)

## 환경변수
| 변수 | 필수 | 용도 |
|------|------|------|
| ANTHROPIC_API_KEY | O | Claude API |
| THREADS_ACCESS_TOKEN | O (--dry-run 제외) | Threads 포스팅 |
| THREADS_USER_ID | O (--dry-run 제외) | Threads 포스팅 |
| TELEGRAM_BOT_TOKEN | X | 텔레그램 알림 |
| TELEGRAM_CHAT_ID | X | 텔레그램 알림 |
| SCRAPECREATORS_API_KEY | X | Reddit/TikTok/Instagram |
| BSKY_HANDLE | X | Bluesky |
| BSKY_APP_PASSWORD | X | Bluesky |
| TRUTHSOCIAL_TOKEN | X | Truth Social |

## CI/CD (.github/workflows/daily.yml)
- **스케줄**: UTC 15:30, 21:30, 01:30, 05:30, 09:30, 13:30 (KST 하루 6회, 4시간 간격)
- **수동 실행**: workflow_dispatch 지원
- **자동 커밋**: `output/` 디렉토리 변경 시 `chore: YYYY-MM-DD 포스트` 커밋
- Python 3.11, yt-dlp + requirements.txt 설치

## Conventions
- `output/{날짜}/post.json`에 생성 결과 저장
- `output/history.json`으로 최근 3일 기사 중복 방지
- Claude 모델: claude-sonnet-4-20250514
- 데이터 정규화: 모든 수집기가 `{title, summary, source, link}` 포맷 통일
- 에러 격리: 개별 소스 실패 시 다른 소스에 영향 없음

## Dependencies (requirements.txt)
- anthropic>=0.40.0
- httpx>=0.27.0
- feedparser>=6.0.0
- yt-dlp (CI에서 별도 설치)

## NEVER
- NEVER 해시태그(#) 사용 — Threads가 스팸 처리
- NEVER 외부 링크 포함 — 도달률 킬러
- NEVER "개인적으로"로 첫 댓글 시작 — 반복되면 봇처럼 보임
- NEVER output/ 내 생성된 파일을 수동 편집 — CI가 매일 자동 덮어씀
- NEVER fonts/ 삭제 — 레거시이나 추후 카드뉴스 부활 가능성
