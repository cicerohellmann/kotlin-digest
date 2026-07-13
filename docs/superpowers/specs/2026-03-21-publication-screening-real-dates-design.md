# Publication screening: every link is an article, dated by its own page

**Date:** 2026-03-21
**Status:** approved (principle + strict date policy confirmed by user)

## Principle

The source is only how a link is *discovered*. The moment a link is a candidate
for the magazine, it is an article-to-be-published and must meet the same bar as
every other article. No source (Slack, RSS, scrape) may bypass screening, and no
source-specific metadata (e.g. a Slack `sentAt` timestamp) may stand in for a
real article property.

## The date lie (root cause)

`scout_slack_channel` (`scout.py:350–376`) stamps each shared link with
`sentAt` — *when someone pasted it into Slack* — and marks `date_uncertain:
False`. A 3½-year-old arXiv paper mentioned this week thus gets this week's date
and ships in "this past week's" edition. The Slack path already fetches each
link (for `fetch_title`) but discards the real date.

Evidence — resolving the *real* publish date for all 11 Slack links in W28:
**0 of 11 have a detectable publish date** (homepages, a raw `.kt` file,
Wikipedia, YouTube, the arXiv abstract, an issue ticket, shortlinks). Genuine
articles carry publish dates; destinations don't.

## Policy (confirmed)

- The edition window is **exactly this week** — `filter_articles(start, end)`.
  There is no 90-day selection; 90 days is only state retention.
- An article's `date` is **the content's real publish date, read from the page**
  (`extract_date_from_html`: `og:article:published_time` → JSON-LD
  `datePublished` → `<time datetime>` → URL date pattern). Never a mention/post
  timestamp.
- **No verifiable publish date → not published.** This also drops non-article
  destinations for free (they have no publish date), and correctly *keeps* a
  real blog post shared in Slack (it has `og:published_time`).

## Implementation

### Phase 1 — date truth (this change)
- Add `fetch_link_meta(url) -> (title, date, date_uncertain)`: one fetch, reuse
  the soup for both title (existing og:title/`<title>` logic) and
  `extract_date_from_html`.
- Rewire `scout_slack_channel` to use it. Store the **real** date (or `None`)
  and the honest `date_uncertain`. `sent_dt` remains only for incremental
  crawling (which threads to scan), never as the article date.
- No new render gate needed: `filter_articles` already requires
  `a.get("date")` in-window, so `None`/out-of-week dates never render.

### Phase 2 — full screen (next)
A `screen.py` stage applying the same bar to every candidate before assemble:
reachable & readable (not 404/paywall/challenge), is-an-article (not a homepage/
video/source-file/index/ticket), on-topic & substantive, summary grounded in
fetched text. Phase 1's date-truth is the highest-value slice and subsumes most
"is-an-article" cases on its own.

## Out of scope
- Reddit OAuth (separate; already benched signal-only via `render:false`).
- Re-dating already-ingested Slack articles in state — Phase 1 fixes new
  ingests; existing W28 Slack items are handled by regenerating the edition,
  where they now fail the in-window date check once re-dated (or can be dropped
  directly since all 11 have no real date).
