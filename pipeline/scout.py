#!/usr/bin/env python3.11
"""
Step 1 — Scout: fetch sources, detect new articles by date, update source health.

Inputs:  sources/sources.yml, state/source_health.json, state/articles.json
Outputs: state/articles.json (appended), state/source_health.json (updated)
"""

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

import feedparser
import httpx
import yaml
from bs4 import BeautifulSoup

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
SOURCES_FILE = ROOT / "sources" / "sources.yml"
STATE_DIR = ROOT / "state"
HEALTH_FILE = STATE_DIR / "source_health.json"
ARTICLES_FILE = STATE_DIR / "articles.json"

# ── Constants ─────────────────────────────────────────────────────────────────
ARTICLE_WINDOW_DAYS = 90
DEFAULT_LOOKBACK_DAYS = 7

KOTLIN_ANDROID_KEYWORDS = {
    "kotlin", "android", "jetpack", "compose", "coroutine", "coroutines",
    "flow", "flows", "kmp", "multiplatform", "gradle", "ktor", "hilt",
    "room", "retrofit", "okhttp", "dagger", "koin", "coil", "viewmodel",
    "navigation", "datastore", "workmanager", "lifecycle", "k2", "ksp",
    "ktx", "jetbrains", "agp",
}

# Sources whose content must pass a keyword filter before being stored
KEYWORD_FILTER_SOURCE_IDS = {"jetbrains-blog"}

HTTP_HEADERS = {
    "User-Agent": "KotlinDigest/1.0 (+https://github.com/cicerohellmann/kotlin-digest)"
}


# ── URL helpers ───────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Strip query params and trailing slash for stable URL-based dedup."""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path.rstrip("/"), "", "", ""))


def article_id(url: str) -> str:
    return hashlib.sha1(normalize_url(url).encode()).hexdigest()[:16]


# ── Date parsing ──────────────────────────────────────────────────────────────

def _parse_iso(s: str) -> Optional[datetime]:
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(s[:len(fmt)], fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_date_str(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    import email.utils
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    return _parse_iso(s.strip())


def feedparser_entry_date(entry) -> Optional[datetime]:
    """Best available date from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for attr in ("published", "updated", "dc_date"):
        val = getattr(entry, attr, None)
        if val:
            dt = parse_date_str(val)
            if dt:
                return dt
    return None


def extract_date_from_url(url: str) -> Optional[datetime]:
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def extract_date_from_html(soup: BeautifulSoup, url: str) -> tuple:
    """Return (date, date_uncertain) using the priority chain from docs/sources.md."""
    # 1. OpenGraph article:published_time
    og = soup.find("meta", property="article:published_time")
    if og and og.get("content"):
        dt = parse_date_str(og["content"])
        if dt:
            return dt, False

    # 2. JSON-LD datePublished
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                dp = data.get("datePublished")
                if dp:
                    dt = parse_date_str(dp)
                    if dt:
                        return dt, False
        except Exception:
            pass

    # 3. <time datetime="...">
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        dt = parse_date_str(time_tag["datetime"])
        if dt:
            return dt, False

    # 4. URL date pattern
    dt = extract_date_from_url(url)
    if dt:
        return dt, False

    return None, True


# ── Keyword filtering ─────────────────────────────────────────────────────────

def is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in KOTLIN_ANDROID_KEYWORDS)


def strip_html(raw: str) -> str:
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)


# ── Per-source scouting ───────────────────────────────────────────────────────

def scout_via_rss(source: dict, last_date: datetime, existing_ids: set) -> tuple:
    """Returns (new_articles, feed_had_entries) — distinguishes parse failure from no-recent-articles."""
    feed_url = source.get("rss") or source.get("atom")
    if not feed_url:
        return [], False

    try:
        feed = feedparser.parse(feed_url)
    except Exception as exc:
        print(f"  [!] feedparser error: {exc}", file=sys.stderr)
        return [], False

    if not feed.entries:
        return [], False

    sid = source["id"]
    needs_filter = sid in KEYWORD_FILTER_SOURCE_IDS
    is_discussion = source.get("type") == "discussion"
    new_articles: list[dict] = []

    for entry in feed.entries:
        url = getattr(entry, "link", None)
        if not url:
            continue

        uid = article_id(url)
        if uid in existing_ids:
            continue

        date = feedparser_entry_date(entry)
        date_uncertain = date is None

        # Skip if clearly older than last known article (skip when uncertain — ingest those)
        if not date_uncertain and date and date <= last_date:
            continue

        title = getattr(entry, "title", "").strip()
        raw_excerpt = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        excerpt = strip_html(raw_excerpt)[:500]

        # Apply source-level keyword filter where required
        if needs_filter or is_discussion:
            if not is_relevant(title + " " + excerpt):
                continue

        new_articles.append({
            "id": uid,
            "title": title,
            "url": url,
            "date": date.strftime("%Y-%m-%d") if date else None,
            "source_id": sid,
            "excerpt": excerpt,
            "date_uncertain": date_uncertain,
            "summarized": False,
        })

    return new_articles, True


def scout_via_scrape(source: dict, last_date: datetime, existing_ids: set) -> list[dict]:
    """Fallback scraper: find article links via <article>/<h2>/<h3> tags."""
    url = source.get("url")
    if not url:
        return []

    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers=HTTP_HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        print(f"  [!] Scrape error: {exc}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    parsed_base = urlparse(url)
    new_articles: list[dict] = []

    for tag in soup.find_all(["article", "h2", "h3"], limit=40):
        link = tag.find("a", href=True)
        if not link:
            continue

        href = link["href"]
        if href.startswith("/"):
            href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        elif not href.startswith("http"):
            continue

        title = link.get_text(strip=True)
        if not title:
            continue

        uid = article_id(href)
        if uid in existing_ids:
            continue

        date, date_uncertain = extract_date_from_html(tag, href)

        if not date_uncertain and date and date <= last_date:
            continue

        new_articles.append({
            "id": uid,
            "title": title,
            "url": href,
            "date": date.strftime("%Y-%m-%d") if date else None,
            "source_id": source["id"],
            "excerpt": "",
            "date_uncertain": date_uncertain,
            "summarized": False,
        })

    return new_articles


def _title_from_soup(soup: BeautifulSoup, url: str) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content", "").strip():
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    # Fallback: readable path from URL
    path = urlparse(url).path.rstrip("/").split("/")[-1]
    return path.replace("-", " ").replace("_", " ").strip() or url


def fetch_title(url: str) -> str:
    """Fetch page title for a URL. Returns URL path as fallback."""
    try:
        with httpx.Client(timeout=8, follow_redirects=True, headers=HTTP_HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
        return _title_from_soup(BeautifulSoup(resp.text, "html.parser"), url)
    except Exception:
        path = urlparse(url).path.rstrip("/").split("/")[-1]
        return path.replace("-", " ").replace("_", " ").strip() or url


def fetch_link_meta(url: str) -> tuple:
    """One fetch → (title, date, date_uncertain, fetch_ok) for a shared link.

    A link shared in Slack is a candidate magazine article and must be dated by
    its OWN page, never by when it was mentioned. Reuses the same date priority
    chain as scraped sources (`extract_date_from_html`). If the page has no
    detectable publish date — as homepages, videos, raw source files, and paper
    abstracts do not — `date` is None and `date_uncertain` is True, so it never
    renders (filter_articles requires an in-window date).

    `fetch_ok` distinguishes a *definitive* read (page loaded; caller may trust
    a None date as "genuinely undated") from a *transient* failure (timeout /
    connection reset / bot-block). On a transient failure the caller must NOT
    persist a None date — the link should be left for a later crawl to retry,
    or a one-off blip would permanently drop a legit article. Uses a browser UA
    because these are arbitrary third-party article hosts (Medium-family, etc.)
    that serve differently to a bot UA.
    """
    try:
        with httpx.Client(timeout=8, follow_redirects=True, headers=SLACK_BROWSER_HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        title = _title_from_soup(soup, url)
        date, date_uncertain = extract_date_from_html(soup, url)
        return title, date, date_uncertain, True
    except Exception:
        path = urlparse(url).path.rstrip("/").split("/")[-1]
        fallback = path.replace("-", " ").replace("_", " ").strip() or url
        return fallback, None, True, False


SLACK_SKIP_DOMAINS = {
    "slack.com", "slack-chats.kotlinlang.org", "linen.dev",
    "twitter.com", "x.com", "linkedin.com",
    "imgur.com", "giphy.com", "tenor.com",
    "google.com", "apple.com",
}

SLACK_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def scout_slack_channel(source: dict, last_date: datetime, existing_ids: set) -> list:
    """Scrape Kotlin Slack public archive channel for shared links."""
    channel = source.get("channel", source["id"].replace("slack-", ""))
    base_url = f"https://slack-chats.kotlinlang.org/c/{channel}"

    articles: list = []
    cursor: Optional[str] = None
    pages_checked = 0
    MAX_PAGES = 5

    while pages_checked < MAX_PAGES:
        url = base_url if not cursor else f"{base_url}?cursor={cursor}"
        try:
            resp = httpx.get(url, headers=SLACK_BROWSER_HEADERS, timeout=15, follow_redirects=True)
            resp.raise_for_status()
        except Exception as exc:
            print(f"  [!] Slack fetch error: {exc}", file=sys.stderr)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script:
            print("  [!] No __NEXT_DATA__ — page structure changed?", file=sys.stderr)
            break

        page_props = json.loads(script.string).get("props", {}).get("pageProps", {})
        threads = page_props.get("threads", [])
        if not threads:
            break

        oldest_dt = datetime.fromtimestamp(
            min(int(t["sentAt"]) for t in threads) / 1000, tz=timezone.utc
        )

        for thread in threads:
            sent_dt = datetime.fromtimestamp(int(thread["sentAt"]) / 1000, tz=timezone.utc)
            if sent_dt < last_date:
                continue

            for message in thread.get("messages", []):
                body = message.get("body", "")
                links = re.findall(r"https?://[^\s<>\"\')\]|]+", body)

                for link in links:
                    link = link.rstrip(".,;:!?)").replace("&amp;", "&")
                    domain = urlparse(link).netloc.lower().lstrip("www.")
                    if any(skip in domain for skip in SLACK_SKIP_DOMAINS):
                        continue

                    uid = article_id(link)
                    if uid in existing_ids:
                        continue

                    # Date the article by its OWN page, never by the Slack post
                    # time. No real date → date=None → never renders.
                    title, date, date_uncertain, fetch_ok = fetch_link_meta(link)
                    if not fetch_ok:
                        # Transient fetch failure — skip without recording so a
                        # later crawl retries it (uid stays out of existing_ids).
                        # Never persist a null date on a blip.
                        continue
                    articles.append({
                        "id": uid,
                        "title": title,
                        "url": link,
                        "date": date.strftime("%Y-%m-%d") if date else None,
                        "source_id": source["id"],
                        "excerpt": body[:400].strip(),
                        "date_uncertain": date_uncertain,
                        "summarized": False,
                    })
                    existing_ids.add(uid)

        if oldest_dt < last_date:
            break

        pages_checked += 1
        cursor = page_props.get("nextCursor", {}).get("prev")
        if not cursor:
            break

        time.sleep(1)

    return articles


def scout_source(
    source: dict,
    last_date: datetime,
    existing_ids: set,
) -> tuple:
    """Scout one source. Returns (new_articles, most_recent_date_or_None)."""
    source_type = source.get("type", "blog")

    if source_type == "conference":
        print(f"  [~] conference source — stub in v1, skipping")
        return [], None

    if source_type == "slack-mirror":
        new_articles = scout_slack_channel(source, last_date, existing_ids)
        most_recent: Optional[datetime] = None
        for a in new_articles:
            if a["date"]:
                dt = datetime.strptime(a["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if most_recent is None or dt > most_recent:
                    most_recent = dt
        return new_articles, most_recent

    new_articles: list[dict] = []
    feed_succeeded = False

    # RSS/Atom first
    if source.get("rss") or source.get("atom"):
        new_articles, feed_succeeded = scout_via_rss(source, last_date, existing_ids)

    # Scrape fallback: only when RSS/Atom failed entirely (not just no recent articles)
    if not feed_succeeded and source.get("url") and source_type != "discussion":
        print("  [~] no RSS/Atom feed — trying scrape")
        new_articles = scout_via_scrape(source, last_date, existing_ids)

    most_recent: Optional[datetime] = None
    for a in new_articles:
        if not a["date_uncertain"] and a["date"]:
            dt = datetime.strptime(a["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if most_recent is None or dt > most_recent:
                most_recent = dt

    return new_articles, most_recent


# ── Health computation ────────────────────────────────────────────────────────

def compute_health(
    source: dict,
    last_article_date: Optional[datetime],
    prev_health: dict,
    had_new_articles: bool,
) -> dict:
    now = datetime.now(tz=timezone.utc)
    cadence = source.get("cadence_days", 30)

    if last_article_date:
        days_since = (now - last_article_date).days
        if days_since <= cadence * 1.5:
            health_state = "active"
        elif days_since <= cadence * 3:
            health_state = "slowing"
        elif days_since <= cadence * 6:
            health_state = "stale"
        else:
            health_state = "dead"
    else:
        days_since = None
        health_state = "unknown"

    consecutive_empty = prev_health.get("consecutive_empty_cycles", 0)
    if had_new_articles:
        consecutive_empty = 0
    else:
        consecutive_empty += 1

    return {
        "last_article_date": last_article_date.strftime("%Y-%m-%d") if last_article_date else None,
        "last_checked": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cadence_days": cadence,
        "days_since_last": days_since,
        "health": health_state,
        "consecutive_empty_cycles": consecutive_empty,
    }


# ── Atomic write ──────────────────────────────────────────────────────────────

def write_atomic(path: Path, data: object) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    STATE_DIR.mkdir(exist_ok=True)

    with open(SOURCES_FILE, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    sources: list[dict] = config["sources"]

    health: dict = json.loads(HEALTH_FILE.read_text(encoding="utf-8")) if HEALTH_FILE.exists() else {}
    articles: list[dict] = json.loads(ARTICLES_FILE.read_text(encoding="utf-8")) if ARTICLES_FILE.exists() else []
    existing_ids: set[str] = {a["id"] for a in articles}

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=ARTICLE_WINDOW_DAYS)

    total_new = 0
    slowing_count = 0
    dead_count = 0

    for source in sources:
        sid = source["id"]
        prev = health.get(sid, {})

        last_str = prev.get("last_article_date")
        last_date = (
            datetime.strptime(last_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if last_str
            else datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        )

        print(f"[{sid}]", flush=True)

        new_articles, most_recent = scout_source(source, last_date, existing_ids)

        if new_articles:
            articles.extend(new_articles)
            existing_ids.update(a["id"] for a in new_articles)
            total_new += len(new_articles)
            print(f"  +{len(new_articles)} articles")

        effective_last = most_recent or (last_date if last_str else None)
        health[sid] = compute_health(source, effective_last, prev, had_new_articles=bool(new_articles))

        h = health[sid]["health"]
        if h == "slowing":
            slowing_count += 1
        elif h == "dead":
            dead_count += 1

    # Prune 90-day rolling window
    before = len(articles)
    articles = [
        a for a in articles
        if not a.get("date") or datetime.strptime(a["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc) >= cutoff
    ]
    pruned = before - len(articles)

    write_atomic(HEALTH_FILE, health)
    write_atomic(ARTICLES_FILE, articles)

    print(f"\n{'─' * 50}")
    print(f"  {total_new} new articles from {len(sources)} sources")
    print(f"  {slowing_count} slowing  {dead_count} dead  {pruned} pruned")

    if dead_count:
        dead_ids = [sid for sid, h in health.items() if h.get("health") == "dead"]
        print(f"  Dead: {', '.join(dead_ids)}")


if __name__ == "__main__":
    main()
