from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Dict, List

from .config import ROOT
from .graph import Node, Edge


VAULT = ROOT / "vault"
DAILY_DIR = VAULT / "Daily"
MONTHLY_DIR = VAULT / "Monthly"
TOPICS_DIR = VAULT / "Topics"
AUDIT_DIR = ROOT / "data" / "audit"


def _sanitize_filename(name: str) -> str:
    illegal = r'\/:*?"<>|'
    for ch in illegal:
        name = name.replace(ch, " ")
    return name.strip()


def _is_blocklisted(name: str, blocklist: list[str]) -> bool:
    return any(name.lower() == b.lower() for b in blocklist)


def write_daily(
    nodes: Dict[str, Node],
    edges: List[Edge],
    today: date,
    audit_info: dict,
    blocklist: list[str] | None = None,
):
    blocklist = blocklist or []
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    today_str = today.isoformat()
    path = DAILY_DIR / f"{today_str}.md"

    # get top-20 topics by repo count for today
    today_month = today.strftime("%Y-%m")
    topic_counts: List[tuple] = []
    for n in nodes.values():
        if n.get("last_seen", "") >= today_str and not _is_blocklisted(n["name"], blocklist):
            repo_count = len(n.get("repo_ids", []))
            topic_counts.append((n["name"], repo_count))
    topic_counts.sort(key=lambda x: -x[1])
    top20 = topic_counts[:20]

    # new topics (first_seen == today)
    new_topics = [n["name"] for n in nodes.values() if n.get("first_seen", "") == today_str and not _is_blocklisted(n["name"], blocklist)]

    lines = [f"# {today_str} — Radar Daily", ""]
    if top20:
        lines.append("## Top Topics Today")

        # group by category
        cat_groups: dict[str, list] = {}
        for name, count in top20:
            n = nodes.get(name)
            cat = n.get("category", "") if n else ""
            cat_groups.setdefault(cat, []).append((name, count))

        sorted_cats = sorted(cat_groups.items(), key=lambda x: -sum(c for _, c in x[1]))

        for cat, items in sorted_cats:
            if cat:
                lines.append(f"### {cat}")
            for name, count in items:
                n = nodes.get(name)
                links = n.get("repo_ids", [])[:5] if n else []
                titles = n.get("repo_titles", {}) if n else {}
                lines.append(f"- [[{name}]] — {count} repo{'s' if count > 1 else ''}")
                for url in links:
                    display = titles.get(url, url)
                    lines.append(f"  - [{display}]({url})")
        lines.append("")

    if new_topics:
        lines.append("## New Topics")
        for name in new_topics:
            lines.append(f"- [[{name}]]")
        lines.append("")

    if not top20 and not new_topics:
        lines.append("_No topics extracted. Check the audit note for details._")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[writer] wrote {path.name}")

    # audit note
    _write_audit(today, audit_info)


def _write_audit(today: date, info: dict):
    today_str = today.isoformat()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / f"{today_str}_audit.md"
    lines = [f"# {today_str} — Run Audit", ""]
    for key, val in info.items():
        lines.append(f"- **{key}**: {val}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_monthly(
    nodes: Dict[str, Node],
    edges: List[Edge],
    today: date,
    blocklist: list[str] | None = None,
):
    blocklist = blocklist or []
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    year, month = today.year, today.month
    month_key = today.strftime("%Y-%m")
    path = MONTHLY_DIR / f"{month_key}.md"

    prev_year = year if month > 1 else year - 1
    prev_month = month - 1 if month > 1 else 12
    prev_key = f"{prev_year}-{prev_month:02d}"

    # current month topics
    current_names = set()
    for n in nodes.values():
        if n.get("last_seen", "") >= f"{month_key}-01" and not _is_blocklisted(n["name"], blocklist):
            current_names.add(n["name"])

    # previous month topics
    prev_names = set()
    for n in nodes.values():
        ls = n.get("last_seen", "")
        if prev_key <= ls < f"{month_key}-01" and not _is_blocklisted(n["name"], blocklist):
            prev_names.add(n["name"])

    new_topics = current_names - prev_names
    dropped_topics = prev_names - current_names

    # count topics by repo
    topic_counts = []
    for n in nodes.values():
        if n["name"] in current_names:
            topic_counts.append((n["name"], len(n.get("repo_ids", []))))
    topic_counts.sort(key=lambda x: -x[1])

    # accelerating: compare edge monthly weights
    accelerating = []
    for e in edges:
        if _is_blocklisted(e["source"], blocklist) or _is_blocklisted(e["target"], blocklist):
            continue
        mw = e.get("monthly_weights", {})
        cur = mw.get(month_key, 0)
        prev = mw.get(prev_key, 0)
        if cur > prev and cur >= 3:
            accelerating.append((e["source"], e["target"], cur, prev))

    accelerating.sort(key=lambda x: -x[2])
    accelerating = accelerating[:10]

    lines = [f"# {month_key} — Monthly Rollup", ""]

    if topic_counts:
        lines.append("## Top Topics")
        for name, count in topic_counts[:15]:
            lines.append(f"- [[{name}]] — {count} repo{'s' if count > 1 else ''}")
        lines.append("")

    if new_topics:
        lines.append(f"## New Topics ({len(new_topics)})")
        for name in sorted(new_topics)[:20]:
            lines.append(f"- [[{name}]]")
        lines.append("")

    if dropped_topics:
        lines.append(f"## Dropped Topics ({len(dropped_topics)})")
        for name in sorted(dropped_topics)[:20]:
            lines.append(f"- [[{name}]]")
        lines.append("")

    if accelerating:
        lines.append("## Accelerating Pairs")
        for src, tgt, cur, prev in accelerating:
            lines.append(f"- [[{src}]] ↔ [[{tgt}]] ({prev} → {cur})")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[writer] wrote monthly/{month_key}.md")


def write_topic_pages(nodes: Dict[str, Node], edges: List[Edge], today: date):
    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    today_str = today.isoformat()

    # build a map: topic name -> co-occuring topics (by edge weight, descending)
    cooccur_map: Dict[str, List[tuple]] = {}
    for e in edges:
        src, tgt = e["source"], e["target"]
        total = sum(e.get("monthly_weights", {}).values())
        cooccur_map.setdefault(src, []).append((tgt, total))
        cooccur_map.setdefault(tgt, []).append((src, total))

    for n in nodes.values():
        name = n["name"]
        filename = _sanitize_filename(name) + ".md"
        path = TOPICS_DIR / filename

        tags = [f"category/{n['category']}"] if n.get("category") else []
        if n.get("last_seen", "") == today_str:
            tags.append(f"daily/{today_str}")

        lines = ["---"]
        lines.append(f'topic: "{name}"')
        lines.append('type: topic')
        if n.get("category"):
            lines.append(f'parent: "{n["category"]}"')
        if tags:
            lines.append(f'tags: [{", ".join(tags)}]')
        lines.append(f'first_seen: "{n.get("first_seen", "")}"')
        lines.append(f'last_seen: "{n.get("last_seen", "")}"')
        lines.append(f'repo_count: {len(n.get("repo_ids", []))}')
        lines.append("---")
        lines.append("")

        # related topics
        related = cooccur_map.get(name, [])
        related.sort(key=lambda x: -x[1])
        if related:
            lines.append("## Related Topics")
            for rel_name, weight in related[:10]:
                lines.append(f"- [[{rel_name}]] (co-occurs {weight}x)")
            lines.append("")

        # mentioned repos
        repo_ids = n.get("repo_ids", [])
        titles = n.get("repo_titles", {})
        if repo_ids:
            lines.append("## Mentioned in")
            for url in repo_ids:
                display = titles.get(url, url)
                lines.append(f"- [{display}]({url})")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

    # category pages
    cat_map: dict[str, list[str]] = {}
    for n in nodes.values():
        cat = n.get("category", "")
        if cat:
            cat_map.setdefault(cat, []).append(n["name"])

    for cat, members in cat_map.items():
        cat_filename = _sanitize_filename(cat) + ".md"
        cat_path = TOPICS_DIR / cat_filename
        members.sort()
        lines = ["---"]
        lines.append(f'category: "{cat}"')
        lines.append('type: category')
        lines.append(f'tags: [category/{cat}]')
        lines.append(f'topic_count: {len(members)}')
        lines.append("---")
        lines.append("")
        lines.append(f"## Topics under {cat}")
        for m_name in members:
            n = nodes.get(m_name)
            count = len(n.get("repo_ids", [])) if n else 0
            lines.append(f"- [[{m_name}]] ({count} repo{'s' if count != 1 else ''})")
        lines.append("")
        cat_path.write_text("\n".join(lines), encoding="utf-8")
