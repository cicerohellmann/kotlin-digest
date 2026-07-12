#!/usr/bin/env python3.11
"""
Step 3 — Summarize + Classify: agent-driven article summarization and snippet extraction.

Modes:

  Default (fetch):
    Fetches full content for unsummarized articles, prints JSON to stdout.
    Agent reads the queue, writes summaries + topics + optional snippets.
    See docs/classifier.md for snippet selection criteria.

  --apply FILE:
    Reads agent-produced summaries from FILE and writes them back to articles.json.
    Format: [{id, summary, topics, code_snippet?, snippet_label?}, ...]

  --classify:
    Outputs summarized articles that have no code_snippet yet, with their
    full fetched content, so the agent can apply the classifier in a second pass.
    Prints JSON to stdout — pipe to classify-queue.json.

  --apply-snippets FILE:
    Reads agent-produced snippets from FILE and writes them back to articles.json.
    Format: [{id, code_snippet, snippet_label}, ...]

Usage:
  python3.11 pipeline/summarize.py > state/queue.json
  python3.11 pipeline/summarize.py --apply state/summaries.json
  python3.11 pipeline/summarize.py --classify > state/classify-queue.json
  python3.11 pipeline/summarize.py --apply-snippets state/snippets.json
"""

import json
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
ARTICLES_FILE = ROOT / "state" / "articles.json"

HTTP_HEADERS = {
    "User-Agent": "KotlinDigest/1.0 (+https://github.com/cicerohellmann/kotlin-digest)"
}


def fetch_content(url: str) -> str:
    """Fetch and extract main article text."""
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=HTTP_HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        return f"[fetch error: {exc}]"

    soup = BeautifulSoup(resp.text, "html.parser")

    container = (
        soup.find("article")
        or soup.find("main")
        or soup.select_one('[role="main"]')
        or soup.select_one(".post-content")
        or soup.select_one(".entry-content")
        or soup.select_one(".article-content")
        or soup.select_one(".post-body")
    )
    if container:
        text = container.get_text(separator=" ", strip=True)
        if len(text.split()) >= 80:
            return text[:6000]

    body = soup.find("body")
    if body:
        for tag in body.find_all(["nav", "footer", "aside", "script", "style", "header"]):
            tag.decompose()
        return body.get_text(separator=" ", strip=True)[:6000]

    return "[no content extracted]"


def write_atomic(path: Path, data: object) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(path)


def cmd_fetch() -> None:
    """Fetch content for unsummarized articles, print JSON queue to stdout."""
    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    pending = [a for a in articles if not a.get("summarized")]

    if not pending:
        print("[]")
        return

    print(f"Fetching content for {len(pending)} articles...", file=sys.stderr)

    queue = []
    for i, article in enumerate(pending):
        print(f"  [{i+1}/{len(pending)}] {article['title'][:70]}", file=sys.stderr, flush=True)
        content = fetch_content(article["url"])
        queue.append({
            "id": article["id"],
            "title": article["title"],
            "url": article["url"],
            "date": article["date"],
            "source_id": article["source_id"],
            "excerpt": article.get("excerpt", ""),
            "content": content,
        })

    print(json.dumps(queue, indent=2, ensure_ascii=False))
    print(f"\nDone. Pipe output to a file and pass to an agent for summarization.", file=sys.stderr)
    print(f"Then run: python3.11 pipeline/summarize.py --apply <summaries.json>", file=sys.stderr)


def cmd_apply(path: str) -> None:
    """Apply agent-produced summaries back to articles.json."""
    summaries_file = Path(path)
    if not summaries_file.exists():
        print(f"[!] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    summaries = json.loads(summaries_file.read_text(encoding="utf-8"))
    summary_map = {s["id"]: s for s in summaries}

    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))

    applied = 0
    for article in articles:
        if article["id"] not in summary_map:
            continue
        s = summary_map[article["id"]]
        article["summary"] = s.get("summary", "")
        article["topics"] = s.get("topics", [])
        if s.get("code_snippet"):
            article["code_snippet"] = s["code_snippet"]
            article["snippet_label"] = s.get("snippet_label", "")
        article["summarized"] = True
        applied += 1

    write_atomic(ARTICLES_FILE, articles)
    print(f"  Applied {applied} summaries to articles.json")


def cmd_classify() -> None:
    """Output summarized articles without snippets so agent can apply the classifier."""
    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    pending = [
        a for a in articles
        if a.get("summarized") and not a.get("code_snippet") and a.get("topics")
    ]

    if not pending:
        print("[]")
        print("All summarized articles already have snippets (or no topics).", file=sys.stderr)
        return

    print(f"Fetching content for {len(pending)} articles needing classification...", file=sys.stderr)

    queue = []
    for i, article in enumerate(pending):
        print(f"  [{i+1}/{len(pending)}] {article['title'][:70]}", file=sys.stderr, flush=True)
        content = fetch_content(article["url"])
        queue.append({
            "id": article["id"],
            "title": article["title"],
            "url": article["url"],
            "source_id": article["source_id"],
            "topics": article.get("topics", []),
            "summary": article.get("summary", ""),
            "content": content,
        })

    print(json.dumps(queue, indent=2, ensure_ascii=False))
    print(f"\nDone. See docs/classifier.md for snippet criteria.", file=sys.stderr)
    print(f"Then run: python3.11 pipeline/summarize.py --apply-snippets <snippets.json>", file=sys.stderr)


def cmd_apply_snippets(path: str) -> None:
    """Apply agent-produced snippets back to articles.json."""
    snippets_file = Path(path)
    if not snippets_file.exists():
        print(f"[!] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    snippets = json.loads(snippets_file.read_text(encoding="utf-8"))
    snippet_map = {s["id"]: s for s in snippets}

    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))

    applied = 0
    for article in articles:
        if article["id"] not in snippet_map:
            continue
        s = snippet_map[article["id"]]
        if s.get("code_snippet"):
            article["code_snippet"] = s["code_snippet"]
            article["snippet_label"] = s.get("snippet_label", "")
            applied += 1

    write_atomic(ARTICLES_FILE, articles)
    print(f"  Applied {applied} snippets to articles.json")


if __name__ == "__main__":
    if not ARTICLES_FILE.exists():
        print("[!] articles.json not found — run scout first", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) >= 3 and sys.argv[1] == "--apply":
        cmd_apply(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "--apply-snippets":
        cmd_apply_snippets(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "--classify":
        cmd_classify()
    else:
        cmd_fetch()
