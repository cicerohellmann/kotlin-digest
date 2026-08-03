#!/usr/bin/env python3.11
"""
Audit YouTube/video candidates for an edition.

This is a read-only diagnostic for tuning video ingestion and placement:

  python3.11 pipeline/audit_youtube.py --edition 2026-W29
  python3.11 pipeline/audit_youtube.py --edition 2026-W29 --all
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pipeline._assemble.articles import cluster_articles, filter_articles, score_articles  # noqa: E402
from pipeline._assemble.videos import (  # noqa: E402
    apply_video_render_filters,
    video_kotlin_relevance,
    video_min_score,
)
from pipeline._assemble.dates import edition_to_dates  # noqa: E402
from pipeline._assemble.scores import lookup_scores_at  # noqa: E402
from pipeline.scout import DEFAULT_LOOKBACK_DAYS, article_id, scout_via_rss  # noqa: E402

ARTICLES_FILE = ROOT / "state" / "articles.json"
BIBLE_FILE = ROOT / "state" / "bible.json"
SOURCES_FILE = ROOT / "sources" / "sources.yml"
TOPICS_FILE = ROOT / "topics" / "topics.yml"

VIDEO_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def is_video_url(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()
    return host in VIDEO_HOSTS


def source_maps(sources_config: dict) -> tuple[dict, set]:
    sources = sources_config.get("sources", [])
    source_type_map = {s["id"]: s.get("type", "blog") for s in sources}
    no_render_sources = {s["id"] for s in sources if not s.get("render", True)}
    return source_type_map, no_render_sources


def drop_reasons(article: dict, start_s: str, end_s: str, no_render_sources: set) -> list[str]:
    reasons = []
    date = article.get("date")
    if not date:
        reasons.append("no publish date")
    elif not (start_s <= date <= end_s):
        reasons.append(f"outside edition window ({date})")
    if article.get("source_id") in no_render_sources:
        reasons.append("source render:false")
    for flag, label in (
        ("dead", "dead"),
        ("low_quality", "low quality"),
        ("unfetchable", "unfetchable"),
    ):
        if article.get(flag):
            reason = article.get(f"{flag}_reason")
            reasons.append(f"{label}: {reason}" if reason else label)
    if not article.get("summarized"):
        reasons.append("not summarized")
    if not article.get("topics"):
        reasons.append("no topics")
    return reasons


def placement_lookup(chapters: list[dict]) -> dict:
    placed = {}
    for chapter in chapters:
        for rank, article in enumerate(chapter["articles"], start=1):
            placed[article["id"]] = (chapter["label"], rank, article["placement_score"])
    return placed


def print_live_candidates(sources_config: dict, articles: list[dict], days: int) -> None:
    existing_ids = {a["id"] for a in articles}
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    video_sources = [s for s in sources_config.get("sources", []) if s.get("type") == "video"]

    print(f"Live YouTube scout preview: {len(video_sources)} video source(s), since {since.date()}\n")
    for source in video_sources:
        candidates, feed_ok = scout_via_rss(source, since, set(existing_ids))
        relevance = source.get("kotlin_relevance", "unset")
        video_cfg = source.get("video") or {}
        min_score = video_min_score(source)
        max_per_edition = video_cfg.get("max_per_edition")
        cap_label = f", max_per_edition={max_per_edition}" if max_per_edition is not None else ""
        print(f"[{source['id']}] {source['name']}  kotlin_relevance={relevance}, min={min_score}{cap_label}")
        if not feed_ok:
            print("  feed unavailable or empty\n")
            continue
        if not candidates:
            print("  no new videos\n")
            continue
        scored_candidates = []
        for candidate in candidates:
            score, reason = video_kotlin_relevance(candidate, source)
            scored_candidates.append((candidate, score, reason))
        by_week = {}
        for item in scored_candidates:
            candidate = item[0]
            if candidate.get("date"):
                iso = date.fromisoformat(candidate["date"]).isocalendar()
                week_key = f"{iso.year}-W{iso.week:02d}"
            else:
                week_key = "undated"
            by_week.setdefault(week_key, []).append(item)
        kept_ids = set()
        for week_items in by_week.values():
            eligible = [item for item in week_items if item[1] >= min_score]
            ranked = sorted(
                eligible,
                key=lambda item: (
                    item[1],
                    item[0].get("date", ""),
                    item[0].get("title", ""),
                ),
                reverse=True,
            )
            kept = ranked if max_per_edition is None else ranked[:int(max_per_edition)]
            kept_ids.update(item[0]["id"] for item in kept)
        for candidate, score, reason in scored_candidates:
            duplicate = article_id(candidate["url"]) in existing_ids
            status = "existing" if duplicate else "new"
            if score < min_score:
                verdict = "drop"
            elif candidate["id"] not in kept_ids:
                verdict = "cap"
            else:
                verdict = "keep"
            print(f"  - {candidate.get('date') or 'none'}  {status}  {verdict} {score}/{min_score}  {candidate['title']}")
            print(f"    {candidate['url']}")
            print(f"    {reason}")
            excerpt = (candidate.get("excerpt") or "").replace("\n", " ").strip()
            if excerpt:
                print(f"    {excerpt[:180]}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", required=True, help="e.g. 2026-W29")
    parser.add_argument("--all", action="store_true", help="include videos outside this edition's date window")
    parser.add_argument("--live", action="store_true", help="also fetch video RSS feeds and preview new candidates")
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help="lookback window for --live candidates")
    args = parser.parse_args()

    start, end = edition_to_dates(args.edition)
    start_s, end_s = start.isoformat(), end.isoformat()

    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    bible = json.loads(BIBLE_FILE.read_text(encoding="utf-8"))
    sources_config = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8"))
    topics_config = yaml.safe_load(TOPICS_FILE.read_text(encoding="utf-8"))

    source_type_map, no_render_sources = source_maps(sources_config)

    if args.live:
        print_live_candidates(sources_config, articles, args.days)
        print("State audit\n")

    scores = lookup_scores_at(bible, end)
    week_articles = filter_articles(articles, start, end, no_render_sources)
    scored = score_articles(week_articles, scores)
    scored, dropped_videos = apply_video_render_filters(scored, sources_config)
    chapters = cluster_articles(scored, topics_config.get("clusters", []))
    placed = placement_lookup(chapters)

    videos = [a for a in articles if is_video_url(a.get("url", ""))]
    if not args.all:
        videos = [
            a for a in videos
            if a["id"] in placed or not a.get("date") or start_s <= a.get("date", "") <= end_s
        ]

    eligible = sum(1 for a in videos if a["id"] in placed)
    print(f"Edition {args.edition}: {start_s} to {end_s}")
    print(f"YouTube/video URLs: {len(videos)} shown, {eligible} placed\n")
    if dropped_videos:
        print("Dropped by video relevance filter:")
        for article, reason in dropped_videos:
            print(f"  - {article.get('title', '')} ({reason})")
        print()

    for article in sorted(videos, key=lambda a: (a.get("date") or "0000-00-00", a.get("title", ""))):
        source_id = article.get("source_id", "")
        source_type = source_type_map.get(source_id, "unknown")
        title = article.get("title", "").strip() or "(untitled)"
        print(f"- {title}")
        print(f"  url: {article.get('url', '')}")
        print(f"  source: {source_id} ({source_type})  date: {article.get('date') or 'none'}")
        if article["id"] in placed:
            chapter, rank, score = placed[article["id"]]
            print(f"  status: placed in {chapter}, rank {rank}, score {score:.1f}")
        else:
            print(f"  status: dropped ({'; '.join(drop_reasons(article, start_s, end_s, no_render_sources))})")
        print(f"  topics: {', '.join(article.get('topics') or []) or 'none'}")
        summary = (article.get("summary") or article.get("excerpt") or "").replace("\n", " ").strip()
        if summary:
            print(f"  note: {summary[:180]}")
        print()


if __name__ == "__main__":
    main()
