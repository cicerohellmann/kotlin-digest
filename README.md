# Kotlin Digest

**Weekly information compiled for Android and Kotlin engineers.**  
Assembled by the community.

---

## What this is

Kotlin Digest scouts the Kotlin and Android official blogs, library releases, conference talks, individual developer writing — and assembles it into a weekly, chapter-structured edition hosted on GitHub Pages.

Chapters are ordered by a living **Topic Bible**: a scored, decaying keyword graph that reflects what the community is actually talking about right now. Topics trending hard this week appear first. Topics fading appear later, or disappear until the discussion picks back up.

The site is a static page. Your reading preferences — which chapters you want, which you don't, which keywords to surface or suppress — are stored in a browser cookie. Lose the cookie, lose nothing important. The default is the full magazine.

This project is entirely open source. The pipeline that generates it, the sources it draws from, the topics it tracks, and the site itself are all in this repository. Everything is a PR.

---

#Read it before contributing a source:

## Editorial philosophy

**We draw from primary sources only.**

A primary source is someone writing their own thoughts: a developer publishing a post-mortem, a library author announcing a release, a conference speaker sharing what they learned, an engineer documenting a pattern they discovered in production. These are people forming opinions and sharing them — raw signal from inside the ecosystem.

We do not ingest newsletters, link roundups, or digest publications — including well-regarded ones. This is a deliberate architectural decision.

Here is why it matters technically: our Topic Bible derives its scores from the content we ingest. If we ingest a newsletter that has already curated this week's Kotlin news, the Bible scores what the newsletter editor decided was important — not what the community actually wrote about. We end up measuring a filter, not the thing being filtered. One newsletter mentioning a topic once carries the same weight as twenty engineers independently writing about it. The signal degrades. The magazine becomes a reflection of other magazines.

**What we look for in a source:**

- Writes original content — analysis, tutorials, announcements, opinions, release notes
- Has an identifiable author or organization
- Publishes with datestamps we can parse
- Has been active within its own cadence in the last 90 days

**What disqualifies a source:**

- Newsletters, roundups, and link aggregators — regardless of quality or reputation
- Sites that primarily re-publish or summarize content from elsewhere without adding original analysis
- Digest-format publications (if you're reading this, you might be one — that's fine, just not a source for us)
- Sites without parseable publication dates, making freshness detection impossible

The goal is to hear the Kotlin and Android ecosystem speak in its own voice. Not to hear it through layers of curation.

---

## Contributing

Every part of this project is a pull request. Here is what you can contribute:

### Add a source

Open `sources/sources.yml` and add an entry:

```yaml
- id: your-source-id         # unique, kebab-case
  name: "Human-readable name"
  url: "https://example.com/"
  rss: "https://example.com/feed/"   # strongly preferred; include if it exists
  type: blog                 # blog | conference | changelog | discussion
  language: en               # ISO 639-1
  cadence_days: 14           # expected publish interval — used to detect staleness
  topics: [kotlin, compose]  # editorial hints; not exclusive
```

Open a PR. In the description, include one sentence on why this source adds something the existing list doesn't.

If the source has an RSS or Atom feed, include it — the pipeline will always prefer a feed over scraping. If it doesn't, include a note on how article dates are detectable on the page.

To test the no-JavaScript fallback locally without touching your normal Chrome
profile, run `make nojs`. It opens `site/index.html` in a temporary Chrome
profile with JavaScript disabled.

### Report a dead source

If a source has gone quiet, open a PR removing it from `sources/sources.yml`. Include the last known article URL and date in the PR description so we have a record.

Alternatively, open an issue. The daily pipeline will eventually flag it automatically, but a human eye catches edge cases — blogs that are technically live but haven't published in a year.

### Add a topic

Open `topics/topics.yml` and add to the seed list or to the appropriate cluster. The pipeline auto-discovers new topics from article content, but curated seeds start with better placement:

```yaml
- id: my-topic
  label: "Human Label"
```

Add it to an existing cluster if it belongs there, or propose a new cluster in the PR description.

### Improve the site

The site lives in `site/index.html` — a single self-contained static page with no build step. CSS, JavaScript, and markup are all in one file so contributors can work on it without setting up a pipeline. Open a PR with before/after screenshots if you're making a visual change.

Internationalization strings live in `site/i18n/`. Adding a new language means copying `en.json`, translating the UI strings, and opening a PR.

### Translate a source

If you know of a high-quality Android or Kotlin source in a language other than English, add it to `sources/sources.yml` with the correct `language:` field. The pipeline groups non-English articles separately. As non-English coverage grows, the site will surface them as parallel editions.

### Change the scoring constants

The Topic Bible's decay rate, source weights, and emergence threshold live in `topics/topics.yml` under `scoring:`. If you have data suggesting different constants would produce a better representation of community activity, open a PR with your reasoning. Include before/after comparisons of topic score evolution if possible.

---

## How the pipeline works

```
sources/sources.yml          — what to scout
topics/topics.yml            — what to track, scoring constants

[Daily: GitHub Actions]
  scout.py    — fetch sources, detect new articles by publication date
  bible.py    — boost topic scores from new articles, apply daily decay
  summarize.py — AI summarization + topic tagging per article
  → commits updated state/ files

[Manual: workflow_dispatch]
  assemble.py — cluster articles into chapters, order by topic score, render HTML
  → deploys site/ to GitHub Pages
```

State files committed to the repo: `state/bible.json`, `state/source_health.json`, `state/articles.json`. Full history is in git. You can look at any past commit and see exactly what the topic scores were on that day.

---

## Reader preferences

The site stores preferences in a browser cookie — no account, no server, no tracking.

```json
{
  "topics": ["kotlin-core", "compose"],
  "keywords_include": ["gradle"],
  "keywords_exclude": ["flutter"],
  "language": "en"
}
```

**FOCUS mode** — select topics to see only those chapters.  
**EXCLUDE mode** — select topics to hide them; the rest of the magazine is unchanged.

Losing the cookie resets to showing everything. No content is ever permanently hidden by default.

---

## Source health

The pipeline tracks how often each source publishes and flags sources that go quiet relative to their own cadence. A blog that publishes monthly is not stale after three weeks. A news feed that hasn't published in four days probably has a problem.

Health states: `active` → `slowing` → `stale` → `dead`.

When a source reaches `dead`, the pipeline opens a GitHub Issue automatically. Anyone can then PR a removal or a replacement.

---

## Language

The digest is English-first. There is no editorial reason for this beyond where the initial contributors are. If a well-maintained source in another language earns enough article volume to merit its own chapter or section, it will get one.

Translations of the site UI are welcome at any point.

---

## License

MIT. Take the pipeline, the site, the structure. Build your own digest for your own community. We only ask that you don't call it Kotlin Digest.

---

## Questions

Open an issue. Or find us in the Kotlin Slack — we're somewhere in `#general` arguing about something.
