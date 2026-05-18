from __future__ import annotations

import json
import time
from typing import List, Optional

import httpx

from .config import Config, ModelEntry
from .scrapers.github import Repo


EXTRACTION_PROMPT = """You are an AI topic extractor. Given the following repository description and README, extract the key AI/ML topics this repository is about.

For each topic, provide:
- "canonical": the canonical name (e.g. "RLHF", "Vision Transformer", "LoRA")
- "aliases": a list of alternative names or abbreviations for this topic (can be empty)

Rules:
- Only include well-defined AI/ML topics, not general technologies
- Limit to 5 topics per repository
- If you see a topic that is an alias for a well-known topic, use the well-known name as canonical and the variant as an alias
- Output ONLY valid JSON, no markdown fences, no commentary

Output format:
[
  {"canonical": "Topic Name", "aliases": ["Alias1", "Alias2"]},
  {"canonical": "Another Topic", "aliases": []}
]"""


def call_openrouter(repo: Repo, model_entry: ModelEntry, api_key: str) -> Optional[List[dict]]:
    prompt = EXTRACTION_PROMPT
    readme_snippet = (repo.readme_content or "")[:4000]
    desc = repo.description or ""

    user_content = f"Repository: {repo.title}\nDescription: {desc}\nREADME excerpt:\n{readme_snippet}"

    payload = {
        "model": model_entry.model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
    }

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        return json.loads(content)
    except Exception as e:
        print(f"  [extractor] LLM call failed ({model_entry.model}): {e}")
        return None


def extract_topics(repo: Repo, config: Config) -> List[str]:
    result = None
    errors = []

    for model_entry in config.model_chain:
        for attempt in range(2):
            api_key = config.openrouter_api_key_primary
            result = call_openrouter(repo, model_entry, api_key)
            if result is not None:
                break
            if config.openrouter_api_key_secondary:
                result = call_openrouter(repo, model_entry, config.openrouter_api_key_secondary)
                if result is not None:
                    break
            if attempt == 0:
                print(f"  [extractor] retrying {model_entry.model}...")
                time.sleep(2)

        if result is not None:
            break
        errors.append(model_entry.model)

    if result is None:
        print(f"  [extractor] all models failed for {repo.title}, errors: {errors}")
        return []

    topics = []
    for entry in result:
        canonical = entry.get("canonical", "").strip()
        if not canonical:
            continue
        topics.append(canonical)

    print(f"  [extractor] {repo.title} -> {topics}")
    return topics
