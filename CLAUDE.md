# AI Threads

## Commands
- `python main.py` — collect -> rank -> generate -> QA -> post
- `python main.py --mode viral` — viral mode
- `python main.py --dry-run` — generate + QA only, no posting
- `python main.py --collect-engagement` — collect Threads insights only
- `python main.py --export-sft output/training_sft.jsonl` — export passed learning records as SFT JSONL
- `python -m pytest tests/ -v` — run tests

## Backend policy
- **Local/manual runs:** default to `THREADS_LLM_BACKEND=claude_cli`
- **GitHub Actions scheduled runs:** force `THREADS_LLM_BACKEND=anthropic_api`
- Local fallback order: `claude_cli -> anthropic_api -> codex_cli`

## Current architecture
- `main.py` — end-to-end pipeline
- `social_collector.py` — Hot/Warm/Cold social collection with 30-day cache awareness
- `rss_collector.py` — RSS collection with recency filtering
- `candidate_ranking.py` — usefulness/freshness ranking before generation
- `article_enricher.py` — lightweight article-body enrichment for top candidates
- `ai_writer.py` — freeform thread generation (`post_main + replies[] + media_plan`)
- `qa_evaluator.py` — quality checks + structured evaluation
- `threads_poster.py` — Threads posting, freeform replies first, legacy fallback second
- `engagement_tracker.py` — engagement history + pattern summaries
- `learning_log.py` — JSONL training data accumulation + SFT export

## Output conventions
- `output/<date>/post.json` stores generated content, QA result, media info, and posting result
- `output/history.json` tracks recently used article titles/URLs for dedupe
- `output/engagement.json` stores post-level engagement summaries
- `output/learning_log.jsonl` stores training-ready generation records
- `output/social_cache.json` stores per-source social collection cache

## Important rules
- Keep posts factual first, interpretive second
- Prefer useful workflow impact over generic AI hype
- Do not invent facts not present in article title/summary/details
- Avoid hashtags and raw links inside thread prose
