from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx

from .config import Config, ModelEntry
from .scrapers.github import Repo

EXTRACTION_PROMPT = """You are a specificity-focused AI topic extractor. Given a repo, extract specific topics and classify each under a broad category.

Rules:
- DO extract: specific model names (DeepSeek-V4, Qwen3.6), architectures (Diffusion Transformer), techniques (GRPO, RLVR, LoRA), frameworks (ComfyUI, LangChain), datasets (AgentTrove), domain-specific apps (Dexterous Manipulation, GUI Agents)
- DO NOT output broad field names as canonical — they go in the category field instead
- Prefer specific over general. "Group Relative Policy Optimization" over "Reinforcement Learning"
- Limit to 5 topic+category pairs per repo
- ONLY extract topics explicitly mentioned or directly evident from the README and description. NEVER invent topics that aren't present.
- If the repo is a well-known tool/project/library, include its name as a high-level topic.
- Each extracted topic MUST be traceable to specific text in the README or description. If you cannot find evidence, do not include it.

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
- "level": "high" or "low" — high for main themes grounded in README, low for specific techniques/models
- "parents": list of high-level canonical names this topic belongs under (for low-level topics only; empty for high-level topics)

Output ONLY valid JSON:
[
  {"canonical": "LoRA", "aliases": ["Low-Rank Adaptation"], "category": "Fine-Tuning", "level": "low", "parents": ["Fine-Tuning"]},
  {"canonical": "DeepSeek-V4", "aliases": [], "category": "Model Architecture", "level": "high", "parents": []}
]"""


def call_openrouter(
    repo: Repo,
    model_entry: ModelEntry,
    api_key: str,
    system_prompt: str | None = None,
    user_content: str | None = None,
    max_tokens: int = 4096,
    thinking: Any = None,
) -> Any:
    system = system_prompt or EXTRACTION_PROMPT

    if user_content is None:
        readme_snippet = (repo.readme_content or "")[:4000]
        desc = repo.description or ""
        user_content = f"Repository: {repo.title}\nDescription: {desc}\nREADME excerpt:\n{readme_snippet}"

    payload = {
        "model": model_entry.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }

    active_thinking = thinking if thinking is not None else getattr(model_entry, "thinking", None)
    if active_thinking:
        if isinstance(active_thinking, dict):
            payload["thinking"] = active_thinking
        else:
            payload["reasoning_effort"] = active_thinking

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
        content = data["choices"][0]["message"].get("content")
        if content is None:
            finish = data["choices"][0]["finish_reason"]
            print(f"  [extractor] {repo.title} | {model_entry.model}: empty content (finish_reason={finish})")
            return None
        content = content.strip()
        # Strip markdown code block fences
        if content.startswith("```"):
            first_newline = content.find("\n")
            if first_newline >= 0:
                content = content[first_newline + 1:]
            closing = content.rfind("```")
            if closing >= 0:
                content = content[:closing]
            content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            bracket = content.find("[")
            if bracket >= 0:
                try:
                    return json.loads(content[bracket:])
                except json.JSONDecodeError:
                    pass
            snippet = content[:200].replace("\n", " ")
            print(f"  [extractor] {repo.title} | {model_entry.model}: JSON parse failed — {e}. Snippet: {snippet}")
            return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise
        detail = e.response.text[:300] if e.response.text else ""
        print(f"  [extractor] {repo.title} | {model_entry.model}: HTTP {e.response.status_code} — {detail}")
        return None
    except httpx.TimeoutException:
        print(f"  [extractor] {repo.title} | {model_entry.model}: timeout (60s)")
        return None
    except Exception as e:
        print(f"  [extractor] {repo.title} | {model_entry.model}: exception — {e}")
        return None


def _extract_direct(
    repo: Repo, model_entry: ModelEntry, api_key: str
) -> tuple[Optional[list[dict]], bool]:
    try:
        result = call_openrouter(repo, model_entry, api_key)
        if result is None:
            return None, False
        return result, False
    except httpx.HTTPStatusError as e:
        return None, e.response.status_code == 429
    except Exception:
        return None, False


def _extract_with_critic_loop(
    repo: Repo, model_entry: ModelEntry, api_key: str
) -> tuple[Optional[list[dict]], bool]:
    from .extraction_graph.graph import run_extraction_graph

    return run_extraction_graph(repo, model_entry, api_key)


def extract_topics(repo: Repo, config: Config) -> Optional[list[dict]]:
    keys = [config.openrouter_api_key_primary]
    if config.openrouter_api_key_secondary:
        keys.append(config.openrouter_api_key_secondary)

    extract_fn = _extract_with_critic_loop if config.use_critic_loop else _extract_direct

    chain_errors = []

    for model_entry in config.model_chain:
        print(f"  [extractor] {repo.title} -> trying {model_entry.model}")
        attempt = 0
        wait = 1

        while wait <= 15:
            api_key = keys[attempt % len(keys)]
            result, is_rate_limit = extract_fn(repo, model_entry, api_key)

            if result is not None:
                return result

            if not is_rate_limit:
                break

            print(f"  [extractor] {repo.title} | {model_entry.model}: rate-limited, retry in {wait}s")
            time.sleep(wait)
            wait += 1
            attempt += 1

        chain_errors.append(model_entry.model)

    print(f"  [extractor] {repo.title}: ALL {len(chain_errors)} models failed — {', '.join(chain_errors)}")
    return None
