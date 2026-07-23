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
SOURCES_OUT = ROOT / "site" / "sources.html"
MANIFEST_FILE = ROOT / "state" / "editions.json"
FEATURED_FILE = ROOT / "state" / "featured.json"


def resolve_featured(edition: str, feature_arg, week_articles: list) -> str:
    """Return the pinned cover article id for this edition.

    With --feature (an id or title substring), resolve against this edition's
    articles and persist the choice in state/featured.json. Without it, reuse a
    previously saved pin. Returns "" for the default score-based cover.
    """
    try:
        pins = json.loads(FEATURED_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        pins = {}

    if feature_arg:
        needle = feature_arg.strip().lower()
        match = next((a for a in week_articles if a["id"] == feature_arg), None)
        if not match:
            hits = [a for a in week_articles if needle in a.get("title", "").lower()]
            if len(hits) == 1:
                match = hits[0]
            elif len(hits) > 1:
                print(f"  [!] --feature '{feature_arg}' matched {len(hits)} articles; "
                      f"be more specific:")
                for a in hits:
                    print(f"        {a['id']}  {a.get('title','')[:70]}")
                return pins.get(edition, "")
        if not match:
            print(f"  [!] --feature '{feature_arg}' matched no article in {edition}; "
                  f"using default cover.")
            return pins.get(edition, "")
        pins[edition] = match["id"]
        FEATURED_FILE.write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")
        print(f"  Cover pinned → {match.get('title','')[:60]} ({match['id']})")
        return match["id"]

    return pins.get(edition, "")

sys.path.insert(0, str(ROOT))

from pipeline._assemble.dates import edition_to_dates
from pipeline._assemble.scores import lookup_scores_at
from pipeline._assemble.articles import filter_articles, score_articles, cluster_articles
from pipeline._assemble.render import (
    build_data_block,
    build_static_digest,
    build_ticker_html,
    inject_data,
    inject_static_digest,
    inject_ticker,
)
from pipeline._assemble.comics import select_comics, comics_needed, COMIC_EVERY
from pipeline.rollup import collapse, load_rollups, write_queue
from pipeline._assemble.archive import (
    write_edition_copy,
    upsert_manifest,
    render_archive,
    render_sources,
)


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.rename(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", required=True, help="e.g. 2026-W28")
    parser.add_argument("--feature", default=None,
                        help="pin the cover story: an article id or a title substring. "
                             "Saved per edition so later re-assembles keep it.")
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

    # Cover story: honour a pinned feature (--feature / state/featured.json),
    # else the default top-scoring article in the top chapter.
    placed = [a for ch in chapters for a in ch["articles"]]
    featured_id = resolve_featured(args.edition, args.feature, placed)

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
        featured_id=featured_id,
    )
    html = inject_data(template, data_block)
    html = inject_ticker(html, build_ticker_html(bible))
    html = inject_static_digest(
        html,
        build_static_digest(
            chapters=chapters,
            source_type_map=source_type_map,
            bible=bible,
            featured_id=featured_id,
            comics=comics,
            comic_every=COMIC_EVERY,
        ),
    )

    n_sources = len({a.get("source_id") for ch in chapters for a in ch["articles"] if a.get("source_id")})

    # Patch masthead edition label, title, date and counts (all static in the
    # template's placeholder W27 masthead).
    edition_display = args.edition.replace("-W", "·W")
    html = html.replace("2026·W27", edition_display)
    html = html.replace("Kotlin Digest — 2026·W27", f"Kotlin Digest — {edition_display}")
    html = html.replace("05 JULY 2026", start.strftime("%d %B %Y").upper())
    # Patched separately so the template can wrap "sources" in a link to sources.html.
    html = html.replace("27 articles", f"{total_arts} articles")
    html = html.replace("8 sources", f"{n_sources} sources")

    # SEO / social meta — real per-edition description + canonical so link previews
    # (WhatsApp, Slack, Twitter) show the right week instead of scraped body text.
    meta_desc = (
        f"Kotlin Digest {edition_display}: {total_arts} hand-picked Android, "
        f"Kotlin, KMP and Jetpack Compose stories from {n_sources} sources, "
        f"for the week of {start.strftime('%d %B %Y')}."
    )
    html = html.replace("__META_DESC__", meta_desc)
    html = html.replace("__CANONICAL__", "https://kotlindigest.com/")

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
    render_sources(sources_config.get("sources", []), SOURCES_OUT)
    print(f"  Archived → site/editions/{args.edition}.html · "
          f"{len(manifest)} edition(s) in archive")


if __name__ == "__main__":
    main()
