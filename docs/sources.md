# Source Health Tracking

## The problem

Web sources go stale. Blogs get abandoned. Conference sites only update annually. We need to know which sources are alive, which are slowing down, and which should be removed — without a human manually checking them.

## Key insight

We do not detect staleness by diffing HTML. We detect it by **comparing the date of the most recent article against the source's expected cadence**.

A blog that publishes monthly is not stale after 3 weeks. A news site that hasn't published in 3 days probably has a problem. Each source carries its own `cadence_days` value so the health engine knows what "normal" looks like per source.

---

## Health states

| State | Condition | Action |
|---|---|---|
| `active` | `days_since_last <= cadence_days * 1.5` | Normal ingestion |
| `slowing` | `<= cadence_days * 3` | Ingest, warn in dashboard |
| `stale` | `<= cadence_days * 6` | Ingest if found, flag for review |
| `dead` | `> cadence_days * 6` | Skip ingestion, open issue automatically |

When a source reaches `dead`, the scout workflow opens a GitHub Issue titled `[source] kotlin-blog appears dead — review needed` with the last-seen date and link. Contributors can then PR a removal or replacement.

---

## Source record schema

`state/source_health.json`:

```json
{
  "kotlin-blog": {
    "last_article_date": "2026-07-03",
    "last_checked": "2026-07-05T06:12:00Z",
    "cadence_days": 7,
    "days_since_last": 2,
    "health": "active",
    "articles_last_30d": 9,
    "articles_last_7d": 2,
    "consecutive_empty_cycles": 0
  }
}
```

`consecutive_empty_cycles` — how many daily scout runs found zero new articles. This catches sources where the site is live but publishing has stopped (no 404, but no content either).

---

## Article date detection strategies

Not all sources provide clean dates. Detection in priority order:

1. **RSS `<pubDate>` or `<dc:date>`** — most reliable, use when available
2. **OpenGraph `article:published_time`** — common in modern blog platforms
3. **JSON-LD `datePublished`** — structured data, very reliable when present
4. **HTML `<time datetime="...">` tags** — common in editorial CMS platforms
5. **URL date pattern** — e.g. `/2026/07/03/article-title` — rough but usable
6. **Heuristic: newest entry in `<article>` list** — fallback for conference sites

If no date is detectable, the article is ingested but flagged `date_uncertain: true` and not used to update the source's `last_article_date`.

---

## Source types and ingestion strategy

### `blog`
- Primary: RSS feed
- Fallback: scrape article list page, extract titles + dates + links
- AI summarization: yes

### `news`
- Primary: RSS feed (most Android news sites have one)
- High cadence: ingest only articles newer than 24h to avoid flooding
- AI summarization: yes (but shorter — news is already short)

### `conference`
- Irregular cadence: ingest talk titles + abstracts when schedule published
- Treat each talk as an article
- `cadence_days` set high (e.g. 180) — annual conferences shouldn't be flagged stale

### `youtube`
- Primary: YouTube channel Atom feed (`https://www.youtube.com/feeds/videos.xml?channel_id=...`)
- Used for official, team, conference, and individual channels that publish original Kotlin, Android, KMP, or Compose videos
- Treat each new video as an article-like record with `media_type: video`, `video_id`, title, date, and feed description
- Renderable in the weekly digest with a no-cookie click-to-load embed facade
- Avoid playlist roundups, repost channels, and channels that mostly curate other people's videos

### `slack-mirror`
- Requires a public Slack export or mirror service
- Ingested as topic signals only (not as full articles)
- Does not generate article summaries — only boosts topic bible scores
- Examples: Kotlin Slack `#general`, `#multiplatform`, `#compose` channels via public archive

---

## Initial source list

See `sources/sources.yml` — a curated baseline to start. Community PRs add more.

Categories in the initial list:
- JetBrains / Kotlin official channels
- Android Developers blog
- Major Android/Kotlin developer blogs (Philipp Lackner, ProAndroidDev, etc.)
- KotlinConf talk archives
- Droidcon talk archives
- Key library changelogs (Compose, Hilt, Ktor, Room, etc.)
- Kotlin Slack public mirrors (if available)
