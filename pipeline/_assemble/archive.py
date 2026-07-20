"""Edition archive: permanent per-edition pages + a generated index list.

Each assemble run drops a byte-stable copy of the edition under site/editions/,
records it in the committed state/editions.json manifest, and regenerates the
bare site/archive.html list. The archive page reuses design.css and the
masthead wordmark so it matches the magazine.
"""

from datetime import date
from html import escape
from pathlib import Path
import json


def _inject_base(html: str) -> str:
    """Add <base href="../"> so an editions/ copy resolves the same relative
    links (design.css, about.html, archive.html) that index.html uses at root."""
    return html.replace("<head>", '<head>\n  <base href="../">', 1)


def write_edition_copy(html: str, edition: str, editions_dir: Path) -> Path:
    """Write a permanent copy of the rendered edition to editions/{edition}.html."""
    editions_dir.mkdir(parents=True, exist_ok=True)
    out = editions_dir / f"{edition}.html"
    tmp = out.with_suffix(".tmp")
    tmp.write_text(_inject_base(html), encoding="utf-8")
    tmp.rename(out)
    return out


def upsert_manifest(manifest_path: Path, entry: dict) -> list:
    """Insert or replace an edition entry, keep the list newest-first, persist."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = []
    manifest = [e for e in manifest if e.get("edition") != entry["edition"]]
    manifest.append(entry)
    manifest.sort(key=lambda e: e.get("edition", ""), reverse=True)
    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    tmp.rename(manifest_path)
    return manifest


def _fmt_range(start: str, end: str) -> str:
    """'2026-07-06','2026-07-12' -> '06–12 Jul' (or '29 Jun–05 Jul' cross-month)."""
    try:
        s = date.fromisoformat(start[:10])
        e = date.fromisoformat(end[:10])
    except ValueError:
        return ""
    if s.month == e.month:
        return f"{s.strftime('%d')}–{e.strftime('%d %b')}"
    return f"{s.strftime('%d %b')}–{e.strftime('%d %b')}"


def _edition_label(edition: str) -> str:
    return edition.replace("-W", " · W")


_TYPE_LABELS = {
    "blog": "Blogs",
    "conference": "Conferences",
    "changelog": "Changelogs & releases",
    "slack-mirror": "Kotlinlang Slack (topic signal)",
    "discussion": "Discussion",
    "news": "News",
}
_TYPE_ORDER = ["blog", "conference", "changelog", "news", "discussion", "slack-mirror"]


def render_sources(sources: list, out_path: Path) -> None:
    """Render the full source registry (sources.yml) as a grouped, readable page.

    Shows every source the digest pulls from, grouped by type. slack-mirror
    sources are labelled as topic-signal feeds (they inform scoring, not article
    cards) so readers understand why they're listed but never appear as stories.
    """
    by_type: dict = {}
    for s in sources:
        by_type.setdefault(s.get("type", "blog"), []).append(s)

    sections = []
    ordered = _TYPE_ORDER + [t for t in by_type if t not in _TYPE_ORDER]
    for t in ordered:
        items = by_type.get(t)
        if not items:
            continue
        label = escape(_TYPE_LABELS.get(t, t.title()))
        rows = []
        for s in sorted(items, key=lambda x: x.get("name", "").lower()):
            name = escape(s.get("name", s.get("id", "")))
            url = escape(s.get("url", "#"))
            lang = escape((s.get("language") or "").upper())
            bible_only = "" if s.get("render", True) else '<span class="src-note">topic signal only</span>'
            rows.append(
                f'    <a class="src-row" href="{url}" target="_blank" rel="noopener noreferrer">'
                f'<span class="src-name">{name}</span>'
                f'<span class="src-lang">{lang}</span>{bible_only}</a>'
            )
        sections.append(
            f'    <section class="src-group">\n'
            f'      <h2 class="src-h">{label} <span class="src-c">{len(items)}</span></h2>\n'
            + "\n".join(rows) + "\n    </section>"
        )
    body = "\n".join(sections) if sections else '    <p class="src-empty">No sources registered.</p>'

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kotlin Digest — Sources</title>
  <script>if(document.cookie.match(/kd_reader=[^;]*%22theme%22%3A%22night%22/)||document.cookie.indexOf('kd_night=1')>=0)document.documentElement.dataset.night='1';</script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="design.css">
  <style>
    body {{ min-height: 100vh; }}
    .src-wrap {{ max-width: 760px; margin: 0 auto; padding: 3rem 1.5rem 4rem; }}
    .src-head {{ border-bottom: 3px double var(--ink); padding-bottom: 1rem; margin-bottom: 1.6rem; }}
    .src-head .site-logo {{ height: 44px; }}
    .src-kicker {{ font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-muted); margin-top: 0.6rem; }}
    .src-intro {{ font-family: 'DM Sans', sans-serif; font-size: 0.82rem; color: var(--ink-mid); margin: 0.9rem 0 1.8rem; line-height: 1.6; }}
    .src-intro a {{ color: var(--blue); text-decoration: none; }}
    .src-group {{ margin-bottom: 1.8rem; }}
    .src-h {{ font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-muted); border-bottom: 1px solid var(--rule); padding-bottom: 0.4rem; margin-bottom: 0.3rem; }}
    .src-h .src-c {{ color: var(--accent); margin-left: 0.35rem; }}
    .src-row {{ display: flex; align-items: baseline; gap: 0.7rem; padding: 0.55rem 0.25rem; border-bottom: 1px solid var(--rule); text-decoration: none; color: var(--ink); }}
    .src-row:hover {{ background: var(--focus-tint); }}
    .src-name {{ font-family: 'Charter', 'Bitstream Charter', Georgia, serif; font-size: 0.95rem; flex: 1; }}
    .src-lang {{ font-family: 'JetBrains Mono', monospace; font-size: 0.55rem; color: var(--ink-muted); }}
    .src-note {{ font-family: 'JetBrains Mono', monospace; font-size: 0.55rem; color: var(--accent-dim); }}
    .src-foot {{ margin-top: 2rem; font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; }}
    .src-foot a {{ color: var(--blue); text-decoration: none; }}
  </style>
</head>
<body>
  <div class="src-wrap">
    <header class="src-head">
      <svg class="site-logo" viewBox="0 0 91 44" xmlns="http://www.w3.org/2000/svg" aria-label="Kotlin Digest">
        <text x="0" y="40" font-family="'JetBrains Mono',monospace" font-size="40" font-weight="600" fill="var(--ink)">K</text>
        <text x="34" y="22" font-family="'JetBrains Mono',monospace" font-size="8.5" font-weight="600" fill="var(--ink)" letter-spacing="2">OTLIN</text>
        <text x="34" y="37" font-family="'JetBrains Mono',monospace" font-size="8.5" font-weight="400" fill="var(--ink-muted)" letter-spacing="2">DIGEST</text>
      </svg>
      <div class="src-kicker">Sources · {len(sources)} feeds</div>
    </header>
    <p class="src-intro">Every feed the digest scouts to assemble each edition. Blogs, conferences and changelogs become story cards; the Kotlinlang Slack channels feed topic signal into the scoring bible and never appear as articles. The registry is open — <a href="https://github.com/cicerohellmann/kotlin-digest/blob/main/sources/sources.yml" target="_blank" rel="noopener noreferrer">propose a source</a>.</p>
{body}
    <div class="src-foot"><a href="index.html">← Latest edition</a> · <a href="archive.html">Archive</a></div>
  </div>
</body>
</html>
"""
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(page, encoding="utf-8")
    tmp.rename(out_path)


def render_archive(manifest: list, out_path: Path) -> None:
    """Render the bare newest-first archive list to site/archive.html."""
    rows = []
    for i, e in enumerate(manifest):
        ed = escape(e.get("edition", ""))
        label = escape(_edition_label(e.get("edition", "")))
        rng = escape(_fmt_range(e.get("start", ""), e.get("end", "")))
        n = e.get("articles", 0)
        latest = '<span class="latest">latest</span>' if i == 0 else ""
        rows.append(
            f'    <a class="ed-row" href="editions/{ed}.html">'
            f'<span class="ed-label">{label}</span>'
            f'<span class="ed-range">{rng}</span>'
            f'<span class="ed-count">{n} articles{latest}</span></a>'
        )
    rows_html = "\n".join(rows) if rows else '    <p class="ed-empty">No editions yet.</p>'

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kotlin Digest — Archive</title>
  <script>if(document.cookie.match(/kd_reader=[^;]*%22theme%22%3A%22night%22/)||document.cookie.indexOf('kd_night=1')>=0)document.documentElement.dataset.night='1';</script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="design.css">
  <style>
    body {{ min-height: 100vh; }}
    .arch-wrap {{ max-width: 720px; margin: 0 auto; padding: 3rem 1.5rem 4rem; }}
    .arch-head {{ border-bottom: 3px double var(--ink); padding-bottom: 1rem; margin-bottom: 1.6rem; }}
    .arch-head .site-logo {{ height: 44px; }}
    .arch-kicker {{ font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-muted); margin-top: 0.6rem; }}
    .ed-row {{ display: flex; align-items: baseline; gap: 1rem; padding: 0.85rem 0.25rem; border-bottom: 1px solid var(--rule); text-decoration: none; color: var(--ink); }}
    .ed-row:hover {{ background: var(--focus-tint); }}
    .ed-label {{ font-family: 'JetBrains Mono', monospace; font-weight: 600; font-size: 0.9rem; flex: 0 0 auto; min-width: 6.5rem; }}
    .ed-range {{ font-family: 'DM Sans', sans-serif; font-size: 0.8rem; color: var(--ink-mid); flex: 1; }}
    .ed-count {{ font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; color: var(--ink-muted); flex: 0 0 auto; }}
    .latest {{ margin-left: 0.6rem; padding: 0.1rem 0.4rem; border-radius: 3px; background: var(--accent); color: #fff; letter-spacing: 0.06em; }}
    .ed-empty {{ color: var(--ink-muted); font-family: 'DM Sans', sans-serif; }}
    .arch-foot {{ margin-top: 2rem; font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; }}
    .arch-foot a {{ color: var(--blue); text-decoration: none; }}
  </style>
</head>
<body>
  <div class="arch-wrap">
    <header class="arch-head">
      <svg class="site-logo" viewBox="0 0 91 44" xmlns="http://www.w3.org/2000/svg" aria-label="Kotlin Digest">
        <text x="0" y="40" font-family="'JetBrains Mono',monospace" font-size="40" font-weight="600" fill="var(--ink)">K</text>
        <text x="34" y="22" font-family="'JetBrains Mono',monospace" font-size="8.5" font-weight="600" fill="var(--ink)" letter-spacing="2">OTLIN</text>
        <text x="34" y="37" font-family="'JetBrains Mono',monospace" font-size="8.5" font-weight="400" fill="var(--ink-muted)" letter-spacing="2">DIGEST</text>
      </svg>
      <div class="arch-kicker">Archive · every edition</div>
    </header>
{rows_html}
    <div class="arch-foot"><a href="index.html">← Latest edition</a></div>
  </div>
</body>
</html>
"""
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(page, encoding="utf-8")
    tmp.rename(out_path)
