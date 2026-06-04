from __future__ import annotations

from typing import Any, Optional

from ..config import ModelEntry
from ..scrapers.github import Repo
from .nodes.extractor import extractor_node
from .nodes.critic import critic_node
from .nodes.refiner import refiner_node
from .state import ExtractionState
from langgraph.graph import StateGraph


def should_refine(state: ExtractionState) -> str:
    """Route from critic: if clean finish, otherwise go to refiner."""
    feedback = state.get("critic_feedback", "")
    return "refine" if feedback else "clean"


def should_continue(state: ExtractionState) -> str:
    """Route from refiner: loop back to critic or finish."""
    return "continue" if state["iteration"] < state["max_iterations"] else "end"


def compile_graph() -> Any:
    graph = StateGraph(ExtractionState)

    graph.add_node("extractor", extractor_node)
    graph.add_node("critic", critic_node)
    graph.add_node("refiner", refiner_node)

    graph.set_entry_point("extractor")
    graph.add_edge("extractor", "critic")

    graph.add_conditional_edges(
        "critic", should_refine, {"refine": "refiner", "clean": "__end__"}
    )

    graph.add_conditional_edges(
        "refiner", should_continue, {"continue": "critic", "end": "__end__"}
    )

    return graph.compile()


def run_extraction_graph(
    repo: Repo,
    model_entry: ModelEntry,
    api_key: str,
) -> tuple[Optional[list[dict]], bool]:
    graph = compile_graph()

    initial_state: ExtractionState = {
        "repo": repo,
        "model_entry": model_entry,
        "api_key": api_key,
        "extracted_topics": [],
        "critic_feedback": "",
        "iteration": 0,
        "max_iterations": 3,
        "errors": [],
    }

    try:
        result = graph.invoke(initial_state)
        topics = result.get("extracted_topics", [])
        if not topics:
            print(f"  [extraction_graph] {repo.title}: no topics extracted")
            return None, False
        return topics, False
    except Exception as e:
        msg = str(e).lower()
        is_rate_limit = "429" in msg or "rate limit" in msg or "rate_limit" in msg
        print(f"  [extraction_graph] {repo.title}: graph failed ({model_entry.model}): {e}")
        return None, is_rate_limit
