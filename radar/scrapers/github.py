from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup


@dataclass
class Repo:
    title: str
    description: str
    url: str
    source_type: str
    readme_content: Optional[str] = None
    arxiv_url: Optional[str] = None


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]


def _headers() -> dict:
    return {"User-Agent": random.choice(USER_AGENTS)}


TRENDING_URL = "https://github.com/trending"


def scrape_github_trending(limit: int = 25) -> List[Repo]:
    repos: List[Repo] = []
    try:
        resp = httpx.get(TRENDING_URL, headers=_headers(), follow_redirects=True, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[github] HTTP error fetching trending page: {e}")
        return repos

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.select("article.Box-row")
    for article in articles[:limit]:
        h2 = article.select_one("h2")
        if not h2:
            continue
        a_tag = h2.select_one("a")
        if not a_tag:
            continue
        href = a_tag.get("href", "").strip("/")
        if not href:
            continue
        title = href
        url = f"https://github.com/{href}"

        desc_tag = article.select_one("p")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        repo = Repo(title=title, description=description, url=url, source_type="github_trending")

        readme = _fetch_readme(href)
        if readme:
            repo.readme_content = readme

        repos.append(repo)

    print(f"[github] scraped {len(repos)} trending repos")
    return repos


def _fetch_readme(repo_path: str) -> Optional[str]:
    for branch in ("main", "master"):
        raw_url = f"https://raw.githubusercontent.com/{repo_path}/{branch}/README.md"
        try:
            resp = httpx.get(raw_url, headers=_headers(), follow_redirects=True, timeout=15)
            if resp.status_code == 200:
                return resp.text[:8000]
        except httpx.HTTPError:
            continue
    return None
