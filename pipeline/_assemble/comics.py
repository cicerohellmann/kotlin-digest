"""Comic interlude selection.

One comic runs before the magazine, then one after roughly every 14 article
cards. Comics are drawn from comics/comics.yml in order and never repeat across
editions — the used set is tracked per edition in state/comics_used.json.

Selection is idempotent: re-assembling the same edition reuses that edition's
recorded comics (it excludes only comics used by *other* editions), so a re-run
never consumes new strips or shifts what was already published.
"""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent.parent
COMICS_FILE = ROOT / "comics" / "comics.yml"
USED_FILE = ROOT / "state" / "comics_used.json"

COMIC_EVERY = 14  # place a comic once this many cards have passed since the last


def comics_needed(chapter_sizes: list) -> int:
    """How many comics the edition will actually place.

    Mirrors the template's placement exactly so state never records a comic that
    isn't shown: one leading comic, then one at a chapter boundary each time
    COMIC_EVERY cards have accrued *since the last comic* (the counter resets, so
    comics never land back-to-back even when one chapter is very large).
    """
    n = 1  # leading comic
    since = 0
    for size in chapter_sizes:
        since += size
        if since >= COMIC_EVERY:
            n += 1
            since = 0
    return n


def _load_pool() -> list:
    if not COMICS_FILE.exists():
        return []
    data = yaml.safe_load(COMICS_FILE.read_text(encoding="utf-8")) or {}
    return data.get("comics", [])


def _write_used(used: dict) -> None:
    tmp = USED_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(used, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(USED_FILE)


def select_comics(edition: str, needed: int) -> list:
    """Return up to `needed` comics for this edition and record them as used.

    Excludes comics used by any *other* edition, so strips never repeat; picks
    deterministically in pool order, so re-running an edition is stable.
    """
    pool = _load_pool()
    if not pool or needed <= 0:
        return []

    used = {}
    if USED_FILE.exists():
        used = json.loads(USED_FILE.read_text(encoding="utf-8"))

    used_by_others = {
        cid for ed, ids in used.items() if ed != edition for cid in ids
    }
    available = [c for c in pool if c["id"] not in used_by_others]
    selected = available[:needed]

    used[edition] = [c["id"] for c in selected]
    _write_used(used)
    return selected
