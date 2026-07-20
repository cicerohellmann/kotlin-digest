# Changelog rollup card duplicates its own summary

**Filed:** 2026-07-20 (recurring — reported more than once)
**Priority:** medium — reader-facing polish on changelog cards

## Problem

On a collapsed changelog card (e.g. Compose Multiplatform dev builds), the
article **summary** and the **rollup paragraph** below it say essentially the
same thing — the card repeats itself.

Example (W29, `v1.12.10-alpha01+dev4492`):

- Summary: *"A development pre-release tag (v1.12.10-alpha01+dev4492) of Compose
  Multiplatform from JetBrains. It bundles versions of the core Compose,
  Material3, lifecycle, and navigation3 artifacts. This is an automated dev
  build listing with no detailed changelog."*
- Rollup: *"Compose Multiplatform published a run of development pre-releases
  this week across the 1.12.10-alpha01 and 1.12.0-beta03 lines. Each dev build
  ships matching artifact coordinates for the compose, material3, lifecycle, and
  navigation3 modules. These are nightly-style snapshots without detailed
  changelogs, aimed at users tracking the latest fixes ahead of stable
  releases."*

Both paragraphs restate "dev pre-releases bundling compose/material3/lifecycle/
navigation3 with no detailed changelog." The rollup adds almost nothing.

## Desired outcome

It's acceptable that a dev-build rollup "says nothing" newsworthy, but the card
shouldn't waste two paragraphs saying it. Either:

1. **De-duplicate** — when the survivor's summary and the rollup paragraph cover
   the same ground, show only one (prefer the rollup, drop/trim the summary, or
   vice-versa), OR
2. **Make the rollup more informative** — instead of re-narrating, have it carry
   concrete signal the summary lacks: the exact version span, the count of
   collapsed builds, and the newest artifact coordinates (e.g. "6 dev builds,
   1.12.10-alpha01+dev4484 → +dev4492; newest bumps navigation3 to
   1.2.0-alpha03"). That turns the second paragraph into a real changelog digest.

Option 2 is preferred — it earns its space instead of just avoiding repetition.

## Where

- Rollup synthesis: `pipeline/rollup.py` (+ the agent prompt that writes rollup
  summaries) — currently produces prose that overlaps the survivor summary.
- Render: `renderRollup(a.rollup)` in `site/template.html` (the "ALSO THIS WEEK ·
  N MORE BUILDS" block) and the survivor's `art-summary`.
- The collapse that creates rollups: `collapse()` in `pipeline/rollup.py`.

## Acceptance criteria

- [ ] A collapsed changelog card no longer restates the same content twice
- [ ] The rollup paragraph carries concrete, non-duplicative signal (version
      span, build count, and/or notable artifact bumps) OR is omitted when it
      would only echo the summary
- [ ] Non-changelog cards are unaffected
- [ ] Re-assemble an edition with a changelog rollup (e.g. Compose Multiplatform)
      and confirm the card reads as one informative unit, not two echoes
