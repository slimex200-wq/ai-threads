"""Structured learning log helpers for future SFT / preference training."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("output")
LEARNING_LOG_FILE = OUTPUT_DIR / "learning_log.jsonl"


def append_learning_record(record: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    path = path or LEARNING_LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    enriched = {
        "created_at": datetime.now().isoformat(),
        **record,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enriched, ensure_ascii=False) + "\n")
    return enriched


def load_learning_records(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or LEARNING_LOG_FILE
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def export_sft_examples(
    path: Path | None = None,
    output_path: Path | None = None,
    *,
    passed_only: bool = True,
) -> list[dict[str, Any]]:
    records = load_learning_records(path=path)
    examples: list[dict[str, Any]] = []

    for record in records:
        qa = record.get("qa", {}) or {}
        if passed_only and not qa.get("passed", False):
            continue

        example = {
            "input": {
                "mode": record.get("mode", "informational"),
                "candidate_articles": record.get("candidate_articles", []),
                "selected_article": record.get("selected_article", {}),
                "engagement_patterns": record.get("engagement_patterns", {}),
            },
            "output": record.get("content", {}),
            "metadata": {
                "qa_score": qa.get("score"),
                "posted": record.get("posted", False),
                "source_date": record.get("source_date"),
            },
        }
        examples.append(example)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for example in examples:
                handle.write(json.dumps(example, ensure_ascii=False) + "\n")

    return examples
