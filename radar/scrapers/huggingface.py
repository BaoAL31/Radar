from __future__ import annotations

import re
from typing import List, Optional

import httpx
from huggingface_hub import HfApi

from .github import Repo


HF_API_URL = "https://huggingface.co"


def _extract_title(readme: Optional[str]) -> Optional[str]:
    if not readme:
        return None
    title_match = re.match(r'^#\s+(.+)$', readme, re.MULTILINE)
    return title_match.group(1).strip() if title_match else None


def _make_repo(item, source_type: str, readme: Optional[str] = None) -> Repo:
    title = item.id if hasattr(item, "id") else item.get("id", "")
    desc = getattr(item, "description", "")
    prefix = source_type.replace("hf_", "") if source_type.startswith("hf_") else ""
    url = f"{HF_API_URL}/{prefix}/{title}" if prefix else f"{HF_API_URL}/{title}"
    return Repo(
        title=title,
        description=desc,
        url=url,
        source_type=source_type,
        readme_content=readme,
        project_title=_extract_title(readme),
    )


_api = HfApi()


def scrape_hf_models(limit: int = 15) -> List[Repo]:
    repos: List[Repo] = []
    try:
        models = list(_api.list_models(sort="trending_score", limit=limit * 2))
    except Exception as e:
        print(f"[hf/models] error: {e}")
        return repos
    for m in models:
        if getattr(m, "gated", False):
            continue
        readme = _fetch_hf_readme(m.id)
        repos.append(_make_repo(m, "hf_models", readme=readme))
        if len(repos) >= limit:
            break
    print(f"[hf/models] scraped {len(repos)} models")
    return repos


def scrape_hf_datasets(limit: int = 15) -> List[Repo]:
    repos: List[Repo] = []
    try:
        datasets = list(_api.list_datasets(sort="trending_score", limit=limit * 2))
    except Exception as e:
        print(f"[hf/datasets] error: {e}")
        return repos
    for d in datasets:
        if getattr(d, "gated", False):
            continue
        readme = _fetch_hf_readme(d.id)
        repos.append(_make_repo(d, "hf_datasets", readme=readme))
        if len(repos) >= limit:
            break
    print(f"[hf/datasets] scraped {len(repos)} datasets")
    return repos


def scrape_hf_spaces(limit: int = 15) -> List[Repo]:
    repos: List[Repo] = []
    try:
        spaces = list(_api.list_spaces(sort="trending_score", limit=limit * 2))
    except Exception as e:
        print(f"[hf/spaces] error: {e}")
        return repos
    for s in spaces:
        if getattr(s, "gated", False):
            continue
        readme = _fetch_hf_readme(s.id)
        repos.append(_make_repo(s, "hf_spaces", readme=readme))
        if len(repos) >= limit:
            break
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
        title = p.get("title", p.get("id", ""))
        summary = p.get("summary", "") or ""
        arxiv_id = p.get("id", "")
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None
        repos.append(Repo(
            title=title,
            description=summary[:500],
            url=p.get("projectPage", "") or f"https://huggingface.co/papers/{arxiv_id}",
            source_type="hf_papers",
            readme_content=summary[:8000],
            arxiv_url=arxiv_url,
            project_title=title,
        ))
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
