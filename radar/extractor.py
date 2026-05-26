from __future__ import annotations

import json
import time
from typing import List, Optional

import httpx

VALID_CATEGORIES = {
    "AI Agent", "Model Architecture", "Fine-Tuning", "Computer Vision",
    "Speech & Audio", "Natural Language Processing", "Reinforcement Learning",
    "Dataset", "Infrastructure", "Quantization", "Security", "Robotics",
    "Generative Models", "Training Pipeline",
}


from .config import Config, ModelEntry
from .scrapers.github import Repo


EXTRACTION_PROMPT = """You are a specificity-focused AI topic extractor. Given a repo, extract specific topics and classify each under a broad category.

Rules:
- DO extract: specific model names (DeepSeek-V4, Qwen3.6), architectures (Diffusion Transformer), techniques (GRPO, RLVR, LoRA), frameworks (ComfyUI, LangChain), datasets (AgentTrove), domain-specific apps (Dexterous Manipulation, GUI Agents)
- DO NOT output broad field names as canonical — they go in the category field instead
- Prefer specific over general. "Group Relative Policy Optimization" over "Reinforcement Learning"
- Limit to 5 topic+category pairs per repo

Categories — pick EXACTLY from this list (case-sensitive):
- "AI Agent" — agent frameworks, tools, platforms (Cursor, LangChain, Claude Code)
- "Model Architecture" — specific models and architectures (DeepSeek-V4, Qwen3.6, MiniCPM-V)
- "Fine-Tuning" — adaptation techniques (LoRA, QLoRA, instruction tuning, distillation)
- "Computer Vision" — image/video understanding, generation, editing
- "Speech & Audio" — TTS, STT, voice cloning, audio generation
- "Natural Language Processing" — text generation, translation, summarization
- "Reinforcement Learning" — RL, GRPO, RLVR, policy optimization
- "Dataset" — specific datasets and benchmarks
- "Infrastructure" — deployment, hosting, Docker, serving, quantization
- "Quantization" — low-bit quantization, activation scaling, MoE optimization
- "Security" — penetration testing, vulnerability analysis, code security
- "Robotics" — manipulation, navigation, embodied AI
- "Generative Models" — diffusion models, GANs, flow matching, video generation
- "Training Pipeline" — data processing, training strategies, synthetic data generation

For each topic:
- "canonical": the specific topic name
- "aliases": alternative names (can be empty)
- "category": EXACTLY one from the list above

Output ONLY valid JSON:
[
  {"canonical": "LoRA", "aliases": ["Low-Rank Adaptation"], "category": "Fine-Tuning"},
  {"canonical": "DeepSeek-V4", "aliases": [], "category": "Model Architecture"}
]"""


def call_openrouter(repo: Repo, model_entry: ModelEntry, api_key: str) -> Optional[List[dict]]:
    prompt = EXTRACTION_PROMPT
    readme_snippet = (repo.readme_content or "")[:4000]
    desc = repo.description or ""

    user_content = f"Repository: {repo.title}\nDescription: {desc}\nREADME excerpt:\n{readme_snippet}"

    payload = {
        "model": model_entry.model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
    }

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        return json.loads(content)
    except Exception as e:
        print(f"  [extractor] {repo.title}: LLM call failed ({model_entry.model}): {e}")
        return None


def extract_topics(repo: Repo, config: Config) -> List[str]:
    result = None
    errors = []

    for model_entry in config.model_chain:
        for attempt in range(2):
            api_key = config.openrouter_api_key_primary
            result = call_openrouter(repo, model_entry, api_key)
            if result is not None:
                break
            if config.openrouter_api_key_secondary:
                result = call_openrouter(repo, model_entry, config.openrouter_api_key_secondary)
                if result is not None:
                    break
            if attempt == 0:
                print(f"  [extractor] retrying {model_entry.model}...")
                time.sleep(2)

        if result is not None:
            break
        errors.append(model_entry.model)

    if result is None:
        print(f"  [extractor] all models failed for {repo.title}, errors: {errors}")
        return []

    topics = []
    for entry in result:
        canonical = entry.get("canonical", "").strip()
        if not canonical:
            continue
        category = entry.get("category", "").strip()
        if category not in VALID_CATEGORIES:
            category = ""
        topics.append({
            "canonical": canonical,
            "category": category,
        })

    names = [t["canonical"] for t in topics]
    print(f"  [extractor] {repo.title} -> {names}")
    time.sleep(1.5)
    return topics
