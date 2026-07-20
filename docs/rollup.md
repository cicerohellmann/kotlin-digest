# Protocol: Bulky Library Releases

How the digest handles high-frequency library changelog sources — the ones that
publish many near-identical nightly/dev builds in a week (Compose Multiplatform,
AndroidX/Jetpack, AGP, Ktor, …). Left alone they produce a wall of identical
`vX.Y.Z+devNNNN: Details` cards that bury everything else and teach the reader
nothing. This protocol collapses them into **one card that says only what
changed**.

The golden rule: **a reader must learn something or learn there's nothing to
learn — in one glance. Version bookkeeping is never the body.**

---

## The pipeline

### 1. Ingest — every release is an article
`pipeline/scout.py` reads each `type: changelog` source's release feed. Each
release has a unique URL, so each becomes its own dated article. A library
shipping 7 nightly builds this week yields 7 articles. Titles are taken
**verbatim** from the feed (`v1.12.10-alpha01+dev4492: Details`) — never rewritten.

### 2. Collapse — one survivor, the rest folded
`collapse()` in `pipeline/rollup.py` runs at assemble time. For each changelog
source in the window it:
- keeps the **single newest *renderable* release** as the **survivor** (renderable
  = summarized/tagged; unsummarized builds are dropped, never shown),
- folds every other build from that source into the survivor as a **rollup**:
  a `rollup_id`, the list of folded builds (title + date + url), and a slot for a
  digest.

Result: 7 cards → 1 survivor card + a rollup of 6.

### 3. Digest — signal or nothing (agent-written)
assemble emits `state/rollup-queue.json` for rollups missing a digest. An agent
reads the folded builds' real content and writes the digest, then
`rollup.py --apply` caches it in `state/rollups.json` keyed by `rollup_id`. The
digest content rules are below — this is where "bulky" becomes "useful."

### 4. Display — the digest IS the body
`articleCard` + `renderRollup` in `site/template.html`:
- the digest renders as the card's normal body (`art-summary`) — **no separate
  box, no second paragraph, no split**,
- `renderRollup` adds only the expandable `▸ Also this week · N more builds`,
- the survivor's own auto-generated per-build summary is **suppressed** when a
  rollup is present (it was boilerplate).

So a collapsed card = title + digest-as-body + expandable builds + tags.

---

## Writing the digest

The digest answers ONE question: **is there anything worth knowing in this week's
releases, or not?** It is not a build listing. Read the folded builds' actual
content, then write one of two things.

### Outcome A — there IS something notable
State it, concisely. A new/changed/removed API, a changed default, a breaking
change, a real feature. One clause per notable item; combine when there are a
few. Name the concrete thing; lead with it.

> One notable change this week — the 1.12.0-beta02 release makes
> `isClearFocusOnMouseDownEnabled` default to false. Everything else is
> automated nightly builds with no changelog.

### Outcome B — there is NOTHING notable
Say so in a single short line. Don't pad it.

> Nightly dev builds only — no notable API or behaviour changes this week.

---

## Hard rules

- **Never put version numbers, `devNNNN` tags, or artifact coordinates in the
  body.** They are clutter the reader learns nothing from. The expandable "N more
  builds" list already carries every raw version for anyone who wants them.
- **Never re-list the bundled modules** ("compose / material3 / lifecycle /
  navigation3 artifacts") — that's what a dev build always is; it's not news.
- **1–2 sentences, max.** A third sentence means you're padding.
- **Lead with the signal**, not the context. The change first; the "rest are
  nightlies" qualifier is a short tail, if included at all.
- **Don't re-narrate the title or the survivor summary.** Add what the title
  doesn't say.
- Plain, factual voice — no hype (see `rollup-summary-plain-style`).

## The test

After writing, ask: *"What did the reader learn?"* If the honest answer is "that
there were some dev builds," delete it and write Outcome B. If it's a concrete
change they could act on, that's Outcome A — keep only that.

---

## Where it lives

| Stage | Code |
|---|---|
| Ingest releases | `pipeline/scout.py` (changelog sources) |
| Collapse + queue | `pipeline/rollup.py` — `collapse()`, `write_queue()` |
| Apply digests | `pipeline/rollup.py --apply` → `state/rollups.json` |
| Display | `articleCard` + `renderRollup` in `site/template.html` |
| Design rationale | `docs/superpowers/specs/2026-07-11-changelog-rollup-design.md` |
