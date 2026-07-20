# Kotlin Digest

AI-assembled Android/Kotlin/KMP developer magazine. Scouts the community, scores topics, assembles editions, publishes to GitHub Pages.

## Project layout

```
sources/sources.yml     — registered sources (community PRs welcome)
topics/topics.yml       — topic bible seed + chapter clusters + scoring constants
state/                  — committed runtime state (bible.json, source_health.json, articles.json)
pipeline/               — Python pipeline: scout → bible → summarize → assemble
site/                   — GitHub Pages output (committed by publish workflow)
docs/                   — architecture and design docs (read these before making changes)
.github/workflows/      — scout.yml (daily cron), publish.yml (manual trigger)
```

## Core docs (read before substantial work)

- `docs/architecture.md` — full 6-stage pipeline, state file schema, workflow triggers
- `docs/topic-bible.md` — scoring model, decay constants, topic emergence rules
- `docs/sources.md` — source health states, date detection strategies, per-type ingestion
- `docs/rollup.md` — protocol for bulky library releases (collapse → digest → display)
- `docs/classifier.md` — code-snippet selection criteria (plain Kotlin; build highlights via Pygments)

## Pipeline stages (implementation order)

1. `pipeline/scout.py` — fetch sources, detect new articles by date, update source health
2. `pipeline/bible.py` — apply mention boosts, decay scores, auto-emerge new topics
3. `pipeline/summarize.py` — Claude API summarization + topic tagging per article
4. `pipeline/assemble.py` — cluster articles into chapters, order by bible score, render HTML

## Tech stack

- Python 3.12, `feedparser`, `httpx`, `BeautifulSoup`
- Claude API (`claude-sonnet-4-6`) for summarization
- GitHub Actions: scout runs daily at 06:00 UTC; publish is manual (`workflow_dispatch`)
- GitHub Pages: static HTML, reader preferences in cookies (no server)
- State stored as JSON committed to repo — full audit trail via git history

## State files

| File | Contents |
|---|---|
| `state/bible.json` | Topic scores + 90-day history |
| `state/source_health.json` | Per-source health, last seen date, cadence |
| `state/articles.json` | Ingested articles (rolling 90-day window) |

## Reader preferences (cookies)

```json
{
  "topics": ["kotlin", "compose"],
  "sources": ["kotlin-blog"],
  "keywords_include": ["gradle"],
  "keywords_exclude": ["flutter"],
  "language": "en"
}
```

Losing cookies = show everything (safe default). Preferences are additive filters only.

## Scoring constants

- `decay_factor: 0.92` — score halves in ~8 days without new mentions
- Source weights: conference 3.0, changelog 2.5, blog 2.0, news 1.5, slack-mirror 1.0
- Auto-emergence threshold: 3 articles in one cycle

## Secrets required (GitHub repo settings)

- `ANTHROPIC_API_KEY` — for Claude summarization
- `GITHUB_TOKEN` — auto-provided by Actions for issue creation and Pages deploy
