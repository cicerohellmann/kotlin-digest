# Content Rights

Kotlin Digest is an **aggregator**: every edition is built from other people's articles, talks,
changelogs, and videos. These rules keep each edition on the right side of copyright, attribution,
paywalls, and licensing. They are **binding on the summarization + classification agent** and on
anyone adding a source or editing the pipeline.

The guiding principle: **we point at work, we do not repackage it.** A reader should always end up
on the creator's own page, and the creator should always get the credit and the click.

---

## Hard rules

### 1. Summarize, never republish
- Produce a **short original summary** (a few sentences) plus a canonical link. Never reproduce the
  full body, and never reproduce so much of it that a reader has no reason to visit the original.
- The summary must be **our own words describing the piece**, not a lightly edited copy of it.
- If there is no usable source text (bare title only), do **not** summarize — the content gate in
  `summarize.py` already drops these; never fill the gap by inventing detail.

### 2. Always attribute
- Every rendered item links to the **original canonical URL** and names the **source** (and author
  where known). No unattributed summaries, ever.
- Attribution is not optional politeness — it is the thing that makes summarizing lawful and fair.

### 3. Never bypass paywalls or member-only content
- If a source is behind a paywall or marked member-only, **do not summarize its body**. `vet.py`
  already flags Medium member-only articles — treat any such flag as "headline + link only," never
  a fetched-body summary.
- Do not use logged-in sessions, cached copies, or archive mirrors to reach content the publisher
  gated. If we can't read it cleanly and publicly, we don't summarize it.

### 4. Code snippets are short attributed citations
- A snippet is a **citation** under the quotation right (Zitatrecht, §51 UrhG): short, purposeful,
  and clearly the author's — not a wholesale copy.
- Keep it to the **≤10 lines** the classifier already targets. Never lift an entire example file.
- Preserve any **license or attribution** the snippet carries. If code is published under an OSS
  license, keep the notice; if provenance is unclear, prefer a shorter excerpt or omit it.

### 5. Respect robots.txt, Terms of Service, and noindex
- Only ingest sources that **allow** it. Skip anything whose robots.txt, ToS, or `noindex` signals
  ask not to be crawled or reused. When in doubt, leave it out.

### 6. No fabrication
- Every fact in a summary must trace to the fetched source. Do not infer version numbers, API
  names, dates, or claims the source does not state. (The content gate enforces the floor; this is
  the rule behind it.)

### 7. Don't reproduce others' images or thumbnails
- No hotlinking or embedding of third-party images, logos, or video thumbnails beyond a
  **privacy-preserving facade** (e.g. the YouTube no-cookie click-to-load embed). Prefer text and
  links over borrowed imagery.

### 8. Featuring paid content is editorial only
- Kotlin Digest may feature or mention third-party **paid** content (courses, books, workshops) as
  editorial coverage — chosen on merit.
- **No affiliate links, no commission, no pay-to-be-listed, no sponsorship.** We take no money in
  either direction. Featuring is a judgement call by the editor, never a transaction.
- This keeps us clean on *money*. It is **separate** from, and does not resolve, the Impressum /
  §18 MStV question (see `docs/legal.md` if present) — that turns on the site being a sustained
  public offering, not on revenue.

---

## Why these exist

Summarizing and quoting other people's work is lawful **because** it is transformative, short,
attributed, and drives readers back to the source. Break any of those — reproduce the whole thing,
strip the credit, bypass the paywall, borrow the images — and the same act stops being fair. Every
rule above protects one of those four properties.
