from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from ...config import ModelEntry
from ...scrapers.github import Repo
from ..prompts import EXTRACTION_PROMPT
from ..state import ExtractionState


def call_openrouter(
    repo: Repo,
    model_entry: ModelEntry,
    api_key: str,
    system_prompt: str | None = None,
    user_content: str | None = None,
    max_tokens: int = 2048,
    thinking: Any = None,
) -> Any:
    system = system_prompt or EXTRACTION_PROMPT

    if user_content is None:
        readme_snippet = (repo.readme_content or "")[:4000]
        desc = repo.description or ""
        user_content = f"Repository: {repo.title}\nDescription: {desc}\nREADME excerpt:\n{readme_snippet}"

    payload = {
        "model": model_entry.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }

    active_thinking = thinking if thinking is not None else getattr(model_entry, "thinking", None)
    if active_thinking:
        if isinstance(active_thinking, dict):
            payload["thinking"] = active_thinking
        else:
            payload["reasoning_effort"] = active_thinking

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
        content = data["choices"][0]["message"].get("content")
        if content is None:
            return None
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            bracket = content.find("[")
            if bracket >= 0:
                try:
                    return json.loads(content[bracket:])
                except json.JSONDecodeError:
                    pass
            return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise
        print(f"  [extractor] {repo.title}: LLM call failed ({model_entry.model}): {e}")
        return None
    except Exception as e:
        print(f"  [extractor] {repo.title}: LLM call failed ({model_entry.model}): {e}")
        return None


def extractor_node(state: ExtractionState) -> dict[str, Any]:
    result = call_openrouter(state["repo"], state["model_entry"], state["api_key"])
    if result is None:
        return {"errors": state["errors"] + ["Extractor node failed"]}
    return {"extracted_topics": result}
