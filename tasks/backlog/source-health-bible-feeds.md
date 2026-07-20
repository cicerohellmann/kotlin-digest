# Fix source health for bible-only (render:false) sources

**Filed:** 2026-07-20
**Priority:** medium — health-tracking correctness, no reader-facing impact

## Problem

`compute_health` in `pipeline/scout.py` judges every source by
`last_article_date` + article cadence (active → slowing → stale → dead). This is
wrong for `render: false` sources (slack mirrors, reddit): they feed **word/term
mentions into the topic bible for scoring**, not dated articles. A quiet-but-
alive channel still contributes mention signal, but with no fresh "article" it
wrongly flips to `dead`/`stale`.

Observed 2026-07-20: a local scout run marked 8 sources dead
(reddit-kotlin + 7 slack channels). All returned HTTP 200 and load fine in a
browser — the URLs are healthy. The "dead" flag was a category error, so
`state/source_health.json` was deliberately left out of commit `879db2b`.

See memory `slack-sources-bible-wordfeed`.

## Fix direction

For `render: false` sources, base health on **fetch success / mention
contribution this cycle**, not article recency — or skip the stale/dead states
for them entirely. Article-feed sources keep the current cadence model.

## Acceptance criteria

- [ ] `compute_health` distinguishes `render:false` (bible-feed) sources from
      article sources
- [ ] Bible-feed sources are not marked `stale`/`dead` purely from article-date
      gaps; health reflects whether the fetch succeeded / mentions were ingested
      this cycle
- [ ] A scout run where slack/reddit fetch OK but yield no dated articles leaves
      those sources in a healthy state
- [ ] Article-feed sources retain the existing cadence-based health behavior
      (no regression)
- [ ] Re-run scout locally; confirm the 8 previously-flagged sources are no
      longer `dead`, then commit a corrected `state/source_health.json`
