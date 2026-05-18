from __future__ import annotations

from typing import List, Optional

import httpx
from huggingface_hub import HfApi

from .github import Repo


HF_API_URL = "https://huggingface.co"


def _make_repo(item, source_type: str, readme: Optional[str] = None) -> Repo:
    title = item.id if hasattr(item, "id") else item.get("id", "")
    desc = getattr(item, "description", "") or item.get("description", "")
    url = f"{HF_API_URL}/{title}" if source_type != "hf_papers" else item.get("url", "")
    arxiv = item.get("arxiv", {}).get("id", "") if isinstance(item, dict) else ""
    if arxiv and not arxiv.startswith("http"):
        arxiv_url = f"https://arxiv.org/abs/{arxiv}"
    else:
        arxiv_url = arxiv or None
    return Repo(
        title=title,
        description=desc,
        url=url,
        source_type=source_type,
        readme_content=readme,
        arxiv_url=arxiv_url,
    )


_api = HfApi()


def scrape_hf_models(limit: int = 15) -> List[Repo]:
    repos: List[Repo] = []
    try:
        models = list(_api.list_models(sort="trending_score", direction=-1, limit=limit))
    except Exception as e:
        print(f"[hf/models] error: {e}")
        return repos
    for m in models:
        readme = _fetch_hf_readme(m.id)
        repos.append(_make_repo(m, "hf_models", readme=readme))
    print(f"[hf/models] scraped {len(repos)} models")
    return repos


def scrape_hf_datasets(limit: int = 15) -> List[Repo]:
    repos: List[Repo] = []
    try:
        datasets = list(_api.list_datasets(sort="trending_score", direction=-1, limit=limit))
    except Exception as e:
        print(f"[hf/datasets] error: {e}")
        return repos
    for d in datasets:
        readme = _fetch_hf_readme(d.id)
        repos.append(_make_repo(d, "hf_datasets", readme=readme))
    print(f"[hf/datasets] scraped {len(repos)} datasets")
    return repos


def scrape_hf_spaces(limit: int = 15) -> List[Repo]:
    repos: List[Repo] = []
    try:
        spaces = list(_api.list_spaces(sort="trending_score", direction=-1, limit=limit))
    except Exception as e:
        print(f"[hf/spaces] error: {e}")
        return repos
    for s in spaces:
        readme = _fetch_hf_readme(s.id)
        repos.append(_make_repo(s, "hf_spaces", readme=readme))
    print(f"[hf/spaces] scraped {len(repos)} spaces")
    return repos


def scrape_hf_papers(limit: int = 15) -> List[Repo]:
    repos: List[Repo] = []
    try:
        resp = httpx.get(f"{HF_API_URL}/api/papers?sort=trending", timeout=30)
        resp.raise_for_status()
        papers = resp.json()[:limit]
    except Exception as e:
        print(f"[hf/papers] error: {e}")
        return repos
    for p in papers:
        repos.append(_make_repo(p, "hf_papers"))
    print(f"[hf/papers] scraped {len(repos)} papers")
    return repos


def _fetch_hf_readme(repo_id: str) -> Optional[str]:
    try:
        readme = _api.repo_info(repo_id, files_metadata=False).cardData
        if readme:
            text = str(readme)
            return text[:8000]
    except Exception:
        pass
    try:
        resp = httpx.get(f"{HF_API_URL}/{repo_id}/raw/main/README.md", timeout=15)
        if resp.status_code == 200:
            return resp.text[:8000]
    except Exception:
        pass
    return None
