# Paged magazine reader — fixed pages you flip through

**Date:** 2026-03-21
**Status:** approved (user confirmed model + measure-to-fit at load)

## Goal

Replace the single long scroll with a **page-turning magazine**: fixed,
screen-sized pages you flip through with ←/→, click zones, or swipe — never
scroll. Every content block is measured and packed onto pages **at load time**
(and on resize / filter change), so page counts and the Contents page numbers
are correct for the device.

## Display model

- **1-up on small screens, 2-up (open spread) on wide screens** — matches the
  existing spread layout. A "screen" shows one or two **page columns**.
- Pagination produces an ordered array of **pages** (each a single column that
  fits the page height). The viewer shows 1 or 2 per screen and advances by that
  many. Because page *width* differs between 1-up and 2-up (and changes card
  heights), pagination is recomputed when the mode or viewport changes.

## Blocks → pages (measure-to-fit)

Reading order is flattened into blocks:
- **Cover** — its own page.
- **Contents** (trending + catalog) — its own page; catalog lists each chapter's
  real start page (known after pagination).
- **Chapter flow** — a chapter-header block followed by its article-card blocks.
  Cards pack onto a page until the next would overflow the page height, then a
  new page starts (carrying a "<chapter> · cont." header). A header is never
  orphaned at the foot of a page.
- **Comic** — each interlude is its own page (placement rule unchanged:
  leading + one per COMIC_EVERY cards).

Packing measures real rendered heights in a hidden measurer sized to the page
width, after `document.fonts.ready` (cards have no images; comics are size-
capped), so measurements are accurate.

## Viewer

- Pages laid out in a horizontal track; `translateX` moves between screens.
- Nav: **← / →** keys, on-screen prev/next buttons, left/right click zones,
  touch swipe. A **page indicator** ("3 / 18").
- Overflow hidden on each page (belt-and-suspenders; packing already guarantees
  fit).

## Preserved

Cover, Contents, night mode, comics, and the focus/exclude + keyword filters all
stay. **Filtering re-runs pagination over the visible set** (instead of toggling
`.hidden` in a scroll), then jumps to page 1. Cookies unchanged.

## Out of scope (v1)

- Fancy page-curl animation (a clean slide/fade is enough).
- Splitting a single over-long card across pages (a card is atomic; an unusually
  tall card just gets its own page).
