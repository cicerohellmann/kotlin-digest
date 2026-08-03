#!/usr/bin/env python3.11
"""
Bundle: produce a single portable HTML file from the assembled site.

Inlines design.css, downloads and base64-embeds Google Fonts (WOFF2),
and writes a self-contained file to dist/kotlin-digest-{edition}.html.

Usage:
  python3.11 pipeline/bundle.py --edition 2026-W28
"""

import argparse
import base64
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"

FONT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def fetch_text(url: str, headers: dict | None = None) -> str:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        resp = client.get(url, headers=headers or {})
        resp.raise_for_status()
        return resp.text


def fetch_bytes(url: str) -> bytes:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


def embed_fonts(font_css: str, local_dir: Path | None = None) -> str:
    """Replace url(...) in @font-face blocks with base64 data URIs.

    Handles remote (http) urls and local self-hosted woff2 files. Local font
    files are referenced by bare filename in site/fonts/fonts.css and read from
    `local_dir` — no network call, so the bundle stays Google-free and offline."""
    def replace_url(m):
        url = m.group(1).strip("'\"")
        data = None
        if url.startswith("http"):
            print(f"    embedding font: {url.split('/')[-1]}", file=sys.stderr)
            data = fetch_bytes(url)
        elif local_dir is not None:
            cand = local_dir / Path(url).name
            if cand.exists():
                print(f"    embedding local font: {cand.name}", file=sys.stderr)
                data = cand.read_bytes()
        if data is not None:
            b64 = base64.b64encode(data).decode()
            return f"url('data:font/woff2;base64,{b64}')"
        return m.group(0)

    return re.sub(r"url\(([^)]+)\)", replace_url, font_css)


# The hosted site persists reader prefs in cookies. But `document.cookie` is a
# no-op on `file://` in Chrome and Safari, so the downloaded bundle needs a
# storage backend that survives locally. Swap the four cookie touchpoints for
# localStorage in the bundle only — the hosted site is left untouched.
STORAGE_SWAPS = [
    # 1. <head> inline night-mode read (avoids theme flash on load)
    (
        "if(document.cookie.includes('kd_night=1'))"
        "document.documentElement.dataset.night='1';",
        "try{if(localStorage.getItem('kd_night')==='1')"
        "document.documentElement.dataset.night='1';}catch(e){}",
    ),
    # 2. saveCookies() write
    (
        "  document.cookie = `digest_prefs=${encodeURIComponent(JSON.stringify(d))}"
        ";max-age=${60*60*24*90};path=/`;",
        "  try{localStorage.setItem('digest_prefs', JSON.stringify(d));}catch(e){}",
    ),
    # 3. loadCookies() read (keeps the trailing `} catch(e) {}` intact)
    (
        "  const m = document.cookie.match(/digest_prefs=([^;]+)/);\n"
        "  if (!m) return;\n"
        "  try {\n"
        "    const d = JSON.parse(decodeURIComponent(m[1]));",
        "  let raw; try { raw = localStorage.getItem('digest_prefs'); }"
        " catch(e) { return; }\n"
        "  if (!raw) return;\n"
        "  try {\n"
        "    const d = JSON.parse(raw);",
    ),
    # 4. toggleNight() write
    (
        "  document.cookie = `kd_night=${next};max-age=${60*60*24*90};path=/`;",
        "  try{localStorage.setItem('kd_night', next);}catch(e){}",
    ),
]


def swap_storage(html: str) -> str:
    """Replace cookie persistence with localStorage for the standalone bundle."""
    for old, new in STORAGE_SWAPS:
        if old not in html:
            print(
                "[!] storage swap failed — expected snippet not found in assembled "
                "HTML. The template's cookie code changed; update STORAGE_SWAPS in "
                "bundle.py to match. Refusing to ship a bundle with broken prefs.",
                file=sys.stderr,
            )
            sys.exit(1)
        html = html.replace(old, new)
    return html


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", required=True, help="e.g. 2026-W28")
    args = parser.parse_args()

    source = SITE_DIR / "index.html"
    if not source.exists():
        print(f"[!] site/index.html not found — run assemble first", file=sys.stderr)
        sys.exit(1)

    html = source.read_text(encoding="utf-8")

    # 1. Inline design.css
    css_path = SITE_DIR / "design.css"
    if css_path.exists():
        print("  Inlining design.css...", file=sys.stderr)
        css = css_path.read_text(encoding="utf-8")
        html = html.replace(
            '<link rel="stylesheet" href="design.css">',
            f"<style>\n{css}\n</style>",
        )

    # 2. Embed fonts. Prefer the local self-hosted set (site/fonts/fonts.css);
    #    fall back to a legacy Google-Fonts link if one is still present.
    fonts_dir = SITE_DIR / "fonts"
    local_css = fonts_dir / "fonts.css"
    if re.search(r'<link[^>]*href="/fonts/fonts\.css"', html) and local_css.exists():
        print("  Embedding self-hosted fonts (no network)...", file=sys.stderr)
        font_css_embedded = embed_fonts(local_css.read_text(encoding="utf-8"), local_dir=fonts_dir)
        # Drop the fontcss link + its <noscript> fallback; inline the embedded @font-face.
        html = re.sub(r'[ \t]*<link[^>]*href="/fonts/fonts\.css"[^>]*>\n?', '', html)
        html = re.sub(r'[ \t]*<noscript><link[^>]*fonts\.css[^>]*></noscript>\n?', '', html)
        html = html.replace("</head>", f"<style>\n{font_css_embedded}\n</style>\n</head>", 1)
    else:
        gf_match = re.search(
            r'<link href="(https://fonts\.googleapis\.com/css2[^"]+)"[^>]*rel="stylesheet"[^>]*>',
            html,
        ) or re.search(
            r'<link rel="stylesheet"[^>]*href="(https://fonts\.googleapis\.com/css2[^"]+)"[^>]*>',
            html,
        )
        if gf_match:
            print("  Fetching Google Fonts CSS (legacy path)...", file=sys.stderr)
            font_css = fetch_text(gf_match.group(1), headers={"User-Agent": FONT_UA})
            font_css_embedded = embed_fonts(font_css)
            html = re.sub(r'<link[^>]+fonts\.gstatic\.com[^>]*>\n?', '', html)
            html = re.sub(r'<link[^>]+fonts\.googleapis\.com[^>]*>\n?', '', html)
            html = html.replace("</head>", f"<style>\n{font_css_embedded}\n</style>\n</head>", 1)

    # 3. Swap cookies → localStorage (bundle opens via file://, cookies are a no-op)
    print("  Swapping cookies → localStorage for standalone use...", file=sys.stderr)
    html = swap_storage(html)

    # 4. Write output
    DIST_DIR.mkdir(exist_ok=True)
    out_name = f"kotlin-digest-{args.edition}.html"
    out_path = DIST_DIR / out_name
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.rename(out_path)

    size_kb = out_path.stat().st_size // 1024
    print(f"  Written → dist/{out_name} ({size_kb} KB)")


if __name__ == "__main__":
    main()
