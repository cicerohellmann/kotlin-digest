import sys
from datetime import date

sys.path.insert(0, '.')

from pipeline.preflight import (
    placeable_articles,
    normalize_featured_entry,
    check_density,
    check_unique_ids,
    check_urls,
    check_featured_pins,
    check_comics_pool,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def art(aid, date_="2026-08-04", summary="a summary", topics=("kotlin",),
        url="https://example.com/x", **extra):
    a = {
        "id": aid,
        "title": f"Article {aid}",
        "url": url,
        "date": date_,
        "summary": summary,
        "topics": list(topics),
    }
    a.update(extra)
    return a


W32 = (date(2026, 8, 3), date(2026, 8, 9))   # 2026-W32
W28 = (date(2026, 7, 6), date(2026, 7, 12))  # 2026-W28


# ── placeable ──────────────────────────────────────────────────────────────────

def test_placeable_requires_window_summary_and_topics():
    arts = [
        art("in"),                                   # placeable
        art("out", date_="2026-07-03"),              # out of window
        art("nosum", summary=""),                    # no summary
        art("notopics", topics=[]),                  # no topics
        art("nodate", date_=None),                   # no date
    ]
    got = {a["id"] for a in placeable_articles(arts, *W32)}
    assert got == {"in"}


def test_placeable_excludes_render_flags():
    arts = [
        art("ok"),
        art("dead", dead=True),
        art("junk", low_quality=True),
        art("short", is_short=True),
        art("unfetch", unfetchable=True),
    ]
    got = {a["id"] for a in placeable_articles(arts, *W32)}
    assert got == {"ok"}


# ── density (HARD) ─────────────────────────────────────────────────────────────

def test_density_fails_at_24():
    placeable = [art(f"a{i}") for i in range(24)]
    ok, msg = check_density(placeable, min_articles=35)
    assert ok is False
    assert "24" in msg


def test_density_passes_at_73():
    placeable = [art(f"a{i}") for i in range(73)]
    ok, msg = check_density(placeable, min_articles=35)
    assert ok is True
    assert "73" in msg


def test_density_boundary_equal_passes():
    placeable = [art(f"a{i}") for i in range(35)]
    ok, _ = check_density(placeable, min_articles=35)
    assert ok is True


# ── unique ids (HARD) ──────────────────────────────────────────────────────────

def test_unique_ids_flags_duplicate():
    arts = [art("a"), art("b"), art("a"), art("c"), art("c")]
    ok, msg = check_unique_ids(arts)
    assert ok is False
    assert "a" in msg and "c" in msg


def test_unique_ids_passes_on_unique():
    arts = [art("a"), art("b"), art("c")]
    ok, msg = check_unique_ids(arts)
    assert ok is True


# ── urls (HARD) ────────────────────────────────────────────────────────────────

def test_url_check_flags_hash_and_empty():
    placeable = [
        art("good"),
        art("hash", url="#"),
        art("empty", url=""),
        art("space", url="   "),
    ]
    ok, msg = check_urls(placeable)
    assert ok is False
    assert "hash" in msg and "empty" in msg and "space" in msg
    assert "good" not in msg


def test_url_check_passes_when_all_real():
    placeable = [art("a"), art("b")]
    ok, _ = check_urls(placeable)
    assert ok is True


# ── featured pins (WARN) ───────────────────────────────────────────────────────

def test_featured_pin_flags_out_of_window_july_id():
    # An August (W32) edition; a July-3 article surfaced as an 'also inside'.
    placeable = [art("cover-id"), art("aug-also")]
    entry = {"cover": "cover-id", "also": ["aug-also", "jul3-id"]}
    ok, msg = check_featured_pins(entry, placeable)
    assert ok is False
    assert "jul3-id" in msg
    assert "aug-also" not in msg


def test_featured_pin_passes_when_all_in_window():
    placeable = [art("cover-id"), art("a1"), art("a2")]
    entry = {"cover": "cover-id", "also": ["a1", "a2"]}
    ok, _ = check_featured_pins(entry, placeable)
    assert ok is True


def test_featured_pin_no_entry_is_ok():
    ok, _ = check_featured_pins(None, [art("x")])
    assert ok is True


def test_featured_pin_legacy_bare_string_cover():
    placeable = [art("cover-id")]
    ok, _ = check_featured_pins("cover-id", placeable)
    assert ok is True

    ok, msg = check_featured_pins("missing-id", placeable)
    assert ok is False
    assert "missing-id" in msg


def test_normalize_featured_entry_forms():
    assert normalize_featured_entry("abc") == {"cover": "abc", "also": []}
    assert normalize_featured_entry({"cover": "c", "also": ["x"]}) == {"cover": "c", "also": ["x"]}
    assert normalize_featured_entry(None) == {"cover": "", "also": []}


# ── comics pool (WARN) ─────────────────────────────────────────────────────────

def _pool(*ids):
    return [{"id": i} for i in ids]


def test_comics_pool_warns_when_exhausted():
    pool = _pool("c1", "c2")
    used = {"2026-W30": ["c1"], "2026-W31": ["c2"]}
    ok, msg = check_comics_pool(pool, used, "2026-W32")
    assert ok is False
    assert "exhausted" in msg


def test_comics_pool_ok_when_available():
    pool = _pool("c1", "c2", "c3")
    used = {"2026-W30": ["c1"]}
    ok, _ = check_comics_pool(pool, used, "2026-W32")
    assert ok is True


def test_comics_pool_ok_when_edition_already_recorded():
    # Re-assembling an edition reuses its own recorded comics even if the rest
    # of the pool is used up.
    pool = _pool("c1", "c2")
    used = {"2026-W31": ["c1"], "2026-W32": ["c2"]}
    ok, _ = check_comics_pool(pool, used, "2026-W32")
    assert ok is True


def test_comics_pool_warns_when_empty():
    ok, msg = check_comics_pool([], {}, "2026-W32")
    assert ok is False
