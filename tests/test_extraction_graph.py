from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

from radar.extraction_graph import invoke_extraction_graph
from radar.extraction_graph.graph import compile_graph, should_refine, should_continue
from radar.extraction_graph.state import ExtractionState


@dataclass
class FakeModelEntry:
    provider: str = ""
    model: str = ""

@dataclass
class FakeRepo:
    title: str = "test/repo"
    description: str = ""
    url: str = "https://github.com/test/repo"
    source_type: str = "test"
    readme_content: str = ""
    arxiv_url: str | None = None
    project_title: str | None = None


def make_state(**overrides: dict) -> ExtractionState:
    base: ExtractionState = {
        "repo": FakeRepo(),
        "model_entry": FakeModelEntry(),
        "api_key": "sk-test",
        "extracted_topics": [],
        "critic_feedback": "",
        "iteration": 0,
        "max_iterations": 3,
        "errors": [],
    }
    base.update(overrides)
    return base


class TestShouldRefine:
    def test_clean_feedback_returns_clean(self):
        state = make_state(critic_feedback="")
        assert should_refine(state) == "clean"

    def test_issues_feedback_returns_refine(self):
        state = make_state(critic_feedback="Granularity too broad")
        assert should_refine(state) == "refine"


class TestShouldContinue:
    def test_under_max_returns_continue(self):
        state = make_state(iteration=0, max_iterations=3)
        assert should_continue(state) == "continue"

    def test_at_max_returns_end(self):
        state = make_state(iteration=3, max_iterations=3)
        assert should_continue(state) == "end"

    def test_exceeded_max_returns_end(self):
        state = make_state(iteration=5, max_iterations=3)
        assert should_continue(state) == "end"


class TestCompileGraph:
    def test_returns_compiled_graph(self):
        graph = compile_graph()
        assert graph is not None
        assert hasattr(graph, "invoke")


class TestInvokeExtractionGraph:
    def test_without_critic_loop_calls_openrouter_not_graph(self):
        mock_topics = [{"canonical": "RLHF", "category": "Training", "level": "high"}]

        config = MagicMock()
        config.use_critic_loop = False
        config.model_chain = [FakeModelEntry()]
        config.openrouter_api_key_primary = "sk-test"
        config.openrouter_api_key_secondary = None

        with (
            patch("radar.extraction_graph.nodes.extractor.call_openrouter") as mock_call,
            patch("radar.extraction_graph.run_extraction_graph") as mock_graph,
        ):
            mock_call.return_value = mock_topics
            result = invoke_extraction_graph(FakeRepo(), config)

        assert result == mock_topics
        mock_call.assert_called_once()
        mock_graph.assert_not_called()
