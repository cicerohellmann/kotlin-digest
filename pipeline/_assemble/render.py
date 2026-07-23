import json
import re
from datetime import date, datetime
from html import escape

from pygments import highlight as _pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import KotlinLexer

from pipeline.writers import load as load_writers, slugify as writer_slug

_KT_LEXER = KotlinLexer()
_KT_FORMATTER = HtmlFormatter(nowrap=True, classprefix="k-")


def highlight_kotlin(code: str) -> str:
    """Syntax-highlight a Kotlin snippet into token <span>s (also HTML-escapes,
    so generics like <Any> survive). Classes are prefixed `k-` to match the
    .snap-code .k-* palette in template.html."""
    return _pyg_highlight(code, _KT_LEXER, _KT_FORMATTER).rstrip("\n")

_YT_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|v/|shorts/))([A-Za-z0-9_-]{11})"
)


def youtube_id(url: str) -> str:
    """Extract an 11-char YouTube id from any common URL form, else ''."""
    m = _YT_RE.search(url or "")
    return m.group(1) if m else ""


SPARK_CHARS = "▁▂▃▄▅▆▇█"
DATA_MARKER = "// @@DIGEST_DATA@@"
STATIC_MARKER = "<!-- @@DIGEST_STATIC@@ -->"
TICKER_MARKER = "<!-- @@DIGEST_TICKER@@ -->"
OFFICIAL_SOURCE_IDS = {"kotlin-blog", "android-developers-blog", "android-developers-medium", "jetbrains-blog"}


def spark_from_history(history: list, n: int = 7) -> str:
    """Map last n history scores to spark bar characters."""
    entries = history[-n:]
    if not entries:
        return ""
    scores = [e.get("score", 0.0) for e in entries]
    max_s = max(scores) or 1.0
    return "".join(SPARK_CHARS[min(7, int(s / max_s * 8))] for s in scores)


def inject_data(template: str, data_block: str) -> str:
    """Replace @@DIGEST_DATA@@ marker in template with generated data block."""
    if DATA_MARKER not in template:
        raise ValueError("DATA_MARKER not found in template — was template.html created?")
    return template.replace(DATA_MARKER, data_block)


def inject_static_digest(template: str, html_block: str) -> str:
    """Replace the static digest marker with pre-rendered readable HTML."""
    if STATIC_MARKER not in template:
        raise ValueError("STATIC_MARKER not found in template — add @@DIGEST_STATIC@@ to #digest")
    return template.replace(STATIC_MARKER, html_block)


def inject_ticker(template: str, html_block: str) -> str:
    """Replace the ticker marker with pre-rendered trending items."""
    if TICKER_MARKER not in template:
        raise ValueError("TICKER_MARKER not found in template — add @@DIGEST_TICKER@@ to #ticker")
    return template.replace(TICKER_MARKER, html_block)


def _stype(source_id: str, source_type: str) -> str:
    if source_id in OFFICIAL_SOURCE_IDS:
        return "official"
    if source_type == "changelog":
        return "changelog"
    if source_type == "discussion":
        return "discussion"
    return "community"


def _js_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")


def _fmt_date(raw: str) -> str:
    """Format an ISO date as '10 Jul'; pass through anything unparseable."""
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%-d %b")
    except Exception:
        return raw or ""


def build_ticker_html(bible: dict, limit: int = 20) -> str:
    """Pre-render the scrolling trending ticker for no-JS readers."""
    trending = sorted(
        [(tid, entry) for tid, entry in bible.items() if not tid.startswith("_")],
        key=lambda x: x[1].get("score", 0.0),
        reverse=True,
    )[:limit]
    items = []
    for _ in range(2):
        for tid, entry in trending:
            items.append(
                '<span class="ticker-item">'
                f'<span class="t-spark">{escape(spark_from_history(entry.get("history", [])))}</span>'
                f'<span class="t-name">{escape(tid)}</span>'
                f'<span class="t-score">{int(entry.get("score", 0.0))}</span>'
                '</span>'
            )
    return "".join(items)


def tag_hue(topic: str) -> int:
    """Stable hue [0, 360) matching the browser tagHue helper."""
    h = 0
    for ch in topic:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % 360


def _article_view(a: dict, source_type_map: dict, writers: dict) -> dict:
    """Normalize article data for both JS and static HTML renderers."""
    src_id = a.get("source_id", "")
    src_type = source_type_map.get(src_id, "blog")
    author = a.get("author", "")
    avatar = ""
    if author:
        w = writers.get(writer_slug(author))
        if w and w.get("photo"):
            avatar = w["photo"]

    snap = None
    if a.get("code_snippet"):
        snap = {
            "label": a.get("snippet_label", ""),
            "code": highlight_kotlin(a.get("code_snippet", "")),
        }

    rollup = None
    if a.get("collapsed_builds"):
        rollup = {
            "summary": a.get("rollup_summary", ""),
            "builds": [
                {
                    "title": b.get("title", ""),
                    "date": _fmt_date(b.get("date", "")),
                    "url": b.get("url", ""),
                }
                for b in a["collapsed_builds"]
            ],
        }

    return {
        "id": a["id"],
        "col": a.get("col", ""),
        "title": a.get("title", ""),
        "url": a.get("url", ""),
        "source": src_id.replace("-", " ").title(),
        "stype": _stype(src_id, src_type),
        "date": _fmt_date(a.get("date", "")),
        "author": author,
        "avatar": avatar,
        "video": youtube_id(a.get("url", "")),
        "paywalled": bool(a.get("paywalled")),
        "topics": a.get("topics", []),
        "summary": a.get("summary") or "",
        "snap": snap,
        "rollup": rollup,
    }


def _render_video_static(video_id: str) -> str:
    if not video_id:
        return ""
    vid = escape(video_id, quote=True)
    return (
        f'<div class="yt-facade" data-yt="{vid}">'
        f'<a class="yt-play" aria-label="Open video on YouTube" '
        f'href="https://www.youtube.com/watch?v={vid}" target="_blank" rel="noopener noreferrer">'
        f'<span class="yt-tri"></span><span class="yt-cap">Watch on YouTube</span></a>'
        f'<a class="yt-ext" href="https://www.youtube.com/watch?v={vid}" '
        f'target="_blank" rel="noopener noreferrer">Open on YouTube</a>'
        f'</div>'
    )


def _render_snapshot_static(snap: dict) -> str:
    if not snap:
        return ""
    return (
        '<div class="snapshot">'
        f'<div class="snap-label">▸ {escape(snap.get("label", ""))}</div>'
        f'<div class="snap-code">{snap.get("code", "")}</div>'
        '</div>'
    )


def _render_rollup_static(rollup: dict) -> str:
    if not rollup:
        return ""
    builds = "".join(
        f'<li><a href="{escape(b.get("url", ""), quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'{escape(b.get("title", ""))}</a><span class="rollup-date">{escape(b.get("date", ""))}</span></li>'
        for b in rollup.get("builds", [])
    )
    n = len(rollup.get("builds", []))
    plural = "" if n == 1 else "s"
    return (
        '<details class="rollup-builds">'
        f'<summary>▸ Also this week · {n} more build{plural}</summary>'
        f'<ul>{builds}</ul></details>'
    )


def _render_comic_static(comic: dict) -> str:
    if not comic:
        return ""
    alt = comic.get("alt", "")
    joke = f'<p class="comic-alt">{escape(alt)}</p>' if alt else ""
    permalink = escape(comic.get("permalink", ""), quote=True)
    img = escape(comic.get("img", ""), quote=True)
    title = escape(comic.get("title", ""))
    source = escape(comic.get("source", ""))
    artist = escape(comic.get("artist", ""))
    return (
        '<section class="comic-interlude">'
        '<div class="comic-kicker">Interlude</div>'
        '<figure class="comic-figure">'
        f'<a href="{permalink}" target="_blank" rel="noopener noreferrer">'
        f'<img class="comic-img" src="{img}" alt="{title}" loading="lazy"></a>'
        '<figcaption class="comic-cap">'
        f'<span class="comic-title">{title}</span>'
        f'<a class="comic-credit" href="{permalink}" target="_blank" rel="noopener noreferrer">'
        f'{source} · {artist}</a>'
        '</figcaption>'
        f'{joke}'
        '</figure>'
        '</section>'
    )


def render_article_card_static(view: dict, id_prefix: str = "static-art") -> str:
    clickable = bool(view.get("url") and view.get("url") != "#")
    url = escape(view.get("url", "#"), quote=True)
    topics = view.get("topics", [])
    tags = "".join(
        f'<span class="tag" style="--tag-h:{tag_hue(t)}">{escape(t)}</span>'
        for t in topics
    )
    byline = ""
    if view.get("author"):
        avatar = ""
        if view.get("avatar"):
            avatar = f'<img class="art-avatar" src="{escape(view["avatar"], quote=True)}" alt="" loading="lazy">'
        byline = f'<span class="art-byline">{avatar}{escape(view["author"])}</span>'
    paywall = (
        '<span class="badge-paywall" title="Member-only story — requires a paid Medium account">🔒 Member-only</span>'
        if view.get("paywalled") else ""
    )
    rollup = view.get("rollup") or {}
    summary = rollup.get("summary") or view.get("summary", "")
    data_url = f' data-url="{url}"' if clickable else ""
    return (
        f'<article class="article {escape(view.get("col", ""))}{" is-clickable" if clickable else ""}" '
        f'id="{escape(id_prefix)}-{escape(view.get("id", ""), quote=True)}" '
        f'data-topics="{escape(",".join(topics), quote=True)}"{data_url}>'
        '<div class="art-meta">'
        f'<span class="source-tag {escape(view.get("stype", ""))}">{escape(view.get("source", ""))}</span>'
        f'{byline}<span class="art-date">{escape(view.get("date", ""))}</span>{paywall}'
        '</div>'
        f'<h3 class="art-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{escape(view.get("title", ""))}</a></h3>'
        f'<p class="art-summary">{escape(summary)}</p>'
        f'{_render_video_static(view.get("video", ""))}'
        f'{_render_snapshot_static(view.get("snap"))}'
        f'{_render_rollup_static(view.get("rollup"))}'
        f'<div class="art-tags">{tags}</div>'
        '</article>'
    )


def _featured_static(views_by_chapter: list, featured_id: str = "") -> tuple:
    feature = views_by_chapter[0]["articles"][0]
    feat_ch = views_by_chapter[0]
    if featured_id:
        for ch in views_by_chapter:
            for article in ch["articles"]:
                if article["id"] == featured_id:
                    return article, ch
    return feature, feat_ch


def _render_cover_static(views_by_chapter: list, featured_id: str = "") -> str:
    feature, feat_ch = _featured_static(views_by_chapter, featured_id)
    secondary = []
    for ch in views_by_chapter:
        if len(secondary) >= 4:
            break
        article = next((a for a in ch["articles"] if a["id"] != feature["id"]), None)
        if article and ch["id"] != feat_ch["id"]:
            secondary.append((article, ch["id"]))
    also = "".join(
        f'<a href="#static-{escape(ch_id, quote=True)}"><span class="n"></span> '
        f'{escape(article["title"])}</a>'
        for article, ch_id in secondary
    )
    return (
        '<section class="pr-page pr-cover static-cover">'
        '<div class="mag-cover-inner">'
        f'<div class="cover-kicker">Cover Story · {escape(feat_ch["label"])}</div>'
        f'{render_article_card_static(feature, "static-cover")}'
        '<div class="also"><span class="lbl">Also inside this issue</span>'
        f'{also}</div>'
        '</div>'
        '</section>'
    )


def build_static_digest(
    chapters: list,
    source_type_map: dict,
    bible: dict,
    featured_id: str = "",
    comics: list = None,
    comic_every: int = 14,
) -> str:
    """Pre-render a readable scroll edition for no-JS readers and crawlers."""
    writers = load_writers()
    views_by_chapter = []
    for ch in chapters:
        views_by_chapter.append({
            "id": ch["id"],
            "label": ch["label"],
            "score": ch["score"],
            "articles": [_article_view(a, source_type_map, writers) for a in ch["articles"]],
        })
    if not views_by_chapter:
        return ""

    trending = sorted(
        [(tid, entry) for tid, entry in bible.items() if not tid.startswith("_")],
        key=lambda x: x[1].get("score", 0.0),
        reverse=True,
    )[:12]
    trend_rows = "".join(
        f'<div class="row"><span>{escape(tid)}</span><span class="sp">{escape(spark_from_history(entry.get("history", [])))}</span></div>'
        for tid, entry in trending
    )
    toc_rows = "".join(
        f'<a class="cat-row pr-jump" href="#static-{escape(ch["id"], quote=True)}">'
        f'<span class="pg">§</span><h3>{escape(ch["label"])}</h3><p>{len(ch["articles"])} stories</p></a>'
        for ch in views_by_chapter
    )
    parts = [
        '<div class="scroll-col static-digest" data-static-digest="1">',
        _render_cover_static(views_by_chapter, featured_id),
        '<section class="pr-page pr-toc static-toc">',
        '<div class="pr-folio"><span class="side">Trending · Contents</span><span class="pg pr-pgnum"></span></div>',
        f'<div class="mag-trend">{trend_rows}</div><div class="pr-cat">{toc_rows}</div>',
        '</section>',
    ]
    comic_index = 0
    articles_since_comic = 0
    comics = comics or []
    if comic_index < len(comics):
        parts.append(f'<section class="pr-page pr-comic">{_render_comic_static(comics[comic_index])}</section>')
        comic_index += 1
    for idx, ch in enumerate(views_by_chapter, start=1):
        parts.append(
            f'<section class="pr-page pr-chapter" id="static-{escape(ch["id"], quote=True)}">'
            f'<div class="pr-folio"><span class="ch-num">§ {idx:02d}</span>'
            f'<h2 class="ch-title">{escape(ch["label"])}</h2><span class="pg pr-pgnum"></span></div>'
            '<div class="mag-arts">'
        )
        for view in ch["articles"]:
            parts.append(render_article_card_static(view))
        parts.append('</div></section>')
        articles_since_comic += len(ch["articles"])
        if articles_since_comic >= comic_every and comic_index < len(comics):
            parts.append(f'<section class="pr-page pr-comic">{_render_comic_static(comics[comic_index])}</section>')
            comic_index += 1
            articles_since_comic = 0
    parts.append('</div>')
    return "\n".join(parts)


def build_data_block(
    edition: str,
    start: date,
    end: date,
    chapters: list,
    bible: dict,
    source_type_map: dict,
    clusters: list,
    comics: list = None,
    comic_every: int = 14,
    featured_id: str = "",
) -> str:
    lines = ["// ══ DATA ════════════════════════════════════════════════════════════════════", ""]

    # Writers registry supplies author photos (null until a source provides one).
    writers = load_writers()

    # FEATURED_ID — pins the cover story to a specific article id; empty falls
    # back to the top-scoring article in the top chapter.
    lines.append("const FEATURED_ID = {};".format(json.dumps(featured_id or "")))
    lines.append("")

    # TOPICS — one entry per cluster (for the filter UI)
    topics_js = ",\n  ".join(
        "{{ id:{}, label:{} }}".format(json.dumps(c["id"]), json.dumps(c["label"]))
        for c in clusters
    )
    lines.append("const TOPICS = [\n  {}\n];".format(topics_js))
    lines.append("")

    # TRENDING_DATA — top 10 non-meta topics by current score
    trending = sorted(
        [(tid, entry) for tid, entry in bible.items() if not tid.startswith("_")],
        key=lambda x: x[1].get("score", 0.0),
        reverse=True,
    )[:20]
    trending_items = []
    for tid, entry in trending:
        sp = spark_from_history(entry.get("history", []))
        score = int(entry.get("score", 0.0))
        trending_items.append(
            "  {{ name:{}, score:{}, spark:{} }}".format(json.dumps(tid), score, json.dumps(sp))
        )
    lines.append("const TRENDING_DATA = [\n" + ",\n".join(trending_items) + "\n];")
    lines.append("")

    # COMICS — interludes: one before the mag, one after every `comic_every` cards
    comic_items = []
    for c in (comics or []):
        comic_items.append(
            "  {{ img:{}, alt:{}, title:{}, permalink:{}, artist:{}, source:{} }}".format(
                json.dumps(c.get("img", "")),
                json.dumps(c.get("alt", "")),
                json.dumps(c.get("title", "")),
                json.dumps(c.get("permalink", "")),
                json.dumps(c.get("artist", "")),
                json.dumps(c.get("source", "")),
            )
        )
    lines.append("const COMICS = [\n" + ",\n".join(comic_items) + "\n];")
    lines.append("const COMIC_EVERY = {};".format(int(comic_every)))
    lines.append("")

    # CHAPTERS
    chapter_blocks = []
    for ch in chapters:
        # use first article's top topic history as chapter spark proxy
        spark = ""
        for a in ch["articles"]:
            for tid in a.get("topics", []):
                if tid in bible:
                    spark = spark_from_history(bible[tid].get("history", []))
                    break
            if spark:
                break

        article_blocks = []
        for a in ch["articles"]:
            view = _article_view(a, source_type_map, writers)
            snap_js = "null"
            if view["snap"]:
                snap_js = "{{ label:{}, code:{} }}".format(
                    json.dumps(view["snap"].get("label", "")),
                    json.dumps(view["snap"].get("code", "")),
                )

            rollup_js = "null"
            if view["rollup"]:
                rollup_js = "{{ summary:{}, builds:{} }}".format(
                    json.dumps(view["rollup"].get("summary", "")),
                    json.dumps(view["rollup"].get("builds", []), ensure_ascii=False),
                )

            topics_js = json.dumps(view["topics"])

            article_blocks.append(
                "      {{ id:{}, col:{},\n"
                "        title:{},\n"
                "        url:{}, source:{}, stype:{}, date:{}, author:{}, avatar:{}, video:{}, paywalled:{},\n"
                "        topics:{},\n"
                "        summary:{},\n"
                "        snap:{},\n"
                "        rollup:{}\n"
                "      }}".format(
                    json.dumps(view["id"]), json.dumps(view["col"]),
                    json.dumps(view["title"]),
                    json.dumps(view["url"]), json.dumps(view["source"]),
                    json.dumps(view["stype"]), json.dumps(view["date"]),
                    json.dumps(view["author"]), json.dumps(view["avatar"]), json.dumps(view["video"]),
                    "true" if view["paywalled"] else "false",
                    topics_js,
                    json.dumps(view["summary"]),
                    snap_js,
                    rollup_js,
                )
            )

        score_int = int(ch["score"])
        chapter_blocks.append(
            "  {{\n"
            "    id:{}, title:{},\n"
            "    topics:[{}], score:{}, spark:{},\n"
            "    articles:[\n"
            "{}\n"
            "    ]\n"
            "  }}".format(
                json.dumps(ch["id"]), json.dumps(ch["label"]),
                json.dumps(ch["id"]), score_int, json.dumps(spark),
                ",\n".join(article_blocks),
            )
        )

    lines.append("const CHAPTERS = [\n" + ",\n".join(chapter_blocks) + "\n];")
    lines.append("")
    return "\n".join(lines)
