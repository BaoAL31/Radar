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


CRITIC_PROMPT = """You are a quality evaluator for extracted AI topics. Given a repo and its extracted topics, evaluate each topic for:

1. **Hallucination**: Is each high-level topic actually present in or directly relevant to this repo?
2. **Granularity**: Are topics specific enough? (prefer "LoRA" over "Fine-Tuning")
3. **Alias quality**: Are aliases accurate and useful?
4. **Completeness**: Are any important topics missing?
5. **Parent validity**: Does each low-level topic have valid high-level parents among the repo's high-level topics?

For each issue found, specify:
- The topic name
- The type of issue
- A suggested fix

If everything is good, respond with only: {"status": "clean"}
Otherwise, respond with: {"status": "issues", "feedback": "<specific feedback>"}"""


REFINER_PROMPT = """You are a topic refiner. Given a repo, its current extracted topics, and critic feedback, produce a corrected version of the topic list.

Rules:
- Make only the surgical changes requested by the critic
- Keep the same JSON schema as the extractor output
- Do not change topics that were not flagged
- Do not add new topics unless explicitly requested by the critic
- Maintain the same categories and level assignments where correct

Output ONLY valid JSON matching the extractor schema:
[
  {"canonical": "...", "aliases": [...], "category": "...", "level": "high|low", "parents": [...]}
]"""
