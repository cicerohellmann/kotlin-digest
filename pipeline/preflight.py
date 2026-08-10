#!/usr/bin/env python3.11
"""Publish preflight gate for a Kotlin Digest edition.

Runs a series of mechanical checks against the committed state so a thin,
corrupt, or misconfigured edition can never be published without a human
having to eyeball it. HARD checks block publish (non-zero exit); WARN checks
print a heads-up but never change the exit code.

    python3.11 pipeline/preflight.py --edition 2026-W32 [--min-articles N]

Exit code 0 only when every HARD check passes.

This tool is READ-ONLY: it loads state/articles.json, state/featured.json,
state/comics_used.json and comics/comics.yml directly and computes in memory.
It never calls the stateful assemble helpers (select_comics, resolve_featured),
so running it consumes no comics and re-pins nothing.

The checks are structured as small pure functions returning ``(ok, message)``
so they can be unit-tested with in-memory fixtures (see tests/test_preflight.py).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pipeline._assemble.dates import edition_to_dates

ARTICLES_FILE = ROOT / "state" / "articles.json"
FEATURED_FILE = ROOT / "state" / "featured.json"
COMICS_USED_FILE = ROOT / "state" / "comics_used.json"
COMICS_FILE = ROOT / "comics" / "comics.yml"

DEFAULT_MIN_ARTICLES = 35

# Report symbols.
OK_MARK = "✓"    # ✓
FAIL_MARK = "✗"  # ✗
WARN_MARK = "⚠"  # ⚠


# ── placeable computation ──────────────────────────────────────────────────────

def _in_window(article: dict, start_s: str, end_s: str) -> bool:
    d = article.get("date")
    return bool(d) and start_s <= d <= end_s


def _is_placeable(article: dict) -> bool:
    """An article that will actually render: it has both a summary and topics
    and is not flagged out of the magazine.

    The core definition (task contract) is: non-empty ``summary`` AND non-empty
    ``topics``. We also honour the same render-exclusion flags assemble.py uses
    (dead / low_quality / unfetchable / is_short) so the density count mirrors
    what is really placed. On the live W32 state this refinement changes nothing
    (73 either way).
    """
    if not article.get("summary"):
        return False
    if not article.get("topics"):
        return False
    if article.get("dead") or article.get("low_quality"):
        return False
    if article.get("unfetchable") or article.get("is_short"):
        return False
    return True


def placeable_articles(articles: list, start, end) -> list:
    """In-window, render-ready ('placeable') articles for the edition."""
    start_s = start.isoformat() if hasattr(start, "isoformat") else start
    end_s = end.isoformat() if hasattr(end, "isoformat") else end
    return [
        a for a in articles
        if _in_window(a, start_s, end_s) and _is_placeable(a)
    ]


# ── featured.json helpers ──────────────────────────────────────────────────────

def normalize_featured_entry(raw) -> dict:
    """Normalize an edition's featured pin to {'cover': str, 'also': [str]}.

    Backward-compatible with the legacy bare-string (cover-only) form and with
    a missing entry (returns empty cover / no also-pins).
    """
    if isinstance(raw, str):
        return {"cover": raw, "also": []}
    if isinstance(raw, dict):
        return {"cover": raw.get("cover", ""), "also": list(raw.get("also", []))}
    return {"cover": "", "also": []}


# ── checks (pure; return (ok, message)) ────────────────────────────────────────

def check_density(placeable: list, min_articles: int):
    """HARD — the edition must have at least ``min_articles`` placeable cards."""
    n = len(placeable)
    if n >= min_articles:
        return True, f"Article density: {n} placeable (>= {min_articles})"
    return False, (
        f"Article density: only {n} placeable article(s) "
        f"(need >= {min_articles}) — edition is too thin to publish"
    )


def check_unique_ids(articles: list):
    """HARD — no duplicate article ids in state (catches merge corruption)."""
    counts = Counter(a.get("id") for a in articles)
    dups = {aid: c for aid, c in counts.items() if aid is not None and c > 1}
    if not dups:
        return True, f"Unique ids: all {len(articles)} article ids are unique"
    detail = ", ".join(f"{aid} (x{c})" for aid, c in sorted(dups.items()))
    return False, (
        f"Unique ids: {len(dups)} duplicate id(s) in state/articles.json "
        f"— corrupt state: {detail}"
    )


def check_urls(placeable: list):
    """HARD — every placeable article has a real outbound url (not empty/'#')."""
    bad = [a.get("id") for a in placeable
           if not (a.get("url") or "").strip() or a.get("url").strip() == "#"]
    if not bad:
        return True, f"Outbound urls: all {len(placeable)} placeable articles have a real url"
    return False, (
        f"Outbound urls: {len(bad)} placeable article(s) have an empty or '#' url: "
        + ", ".join(str(x) for x in bad)
    )


def check_featured_pins(featured_entry: dict, placeable: list):
    """WARN — cover + each 'also' pin must resolve to an in-window placeable id.

    An empty entry (no pins for this edition) is fine. Stale / out-of-window
    pins (e.g. a July article surfaced as an August 'also inside') are reported
    but do not block publish.
    """
    entry = normalize_featured_entry(featured_entry)
    cover = (entry.get("cover") or "").strip()
    also = [x for x in entry.get("also", []) if (x or "").strip()]

    if not cover and not also:
        return True, "Featured pins: no pins configured for this edition"

    valid = {a.get("id") for a in placeable}
    stale = []
    if cover and cover not in valid:
        stale.append(f"cover:{cover}")
    for x in also:
        if x not in valid:
            stale.append(f"also:{x}")

    if not stale:
        n = (1 if cover else 0) + len(also)
        return True, f"Featured pins: all {n} pin(s) resolve to in-window placeable articles"
    return False, (
        f"Featured pins: {len(stale)} pin(s) are stale / out-of-window / "
        f"un-summarized: " + ", ".join(stale)
    )


def check_comics_pool(pool: list, used: dict, edition: str):
    """WARN — the comic pool can likely still supply this edition's interludes.

    Heuristic (the exact bug that shipped 0 comics): if this edition has not yet
    recorded any comics and every comic in the pool has already been consumed by
    other editions, the edition will get zero interludes. Re-assembling an
    edition that already has recorded comics reuses them, so that case is fine.
    """
    pool_ids = [c.get("id") for c in pool if c.get("id")]
    if not pool_ids:
        return False, "Comics pool: comics/comics.yml has no comics — 0 interludes"

    used_by_others = {
        cid for ed, ids in (used or {}).items() if ed != edition for cid in ids
    }
    already_recorded = bool((used or {}).get(edition))
    available_for_new = [cid for cid in pool_ids if cid not in used_by_others]

    if already_recorded:
        return True, (
            f"Comics pool: edition already has {len(used[edition])} recorded "
            f"comic(s) (reused on re-assemble)"
        )
    if not available_for_new:
        return False, (
            f"Comics pool: exhausted — all {len(pool_ids)} comic(s) used by other "
            f"editions; this edition will get 0 interludes. Add strips to comics/comics.yml"
        )
    return True, (
        f"Comics pool: {len(available_for_new)} of {len(pool_ids)} comic(s) still "
        f"available for this edition"
    )


# ── loaders (main only; keep checks path-free) ─────────────────────────────────

def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _load_comics(path: Path) -> list:
    if not path.exists():
        return []
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("comics", []) or []


# ── CLI ────────────────────────────────────────────────────────────────────────

def _print(mark: str, label: str, msg: str):
    print(f"  {mark} [{label}] {msg}")


def run(edition: str, min_articles: int) -> int:
    start, end = edition_to_dates(edition)
    print(f"Preflight — edition {edition}  ({start.isoformat()} .. {end.isoformat()})")
    print()

    hard_ok = True

    # HARD 3 (schema-ish): articles.json must parse. A parse failure is fatal.
    try:
        articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
        if not isinstance(articles, list):
            raise ValueError("articles.json is not a JSON list")
    except (json.JSONDecodeError, ValueError, FileNotFoundError) as exc:
        _print(FAIL_MARK, "HARD", f"Valid JSON: state/articles.json failed to load: {exc}")
        print()
        print(f"RESULT: FAIL ({FAIL_MARK} publish blocked)")
        return 1

    placeable = placeable_articles(articles, start, end)

    # HARD checks.
    for fn, args in (
        (check_density, (placeable, min_articles)),
        (check_unique_ids, (articles,)),
        (check_urls, (placeable,)),
    ):
        ok, msg = fn(*args)
        _print(OK_MARK if ok else FAIL_MARK, "HARD", msg)
        hard_ok = hard_ok and ok

    # WARN checks.
    featured = _load_json(FEATURED_FILE, {})
    ok, msg = check_featured_pins(featured.get(edition), placeable)
    _print(OK_MARK if ok else WARN_MARK, "WARN", msg)

    pool = _load_comics(COMICS_FILE)
    used = _load_json(COMICS_USED_FILE, {})
    ok, msg = check_comics_pool(pool, used, edition)
    _print(OK_MARK if ok else WARN_MARK, "WARN", msg)

    print()
    if hard_ok:
        print(f"RESULT: PASS ({OK_MARK} all hard checks passed)")
        return 0
    print(f"RESULT: FAIL ({FAIL_MARK} publish blocked — fix the HARD checks above)")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="preflight.py",
        description=(
            "Publish preflight gate for a Kotlin Digest edition. Runs HARD checks "
            "(block publish) and WARN checks (advisory) and exits non-zero if any "
            "HARD check fails, so a Makefile can gate `make promote` on it."
        ),
        epilog="Exit code is 0 only when every HARD check passes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--edition", required=True,
        help="ISO-week edition to check, e.g. 2026-W32",
    )
    parser.add_argument(
        "--min-articles", type=int, default=DEFAULT_MIN_ARTICLES,
        help=(
            "Minimum placeable articles (in-window with summary + topics) required "
            "to publish. The broken edition had 24; typical editions are 40+."
        ),
    )
    args = parser.parse_args(argv)
    return run(args.edition, args.min_articles)


if __name__ == "__main__":
    raise SystemExit(main())
