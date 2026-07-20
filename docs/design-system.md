# Kotlin Digest — Design System (Atomic)

The digest is an **editorial / magazine** interface: warm paper, ink, and a
single hot accent; a serif for reading, a monospace for labels/UI, a display
italic for mastheads. This document organises the whole UI into Brad Frost's
five layers — **atoms → molecules → organisms → templates → pages** — so every
piece has one name, one home, and one reason to change.

Living reference: **`site/styleguide.html`** renders each layer with the real
tokens and fonts. Change a token, both the reader and the style guide move
together.

> **Source of truth for tokens:** `site/design.css`. Component styles currently
> live in `site/template.html`'s `<style>` block; the roadmap (bottom) extracts
> them into a layered `components.css` so the style guide and the reader share
> one stylesheet. Until then, keep the two in sync.

---

## 0. Foundations (tokens)

### Colour — `site/design.css`
Light is the default; `html[data-night="1"]` swaps the same token names.

| Token | Light | Role |
|---|---|---|
| `--paper` | `#F3EDE2` | page background |
| `--paper-b` | `#E8DFCE` | raised surfaces (panels, chips, arrows) |
| `--ink` | `#1C1B18` | primary text |
| `--ink-mid` | `#3A3830` | body / secondary text |
| `--ink-muted` | `#6B6457` | labels, meta, captions |
| `--rule` | `#C9BFB0` | hairlines, borders |
| `--chip-bg` | `#E5DDD0` | topic-tag fill |
| `--accent` | `#E06020` | THE hot accent — kickers, active states, section numbers |
| `--accent-dim` | `#8B3608` | accent on hover / sparks |
| `--blue` | `#1A4A8C` | links |
| `--green` | `#2A6049` | changelog source-tag |
| `--focus-tint` / `--exclude-tint` | `#FFF4E6` / `#EEF2FF` | filter-mode wash |
| `--code-bg` / `--code-text` | `#18171A` / `#D4CFC6` | code snapshot |

Rule: **one accent.** Orange carries emphasis; blue is reserved for links;
green only marks changelog sources. Never introduce a fourth hue.

### Type
| Family | Role | Notes |
|---|---|---|
| **Charter** (serif) | reading — summaries, decks, contents | `--read-font` lets readers swap it |
| **JetBrains Mono** | UI chrome — labels, tags, meta, buttons, kickers | uppercase + letter-spacing for labels |
| **DM Sans** | small sans meta (source lists, dates in places) | supporting only |
| **Playfair Display** (italic) | display — chapter titles, comic titles | never for body |

Reader scale: `--read-scale` (S 0.92 / M 1 / L 1.12) multiplies reading sizes.

### Motion
Page turns `0.34–0.42s cubic-bezier(.33,0,.2,1)`; micro-interactions `0.12–0.15s`.
Respect `prefers-reduced-motion` (the pager already does).

### Spacing / radius
Rhythm in `rem`; card gaps `0.8rem`; radii small (`2–4px`) — this is print, not
a soft app.

---

## 1. Atoms

The smallest styled elements. Cannot be broken down without losing meaning.

| Atom | Class | Notes |
|---|---|---|
| Source tag | `.source-tag` (+`.official` blue, `.changelog` green) | mono, bordered pill |
| Topic tag | `.tag` | chip-bg, lowercase topic id |
| Filter chip | `.chip` (+`.focus-chip`/`.exclude-chip`/`.kw-chip`) | active-filter token |
| Paywall badge | `.badge-paywall` | 🔒 member-only |
| Kicker | `.comic-kicker`, `.cover-kicker` | accent, uppercase, tracked |
| Label | `.snap-label`, `.filter-toggle-label`, `.set-label` | mono micro-label |
| Date | `.art-date` | mono muted |
| Reading title | `.art-title` | Charter, scales with `--read-scale` |
| Reading body | `.art-summary` | `--read-font`, scales |
| Display title | `.ch-title`, `.comic-title` | Playfair italic |
| Wordmark | `.site-logo` | the K·OTLIN DIGEST SVG lockup |
| Rule | `border` on `--rule` | hairline / `3px double` masthead rule |
| Buttons | `.mode-btn`, `.seg button`, `.settings-btn`, `.reset-btn`, `.pr-arrow` | mono, bordered, accent when active |

## 2. Molecules

Small groups of atoms working as a unit.

| Molecule | Class | Composed of |
|---|---|---|
| Article meta row | `.art-meta` | source-tag + date + paywall badge |
| Comic caption | `.comic-cap` | comic-title + comic-credit |
| Segmented control | `.seg` | 2–4 `button` atoms, one `.active` |
| Settings row | `.set-row` | set-label + `.seg` |
| Filter toggle | `.filter-toggle` | label + `.mode-switcher` + count + chevron |
| Keyword field | `.kw-field` | label + text input |
| Masthead meta | `.masthead-meta` | edition + date + counts + Archive link |
| Trending row | `.ticker-item` / `.t-name`+`.t-score`+`.t-spark` | topic + score + sparkline |
| Folio header | `.pr-folio` | section number + title + page number |
| Also-inside teaser | `.also a` | page-ref + article title |

## 3. Organisms

Distinct, self-contained sections — the recognisable "things" on the page.

| Organism | Class | Contains |
|---|---|---|
| **Article card** | `.article` | art-meta + art-title + art-summary + `.snapshot`? + `.rollup`? + `.art-tags` |
| Code snapshot | `.snapshot` | snap-label + `.snap-code` (Pygments-highlighted) |
| Changelog rollup | `.rollup` | digest body (now the card body) + `.rollup-builds` details |
| Comic interlude | `.comic-interlude` | kicker + `.comic-figure` (img + caption + alt) |
| Cover | `.mag-cover-inner` | cover-kicker + featured `.article` + `.also` teasers |
| Masthead | `.masthead` | wordmark + masthead-meta + tagline + stats + ⚙ |
| Trending ticker | `.ticker-wrap` | label + scrolling `.ticker-track` of trending rows |
| Filter bar | `.filter-bar` | filter-toggle + `.filter-panel` (mode + topic checks + keyword rows) |
| Settings panel | `.settings-panel` | 4 `.set-row`s (theme / font / size / layout) |
| Contents | `.pr-toc` | trending list + chapter catalog (`.cat-row`) |

## 4. Templates

Page-level structure — the skeleton that arranges organisms; content-agnostic.

| Template | Where | Structure |
|---|---|---|
| **Paged reader** | `renderPager` | fixed-height `#digest`; `.pr-screen` → `.pr-page` (measure-to-fit); `.pr-arrow` / `.pr-indicator` chrome |
| **Scroll reader** | `renderScroll` | `.scroll-col` single column of the same blocks, no pagination |
| Archive | `render_archive` | wordmark head + edition rows |
| Sources | `render_sources` | wordmark head + type-grouped feed list |
| About | `about.html` | static editorial page |

Above the reader templates sits the **shell**: `.ticker-wrap` + `.masthead` +
`.filter-bar` as fixed chrome. *(This shell is the target of the planned
reader refactor — see the flip/headerless work.)*

## 5. Pages

Templates filled with a real edition.

- **Edition** — `site/index.html` (latest) and `site/editions/{edition}.html`.
- Pages are build artifacts from `pipeline/assemble.py`; never hand-edit.

---

## Naming conventions

Prefixes signal the organism/template a class belongs to:

- `pr-*` — paged reader (screen, page, folio, arrow, indicator, turn, leaf)
- `mag-*` — magazine layout blocks (cover, arts, folio)
- `comic-*` — comic interlude
- `filter-*` / `kw-*` / `mode-*` — filter bar
- `settings-*` / `seg` / `set-*` — settings panel
- `rollup-*` — changelog rollup
- `art-*` / `.article` — article card
- `ch-*` / `t-*` — chapter / trending bits

New components follow the same pattern: prefix by owning organism.

---

## Roadmap (to make this "well-defined")

1. **Extract component CSS** from `template.html`'s inline `<style>` into a
   layered `site/components.css` (`/* atoms */ /* molecules */ /* organisms */`),
   imported by both the reader template and `styleguide.html`. One source of
   truth; the style guide can never drift.
2. **Shell as an organism** — treat masthead/ticker/filter as a composable shell
   so the reader refactor (masthead-as-page-1-content for seamless flips) is a
   clean organism swap, not a special case.
3. **Token audit** — confirm every colour used resolves to a token (no literals
   in components) so night mode and future themes are total.
