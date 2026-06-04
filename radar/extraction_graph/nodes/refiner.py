from __future__ import annotations

import json
from typing import Any

from ..prompts import REFINER_PROMPT
from ..state import ExtractionState
from .extractor import call_openrouter


def refiner_node(state: ExtractionState) -> dict[str, Any]:
    repo = state["repo"]
    topics = state.get("extracted_topics", [])
    feedback = state.get("critic_feedback", "")

    if not feedback:
        return {"extracted_topics": topics, "iteration": state["iteration"] + 1}

    readme_snippet = (repo.readme_content or "")[:4000]
    desc = repo.description or ""
    topics_json = json.dumps(topics, indent=2)

    user_content = (
        f"Repository: {repo.title}\n"
        f"Description: {desc}\n"
        f"README excerpt:\n{readme_snippet}\n\n"
        f"Current topics:\n{topics_json}\n\n"
        f"Critic feedback:\n{feedback}"
    )

    result = call_openrouter(
        repo,
        state["model_entry"],
        state["api_key"],
        system_prompt=REFINER_PROMPT,
        user_content=user_content,
        max_tokens=1000,
        thinking="medium",
    )

    if result is None:
        return {"errors": state["errors"] + ["Refiner node failed"]}

    refined = result if isinstance(result, list) else []
    return {"extracted_topics": refined, "iteration": state["iteration"] + 1}
