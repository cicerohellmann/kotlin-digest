"""Privacy / DSGVO compliance guards for the published site.

These tests exist because privacy fixes regress silently at the *data* level:
the DSGVO cleanup self-hosted the fonts but comics kept hotlinking xkcd through
several editions, and two orphan font-picker pages kept pulling Google Fonts.
Nothing failed a build — the leak just shipped. These tests turn the site's
promise ("zero third-party requests on page load", see site/tracking.html) into
something CI enforces.

The core check parses every built page and asserts that no auto-loading asset
(img/script/iframe/link/css url()) points at a host other than our own. It does
NOT flag <a href> links or JSON-LD metadata — those are user clicks / data, not
requests the browser makes on page view.
"""
import glob
import os
import re

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")

# Requests to these hosts are same-origin. "" covers relative / root-absolute.
OWN_HOSTS = {"", "kotlindigest.com", "www.kotlindigest.com"}

# Attributes whose URL the browser fetches automatically on page view.
AUTO_LOAD_ATTRS = [
    ("img", "src"), ("img", "srcset"), ("script", "src"), ("iframe", "src"),
    ("source", "src"), ("source", "srcset"), ("video", "src"), ("audio", "src"),
    ("track", "src"), ("embed", "src"), ("object", "data"), ("input", "src"),
]
# <link rel=...> values that trigger a fetch or connection on load.
AUTO_LOAD_LINK_RELS = {
    "stylesheet", "preload", "preconnect", "dns-prefetch", "prefetch",
    "modulepreload", "icon", "apple-touch-icon", "mask-icon", "manifest",
}
_CSS_URL = re.compile(r"url\(\s*([^)]+?)\s*\)")


def _html_files():
    return sorted(glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True))


def _external_hosts(value):
    """Yield the external host(s) referenced by an attribute value, or nothing
    if every candidate is same-origin. Handles srcset (comma-separated)."""
    if not value:
        return
    for candidate in value.split(","):
        url = candidate.strip().split(" ")[0].strip().strip("'\"")
        if not url or url.startswith(
            ("data:", "mailto:", "tel:", "#", "javascript:", "blob:", "{")
        ):
            continue
        if url.startswith("//"):
            host = url[2:].split("/")[0]
        elif url.startswith(("http://", "https://")):
            host = url.split("://", 1)[1].split("/")[0]
        else:
            continue  # relative or root-absolute -> same origin
        host = host.lower().split(":")[0]
        if host not in OWN_HOSTS:
            yield host


def _leaks_in_html(path):
    soup = BeautifulSoup(open(path, encoding="utf-8").read(), "html.parser")
    leaks = []
    for tag, attr in AUTO_LOAD_ATTRS:
        for el in soup.find_all(tag):
            for host in _external_hosts(el.get(attr)):
                leaks.append((f"{tag}[{attr}]", host, (el.get(attr) or "")[:70]))
    for el in soup.find_all("link"):
        rels = {r.lower() for r in (el.get("rel") or [])}
        if rels & AUTO_LOAD_LINK_RELS:
            for host in _external_hosts(el.get("href")):
                leaks.append((f"link {sorted(rels)}", host, (el.get("href") or "")[:70]))
    for style in soup.find_all("style"):
        for m in _CSS_URL.findall(style.get_text()):
            for host in _external_hosts(m):
                leaks.append(("<style> url()", host, m[:70]))
    return leaks


def test_no_third_party_assets_on_page_load():
    """No page may auto-load an asset from a third-party host (DSGVO: the reader's
    IP must never reach a third party on page view). Covers fonts, comics, embeds."""
    violations = []
    for path in _html_files():
        for kind, host, snippet in _leaks_in_html(path):
            violations.append(f"{os.path.relpath(path, ROOT)}: {kind} -> {host}  ({snippet})")
    for path in glob.glob(os.path.join(SITE, "**", "*.css"), recursive=True):
        for m in _CSS_URL.findall(open(path, encoding="utf-8").read()):
            for host in _external_hosts(m):
                violations.append(f"{os.path.relpath(path, ROOT)}: css url() -> {host}  ({m[:70]})")
    assert not violations, "Third-party asset requests found (privacy leak):\n" + "\n".join(violations)


def test_no_analytics_or_tracker_snippets():
    """No known analytics/tracking snippet may appear anywhere in the site."""
    signatures = [
        "google-analytics.com", "googletagmanager.com", "gtag(", "ga('create'",
        "plausible.io", "static.cloudflareinsights.com", "connect.facebook.net",
        "fbq(", "hotjar.com", "matomo", "segment.com",
    ]
    hits = []
    for path in _html_files():
        text = open(path, encoding="utf-8").read()
        for sig in signatures:
            if sig in text:
                hits.append(f"{os.path.relpath(path, ROOT)}: {sig!r}")
    assert not hits, "Tracker/analytics signatures found:\n" + "\n".join(hits)


def test_legal_pages_present_and_complete():
    """Impressum + Datenschutz must exist with the address and key required parts."""
    imp = open(os.path.join(SITE, "impressum.html"), encoding="utf-8").read()
    ds = open(os.path.join(SITE, "datenschutz.html"), encoding="utf-8").read()
    for needle in ["§ 5 DDG", "In den Alboigärten 29", "12103 Berlin", "hello@kotlindigest.com"]:
        assert needle in imp, f"Impressum missing: {needle!r}"
    for needle in ["Verantwortlicher", "In den Alboigärten 29", "12103 Berlin"]:
        assert needle in ds, f"Datenschutz missing: {needle!r}"


def test_editions_link_to_legal_pages():
    """Every published edition + the front page must link to Impressum & Datenschutz."""
    pages = [os.path.join(SITE, "index.html")] + sorted(
        glob.glob(os.path.join(SITE, "editions", "*.html"))
    )
    missing = []
    for path in pages:
        text = open(path, encoding="utf-8").read()
        if "impressum.html" not in text or "datenschutz.html" not in text:
            missing.append(os.path.relpath(path, ROOT))
    assert not missing, "Pages not linking to legal pages:\n" + "\n".join(missing)
