# AI Threads

AI/개발 관련 뉴스와 커뮤니티 신호를 모아서, **한국어 Threads 초안 + 꼬리글 + 관련 미디어**까지 자동으로 만드는 파이프라인.

이 프로젝트는 단순 뉴스 요약기가 아니라 아래를 목표로 한다:

- **실전 팁이 있는 글**
- **업계 변화의 의미를 같이 해석하는 글**
- **개발자 / 초보 / 바이브코더가 같이 읽을 수 있는 글**
- **공유하고 팔로우하고 싶게 만드는 Threads**

---

## 핵심 특징

- **자유형 스레드 생성**
  - 고정 reply 슬롯 대신 `post_main + replies[] + media_plan`
- **수집 비용 최적화**
  - social collector는 Hot / Warm / Cold / Cache 전략 사용
  - 30일 인식은 유지하지만 매번 30일 풀수집하지 않음
- **후보 랭킹 보정**
  - 최신 릴리즈/업데이트/실용 변화 우대
  - YouTube 설명형/Polymarket 예측형 패널티
- **원문 grounding 강화**
  - 상위 기사 본문 일부 추출 후 프롬프트에 주입
  - 원문에 없는 주장/성능/호환성 추정 억제
- **관련 링크/영상 선반영**
  - 기사 선택 직후 `source_link`, `og:image`, `og:video`, 관련 demo video 탐색
  - preview에서 글과 함께 바로 확인 가능
- **학습 데이터 플라이휠**
  - generation / QA / media / posting 결과를 JSONL로 축적
  - SFT용 JSONL export 지원

---

## 실행 모드

### 로컬 / 수동 실행
기본값은 **CLI-first**:

- `THREADS_LLM_BACKEND=claude_cli`

백엔드 우선순위:

1. `claude_cli`
2. `anthropic_api`
3. `codex_cli`

### GitHub Actions 스케줄 실행
워크플로에서는 명시적으로:

- `THREADS_LLM_BACKEND=anthropic_api`

를 사용한다.  
즉, **스케줄은 API**, **수동은 CLI** 구조다.

---

## 주요 명령어

```bash
# 기본 실행 (informational)
python main.py

# 바이럴 모드
python main.py --mode viral

# 포스팅 없이 생성 + QA만
python main.py --dry-run

# engagement 수집만
python main.py --collect-engagement

# 누적 학습 로그를 SFT JSONL로 export
python main.py --export-sft output/training_sft.jsonl

# 테스트
python -m pytest tests -v
```

---

## 환경변수

### 공통

| 변수 | 설명 |
|---|---|
| `CONTENT_MODE` | `informational` 또는 `viral` |
| `THREADS_LLM_BACKEND` | `claude_cli`, `anthropic_api`, `codex_cli`, `auto` |

### LLM

| 변수 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API 사용 시 필요 |

### Threads / 알림

| 변수 | 설명 |
|---|---|
| `THREADS_ACCESS_TOKEN` | Threads post/inisghts API |
| `THREADS_USER_ID` | Threads user id |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 preview/result 알림 |
| `TELEGRAM_CHAT_ID` | 텔레그램 채팅 대상 |

### 선택적 수집 소스

| 변수 | 설명 |
|---|---|
| `SCRAPECREATORS_API_KEY` | Reddit / TikTok / Instagram |
| `BSKY_HANDLE` | Bluesky |
| `BSKY_APP_PASSWORD` | Bluesky app password |
| `TRUTHSOCIAL_TOKEN` | Truth Social |
| `SUPABASE_URL` | promo video upload fallback |
| `SUPABASE_SERVICE_ROLE_KEY` | promo video upload fallback |

---

## 현재 파이프라인

```text
1. 과거 engagement 로드
2. social + RSS 수집
3. keyword filter + dedupe
4. candidate ranking
5. 상위 기사 본문 enrichment
6. 자유형 thread 생성
7. 기사 선택 직후 링크/미디어 prefetch
8. QA
9. preview
10. post / dry-run
11. learning log 저장
```

---

## 수집 전략

### social_collector.py

`last30days` 어댑터들을 사용하지만, 매번 30일 풀수집하지 않는다.

- **Hot**
  - HN, YouTube
  - 매 실행마다 짧은 윈도우 재조회
- **Warm**
  - 비싼 소스 재조회 간격 완화
- **Cold**
  - 30일 시야 유지용 재동기화
- **Cache**
  - 최근 refresh면 캐시 재사용
  - 빈 결과도 negative cache로 저장

캐시 파일:

- `output/social_cache.json`

### RSS

- 최근성 기준으로 필터링
- 기사 날짜를 `date` 필드로 보존

---

## 출력 파일

| 파일 | 설명 |
|---|---|
| `output/<date>/post.json` | 생성 결과, QA, media, posting result |
| `output/history.json` | 최근 사용 기사 dedupe |
| `output/engagement.json` | engagement 요약 |
| `output/learning_log.jsonl` | 학습용 generation 로그 |
| `output/social_cache.json` | social 수집 캐시 |

---

## 핵심 모듈

| 파일 | 역할 |
|---|---|
| `main.py` | 전체 파이프라인 |
| `social_collector.py` | Hot/Warm/Cold social 수집 |
| `rss_collector.py` | RSS 수집 |
| `candidate_ranking.py` | 후보 기사 랭킹 |
| `article_enricher.py` | 기사 본문 일부 추출 |
| `ai_writer.py` | 자유형 thread 생성 |
| `qa_evaluator.py` | 규칙 + 품질 평가 |
| `threads_poster.py` | Threads posting |
| `telegram_notify.py` | preview/result 알림 |
| `learning_log.py` | 학습 로그 / SFT export |
| `llm_backend.py` | CLI/API/Codex backend 추상화 |

---

## Preview 예시

Preview에는 이제 아래가 함께 포함된다:

- 선택 기사
- 선택 이유
- 원문 링크
- 메인글
- 꼬리글들
- video / og:image
- media plan

즉, 글만 보는 게 아니라 **“이 글이 무슨 원문을 기반으로 하고 어떤 영상이 붙는지”**까지 한 번에 검토할 수 있다.

---

## GitHub Actions

워크플로:

- `.github/workflows/daily.yml`
- `.github/workflows/refresh-token.yml`

`daily.yml`은 현재:

- 스케줄 실행
- `THREADS_LLM_BACKEND=anthropic_api`
- `python main.py`

구조다.

---

## 테스트

```bash
python -m pytest tests -v
```

현재 테스트 범위:

- freeform generation prompt
- QA rule checks
- social collection policy
- candidate ranking
- article enrichment
- media helpers
- telegram preview formatting
- LLM backend selection/fallback

---

## 운영 팁

- 로컬 수동 운영은 CLI-first가 맞다
- GitHub-hosted Actions는 API-first가 더 안정적이다
- dry-run 결과가 약하면:
  1. candidate ranking
  2. article enrichment
  3. prompt grounding
  순서로 손보는 게 효과가 크다
