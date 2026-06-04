from __future__ import annotations

from typing import TypedDict

from ..config import ModelEntry
from ..scrapers.github import Repo


class ExtractionState(TypedDict):
    repo: Repo
    model_entry: ModelEntry
    api_key: str
    extracted_topics: list[dict]
    critic_feedback: str
    iteration: int
    max_iterations: int
    errors: list[str]
