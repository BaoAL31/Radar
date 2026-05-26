from __future__ import annotations

import random
import re
import time
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
    project_title: Optional[str] = None


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


TRENDING_URL = "https://github.com/trending"
SELECTORS = [
    "article.Box-row",
    ".Box-row",
    "div.Box-row",
    "article",
]
REPO_HREF_RE = re.compile(r'href="(/[^/]+/[^/]+)"')


def _fetch_page(retries: int = 3) -> Optional[str]:
    for i in range(retries):
        try:
            resp = httpx.get(
                TRENDING_URL,
                headers=_headers(),
                follow_redirects=True,
                timeout=30,
            )
            resp.raise_for_status()
            if len(resp.text) > 5000:
                return resp.text
            print(f"[github] page too short ({len(resp.text)} bytes), retry {i+1}/{retries}")
        except httpx.HTTPError as e:
            print(f"[github] HTTP error: {e}, retry {i+1}/{retries}")
        time.sleep(2 + i * 2)
    return None


def _parse_repos(html: str, limit: int) -> List[Repo]:
    repos: List[Repo] = []
    seen = set()

    for selector in SELECTORS:
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select(selector)
        for article in articles:
            if len(repos) >= limit:
                break
            h2 = article.select_one("h2")
            if not h2:
                continue
            a_tag = h2.select_one("a")
            if not a_tag:
                continue
            href = a_tag.get("href", "").strip("/")
            if not href or "/" not in href or href in seen:
                continue
            seen.add(href)

            desc_tag = article.select_one("p")
            description = desc_tag.get_text(strip=True) if desc_tag else ""

            repo = Repo(
                title=href,
                description=description,
                url=f"https://github.com/{href}",
                source_type="github_trending",
            )

            readme = _fetch_readme(href)
            if readme:
                repo.readme_content = readme
                title_match = re.match(r'^#\s+(.+)$', readme, re.MULTILINE)
                if title_match:
                    repo.project_title = title_match.group(1).strip()

            repos.append(repo)

        if repos:
            break

    # Fallback: regex parse if selectors found nothing
    if not repos:
        for m in REPO_HREF_RE.finditer(html):
            if len(repos) >= limit:
                break
            href = m.group(1).strip("/")
            if not href or "/" not in href or href in seen:
                continue
            seen.add(href)
            repos.append(Repo(
                title=href,
                description="",
                url=f"https://github.com/{href}",
                source_type="github_trending",
            ))

    return repos


def scrape_github_trending(limit: int = 25) -> List[Repo]:
    html = _fetch_page(retries=3)
    if not html:
        print("[github] failed to fetch trending page after retries")
        return []

    repos = _parse_repos(html, limit)
    print(f"[github] scraped {len(repos)} trending repos (limit {limit})")
    return repos


def _fetch_readme(repo_path: str) -> Optional[str]:
    for branch in ("main", "master", "develop"):
        raw_url = f"https://raw.githubusercontent.com/{repo_path}/{branch}/README.md"
        try:
            resp = httpx.get(raw_url, headers=_headers(), follow_redirects=True, timeout=15)
            if resp.status_code == 200 and len(resp.text) > 50:
                return resp.text[:8000]
        except httpx.HTTPError:
            continue
    return None
