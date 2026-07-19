# Edition Archive — Design

## Problem

Each `assemble.py` run overwrites `site/index.html`. Publishing a new edition
destroys the previous one — no history is browsable on the site. Only
`2026-W28` exists today.

## Goal

Preserve every published edition at a stable URL and expose a plain,
auto-generated archive list, reachable from a link in the masthead meta block.

## Non-goals

- No per-volume blurbs, covers, or thumbnails (bare list only).
- No pagination or search — a flat newest-first list is enough for now.
- No change to the scout/bible/summarize stages.

## Architecture

### 1. Permanent edition pages

After rendering, `assemble.py` writes the edition HTML to **two** paths:

- `site/index.html` — the latest edition (unchanged behavior).
- `site/editions/{edition}.html` — a byte-identical permanent copy
  (e.g. `site/editions/2026-W28.html`).

Both are produced from the same rendered `html` string via the existing
`write_atomic` helper. `site/editions/` is created if absent.

Internal links inside an edition page (`about.html`, `archive.html`,
`design.css`) must resolve from the `site/editions/` subdirectory. Options
checked during implementation: either the template already uses root-relative
or `../`-safe paths, or the edition copy gets a `<base href="../">` injected.
Chosen approach: **inject `<base href="../">`** into the `editions/` copy only,
so the same relative links used by `index.html` resolve one level up. The
canonical `index.html` copy is written without the base tag.

### 2. Committed manifest — `state/editions.json`

New committed JSON, following the existing `state/*.json` audit-trail pattern.
Shape:

```json
[
  { "edition": "2026-W28", "start": "2026-07-06", "end": "2026-07-12",
    "articles": 27, "sources": 8 }
]
```

`assemble.py` reads it, upserts the current edition (replace on matching
`edition` key, else append), sorts newest-first by `edition`, writes it back.
`articles` = placed-article count already computed as `total_arts`. `sources`
= distinct source count in the rendered edition.

### 3. Generated archive page — `site/archive.html`

`assemble.py` regenerates `archive.html` from the manifest on every run. Bare
list, newest first, one row per edition:

```
2026 · W28   06–12 Jul   27 articles
```

Each row links to `editions/{edition}.html`. The page reuses `design.css` and
the masthead wordmark SVG for visual consistency (per the design-system rule —
JetBrains Mono / DM Sans / Charter, no invented fonts). A dedicated renderer
function builds it from the manifest list; no template placeholder juggling.

### 4. Masthead link — `template.html`

Add an `Archive` link to the masthead-meta block (currently lines 885–889,
by the `N articles · M sources` line):

```html
<div><a href="archive.html">Archive →</a></div>
```

Styled to match the existing muted meta text. This ships in `template.html`,
so every future edition (and the next `index.html`) carries the link.

### 5. Backfill W28

One-time: copy the current `site/index.html` to `site/editions/2026-W28.html`
(with the `<base href="../">` injection) and seed `state/editions.json` with the
W28 entry, so the archive is non-empty on first publish. Because the masthead
link is added to the template but the *existing* `index.html` was rendered
before this change, re-run `assemble.py --edition 2026-W28` to regenerate
`index.html` + its edition copy + `archive.html` from the updated template in
one pass, rather than hand-patching the frozen HTML.

## Data flow

```
assemble.py --edition E
  render html
  write site/index.html                     (as today)
  write site/editions/E.html                 (+ <base href="../">)
  upsert state/editions.json                 (E, dates, counts)
  render site/archive.html  <-- from manifest
```

## New / changed files

| File | Change |
|---|---|
| `pipeline/assemble.py` | write edition copy, upsert manifest, render archive |
| `pipeline/_assemble/archive.py` (new) | `write_edition_copy`, `upsert_manifest`, `render_archive` |
| `site/template.html` | Archive link in masthead-meta |
| `site/archive.html` (new, generated) | bare edition list |
| `site/editions/*.html` (new, generated) | permanent per-edition copies |
| `state/editions.json` (new, committed) | edition manifest |

Archive/manifest logic lives in a new `pipeline/_assemble/archive.py` so
`assemble.py`'s `main()` stays a thin orchestrator, matching the existing
`_assemble/` module split (`dates`, `scores`, `articles`, `render`, `comics`).

## Testing / verification

- Run `assemble.py --edition 2026-W28`; confirm `index.html`,
  `editions/2026-W28.html`, `archive.html`, and `state/editions.json` all
  written.
- Open `archive.html` in a browser: one W28 row, links to the edition page.
- Open `editions/2026-W28.html`: renders identically to `index.html`, and its
  `about.html` / `design.css` / `archive.html` links resolve (via `<base>`).
- Simulate a second edition (temp manifest entry) to confirm newest-first
  ordering and that the older edition page is untouched.

## Risks

- **Relative-link breakage** in `editions/` copies — mitigated by the
  `<base href="../">` injection; verified by opening an edition page directly.
- **Manifest drift** if an edition is re-assembled — upsert-by-edition-key makes
  re-runs idempotent (replace, not duplicate).
