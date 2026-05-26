from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv
import toml


ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ModelEntry:
    provider: str
    model: str


@dataclass
class HFSourceLimits:
    models: int = 15
    datasets: int = 15
    spaces: int = 15
    papers: int = 15


@dataclass
class Config:
    openrouter_api_key_primary: str = ""
    openrouter_api_key_secondary: str = ""
    huggingface_token: str = ""
    model_chain: list[ModelEntry] = field(default_factory=list)
    github_limit: int = 25
    hf_limits: HFSourceLimits = field(default_factory=HFSourceLimits)
    topic_blocklist: list[str] = field(default_factory=list)


def load_config() -> Config:
    load_dotenv(ROOT / ".env")

    cfg = Config(
        openrouter_api_key_primary=os.getenv("OPENROUTER_API_KEY_PRIMARY", ""),
        openrouter_api_key_secondary=os.getenv("OPENROUTER_API_KEY_SECONDARY", ""),
        huggingface_token=os.getenv("HUGGINGFACE_TOKEN", ""),
    )

    toml_path = ROOT / "config.toml"
    if toml_path.exists():
        data = toml.load(str(toml_path))
        models_data = data.get("models", {})
        chain = models_data.get("chain", [])
        cfg.model_chain = [ModelEntry(**m) for m in chain]

        gh = data.get("sources", {}).get("github", {})
        cfg.github_limit = gh.get("limit", 25)

        hf = data.get("sources", {}).get("huggingface", {})
        cfg.hf_limits = HFSourceLimits(
            models=hf.get("models", 15),
            datasets=hf.get("datasets", 15),
            spaces=hf.get("spaces", 15),
            papers=hf.get("papers", 15),
        )

        cfg.topic_blocklist = data.get("topics", {}).get("blocklist", [])

    return cfg
