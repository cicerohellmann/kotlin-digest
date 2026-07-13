# Bench Reddit as article source + general "openable URL" gate

**Date:** 2026-03-21
**Status:** approved

## Problem

Reddit posts render as full articles with summaries, but (a) the summarizer's
bot user-agent gets a 403 challenge from Reddit — it never reads the live page,
and (b) for Reddit link/discussion posts the RSS `excerpt` is boilerplate
(`submitted by /u/... [link] [comments]`), so the model fabricated plausible
detail from the title alone. `sources.yml` already documents Reddit as
"topic signal only, not an article source" — that intent was lost.

## Design

### 1. Reddit renders never, signals always
- Add `render: false` to the two Reddit entries in `sources/sources.yml`.
- `bible.py` is **untouched** — it derives topic signal from each article's
  `title + excerpt` independently, so Reddit keeps feeding topic scores.
- `summarize.py` skips `render: false` sources (no wasted Claude calls, no
  fabrication risk).
- `assemble.py` `filter_articles` excludes articles whose source has
  `render: false`. This is the real render gate and also drops the ~50
  already-summarized Reddit posts without editing state.

Rationale for an explicit flag over gating on `type: discussion`: decouples
"what kind of source" from "should it render" — the exact conflation that
caused the bug.

### 2. General fetch-verification gate (all sources)
In `summarize.py`, before queueing an article for summarization, require usable
content: a real fetched body **or** a substantive `excerpt` (≥ 80 words, matching
the existing fetch heuristic). If it has neither:

- **Definitive empty read** (page fetched but body was `[no content extracted]`
  or too short, and the excerpt is thin) → flag a dedicated `unfetchable = true`
  (reason `no-content`) and never summarize it.
- **Transient fetch error** (`[fetch error: ...]` — timeout / reset / one-off
  5xx) → skip this run only, persist nothing, so a later run retries. Mirrors
  `vet.py`'s "transient never changes state" rule; a network blip must not
  bench a good article forever.

`filter_articles` excludes `unfetchable` (alongside `dead` / `low_quality`), so
it never renders. Kills "summarize from the title" universally.

A dedicated flag is used rather than `low_quality` because `vet.py --apply`'s
reconcile logic clears any `low_quality` flag it didn't set itself, which would
un-hide these articles on the next vet run.

### 3. Regenerate W28
1. `vet.py --edition 2026-W28 --apply` (catches non-Reddit no-content articles).
2. `assemble.py --edition 2026-W28` → new `site/index.html`, no Reddit.
3. Commit/publish left to the user.

## Out of scope
- `scout.py` keeps ingesting Reddit for bible signal.
- If Reddit's `.rss` gets bot-blocked in CI, signal quietly stops — noted, not fixed.
- Reddit OAuth (would restore real reading + deletion detection) — future.
