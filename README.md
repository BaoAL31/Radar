# Radar

AI trending & topic graph. Scrapes GitHub Trending + Hugging Face (models, datasets, spaces, papers), extracts AI topics via LLM (OpenRouter, free tier), builds a co-occurrence topic graph, and writes an Obsidian vault.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in OpenRouter API keys.

## Usage

```powershell
python -m radar.main           # full daily run
python -m radar.main --source github   # single source for testing
```

Output goes to `vault/` — an Obsidian vault with `Daily/`, `Monthly/`, and `Topics/` notes.

## Structure

```
radar/
├── main.py          ← entry point: scrape → extract → graph → write
├── scrapers/        ← github.py, huggingface.py
├── extractor.py     ← LLM topic extraction via OpenRouter
├── graph.py         ← node/edge store, dedup, alias resolution
├── writer.py        ← generates vault markdown
└── config.py        ← loads .env + config.toml
```
