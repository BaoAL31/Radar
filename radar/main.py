from __future__ import annotations

import argparse
import sys
from datetime import date

from .config import load_config, ROOT
from .graph import load_graph, save_graph, merge_results
from .extractor import extract_topics
from .writer import write_daily, write_monthly, write_topic_pages
from .scrapers.github import scrape_github_trending
from .scrapers.huggingface import (
    scrape_hf_models,
    scrape_hf_datasets,
    scrape_hf_spaces,
    scrape_hf_papers,
)


def main():
    parser = argparse.ArgumentParser(description="Radar — AI trending & topic graph")
    parser.add_argument("--source", choices=["github", "hf", "all"], default="all")
    args = parser.parse_args()

    config = load_config()
    today = date.today()

    nodes, edges = load_graph()

    audit = {"date": today.isoformat(), "sources": {}}

    repos = []

    if args.source in ("github", "all"):
        gh = scrape_github_trending(config.github_limit)
        audit["sources"]["github"] = len(gh)
        repos.extend(gh)

    if args.source in ("hf", "all"):
        models = scrape_hf_models(config.hf_limits.models)
        datasets = scrape_hf_datasets(config.hf_limits.datasets)
        spaces = scrape_hf_spaces(config.hf_limits.spaces)
        papers = scrape_hf_papers(config.hf_limits.papers)
        audit["sources"]["hf_models"] = len(models)
        audit["sources"]["hf_datasets"] = len(datasets)
        audit["sources"]["hf_spaces"] = len(spaces)
        audit["sources"]["hf_papers"] = len(papers)
        repos.extend(models)
        repos.extend(datasets)
        repos.extend(spaces)
        repos.extend(papers)

    total = len(repos)
    success = 0
    fail = 0

    for repo in repos:
        topics = extract_topics(repo, config)
        if topics:
            merge_results(nodes, edges, repo.url, topics, today, project_title=repo.project_title)
            success += 1
        else:
            fail += 1

    save_graph(nodes, edges, today)

    audit["total_repos"] = total
    audit["extraction_success"] = success
    audit["extraction_fail"] = fail

    write_daily(nodes, edges, today, audit, blocklist=config.topic_blocklist)
    write_monthly(nodes, edges, today, blocklist=config.topic_blocklist)
    write_topic_pages(nodes, edges, today)

    print(f"[radar] done — {success}/{total} repos extracted, {len(nodes)} topics, {len(edges)} edges")


if __name__ == "__main__":
    main()
