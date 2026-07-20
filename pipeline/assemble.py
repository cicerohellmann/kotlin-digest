#!/usr/bin/env python3.11
"""
Step 4 — Assemble: cluster articles into chapters, render site/index.html.

Usage:
  python3.11 pipeline/assemble.py --edition 2026-W28
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
ARTICLES_FILE = ROOT / "state" / "articles.json"
BIBLE_FILE = ROOT / "state" / "bible.json"
SOURCES_FILE = ROOT / "sources" / "sources.yml"
TOPICS_FILE = ROOT / "topics" / "topics.yml"
TEMPLATE_FILE = ROOT / "site" / "template.html"
OUTPUT_FILE = ROOT / "site" / "index.html"
EDITIONS_DIR = ROOT / "site" / "editions"
ARCHIVE_FILE = ROOT / "site" / "archive.html"
MANIFEST_FILE = ROOT / "state" / "editions.json"

sys.path.insert(0, str(ROOT))

from pipeline._assemble.dates import edition_to_dates
from pipeline._assemble.scores import lookup_scores_at
from pipeline._assemble.articles import filter_articles, score_articles, cluster_articles
from pipeline._assemble.render import build_data_block, inject_data
from pipeline._assemble.comics import select_comics, comics_needed, COMIC_EVERY
from pipeline.rollup import collapse, load_rollups, write_queue
from pipeline._assemble.archive import (
    write_edition_copy,
    upsert_manifest,
    render_archive,
)


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.rename(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", required=True, help="e.g. 2026-W28")
    args = parser.parse_args()

    start, end = edition_to_dates(args.edition)
    print(f"  Edition {args.edition}: {start} → {end}")

    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    bible = json.loads(BIBLE_FILE.read_text(encoding="utf-8"))
    topics_config = yaml.safe_load(TOPICS_FILE.read_text(encoding="utf-8"))
    sources_config = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8"))
    template = TEMPLATE_FILE.read_text(encoding="utf-8")

    clusters = topics_config.get("clusters", [])
    source_type_map = {s["id"]: s.get("type", "blog") for s in sources_config.get("sources", [])}
    # Sources marked `render: false` (e.g. Reddit) feed the topic bible but are
    # never rendered as articles — the site can't reliably read/summarize them.
    no_render_sources = {
        s["id"] for s in sources_config.get("sources", [])
        if not s.get("render", True)
    }

    scores = lookup_scores_at(bible, end)

    week_articles = filter_articles(articles, start, end, no_render_sources)

    # Collapse high-frequency changelog sources to their single newest release,
    # folding the rest into a rollup on the survivor card.
    before = len(week_articles)
    week_articles, rollups = collapse(week_articles, source_type_map)
    if before != len(week_articles):
        print(f"  collapsed {before - len(week_articles)} older releases "
              f"across {len(rollups)} changelog source(s)")

    # Attach synthesized rollup paragraphs from cache; queue any that are missing.
    cache = load_rollups()
    summary_by_rid = {}
    missing = []
    for r in rollups:
        cached = cache.get(r["rollup_id"])
        if cached and cached.get("summary"):
            summary_by_rid[r["rollup_id"]] = cached["summary"]
        else:
            missing.append(r)
    for a in week_articles:
        rid = a.get("rollup_id")
        if rid in summary_by_rid:
            a["rollup_summary"] = summary_by_rid[rid]
    if missing:
        write_queue(missing)
        print(f"  {len(missing)} rollup(s) need synthesis → state/rollup-queue.json")
        print("    agent: write [{rollup_id, summary}], then "
              "`python3.11 pipeline/rollup.py --apply <file>`, then re-run assemble")

    week_articles = score_articles(week_articles, scores)
    print(f"  {len(week_articles)} articles in window")

    chapters = cluster_articles(week_articles, clusters)
    total_arts = sum(len(ch["articles"]) for ch in chapters)
    print(f"  {len(chapters)} chapters, {total_arts} placed articles")

    # Comic interludes: one up top + one per COMIC_EVERY cards, no repeats.
    needed = comics_needed([len(ch["articles"]) for ch in chapters])
    comics = select_comics(args.edition, needed)
    print(f"  {len(comics)}/{needed} comic interludes "
          f"({'pool exhausted' if len(comics) < needed else 'from pool'})")

    data_block = build_data_block(
        edition=args.edition,
        start=start,
        end=end,
        chapters=chapters,
        bible=bible,
        source_type_map=source_type_map,
        clusters=clusters,
        comics=comics,
        comic_every=COMIC_EVERY,
    )
    html = inject_data(template, data_block)

    n_sources = len({a.get("source_id") for ch in chapters for a in ch["articles"] if a.get("source_id")})

    # Patch masthead edition label, title, date and counts (all static in the
    # template's placeholder W27 masthead).
    edition_display = args.edition.replace("-W", "·W")
    html = html.replace("2026·W27", edition_display)
    html = html.replace("Kotlin Digest — 2026·W27", f"Kotlin Digest — {edition_display}")
    html = html.replace("05 JULY 2026", start.strftime("%d %B %Y").upper())
    html = html.replace("27 articles · 8 sources", f"{total_arts} articles · {n_sources} sources")

    write_atomic(OUTPUT_FILE, html)
    print(f"  Written → site/index.html")

    # Archive: keep a permanent copy of this edition, record it in the manifest,
    # and regenerate the archive list. Publishing a new edition no longer
    # destroys the previous one.
    write_edition_copy(html, args.edition, EDITIONS_DIR)
    manifest = upsert_manifest(MANIFEST_FILE, {
        "edition": args.edition,
        "start": str(start),
        "end": str(end),
        "articles": total_arts,
        "sources": n_sources,
    })
    render_archive(manifest, ARCHIVE_FILE)
    print(f"  Archived → site/editions/{args.edition}.html · "
          f"{len(manifest)} edition(s) in archive")


if __name__ == "__main__":
    main()
