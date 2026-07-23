"""Writers registry — a durable slug→writer map grown as articles are scouted.

Keyed by a slug of the author identifier as it appears in the feed. We do NOT
try to merge the same human across platforms (e.g. a Medium display name and a
GitHub handle) — that's a future problem; each identifier is its own entry.

The `photo` slot stays null until a source actually provides an author image.
When one does, store a LOCAL, site-relative asset path (e.g. "writers/<slug>.jpg",
committed under site/writers/) — never a remote URL — so the published page and
its link previews stay self-contained. The value is used verbatim as an <img src>.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WRITERS_FILE = Path(__file__).parent.parent / "state" / "writers.json"


def slugify(identifier: str) -> str:
    """'Viliam Sedliak' → 'viliam-sedliak', '/u/3dom' → 'u-3dom'."""
    s = re.sub(r"[^a-z0-9]+", "-", (identifier or "").strip().lower())
    return s.strip("-")


def load(path: Path = WRITERS_FILE) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(registry: dict, path: Path = WRITERS_FILE) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.rename(path)


def upsert(registry: dict, name: str, source_id: str = "", date: str | None = None) -> str:
    """Record one sighting of a writer. Returns the slug, or '' if no usable name.

    New writers get a null photo/profile (filled in later, by hand or by a
    future image-bearing source). Existing writers keep their photo/profile and
    just accrue the sighting.
    """
    name = (name or "").strip()
    slug = slugify(name)
    if not slug:
        return ""
    w = registry.get(slug)
    if w is None:
        w = {
            "name": name,
            "photo": None,      # local path, e.g. site/writers/<slug>.jpg, once available
            "profile": None,    # optional profile URL
            "sources": [],
            "articles": 0,
            "first_seen": date,
            "last_seen": date,
        }
        registry[slug] = w
    w["articles"] += 1
    if source_id and source_id not in w["sources"]:
        w["sources"].append(source_id)
    if date:
        if not w.get("first_seen") or date < w["first_seen"]:
            w["first_seen"] = date
        if not w.get("last_seen") or date > w["last_seen"]:
            w["last_seen"] = date
    return slug
