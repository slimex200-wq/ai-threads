import json
import tempfile
from pathlib import Path

from learning_log import append_learning_record, export_sft_examples, load_learning_records


def test_append_and_load_learning_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "learning_log.jsonl"
        record = {
            "mode": "informational",
            "selected_article": {"original_title": "A useful article"},
            "content": {"post_main": "hello", "replies": ["one", "two"]},
            "qa": {"passed": True, "score": 0.82},
        }

        append_learning_record(record, path=log_path)
        loaded = load_learning_records(path=log_path)

        assert len(loaded) == 1
        assert loaded[0]["mode"] == "informational"
        assert loaded[0]["content"]["replies"] == ["one", "two"]


def test_export_sft_examples_filters_to_passed_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        log_path = root / "learning_log.jsonl"
        output_path = root / "training_sft.jsonl"

        append_learning_record(
            {
                "mode": "informational",
                "candidate_articles": [{"title": "Useful launch", "summary": "Tool launch"}],
                "selected_article": {"original_title": "Useful launch", "reason": "Useful"},
                "content": {"post_main": "main", "replies": ["reply 1"]},
                "qa": {"passed": True, "score": 0.91},
            },
            path=log_path,
        )
        append_learning_record(
            {
                "mode": "informational",
                "candidate_articles": [{"title": "Weak launch", "summary": "Weak"}],
                "selected_article": {"original_title": "Weak launch", "reason": "Weak"},
                "content": {"post_main": "bad", "replies": ["reply"]},
                "qa": {"passed": False, "score": 0.2},
            },
            path=log_path,
        )

        examples = export_sft_examples(path=log_path, output_path=output_path, passed_only=True)

        assert len(examples) == 1
        saved = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(saved) == 1
        assert saved[0]["output"]["replies"] == ["reply 1"]
