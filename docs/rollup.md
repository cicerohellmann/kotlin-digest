# Changelog Rollup Digest

Used during rollup synthesis (`pipeline/rollup.py` queue → agent → `--apply`) to
write the **digest** that becomes the body of a collapsed changelog card.

The digest answers ONE question for the reader: **is there anything worth
knowing in this week's releases, or not?** It is not a build listing.

---

## The two outcomes

Read the folded builds' actual content (titles, excerpts, changelog bodies).
Then write one of two things:

### 1. There IS something notable

State it — concisely. A new/changed/removed API, a changed default, a breaking
change, a real feature. One clause per notable item; combine when there are a
few. Name the concrete thing.

> One notable change this week — the 1.12.0-beta02 release makes
> `isClearFocusOnMouseDownEnabled` default to false. Everything else is
> automated nightly builds with no changelog.

### 2. There is NOTHing notable

Say so in a single short line. Don't pad it.

> Nightly dev builds only — no notable API or behaviour changes this week.

---

## Hard rules

- **Never list dev-build version numbers** (`dev4462 → dev4484`), artifact
  coordinates, or "bundles the compose/material3/lifecycle/navigation3 modules"
  bookkeeping. That is clutter the reader learns nothing from — the expandable
  "N more builds" list already carries the raw versions for anyone who wants them.
- **1–2 sentences, max.** If you're writing a third sentence, you're padding.
- **Lead with the signal**, not the context. The notable change comes first; the
  "rest are nightlies" qualifier is a short tail, if included at all.
- **No re-narrating the release title or the survivor summary.** The card already
  shows the title; the digest adds what the title doesn't.
- Plain, factual voice (see the `rollup-summary-plain-style` guidance) — no hype.

---

## Test

After writing, ask: *"What did the reader learn?"* If the honest answer is "that
there were some dev builds," delete it and write outcome #2. If it's a concrete
change they could act on, that's outcome #1 — keep only that.
