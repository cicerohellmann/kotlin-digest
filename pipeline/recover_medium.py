#!/usr/bin/env python3.11
"""Recover Medium-family article bodies via a real cmux browser navigation.

Medium and the Medium-family hosts (proandroiddev.com, blog.devgenius.io,
levelup.gitconnected.com, *.medium.com) hard-block the HTTP fetcher at
Cloudflare (403). A sandboxed same-origin ``fetch()`` from inside a Medium page
*also* fails for many articles ("Failed to fetch") and returns only a ~180-word
"Member-only story" teaser for others.

The proven fix is a real browser **navigation**: a ``goto`` to the article URL
carries the Cloudflare clearance that a sandboxed ``fetch()`` lacks, so the
server-rendered full body comes back. Genuine member-only articles still return
a gated ~180-word teaser; those are flagged ``gated`` and MUST be dropped
downstream (see ``docs/content-rights.md`` rule 3).

The browser is driven through the **cmux** CLI over its unix socket.

Usage:
    python3.11 pipeline/recover_medium.py --edition 2026-W33 [--surface surface:NN] [--limit N]

Behaviour:
  * Selects in-window (edition Mon-Sun), not-yet-summarized, non-short,
    render:true, Medium-family articles from ``state/articles.json``.
  * Resumable: skips any id that already has ``state/recovered/<id>.json``.
  * Writes ``state/recovered/<id>.json`` = ``{id,url,words,gated,content}``
    (plus ``error`` on failure).

This is fetch-to-summarize, identical in intent to the HTTP fetcher -- not
republishing. The same ``content-rights.md`` rules apply downstream.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlparse, urlsplit, urlunsplit

# Repo root = parent of this file's directory (pipeline/).
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "pipeline"))
from _assemble.dates import edition_to_dates  # noqa: E402

SOCK = "/Users/cicerohellmann/Library/Application Support/cmux/cmux.sock"
OUT = os.path.join(REPO, "state", "recovered")
ARTICLES = os.path.join(REPO, "state", "articles.json")
SOURCES = os.path.join(REPO, "sources", "sources.yml")
WORKSPACE = "workspace:4"

# Medium-family hosts that Cloudflare-block the HTTP fetcher.
MEDIUM_HOSTS = (
    "medium.com",
    "proandroiddev.com",
    "blog.devgenius.io",
    "levelup.gitconnected.com",
)
MEDIUM_SOURCE_PREFIXES = ("medium", "proandroiddev")

# Extraction JS -- kept byte-identical to the validated prototype
# (scratchpad_recover.py) so recovered results match what was validated.
EVAL = ('(()=>{const el=document.querySelector("article")||document.body;'
        'const t=(el?el.textContent:"").replace(/\\s+/g," ").trim().slice(0,6000);'
        'return JSON.stringify({words:t.split(" ").length,'
        'gated:/member-only story|Sign in to read|Become a member/i.test(t.slice(0,400)),'
        'content:t});})()')

USABLE_MIN_WORDS = 60


def cmux(surface: str, *args, timeout: int = 40) -> subprocess.CompletedProcess:
    """Run a `cmux browser --surface <S> ...` command with CMUX_SOCK set."""
    env = {**os.environ, "CMUX_SOCK": SOCK}
    return subprocess.run(
        ["cmux", "browser", "--surface", surface, *args],
        env=env, capture_output=True, text=True, timeout=timeout,
    )


def cmux_open() -> str:
    """Open a fresh browser surface and return its handle (e.g. 'surface:81')."""
    env = {**os.environ, "CMUX_SOCK": SOCK}
    r = subprocess.run(
        ["cmux", "browser", "open", "about:blank", "--workspace", WORKSPACE],
        env=env, capture_output=True, text=True, timeout=40,
    )
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    m = re.search(r"surface:\d+", out)
    if not m:
        raise RuntimeError(f"could not parse surface handle from cmux open output:\n{out.strip()}")
    return m.group(0)


def cmux_close(surface: str) -> None:
    env = {**os.environ, "CMUX_SOCK": SOCK}
    try:
        subprocess.run(
            ["cmux", "close-surface", "--surface", surface],
            env=env, capture_output=True, text=True, timeout=20,
        )
    except Exception:
        pass


def load_render_false_ids() -> set:
    """Source ids with `render: false` in sources.yml (excluded from selection)."""
    try:
        import yaml
    except ImportError:
        return set()
    try:
        data = yaml.safe_load(open(SOURCES))
    except Exception:
        return set()
    return {s["id"] for s in (data or {}).get("sources", []) if s.get("render") is False}


def is_medium_family(article: dict) -> bool:
    host = urlparse(article.get("url", "")).netloc.lower()
    if host in MEDIUM_HOSTS or host.endswith(".medium.com"):
        return True
    sid = article.get("source_id", "") or ""
    return sid.startswith(MEDIUM_SOURCE_PREFIXES)


def in_window(article: dict, monday, sunday) -> bool:
    d = article.get("date")
    if not d:
        return False
    return monday.isoformat() <= d[:10] <= sunday.isoformat()


def clean_url(url: str) -> str:
    """Strip the query string (e.g. ?source=...) but keep path (trailing hex id)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def select_articles(edition: str) -> list:
    monday, sunday = edition_to_dates(edition)
    render_false = load_render_false_ids()
    articles = json.load(open(ARTICLES))
    out = []
    for a in articles:
        if a.get("summarized"):
            continue
        if a.get("is_short"):
            continue
        if not is_medium_family(a):
            continue
        if a.get("source_id") in render_false:
            continue
        if not in_window(a, monday, sunday):
            continue
        out.append(a)
    return out


def recover_one(surface: str, aid: str, url: str, sleep_s: float) -> dict:
    """Navigate + extract a single article. Returns the record dict."""
    cmux(surface, "goto", url, timeout=40)
    # Best-effort wait for load completion; swallow failures and fall back to
    # the proven sleep -> eval path (never let wait abort an article).
    try:
        cmux(surface, "wait", "--load-state", "complete", "--timeout", "20", timeout=25)
    except Exception:
        pass
    time.sleep(sleep_s)
    r = cmux(surface, "eval", EVAL, timeout=30)
    data = json.loads((r.stdout or "").strip())
    data["id"] = aid
    data["url"] = url
    return data


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="recover_medium.py",
        description="Recover Medium-family article bodies via a real cmux browser "
                    "navigation (carries Cloudflare clearance that fetch() lacks).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--edition", required=True,
                    help="ISO edition, e.g. 2026-W33. Selects that Mon-Sun window.")
    ap.add_argument("--surface", default=None,
                    help="Reuse an existing cmux surface (e.g. surface:81) and leave "
                         "it open. If omitted, a new surface is opened and closed.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Max number of articles actually attempted (already-recovered "
                         "ids are skipped without counting toward the limit).")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="Delay (seconds) between articles. Default 1.0.")
    ap.add_argument("--sleep", type=float, default=2.2,
                    help="Settle time (seconds) after navigation before extraction. "
                         "Default 2.2 (matches the validated prototype).")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)

    try:
        selected = select_articles(args.edition)
    except Exception as e:
        print(f"ERROR selecting articles: {e}", file=sys.stderr)
        return 2

    print(f"edition {args.edition}: {len(selected)} Medium-family pending articles selected",
          flush=True)
    if not selected:
        print("nothing to recover.", flush=True)
        return 0

    own_surface = args.surface is None
    surface = args.surface
    if own_surface:
        try:
            surface = cmux_open()
            print(f"opened surface {surface}", flush=True)
        except Exception as e:
            print(f"ERROR opening browser surface: {e}", file=sys.stderr)
            return 2

    ok = gated = err = skip = attempted = 0
    try:
        for a in selected:
            if args.limit is not None and attempted >= args.limit:
                break
            aid = a["id"]
            dest = os.path.join(OUT, f"{aid}.json")
            if os.path.exists(dest):
                skip += 1
                continue
            url = clean_url(a["url"])
            attempted += 1
            try:
                data = recover_one(surface, aid, url, args.sleep)
                json.dump(data, open(dest, "w"), ensure_ascii=False)
                if data.get("gated"):
                    gated += 1
                elif data.get("words", 0) >= USABLE_MIN_WORDS:
                    ok += 1
                else:
                    err += 1
            except Exception as e:
                json.dump({"id": aid, "url": url, "words": 0, "gated": False,
                           "content": "", "error": str(e)[:200]},
                          open(dest, "w"), ensure_ascii=False)
                err += 1
            if attempted % 10 == 0:
                print(f"[attempted {attempted}] usable={ok} gated={gated} err={err} skip={skip}",
                      flush=True)
            time.sleep(args.delay)
    finally:
        if own_surface:
            cmux_close(surface)
            print(f"closed surface {surface}", flush=True)

    print(f"DONE {args.edition}: attempted={attempted} usable={ok} "
          f"gated(dropped)={gated} errors={err} skipped(existing)={skip}", flush=True)
    print("  usable = words>=60 and not gated (recovered full body)", flush=True)
    print("  gated  = member-only teaser -> drop per content-rights rule 3", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
