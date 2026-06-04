from __future__ import annotations

import json
from typing import Any

from ..prompts import CRITIC_PROMPT
from ..state import ExtractionState
from .extractor import call_openrouter


def critic_node(state: ExtractionState) -> dict[str, Any]:
    repo = state["repo"]
    topics = state.get("extracted_topics", [])
    topics_json = json.dumps(topics, indent=2)

    readme_snippet = (repo.readme_content or "")[:4000]
    desc = repo.description or ""

    user_content = (
        f"Repository: {repo.title}\n"
        f"Description: {desc}\n"
        f"README excerpt:\n{readme_snippet}\n\n"
        f"Extracted topics:\n{topics_json}"
    )

    result = call_openrouter(
        repo,
        state["model_entry"],
        state["api_key"],
        system_prompt=CRITIC_PROMPT,
        user_content=user_content,
        max_tokens=500,
        thinking="low",
    )

    if result is None:
        return {"errors": state["errors"] + ["Critic node failed"]}

    status = result.get("status", "issues") if isinstance(result, dict) else "issues"
    if status == "clean":
        return {"critic_feedback": ""}
    feedback = result.get("feedback", "No details provided") if isinstance(result, dict) else "No details provided"
    return {"critic_feedback": feedback}
