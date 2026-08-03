#!/usr/bin/env python3
"""Prerender — freeze the JS reader's output into the page so no-JS readers and
search crawlers get the full digest, with NO second renderer to maintain.

The JS reader in site/template.html stays the single source of truth. This step
loads an assembled page in headless Chromium, lets the reader render, and writes
the resulting #digest HTML back into the file's empty <main id="digest">. When
JS is on the reader wipes and rebuilds #digest as usual (the snapshot is inert
for those visitors); when JS is off — or on ?nojs — the snapshot is what shows.

Run AFTER assemble, on the generated files:
  python3 pipeline/prerender.py site/index.html site/editions/2026-W29.html
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# A narrow viewport forces the reader's scroll feed (see effectiveLayout / the
# <=700px rule), which lays out EVERY article in one column. Paged mode only
# builds the currently-visible cards, so it would snapshot an incomplete digest.
SNAPSHOT_VIEWPORT = {"width": 390, "height": 900}
DIGEST_RE = re.compile(r'(<main id="digest">)\s*(</main>)')


def prerender(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    if not DIGEST_RE.search(html):
        raise SystemExit(f"prerender: no empty <main id=\"digest\"> in {path.name}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=SNAPSHOT_VIEWPORT)
        page.goto(path.as_uri())
        # Reader renders after fonts settle; wait for the first card, then settle.
        page.wait_for_selector("#digest .article", timeout=20000)
        page.wait_for_timeout(400)
        digest = page.inner_html("#digest")
        browser.close()

    # Inject via a function replacement so backslashes/$-groups in the snapshot
    # are treated literally.
    new_html = DIGEST_RE.sub(lambda m: m.group(1) + digest + m.group(2), html, count=1)
    path.write_text(new_html, encoding="utf-8")
    print(f"  prerendered {path.name}: +{len(digest):,} chars into #digest")


if __name__ == "__main__":
    targets = sys.argv[1:]
    if not targets:
        raise SystemExit("usage: prerender.py <file.html> [<file.html> ...]")
    for t in targets:
        prerender(Path(t).resolve())
