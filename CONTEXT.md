# Radar — Glossary

## Node
A **topic** extracted from a project/repo (e.g. "RLHF", "Vision Transformer", "LoRA"). Nodes are the vertices of the knowledge graph. Each Node carries a **canonical name**, a list of **aliases**, a **level** (`"high"` or `"low"`), and a **category**. Node identity is resolved by exact match against canonical name or any alias — no fuzzy matching. The manual alias map (`topic-aliases.json`) is for overriding LLM mistakes only.

## High-Level Topic
A Node with `level: "high"`. High-level topics represent the main themes of a repo and **must be grounded in the README content**. Extracted and validated by the Critic node for hallucination and completeness.

## Low-Level Topic
A Node with `level: "low"`. Low-level topics represent specific techniques, models, or concepts related to a repo's high-level topics. They **need not appear in the README** — they come from the LLM's domain knowledge. However, each low-level topic must connect via an Edge to at least one high-level topic from the same repo. A repo with zero low-level topics is invalid and is dropped.

## Edge
A connection between two Nodes. Edges are created either explicitly (a low-level topic declares a parent high-level topic) or via co-occurrence (high↔high and low↔low pairs from the same repo). Declared parent edges replace any co-occurrence edges between that low topic and those high topics. Each Edge carries a `monthly_weights` dict (e.g. `{"2026-01": 10, "2026-05": 2}`) so the monthly rollup can query per-calendar-month activity. Total weight is the sum across all months.

## Extraction Graph
A LangGraph state machine that processes a single repo through four nodes: **Extractor** (initial topic extraction), **Critic** (evaluates extracted topics against README for hallucination, granularity, alias quality, and completeness), **Refiner** (surgically fixes issues flagged by Critic), and a **Router** (loops back to Critic if issues remain and `iteration < max_iterations`, otherwise exits). Node failure at any point causes the entire repo to be skipped.

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
