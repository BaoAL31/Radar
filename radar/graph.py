from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import ROOT


DATA_DIR = ROOT / "data"
NODES_PATH = DATA_DIR / "nodes.json"
EDGES_PATH = DATA_DIR / "edges.json"
ALIASES_PATH = DATA_DIR / "topic-aliases.json"
BACKUP_PATH = DATA_DIR / "graph_backup.json"
LAST_RUN_PATH = DATA_DIR / "last_run_date.txt"


def get_last_run_date() -> Optional[str]:
    if LAST_RUN_PATH.exists():
        return LAST_RUN_PATH.read_text(encoding="utf-8").strip()
    return None


def save_graph_backup(nodes: Dict[str, Node], edges: List[Edge]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    backup = {
        "nodes": [dict(n) for n in nodes.values()],
        "edges": [dict(e) for e in edges],
    }
    BACKUP_PATH.write_text(json.dumps(backup, indent=2, ensure_ascii=False), encoding="utf-8")


def restore_graph_backup() -> Tuple[Dict[str, Node], List[Edge]]:
    if BACKUP_PATH.exists():
        data = json.loads(BACKUP_PATH.read_text(encoding="utf-8"))
        nodes = {n["name"]: Node(n) for n in data.get("nodes", [])}
        edges = [Edge(e) for e in data.get("edges", [])]
        return nodes, edges
    return {}, []


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


def get_processed_repo_urls(nodes: Dict[str, Node]) -> set[str]:
    """Return the set of repo URLs that have already been extracted."""
    return {url for node in nodes.values() for url in node.repo_ids}


def save_graph(nodes: Dict[str, Node], edges: List[Edge], today: date):
    _ensure_data_dir()
    NODES_PATH.write_text(
        json.dumps([dict(n) for n in nodes.values()], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    EDGES_PATH.write_text(
        json.dumps([dict(e) for e in edges], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    save_graph_backup(nodes, edges)


def merge_nodes(nodes: Dict[str, Node], edges: List[Edge], keep: str, drop: str):
    """Merge `drop` topic into `keep` topic: reassign all edges and repo_ids, then delete drop."""
    if keep == drop or drop not in nodes:
        return
    if keep not in nodes:
        nodes[keep] = Node({"name": keep, "aliases": [], "repo_ids": [], "first_seen": nodes[drop].get("first_seen", ""), "last_seen": nodes[drop].get("last_seen", "")})

    drop_node = nodes[drop]
    keep_node = nodes[keep]

    keep_node.setdefault("repo_ids", [])
    for rid in drop_node.get("repo_ids", []):
        if rid not in keep_node["repo_ids"]:
            keep_node["repo_ids"].append(rid)
    keep_node.setdefault("repo_titles", {}).update(drop_node.get("repo_titles", {}))
    keep_node["last_seen"] = max(keep_node.get("last_seen", ""), drop_node.get("last_seen", ""))
    keep_node.setdefault("aliases", [])
    keep_node["aliases"].append(drop)

    for e in edges:
        if e["source"] == drop:
            e["source"] = keep
        if e["target"] == drop:
            e["target"] = keep

    edges[:] = [e for e in edges if e["source"] != e["target"]]

    # dedup edges
    seen: set[tuple[str, str]] = set()
    deduped = []
    for e in edges:
        key = (e["source"], e["target"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    edges[:] = deduped

    del nodes[drop]


def load_aliases() -> Dict[str, str]:
    if ALIASES_PATH.exists():
        return json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    return {}


def _normalize_plural(name: str) -> str:
    """Strip trailing 's' for simple pluralization normalization."""
    if name.endswith('s') and not name.endswith('ss'):
        return name[:-1]
    return name


def merge_results(
    nodes: Dict[str, Node],
    edges: List[Edge],
    repo_id: str,
    topics: List[dict],
    today: date,
    project_title: Optional[str] = None,
):
    today_str = today.isoformat()
    month_key = today.strftime("%Y-%m")

    def _normalize(name: str) -> str:
        lower = name.lower().strip()
        aliases = load_aliases()
        if lower in {a.lower() for a in aliases}:
            return aliases[lower]
        # Normalize pluralization
        normalized = _normalize_plural(name)
        # Check if normalized version matches existing node
        for n in nodes.values():
            if n["name"].lower() == normalized.lower():
                return n["name"]
            if any(a.lower() == normalized.lower() for a in n.get("aliases", [])):
                return n["name"]
        return name

    resolved = []
    high_names: set[str] = set()
    low_parents: dict[str, list[str]] = {}
    aliases_map: dict[str, list[str]] = {}

    for t in topics:
        canonical = _normalize(t["canonical"])
        category = t.get("category", "")
        level = t.get("level", "high") or "high"
        parents = t.get("parents", []) or []
        aliases = t.get("aliases", []) or []

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
            found.setdefault("level", level)
            if level == "low":
                found.setdefault("parents", parents)
            if category and not found.get("category"):
                found["category"] = category
            if repo_id not in found.get("repo_ids", []):
                found.setdefault("repo_ids", []).append(repo_id)
                if project_title:
                    found.setdefault("repo_titles", {})[repo_id] = project_title
            name = found["name"]
        else:
            node_data = {
                "name": canonical,
                "aliases": [],
                "category": category,
                "level": level,
                "first_seen": today_str,
                "last_seen": today_str,
                "repo_ids": [repo_id],
            }
            if level == "low":
                node_data["parents"] = parents
            if project_title:
                node_data["repo_titles"] = {repo_id: project_title}
            node = Node(node_data)
            nodes[canonical] = node
            resolved.append(canonical)
            name = canonical

        aliases_map[name] = aliases if level == "low" else []

        if level == "high":
            high_names.add(name)
        elif level == "low":
            low_parents[name] = parents

    def _upsert_edge(src: str, tgt: str):
        src, tgt = sorted([src, tgt])
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

    # high↔high: all-pairs
    h_list = sorted(high_names)
    for i in range(len(h_list)):
        for j in range(i + 1, len(h_list)):
            _upsert_edge(h_list[i], h_list[j])

    # low↔low: all-pairs
    l_names = [n for n in resolved if n in low_parents]
    for i in range(len(l_names)):
        for j in range(i + 1, len(l_names)):
            _upsert_edge(l_names[i], l_names[j])

    # low↔high: only to declared parents that exist in this repo's high topics
    for low_name, parent_list in low_parents.items():
        for parent in parent_list:
            resolved_parent = _normalize(parent)
            if resolved_parent in high_names:
                _upsert_edge(low_name, resolved_parent)
