from __future__ import annotations

import json
from pathlib import Path

import pytest

from unittest.mock import ANY, MagicMock, patch

from radar.eval.judge import load_dataset, JudgeEntry, run_entry, judge_entry, JudgeScore


SAMPLE = [
    {
        "repo": {
            "title": "test/repo",
            "description": "A test repo",
            "readme_content": "This repo implements LoRA fine-tuning",
            "source_type": "github",
            "url": "https://github.com/test/repo",
        },
        "expected": [
            {"canonical": "LoRA", "level": "low", "category": "Fine-Tuning", "parents": ["Fine-Tuning"]},
        ],
    }
]


class TestRunEntry:
    def test_converts_repo_and_calls_pipeline(self):
        entry = JudgeEntry(repo=SAMPLE[0]["repo"], expected=SAMPLE[0]["expected"])
        mock_result = [{"canonical": "LoRA", "level": "low", "category": "Fine-Tuning"}]

        with patch("radar.eval.judge.invoke_extraction_graph", return_value=mock_result) as mock:
            result = run_entry(entry)

        mock.assert_called_once()
        args = mock.call_args[0]
        assert args[0].title == "test/repo"
        assert args[0].url == "https://github.com/test/repo"
        assert result == mock_result

    def test_returns_none_on_failure(self):
        entry = JudgeEntry(repo=SAMPLE[0]["repo"], expected=SAMPLE[0]["expected"])

        with patch("radar.eval.judge.invoke_extraction_graph", return_value=None):
            result = run_entry(entry)

        assert result is None


class TestJudgeEntry:
    def test_parses_score_from_judge_response(self):
        actual = [{"canonical": "LoRA", "level": "low"}]
        expected = [{"canonical": "LoRA", "level": "low"}]
        judge_reply = '{"precision": 5, "recall": 5, "quality": 4, "explanation": "Perfect match"}'

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"choices": [{"message": {"content": judge_reply}}]}

        with patch("httpx.post", return_value=mock_resp) as mock:
            result = judge_entry(actual, expected, api_key="sk-test")

        mock.assert_called_once()
        assert result.precision == 5
        assert result.recall == 5
        assert result.quality == 4
        assert "Perfect match" in result.explanation

    def test_missing_score_defaults_to_zero(self):
        judge_reply = '{"explanation": "No scores given"}'

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"choices": [{"message": {"content": judge_reply}}]}

        with patch("httpx.post", return_value=mock_resp):
            result = judge_entry([], [], api_key="sk-test")

        assert result.precision == 0
        assert result.recall == 0
        assert result.quality == 0


class TestAggregateResults:
    def test_averages_scores(self):
        from radar.eval.judge import aggregate_results
        scores = [
            JudgeScore(precision=5, recall=5, quality=4, explanation="good"),
            JudgeScore(precision=3, recall=4, quality=3, explanation="ok"),
            JudgeScore(precision=1, recall=2, quality=2, explanation="bad"),
        ]
        report = aggregate_results(scores)
        assert report["avg_precision"] == 3.0
        assert report["avg_recall"] == pytest.approx(3.67, rel=0.01)
        assert report["avg_quality"] == 3.0
        assert report["total"] == 3
        assert len(report["failures"]) == 1  # only the one with avg < 3
        assert report["failures"][0] == "bad"

    def test_empty_returns_zeros(self):
        from radar.eval.judge import aggregate_results
        report = aggregate_results([])
        assert report["avg_precision"] == 0
        assert report["total"] == 0
        assert report["failures"] == []


class TestLoadDataset:
    def test_loads_valid_json(self, tmp_path: Path):
        f = tmp_path / "dataset.json"
        f.write_text(json.dumps(SAMPLE))
        entries = load_dataset(str(f))
        assert len(entries) == 1
        assert isinstance(entries[0], JudgeEntry)
        assert entries[0].repo["title"] == "test/repo"

    def test_missing_repo_title_raises(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps([{"expected": []}]))
        with pytest.raises(ValueError, match="repo"):
            load_dataset(str(f))

    def test_missing_expected_raises(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps([{"repo": {"title": "x"}}]))
        with pytest.raises(ValueError, match="expected"):
            load_dataset(str(f))

    def test_non_list_raises(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps({}))
        with pytest.raises(ValueError):
            load_dataset(str(f))
