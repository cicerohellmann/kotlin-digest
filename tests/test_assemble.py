import sys
import pytest
sys.path.insert(0, '.')

from datetime import date
from pipeline._assemble.dates import edition_to_dates
from pipeline._assemble.scores import lookup_scores_at
from pipeline._assemble.articles import filter_articles, score_articles, assign_col, cluster_articles
from pipeline._assemble.render import (
    spark_from_history,
    inject_data,
    inject_static_digest,
    inject_ticker,
    build_data_block,
    build_static_digest,
    build_ticker_html,
    highlight_kotlin,
)


# ── dates ────────────────────────────────────────────────────────────────────

def test_edition_to_dates_w28():
    start, end = edition_to_dates("2026-W28")
    assert start == date(2026, 7, 6)
    assert end   == date(2026, 7, 12)


def test_edition_to_dates_week_bounds():
    start, end = edition_to_dates("2026-W01")
    assert start.weekday() == 0  # Monday
    assert end.weekday()   == 6  # Sunday
    assert (end - start).days == 6


# ── scores ───────────────────────────────────────────────────────────────────

def test_lookup_scores_exact_date():
    bible = {
        "compose": {
            "score": 200.0,
            "history": [
                {"date": "2026-07-06", "score": 80.0, "mentions": 3},
                {"date": "2026-07-12", "score": 100.0, "mentions": 5},
            ]
        }
    }
    scores = lookup_scores_at(bible, date(2026, 7, 12))
    assert scores["compose"] == 100.0


def test_lookup_scores_between_entries():
    bible = {
        "kotlin": {
            "score": 50.0,
            "history": [
                {"date": "2026-07-06", "score": 40.0, "mentions": 2},
                {"date": "2026-07-13", "score": 55.0, "mentions": 3},
            ]
        }
    }
    scores = lookup_scores_at(bible, date(2026, 7, 12))
    assert scores["kotlin"] == 40.0


def test_lookup_scores_no_history():
    bible = {"testing": {"score": 10.0, "history": []}}
    scores = lookup_scores_at(bible, date(2026, 7, 12))
    assert scores["testing"] == 0.0


def test_lookup_scores_skips_meta():
    bible = {
        "_meta": {"last_run": "2026-07-12"},
        "kotlin": {"score": 5.0, "history": [{"date": "2026-07-06", "score": 5.0, "mentions": 1}]},
    }
    scores = lookup_scores_at(bible, date(2026, 7, 12))
    assert "_meta" not in scores
    assert "kotlin" in scores


# ── articles ─────────────────────────────────────────────────────────────────

def test_filter_articles_keeps_window():
    articles = [
        {"id": "a", "date": "2026-07-06", "topics": []},
        {"id": "b", "date": "2026-07-12", "topics": []},
        {"id": "c", "date": "2026-07-13", "topics": []},
        {"id": "d", "date": "2026-07-05", "topics": []},
        {"id": "e", "date": None,          "topics": []},
    ]
    result = filter_articles(articles, date(2026, 7, 6), date(2026, 7, 12))
    assert [a["id"] for a in result] == ["a", "b"]


def test_filter_articles_skips_dead_and_low_quality():
    articles = [
        {"id": "a", "date": "2026-07-07", "topics": []},
        {"id": "b", "date": "2026-07-07", "topics": [], "dead": True},
        {"id": "c", "date": "2026-07-07", "topics": [], "low_quality": True},
    ]
    result = filter_articles(articles, date(2026, 7, 6), date(2026, 7, 12))
    assert [a["id"] for a in result] == ["a"]


def test_score_articles_sums_topic_scores():
    articles = [{"id": "a", "topics": ["kotlin", "compose"], "date": "2026-07-07"}]
    scores = {"kotlin": 100.0, "compose": 80.0}
    result = score_articles(articles, scores)
    assert result[0]["placement_score"] == 180.0


def test_score_articles_unknown_topics_zero():
    articles = [{"id": "a", "topics": ["unknown-lib"], "date": "2026-07-07"}]
    scores = {"kotlin": 50.0}
    result = score_articles(articles, scores)
    assert result[0]["placement_score"] == 0.0


def test_assign_col():
    assert assign_col(1) == "c12"
    assert assign_col(2) == "c8"
    assert assign_col(3) == "c8"
    assert assign_col(4) == "c6"
    assert assign_col(6) == "c6"
    assert assign_col(7) == "c4"
    assert assign_col(99) == "c4"


def test_cluster_articles_groups_by_primary_cluster():
    clusters = [
        {"id": "ui",   "label": "Compose & UI", "topics": ["compose", "navigation"]},
        {"id": "core", "label": "Kotlin Core",  "topics": ["kotlin", "coroutines"]},
    ]
    articles = [
        {"id": "a", "topics": ["compose"],    "placement_score": 80.0, "date": "2026-07-07"},
        {"id": "b", "topics": ["kotlin"],     "placement_score": 50.0, "date": "2026-07-07"},
        {"id": "c", "topics": ["navigation"], "placement_score": 30.0, "date": "2026-07-07"},
    ]
    chapters = cluster_articles(articles, clusters)
    ui_ch = next(ch for ch in chapters if ch["id"] == "ui")
    core_ch = next(ch for ch in chapters if ch["id"] == "core")
    assert len(ui_ch["articles"]) == 2
    assert len(core_ch["articles"]) == 1


def test_cluster_articles_ordered_by_chapter_score():
    clusters = [
        {"id": "ui",   "label": "UI",   "topics": ["compose"]},
        {"id": "core", "label": "Core", "topics": ["kotlin"]},
    ]
    articles = [
        {"id": "a", "topics": ["compose"], "placement_score": 10.0, "date": "2026-07-07"},
        {"id": "b", "topics": ["kotlin"],  "placement_score": 90.0, "date": "2026-07-07"},
    ]
    chapters = cluster_articles(articles, clusters)
    assert chapters[0]["id"] == "core"
    assert chapters[1]["id"] == "ui"


def test_cluster_articles_assigns_col():
    clusters = [{"id": "ui", "label": "UI", "topics": ["compose"]}]
    articles = [
        {"id": "a", "topics": ["compose"], "placement_score": 100.0, "date": "2026-07-07"},
        {"id": "b", "topics": ["compose"], "placement_score": 80.0,  "date": "2026-07-07"},
        {"id": "c", "topics": ["compose"], "placement_score": 60.0,  "date": "2026-07-07"},
        {"id": "d", "topics": ["compose"], "placement_score": 40.0,  "date": "2026-07-07"},
    ]
    chapters = cluster_articles(articles, clusters)
    cols = [a["col"] for a in chapters[0]["articles"]]
    # rule: rank1→c12, rank2-3→c8, rank4-6→c6, rank7+→c4
    assert cols == ["c12", "c8", "c8", "c6"]


# ── render ───────────────────────────────────────────────────────────────────

def test_spark_all_same():
    history = [{"score": 50.0}] * 7
    result = spark_from_history(history)
    assert len(result) == 7
    assert all(c == result[0] for c in result)


def test_spark_ascending():
    history = [{"score": float(i * 10)} for i in range(1, 8)]
    result = spark_from_history(history)
    assert result[-1] == "█"


def test_spark_empty():
    assert spark_from_history([]) == ""


def test_spark_uses_last_n():
    history = [{"score": 100.0}] * 20
    result = spark_from_history(history, n=7)
    assert len(result) == 7


def test_inject_data_replaces_marker():
    template = "before\n// @@DIGEST_DATA@@\nafter"
    result = inject_data(template, "const X = 1;")
    assert "const X = 1;" in result
    assert "@@DIGEST_DATA@@" not in result


def test_inject_data_raises_if_no_marker():
    with pytest.raises(ValueError, match="DATA_MARKER not found"):
        inject_data("no marker here", "data")


def test_inject_static_digest_replaces_marker():
    template = '<main id="digest">\n<!-- @@DIGEST_STATIC@@ -->\n</main>'
    result = inject_static_digest(template, "<p>Readable digest</p>")
    assert "<p>Readable digest</p>" in result
    assert "@@DIGEST_STATIC@@" not in result


def test_inject_ticker_replaces_marker():
    template = '<div id="ticker"><!-- @@DIGEST_TICKER@@ --></div>'
    result = inject_ticker(template, "<span>trend</span>")
    assert "<span>trend</span>" in result
    assert "@@DIGEST_TICKER@@" not in result


def test_build_ticker_html_duplicates_items_for_marquee():
    bible = {"kotlin": {"score": 10.0, "history": [{"score": 10.0}]}}
    html = build_ticker_html(bible)
    assert html.count("ticker-item") == 2
    assert "kotlin" in html


def test_build_data_block_valid_js_structure():
    clusters = [{"id": "ui", "label": "Compose & UI", "topics": ["compose"]}]
    chapters = [
        {
            "id": "ui",
            "label": "Compose & UI",
            "score": 80.0,
            "articles": [
                {
                    "id": "abc123",
                    "col": "c12",
                    "title": "Test Article",
                    "url": "https://example.com/test",
                    "source_id": "kotlin-blog",
                    "date": "2026-07-07",
                    "topics": ["compose"],
                    "placement_score": 80.0,
                    "summary": "A great article.",
                    "summarized": True,
                }
            ],
        }
    ]
    bible = {
        "compose": {
            "label": "Jetpack Compose",
            "score": 80.0,
            "history": [{"date": "2026-07-07", "score": 80.0, "mentions": 3}],
        }
    }
    source_type_map = {"kotlin-blog": "blog"}
    block = build_data_block(
        edition="2026-W28",
        start=date(2026, 7, 6),
        end=date(2026, 7, 12),
        chapters=chapters,
        bible=bible,
        source_type_map=source_type_map,
        clusters=clusters,
    )
    assert "const TOPICS" in block
    assert "const TRENDING_DATA" in block
    assert "const CHAPTERS" in block
    assert "Test Article" in block
    assert "abc123" in block
    assert "c12" in block
    assert "official" in block  # kotlin-blog is an official source


def test_highlight_kotlin_tokens_and_escapes_generics():
    out = highlight_kotlin('val backStack = mutableStateListOf<Any>(Home)')
    assert 'class="k-' in out                 # produced prefixed token spans (colorable)
    assert '&lt;' in out and '&gt;' in out     # generics HTML-escaped, not eaten
    assert '<Any>' not in out                  # raw angle brackets gone
    assert 'class="k-kd"' in out               # 'val' tokenized as a keyword
    assert '>Any</span>' in out                # 'Any' preserved as a token


def test_build_data_block_emits_rollup():
    clusters = [{"id": "kmp", "label": "KMP", "topics": ["compose-multiplatform"]}]
    chapters = [{
        "id": "kmp", "label": "KMP", "score": 50.0,
        "articles": [{
            "id": "surv", "col": "c12",
            "title": "v1.12.10-alpha01+dev4443: Details",
            "url": "https://x/dev4443",
            "source_id": "lib-compose-multiplatform",
            "date": "2026-07-10", "topics": ["compose-multiplatform"],
            "placement_score": 50.0, "summary": "newest build", "summarized": True,
            "rollup_summary": "Across 7 dev builds this week the alpha and beta trains landed fixes.",
            "collapsed_builds": [
                {"title": "v1.12.10-alpha01+dev4438: Details", "date": "2026-07-09", "url": "https://x/dev4438"},
            ],
        }],
    }]
    bible = {"compose-multiplatform": {"label": "CMP", "score": 50.0,
             "history": [{"date": "2026-07-10", "score": 50.0, "mentions": 2}]}}
    block = build_data_block(
        edition="2026-W28", start=date(2026, 7, 6), end=date(2026, 7, 12),
        chapters=chapters, bible=bible,
        source_type_map={"lib-compose-multiplatform": "changelog"}, clusters=clusters,
    )
    assert "rollup:" in block
    assert "Across 7 dev builds" in block
    assert "dev4438" in block


def test_build_data_block_no_rollup_is_null():
    clusters = [{"id": "ui", "label": "UI", "topics": ["compose"]}]
    chapters = [{
        "id": "ui", "label": "UI", "score": 10.0,
        "articles": [{
            "id": "a", "col": "c12", "title": "Plain", "url": "https://x/a",
            "source_id": "kotlin-blog", "date": "2026-07-07", "topics": ["compose"],
            "placement_score": 10.0, "summary": "s", "summarized": True,
        }],
    }]
    bible = {"compose": {"label": "C", "score": 10.0,
             "history": [{"date": "2026-07-07", "score": 10.0, "mentions": 1}]}}
    block = build_data_block(
        edition="2026-W28", start=date(2026, 7, 6), end=date(2026, 7, 12),
        chapters=chapters, bible=bible,
        source_type_map={"kotlin-blog": "blog"}, clusters=clusters,
    )
    assert "rollup:null" in block


def test_build_static_digest_contains_readable_articles_and_video_link():
    chapters = [{
        "id": "community", "label": "Community", "score": 10.0,
        "articles": [{
            "id": "v1", "col": "c12", "title": "Kotlin Talk",
            "url": "https://www.youtube.com/watch?v=bbbbbbbbbbb",
            "source_id": "kotlin-youtube", "date": "2026-07-07",
            "topics": ["kotlin"], "placement_score": 10.0,
            "summary": "A Kotlin video.", "summarized": True,
        }],
    }]
    bible = {"kotlin": {"score": 10.0, "history": [{"date": "2026-07-07", "score": 10.0}]}}
    html = build_static_digest(chapters, {"kotlin-youtube": "youtube"}, bible)
    assert 'data-static-digest="1"' in html
    assert "Kotlin Talk" in html
    assert "https://www.youtube.com/watch?v=bbbbbbbbbbb" in html
    assert "<script" not in html


def test_build_static_digest_contains_cover_and_comic_interlude():
    chapters = [
        {
            "id": "core",
            "label": "Kotlin Core",
            "score": 80.0,
            "articles": [{
                "id": "a1",
                "col": "c12",
                "title": "Featured Kotlin Story",
                "url": "https://example.com/a1",
                "source_id": "kotlin-blog",
                "date": "2026-07-07",
                "topics": ["kotlin"],
                "summary": "Main story.",
            }],
        },
        {
            "id": "ui",
            "label": "Compose & UI",
            "score": 60.0,
            "articles": [{
                "id": "a2",
                "col": "c12",
                "title": "Secondary Compose Story",
                "url": "https://example.com/a2",
                "source_id": "proandroiddev",
                "date": "2026-07-08",
                "topics": ["compose"],
                "summary": "Secondary story.",
            }],
        },
    ]
    bible = {"kotlin": {"score": 10.0, "history": [{"score": 10.0}]}}
    comics = [{
        "img": "comic.png",
        "alt": "Comic alt text.",
        "title": "Kotlin Comic",
        "permalink": "https://example.com/comic",
        "artist": "Artist",
        "source": "Comic Source",
    }]
    html = build_static_digest(
        chapters,
        {"kotlin-blog": "blog", "proandroiddev": "blog"},
        bible,
        featured_id="a1",
        comics=comics,
        comic_every=1,
    )
    assert "Cover Story · Kotlin Core" in html
    assert "Featured Kotlin Story" in html
    assert "Also inside this issue" in html
    assert "Kotlin Comic" in html
    assert "Comic alt text." in html
