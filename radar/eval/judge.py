from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..config import load_config
from ..extraction_graph import invoke_extraction_graph
from ..scrapers.github import Repo


@dataclass
class JudgeEntry:
    repo: dict
    expected: list[dict]


def load_dataset(path: str) -> list[JudgeEntry]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("dataset must be a JSON array")

    entries: list[JudgeEntry] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"entry {i}: must be an object")
        repo = item.get("repo")
        if not repo or not isinstance(repo, dict) or not repo.get("title"):
            raise ValueError(f"entry {i}: missing valid 'repo' with 'title'")
        expected = item.get("expected")
        if not isinstance(expected, list):
            raise ValueError(f"entry {i}: missing valid 'expected' list")
        entries.append(JudgeEntry(repo=repo, expected=expected))
    return entries


JUDGE_PROMPT = """You are an AI topic extraction evaluator. Compare the actual extracted topics against the expected topics and score them.

Score each axis 1-5:
- **precision**: Are all actual topics correct? No hallucinated or irrelevant topics. (1 = all wrong, 5 = all correct)
- **recall**: Are all expected topics present in the actual output? (1 = none found, 5 = all found)
- **quality**: How good are the actual topics? Consider granularity, alias accuracy, category fit, level assignment, and parent assignment. (1 = poor, 5 = excellent)

Output ONLY valid JSON:
{"precision": <1-5>, "recall": <1-5>, "quality": <1-5>, "explanation": "<brief reason>"}"""


@dataclass
class JudgeScore:
    precision: int = 0
    recall: int = 0
    quality: int = 0
    explanation: str = ""


def judge_entry(
    actual: list[dict],
    expected: list[dict],
    model: str = "openai/o3-mini",
    api_key: str = "",
) -> JudgeScore:
    import httpx

    actual_json = json.dumps(actual, indent=2)
    expected_json = json.dumps(expected, indent=2)

    user_content = f"Actual topics:\n{actual_json}\n\nExpected topics:\n{expected_json}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        parsed = json.loads(content)
        return JudgeScore(
            precision=int(parsed.get("precision", 0)),
            recall=int(parsed.get("recall", 0)),
            quality=int(parsed.get("quality", 0)),
            explanation=parsed.get("explanation", ""),
        )
    except Exception as e:
        print(f"  [judge] judge call failed: {e}")
        return JudgeScore()


def aggregate_results(scores: list[JudgeScore]) -> dict:
    if not scores:
        return {"total": 0, "avg_precision": 0, "avg_recall": 0, "avg_quality": 0, "failures": []}

    avg_precision = sum(s.precision for s in scores) / len(scores)
    avg_recall = sum(s.recall for s in scores) / len(scores)
    avg_quality = sum(s.quality for s in scores) / len(scores)
    failures = [s.explanation for s in scores if (s.precision + s.recall + s.quality) / 3 < 3]

    return {
        "total": len(scores),
        "avg_precision": round(avg_precision, 2),
        "avg_recall": round(avg_recall, 2),
        "avg_quality": round(avg_quality, 2),
        "failures": failures,
    }


def main():
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Radar Eval — judge extraction quality")
    parser.add_argument("--dataset", default="eval/dataset.json", help="path to dataset JSON")
    parser.add_argument("--judge-model", default="openai/o3-mini", help="judge LLM model")
    parser.add_argument("--output", default="eval/report.json", help="output report path")
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY_PRIMARY", "")
    if not api_key:
        print("[eval] OPENROUTER_API_KEY_PRIMARY not set")
        return

    entries = load_dataset(args.dataset)
    config = load_config()
    scores: list[JudgeScore] = []

    for i, entry in enumerate(entries):
        print(f"[eval] entry {i + 1}/{len(entries)}: {entry.repo['title']}")
        actual = run_entry(entry, config)
        if actual is None:
            print(f"  [eval] pipeline returned None, treating as empty")
            actual = []
        score = judge_entry(actual, entry.expected, model=args.judge_model, api_key=api_key)
        print(f"  [eval] p={score.precision} r={score.recall} q={score.quality}")
        scores.append(score)

    report = aggregate_results(scores)
    report["scores"] = [{"precision": s.precision, "recall": s.recall, "quality": s.quality, "explanation": s.explanation} for s in scores]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[eval] report written to {out_path}")
    print(f"  avg_precision={report['avg_precision']}  avg_recall={report['avg_recall']}  avg_quality={report['avg_quality']}")
    print(f"  failures={len(report['failures'])}")


if __name__ == "__main__":
    main()


def run_entry(entry: JudgeEntry, config: Any | None = None) -> Optional[list[dict]]:
    if config is None:
        config = load_config()

    repo = Repo(
        title=entry.repo["title"],
        description=entry.repo.get("description", ""),
        url=entry.repo.get("url", ""),
        source_type=entry.repo.get("source_type", "eval"),
        readme_content=entry.repo.get("readme_content", ""),
        arxiv_url=entry.repo.get("arxiv_url"),
        project_title=entry.repo.get("project_title"),
    )

    return invoke_extraction_graph(repo, config)
