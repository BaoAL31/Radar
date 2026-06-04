from __future__ import annotations

import time
from typing import Optional

import httpx

from ..config import Config
from ..scrapers.github import Repo
from .graph import run_extraction_graph
from .nodes import extractor as _extractor


def _extract_direct(
    repo: Repo, model_entry: object, api_key: str
) -> tuple[Optional[list[dict]], bool]:
    """Extract topics with a single LLM call — no critic/refiner loop."""
    try:
        result = _extractor.call_openrouter(repo, model_entry, api_key)
        if result is None:
            return None, False
        return result, False
    except httpx.HTTPStatusError as e:
        return None, e.response.status_code == 429
    except Exception:
        return None, False


def _extract_with_graph(
    repo: Repo, model_entry: object, api_key: str
) -> tuple[Optional[list[dict]], bool]:
    """Extract topics with full LangGraph critic/refiner loop."""
    return run_extraction_graph(repo, model_entry, api_key)


def invoke_extraction_graph(repo: Repo, config: Config) -> Optional[list[dict]]:
    keys = [config.openrouter_api_key_primary]
    if config.openrouter_api_key_secondary:
        keys.append(config.openrouter_api_key_secondary)

    extract_fn = _extract_direct if not config.use_critic_loop else _extract_with_graph

    for model_entry in config.model_chain:
        attempt = 0
        wait = 1

        while wait <= 15:
            api_key = keys[attempt % len(keys)]
            result, is_rate_limit = extract_fn(repo, model_entry, api_key)

            if result is not None:
                return result

            if not is_rate_limit:
                break

            time.sleep(wait)
            wait += 1
            attempt += 1

        print(f"  [extraction_graph] model {model_entry.model} failed for {repo.title}")

    print(f"  [extraction_graph] all models failed for {repo.title}")
    return None
