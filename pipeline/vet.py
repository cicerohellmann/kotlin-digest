#!/usr/bin/env python3.11
"""
Deterministic article vetting — junk / relevance / language / spam removal.

This is the offline, no-agent half of quality control: it flags articles that
are off-topic, non-English, spam, or carry no Kotlin/Android signal at all.
Network signals (liveness, paywall, Reddit engagement) come in a later pass.

Dry-run report (no writes):
  python3.11 pipeline/vet.py --edition 2026-W28

Apply flags to state/articles.json:
  python3.11 pipeline/vet.py --edition 2026-W28 --apply
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.scout import KOTLIN_ANDROID_KEYWORDS  # noqa: E402
from pipeline._assemble.dates import edition_to_dates  # noqa: E402

ARTICLES_FILE = ROOT / "state" / "articles.json"

# Broader relevance vocabulary for the "no signal at all" check. Deterministic
# removal must be high-precision: a legit Android/Compose/Kotlin post that lacks
# scout's 30 narrow ingest keywords should still survive here. Anything truly
# borderline is left for the AI substance pass, not auto-removed.
VET_KEYWORDS = KOTLIN_ANDROID_KEYWORDS | {
    "lazycolumn", "lazyrow", "lazy list", "lazy lists", "recyclerview",
    "diffutil", "listadapter", "paging", "material", "material3", "sqldelight",
    "proguard", "r8", "wear os", "wearos", "paparazzi", "turbine", "mockk",
    "detekt", "voyager", "decompose", "arrow", "exposed", "kapt", "molecule",
    "serialization", "serializer", "square wire", "spring boot", "kmm",
    "swiftui", "swift export", "livedata", "annotation processor", "proto datastore",
    "state hoisting", "recomposition", "side effect", "modifier", "subcompose",
    "predictive back", "foldable", "activity", "fragment", "intent", "sdk",
}

# Competing / off-topic ecosystems — junk when present with no real Kotlin signal.
OFF_TOPIC = {
    "flutter", "react native", "reactnative", "react-native", "swiftui",
    "xamarin", "ionic", "cordova", ".net maui", " maui ",
}

# Obvious spam / non-developer content.
SPAM_PATTERNS = [
    r"\bmod apk\b", r"\bapk download\b", r"\bdownload\b[^.]{0,30}\bapk\b",
    r"\bfree fire\b", r"\bpubg\b", r"\bgame apk\b", r"\bpakistan\b",
    r"<!doctype html", r"<html", r"\bnulled\b", r"\bcracked?\b",
    r"\bcasino\b", r"\bbetting\b",
]

# Aggregator tag feeds ingested WITHOUT a relevance filter (unlike reddit/jetbrains).
OPEN_AGGREGATORS = {"medium-kotlin-tag", "medium-android-tag"}

NON_LATIN_SCRIPTS = (
    "CJK", "HIRAGANA", "KATAKANA", "HANGUL", "DEVANAGARI",
    "ARABIC", "CYRILLIC", "HEBREW", "THAI", "BENGALI", "TAMIL", "TELUGU",
)


def _text(a: dict) -> str:
    return (a.get("title", "") + " " + a.get("excerpt", "")).lower()


def non_latin_ratio(s: str) -> float:
    """Fraction of alphabetic characters that belong to a non-Latin script."""
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    non_latin = 0
    for c in letters:
        try:
            name = unicodedata.name(c)
        except ValueError:
            continue
        if any(scr in name for scr in NON_LATIN_SCRIPTS):
            non_latin += 1
    return non_latin / len(letters)


def relevance_hits(text: str) -> int:
    return sum(1 for kw in VET_KEYWORDS if kw in text)


def classify(article: dict) -> list:
    """Return a list of junk reasons for an article ([] means it passes).

    Strong signals (spam, non-English) always apply — they're unambiguous.
    Soft signals (off-topic ecosystem, no Kotlin keyword) only apply to articles
    the AI has NOT yet topic-tagged: once the summarizer assigns real topics it
    has vouched for relevance, and a deterministic keyword check must not override
    that. So the vetter is really a *pre-summarize* junk gate.
    """
    reasons = []
    title = article.get("title", "")
    t = _text(article)
    sid = article.get("source_id", "")

    # ── strong signals (always) ──
    if non_latin_ratio(title) > 0.2:
        reasons.append("non-english")

    for pat in SPAM_PATTERNS:
        if re.search(pat, t):
            reasons.append("spam/non-dev")
            break

    # ── soft signals (only before the AI has tagged topics) ──
    if not article.get("topics"):
        off = [k.strip() for k in OFF_TOPIC if k in t]
        if off and relevance_hits(t) < 2:
            reasons.append(f"off-topic:{off[0]}")

        if sid in OPEN_AGGREGATORS and relevance_hits(t) == 0:
            reasons.append("no-kotlin-signal")

    return reasons


def _window_articles(articles, start, end):
    s, e = start.isoformat(), end.isoformat()
    return [a for a in articles if a.get("date") and s <= a["date"] <= e]


def write_atomic(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", required=True)
    ap.add_argument("--apply", action="store_true", help="write low_quality flags back to state")
    args = ap.parse_args()

    start, end = edition_to_dates(args.edition)
    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    window = _window_articles(articles, start, end)

    flagged = []
    by_source = defaultdict(list)
    for a in window:
        reasons = classify(a)
        if reasons:
            flagged.append((a, reasons))
            by_source[a["source_id"]].append((a["title"][:60], reasons))

    print(f"  Edition {args.edition}: {len(window)} articles in window")
    print(f"  Flagged as junk: {len(flagged)}\n")
    for sid in sorted(by_source):
        print(f"  [{sid}] — {len(by_source[sid])}")
        for title, reasons in by_source[sid]:
            print(f"      · {title}  ({', '.join(reasons)})")
    print()

    if args.apply:
        # Reconcile within the window so re-runs are idempotent: set the flag on
        # currently-flagged articles, clear a previously vet-set flag on any that
        # no longer classify (e.g. after the AI tags topics).
        window_ids = {a["id"] for a in window}
        reason_map = {a["id"]: reasons for a, reasons in flagged}
        set_n = cleared_n = 0
        for a in articles:
            if a["id"] not in window_ids:
                continue
            if a["id"] in reason_map:
                a["low_quality"] = True
                a["low_quality_reason"] = ", ".join(reason_map[a["id"]])
                set_n += 1
            elif a.get("low_quality") and "vet" not in str(a.get("low_quality_source", "")):
                # only clear flags this vetter set (tracked via low_quality_reason)
                if a.get("low_quality_reason"):
                    a.pop("low_quality", None)
                    a.pop("low_quality_reason", None)
                    cleared_n += 1
        write_atomic(ARTICLES_FILE, articles)
        print(f"  low_quality: set {set_n}, cleared {cleared_n} stale flags.")


if __name__ == "__main__":
    main()
