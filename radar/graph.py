from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

from .config import ROOT


DATA_DIR = ROOT / "data"
NODES_PATH = DATA_DIR / "nodes.json"
EDGES_PATH = DATA_DIR / "edges.json"
ALIASES_PATH = DATA_DIR / "topic-aliases.json"


class Node(dict):
    @property
    def name(self) -> str: return self.get("name", "")

    @property
    def aliases(self) -> list: return self.get("aliases", [])

    @property
    def first_seen(self) -> str: return self.get("first_seen", "")

    @property
    def last_seen(self) -> str: return self.get("last_seen", "")

    @property
    def repo_ids(self) -> list: return self.get("repo_ids", [])


class Edge(dict):
    @property
    def source(self) -> str: return self.get("source", "")

    @property
    def target(self) -> str: return self.get("target", "")

    @property
    def monthly_weights(self) -> dict: return self.get("monthly_weights", {})

    @property
    def last_seen(self) -> str: return self.get("last_seen", "")


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_graph() -> Tuple[Dict[str, Node], List[Edge]]:
    _ensure_data_dir()
    nodes: Dict[str, Node] = {}
    if NODES_PATH.exists():
        raw = json.loads(NODES_PATH.read_text(encoding="utf-8"))
        for n in raw:
            node = Node(n)
            nodes[node["name"]] = node

    edges: List[Edge] = []
    if EDGES_PATH.exists():
        raw = json.loads(EDGES_PATH.read_text(encoding="utf-8"))
        edges = [Edge(e) for e in raw]

    return nodes, edges


def save_graph(nodes: Dict[str, Node], edges: List[Edge]):
    _ensure_data_dir()
    NODES_PATH.write_text(
        json.dumps([dict(n) for n in nodes.values()], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    EDGES_PATH.write_text(
        json.dumps([dict(e) for e in edges], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_aliases() -> Dict[str, str]:
    if ALIASES_PATH.exists():
        return json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    return {}


def merge_results(
    nodes: Dict[str, Node],
    edges: List[Edge],
    repo_id: str,
    topics: List[str],
    today: date,
):
    today_str = today.isoformat()
    month_key = today.strftime("%Y-%m")

    def _normalize(name: str) -> str:
        lower = name.lower().strip()
        aliases = load_aliases()
        if lower in {a.lower() for a in aliases}:
            return aliases[lower]
        return name

    resolved = []
    for t in topics:
        canonical = _normalize(t)
        # find existing node by name or alias match
        found = None
        for n in nodes.values():
            if n["name"].lower() == canonical.lower():
                found = n
                break
            if any(a.lower() == canonical.lower() for a in n.get("aliases", [])):
                found = n
                break
        if found:
            resolved.append(found["name"])
            found["last_seen"] = today_str
            if repo_id not in found.get("repo_ids", []):
                found.setdefault("repo_ids", []).append(repo_id)
        else:
            node = Node({
                "name": canonical,
                "aliases": [],
                "first_seen": today_str,
                "last_seen": today_str,
                "repo_ids": [repo_id],
            })
            nodes[canonical] = node
            resolved.append(canonical)

    # create/update edges between all topic pairs in this repo
    for i in range(len(resolved)):
        for j in range(i + 1, len(resolved)):
            src, tgt = sorted([resolved[i], resolved[j]])
            existing = None
            for e in edges:
                if e["source"] == src and e["target"] == tgt:
                    existing = e
                    break
            if existing:
                mw = existing.setdefault("monthly_weights", {})
                mw[month_key] = mw.get(month_key, 0) + 1
                existing["last_seen"] = today_str
            else:
                edges.append(Edge({
                    "source": src,
                    "target": tgt,
                    "monthly_weights": {month_key: 1},
                    "last_seen": today_str,
                }))
