"""Comic interlude selection.

One comic runs before the magazine, then one after roughly every 14 article
cards. Comics are drawn from comics/comics.yml in order and never repeat across
editions — the used set is tracked per edition in state/comics_used.json.

Selection is idempotent: re-assembling the same edition reuses that edition's
recorded comics (it excludes only comics used by *other* editions), so a re-run
never consumes new strips or shifts what was already published.
"""
import json
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent.parent
COMICS_FILE = ROOT / "comics" / "comics.yml"
USED_FILE = ROOT / "state" / "comics_used.json"
SITE_COMICS_DIR = ROOT / "site" / "comics"

COMIC_EVERY = 14  # place a comic once this many cards have passed since the last


def _localize(comic: dict) -> dict:
    """Guarantee a comic's image is served from our own origin.

    DSGVO/privacy: the site must make **zero third-party requests** on page
    load, so a comic's `img` must be a root-absolute local path (/comics/x.png),
    never a remote URL. If the local file is missing we re-fetch it from the
    entry's `remote` origin (or from a remote `img`, for legacy entries) and
    write it under site/comics/. Idempotent: with the file already committed,
    this touches the network zero times.

    Raises if an image can't be made local — a hotlink must fail the build, not
    ship silently. This is the guardrail that keeps [self-hosting] from
    regressing again.
    """
    img = comic.get("img", "")
    remote = comic.get("remote") or (img if img.startswith(("http://", "https://")) else "")

    if img.startswith(("http://", "https://")):
        fn = img.rsplit("/", 1)[-1]
    elif img.startswith("/comics/"):
        fn = img.rsplit("/", 1)[-1]
    else:
        raise ValueError(
            f"comic {comic.get('id')!r}: img must be a /comics/ path or a remote "
            f"URL to fetch, got {img!r}"
        )

    dest = SITE_COMICS_DIR / fn
    if not dest.exists() or dest.stat().st_size == 0:
        if not remote:
            raise RuntimeError(
                f"comic {comic.get('id')!r}: image {fn} missing under site/comics/ "
                f"and no `remote` to fetch it from"
            )
        SITE_COMICS_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(remote, dest)
        if not dest.exists() or dest.stat().st_size == 0:
            raise RuntimeError(f"comic {comic.get('id')!r}: fetched empty image from {remote}")

    out = dict(comic)
    out["img"] = f"/comics/{fn}"
    return out


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
    # Self-host every image before it reaches the renderer — no comic may hotlink.
    return [_localize(c) for c in selected]
