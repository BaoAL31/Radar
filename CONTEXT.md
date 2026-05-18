# Radar — Glossary

## Node
A **topic** extracted from a project/repo (e.g. "RLHF", "Vision Transformer", "LoRA"). Nodes are the vertices of the knowledge graph. Each Node carries a **canonical name** and a list of **aliases** (extracted by the LLM in one shot). Node identity is resolved by exact match against canonical name or any alias — no fuzzy matching. The manual alias map (`topic-aliases.json`) is for overriding LLM mistakes only.

## Edge
A connection between two Nodes that co-occur in the same repo. Edges signal topical relationship. Each Edge carries a `monthly_weights` dict (e.g. `{"2026-01": 10, "2026-05": 2}`) so the monthly rollup can query per-calendar-month activity. Total weight is the sum across all months.

## Source
A content origin that we scrape. Each Source has a **type** (GitHub Trending, HF Models, HF Datasets, HF Papers, HF Spaces).

## Repo (or Project)
A unit of content from a Source. Each repo yields zero or more Nodes.

## Monthly Rollup
A calendar-month summary (`Monthly/YYYY-MM.md`) comparing topic activity against the previous month. Tracks new, persistent, dropped, accelerating, and decelerating topics based on node first_seen/last_seen timestamps and edge weights.

## Vault
The Obsidian vault directory at `radar/vault/` containing the generated wiki: daily digests, monthly rollups, and topic pages.

## Audit Note
A daily run report (`YYYY-MM-DD_audit.md`) written alongside each daily digest. Logs success/failure per source and per repo, so failures are visible inside Obsidian.
