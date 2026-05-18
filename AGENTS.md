# Radar — AI trending & topic graph

Scrapes GitHub trending + Hugging Face (models/datasets/spaces/papers), extracts AI topics via LLM, and writes an Obsidian wiki vault with topic graph.

## First-time setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in OpenRouter keys.

## Key architecture

```
radar/
├── main.py              ← daily entry point: scrape → extract → write
├── scrapers/
│   ├── github.py         HTML scrape of github.com/trending
│   └── huggingface.py    HF API (huggingface_hub) models/datasets/spaces + REST for papers
├── extractor.py          LLM topic extraction via OpenRouter (fallback model list)
├── graph.py              node/edge store (JSON), dedup, alias resolution
├── writer.py             generates vault/Daily/*.md, vault/Topics/*.md
└── config.py             loads .env + config.toml
```

## Sources

| Source | Method | Rate |
|--------|--------|------|
| GitHub trending | HTML scrape (no API) | 25 repos |
| HF models | `list_models(sort="trending_score")` | 15 |
| HF datasets | `list_datasets(sort="trending_score")` | 15 |
| HF spaces | `list_spaces(sort="trending_score")` | 15 |
| HF papers | `GET /api/papers?sort=trending` | 15 |

## LLM extraction

- OpenRouter with fallback model chain (defined in config.toml)
- Keys from `.env`: `OPENROUTER_API_KEY_PRIMARY`, `OPENROUTER_API_KEY_SECONDARY`
- Prompt uses strict JSON schema so output is model-agnostic
- Each repo: fetch README + description (+ arxiv abstract if linked)

## Obsidian vault

```
vault/
├── Daily/
│   ├── 2026-05-18.md          ← top-N topics across all sources, new topics
│   └── 2026-05-18_audit.md    ← run report with failures logged
├── Monthly/
│   └── 2026-05.md             ← rollup: top topics, new/persistent
└── Topics/
    └── RLHF.md                ← auto-generated topic pages with backlinks
```

## Error handling

- **Fail quietly, log loudly**: never crash on one failed source/model
- Audit note (`_audit.md`) created per run with success count + failure details
- LLM failures: retry 2x → fall through to next model in chain → log and skip repo
- Network failures: retry 2x with exponential backoff → skip that source

## Data persistence

- `data/nodes.json` — topic metadata (first_seen, last_seen, repo_ids)
- `data/edges.json` — co-occurrence edges (source, target, monthly_weights, last_seen)
- `data/topic-aliases.json` — manual synonym map (curated)
- `data/` is gitignored

## Commands

```powershell
python -m radar.main                    # full daily run
python -m radar.main --source github    # single source for testing
```

## Monthly evolution

- Monthly rollup compares current month vs. previous using nodes.json/edges.json
- Track topic acceleration/deceleration, new/persistent/dropped topics

## Investigate failures

1. Check `vault/Daily/<date>_audit.md` for per-source/summary failure report
2. Check `data/` for node/edge state at time of failure
3. Run `python -m radar.main --source <source>` to isolate one source
