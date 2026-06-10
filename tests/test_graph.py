from __future__ import annotations

from datetime import date
from typing import Dict, List

from radar.graph import Node, Edge, merge_results


def make_topic(canonical: str, level: str, category: str = "",
               aliases: list[str] | None = None,
               parents: list[str] | None = None) -> dict:
    return {
        "canonical": canonical,
        "aliases": aliases or [],
        "category": category,
        "level": level,
        "parents": parents or [],
    }


class TestMergeResultsLevelAndParents:
    """Edge logic: parents replace all-pairs for high↔low;
    all-pairs for high↔high and low↔low."""

    def test_high_high_all_pairs(self):
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        today = date(2026, 5, 26)

        topics = [
            make_topic("Transformer", "high", "Model Architecture"),
            make_topic("Fine-Tuning", "high", "Fine-Tuning"),
            make_topic("LoRA", "low", "Fine-Tuning", parents=["Fine-Tuning"]),
        ]

        merge_results(nodes, edges, "repo/1", topics, today)

        # High↔high edge created
        assert any(
            e["source"] == "Fine-Tuning" and e["target"] == "Transformer"
            for e in edges
        ), "high↔high edge missing"

    def test_low_only_connects_to_declared_parent(self):
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        today = date(2026, 5, 26)

        topics = [
            make_topic("Transformer", "high", "Model Architecture"),
            make_topic("Fine-Tuning", "high", "Fine-Tuning"),
            make_topic("LoRA", "low", "Fine-Tuning", parents=["Fine-Tuning"]),
        ]

        merge_results(nodes, edges, "repo/1", topics, today)

        # LoRA → Fine-Tuning edge exists
        assert any(
            e["source"] == "Fine-Tuning" and e["target"] == "LoRA"
            for e in edges
        ), "low→parent edge missing"

        # LoRA → Transformer edge should NOT exist
        assert not any(
            (e["source"] == "LoRA" and e["target"] == "Transformer") or
            (e["source"] == "Transformer" and e["target"] == "LoRA")
            for e in edges
        ), "low→non-parent edge should not exist"

    def test_low_low_all_pairs(self):
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        today = date(2026, 5, 26)

        topics = [
            make_topic("Transformer", "high"),
            make_topic("LoRA", "low", parents=["Transformer"]),
            make_topic("Gradient Checkpointing", "low", parents=["Transformer"]),
        ]

        merge_results(nodes, edges, "repo/1", topics, today)

        # Low↔low edge exists
        assert any(
            e["source"] == "Gradient Checkpointing" and e["target"] == "LoRA"
            for e in edges
        ), "low↔low edge missing"

    def test_node_stores_level_and_parents(self):
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        today = date(2026, 5, 26)

        topics = [
            make_topic("Transformer", "high", "Model Architecture"),
            make_topic("LoRA", "low", "Fine-Tuning", parents=["Transformer"]),
        ]

        merge_results(nodes, edges, "repo/1", topics, today)

        assert nodes["Transformer"].get("level") == "high"
        assert nodes["LoRA"].get("level") == "low"
        assert nodes["LoRA"].get("parents") == ["Transformer"]

    def test_node_level_defaults_to_high_when_missing(self):
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        today = date(2026, 5, 26)

        topic = {"canonical": "RLHF", "aliases": [], "category": "RL"}
        merge_results(nodes, edges, "repo/1", [topic], today)

        assert nodes["RLHF"].get("level") == "high"

    def test_orphan_low_topic_no_parent_edge(self):
        """Low topic whose parents don't match any high topic
        still gets included (but no high↔low edges for it)."""
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        today = date(2026, 5, 26)

        topics = [
            make_topic("Transformer", "high"),
            make_topic("LoRA", "low", parents=["NonExistent"]),
        ]

        merge_results(nodes, edges, "repo/1", topics, today)

        assert "LoRA" in nodes, "orphan low topic should still be stored"
        assert not any(
            e["source"] == "LoRA" or e["target"] == "LoRA"
            for e in edges
        ), "orphan low topic should have no edges"
