# System Architecture

## Overview

The pipeline runs in two cadences:

- **Daily (automated)** — GitHub Actions scouts sources, updates the topic bible, ingests new articles
- **On-demand (manual)** — a human triggers the edition publish workflow, which assembles and deploys to GitHub Pages

Nothing requires a server. State lives in the repo as committed JSON/YAML files.

---

## Stage 1 — Source Registry

`sources/sources.yml` is the single source of truth for what gets scouted. Community members open PRs to add or remove sources. Each entry records:

```yaml
- id: kotlin-blog
  name: "Kotlin Blog"
  url: "https://blog.jetbrains.com/kotlin/"
  rss: "https://blog.jetbrains.com/kotlin/feed/"
  type: blog          # blog | news | conference | video | slack-mirror
  language: en
  cadence_days: 7     # expected publish interval — used to compute staleness
  topics: [kotlin, language, jetbrains]   # editorial hints, not exclusive
```

Source types:
- `blog` — RSS preferred, date-based article detection
- `news` — high-cadence, may need custom scraper
- `conference` — periodic, talk titles + abstracts
- `video` — YouTube channel RSS, real upload dates and metadata
- `slack-mirror` — digest exports or public Slack archives

---

## Stage 2 — Scout Engine

The scout checks each source using **publication date**, not HTML diff:

```
for each source:
  1. fetch RSS feed OR scrape article list
  2. find articles published after last_seen_date
  3. for each new article: store {title, url, date, excerpt, source_id}
  4. update source health: last_seen_date, article_count_this_cycle
```

### Source health

Each source accumulates a health record:

```json
{
  "id": "kotlin-blog",
  "last_article_date": "2026-07-03",
  "cadence_days": 7,
  "days_since_last": 2,
  "health": "active",
  "articles_last_30d": 5
}
```

Health states:
- `active` — last article within `cadence_days * 1.5`
- `slowing` — within `cadence_days * 3`
- `stale` — within `cadence_days * 6`
- `dead` — beyond that — flagged for contributor review

Health state is committed to `state/source_health.json` daily. Dashboard surfaces dead/stale sources so someone can open a PR to remove them.

---

## Stage 3 — Topic Bible

`topics/topics.yml` seeds the bible with a curated baseline. The bible itself lives in `state/bible.json`:

```json
{
  "kotlin": {
    "score": 142.7,
    "mentions_today": 18,
    "history": [
      {"date": "2026-07-04", "mentions": 18, "score": 142.7},
      {"date": "2026-07-03", "mentions": 12, "score": 133.1}
    ]
  }
}
```

### Scoring model

Each day:

1. **Ingestion boost** — for every article mentioning a topic: `score += weight` where weight depends on source type (conference > changelog > video > blog > news)
2. **Decay** — after boost: `score = score * decay_factor` (e.g. `0.92` daily → a score halves in ~8 days without new mentions)
3. **Emergence** — if an AI-extracted term is not in the bible but appears in ≥3 articles in one cycle, it's added automatically with a note that it's unvetted

This makes the bible a real-time barometer: what's trending resists decay because it keeps getting boosted; what's fading loses to decay without new fuel.

### Topic graph

`state/bible.json` history is the raw data. The site renders per-topic sparklines (7-day volume bars) inline next to article tags.

---

## Stage 4 — AI Aggregator

For each new article:

1. **Fetch full content** (or use RSS description if sufficient)
2. **Summarize** via Claude — target 3–5 sentences: what it is, what's new, why it matters
3. **Tag** — match content against top-N bible topics (semantic match, not just keyword)
4. **Score signal** — compute a placement score: `sum(bible_score for matched_topics)`

Output per article:
```json
{
  "title": "Kotlin 2.2 K2 compiler — what changes",
  "url": "...",
  "source": "kotlin-blog",
  "date": "2026-07-03",
  "summary": "...",
  "topics": ["kotlin", "k2-compiler", "performance"],
  "placement_score": 387.4,
  "implementation_snapshot": "..."
}
```

`implementation_snapshot` — for library/API change articles, Claude is prompted to extract the MVP of how the implementation changes (before/after code snippet if available).

---

## Stage 5 — Chapter Assembler

Articles are grouped into chapters by topic cluster. Chapter order is determined by the aggregate bible score of its topics.

Example chapter order for a given edition:
1. **Kotlin Core** (k2, language, coroutines) — score 890
2. **Compose** (compose, animation, state) — score 710
3. **KMP** (multiplatform, ios-interop, gradle) — score 540
4. **Libraries** (hilt, koin, ktor, retrofit) — score 420
5. **Android Platform** (api-35, permissions, wear) — score 310
6. **Community** (droidcon, kotlinconf, podcast) — score 210

Each chapter gets a brief AI-generated intro summarizing the theme of that week's stories.

---

## Stage 6 — GitHub Pages Site

The assembler writes static HTML to `site/`. GitHub Actions commits and pushes on each publish run.

### Reader preferences (cookies)

All stored client-side. No account, no server session.

```js
// Cookie schema (JSON string, 90-day expiry)
{
  "topics": ["kotlin", "compose", "kmp"],    // topic filter (show only these chapters)
  "sources": ["kotlin-blog", "droidcon"],    // source filter
  "keywords_include": ["gradle", "plugin"],  // only show articles containing these
  "keywords_exclude": ["flutter", "react"],  // hide articles containing these
  "language": "en"
}
```

Losing cookies resets to "show everything" — the default is the full magazine. Preferences are additive filters, never destructive.

### Preference UI

Top of the page: collapsible filter bar. Checkboxes for topic chapters, source list, language. Keyword include/exclude text inputs. "Reset to defaults" button. Changes apply instantly (client-side filter on pre-rendered article list).

---

## State files (committed to repo)

| File | Updated by | Contents |
|---|---|---|
| `state/bible.json` | Daily scout workflow | Topic scores + history |
| `state/source_health.json` | Daily scout workflow | Per-source health + last seen date |
| `state/articles.json` | Daily scout workflow | Ingested articles (rolling 90-day window) |
| `site/` | Publish workflow | Rendered edition HTML |

State files being in the repo means: full audit trail via git history, contributors can inspect the bible evolution, and no external database is needed.

---

## Workflow triggers

```yaml
# .github/workflows/scout.yml
on:
  schedule:
    - cron: '0 6 * * *'   # 06:00 UTC daily

# .github/workflows/publish.yml
on:
  workflow_dispatch:       # manual trigger only
    inputs:
      edition_label:
        description: 'Edition label (e.g. 2026-W27)'
        required: true
```

The scout runs every morning. Publishing is always a human decision.
