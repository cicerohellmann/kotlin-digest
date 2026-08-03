#!/usr/bin/env python3.11
"""Maintain site/sitemap.xml when promoting an edition.

The sitemap is hand-maintained (the pipeline never touched it), so promoting an
edition to the front page must both:
  · --add  the new edition's permanent archive URL (else it's live but invisible
    to crawlers). Idempotent — a URL already present is left untouched.
  · --touch the pages whose *content* changed (the homepage and the archive
    index) so their <lastmod> reflects today, giving Googlebot a recrawl signal.
    Without this the front page silently becomes W31 while the sitemap still
    claims it was last modified weeks ago.

Usage:
  python3.11 pipeline/sitemap.py --add editions/2026-W31.html --touch / --touch archive.html
"""
import argparse
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = ROOT / "site" / "sitemap.xml"
BASE = "https://kotlindigest.com/"


def _loc(path: str) -> str:
    # "" or "/" → homepage; else the site-relative path.
    return BASE + path.lstrip("/")


def add_url(xml: str, path: str, today: str) -> str:
    loc = _loc(path)
    if loc in xml:
        print(f"  sitemap: {loc} already present — no change")
        return xml

    entry = (
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        "    <changefreq>yearly</changefreq>\n"
        "    <priority>0.7</priority>\n"
        "  </url>\n"
    )
    # Insert before the first existing editions/ entry (keeps newest-first
    # ordering), else before the closing tag.
    marker = "  <url>\n    <loc>" + BASE + "editions/"
    idx = xml.find(marker)
    if idx == -1:
        idx = xml.rfind("</urlset>")
    print(f"  sitemap: added {loc}")
    return xml[:idx] + entry + xml[idx:]


def touch_url(xml: str, path: str, today: str) -> str:
    """Set the <lastmod> of an existing <loc> to today."""
    loc = _loc(path)
    # Match the <lastmod> that belongs to this <loc> (same <url> block: loc is
    # immediately followed by its lastmod in every entry).
    pattern = re.compile(
        r"(<loc>" + re.escape(loc) + r"</loc>\s*<lastmod>)[^<]*(</lastmod>)"
    )
    new_xml, n = pattern.subn(rf"\g<1>{today}\g<2>", xml)
    if n:
        print(f"  sitemap: touched {loc} → {today}")
    else:
        print(f"  sitemap: WARNING {loc} not found — nothing touched")
    return new_xml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--add", default=None,
                        help="site-relative path to add, e.g. editions/2026-W31.html")
    parser.add_argument("--touch", action="append", default=[],
                        help="site-relative path whose <lastmod> to bump to today "
                             "(repeatable; use / for the homepage)")
    args = parser.parse_args()

    today = date.today().isoformat()
    xml = SITEMAP.read_text(encoding="utf-8")
    if args.add:
        xml = add_url(xml, args.add, today)
    for path in args.touch:
        xml = touch_url(xml, path, today)
    SITEMAP.write_text(xml, encoding="utf-8")


if __name__ == "__main__":
    main()
