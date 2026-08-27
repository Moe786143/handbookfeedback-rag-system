"""
ZAIO website crawler.

Part 1 of this assignment asks the system to "crawl and extract text from
the ZAIO website" and "clean the extracted website content (remove
navigation, headers, footers where appropriate)".

The ZAIO site (https://www.zaio.io) is server-rendered — its HTML already
contains the real page content without needing JavaScript to run first.
That's what makes a plain requests + BeautifulSoup crawler a reasonable
choice here instead of a headless browser like Puppeteer: there's nothing
for a browser to render that a simple HTTP GET doesn't already receive.
If a future knowledge source turned out to be a JavaScript-heavy single
page app, that assumption would need revisiting.
"""
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    # Some sites block the default python-requests user agent outright.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# File extensions that are never worth crawling as "pages" — following
# these would just download binaries instead of finding more text content.
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
    ".css", ".js", ".woff", ".woff2", ".zip", ".mp4",
)

# Tags that hold site chrome rather than actual page content. Removing
# these before extracting text is the "clean the extracted website
# content" step the assignment asks for.
BOILERPLATE_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "svg", "form"]


def _same_domain(url: str, root_domain: str) -> bool:
    """
    Only follow links that stay on the exact same host as the starting
    page — not subdomains like applications.zaio.io, and not external
    sites like Discord or Trustpilot that the homepage happens to link to.
    """
    return urlparse(url).netloc == root_domain


def _is_crawlable(url: str) -> bool:
    """Filters out mailto:, tel:, javascript: links and binary file links."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if any(parsed.path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return False
    return True


def clean_page_text(html: str) -> str:
    """
    Strips navigation, headers, footers and non-content elements from a
    page's raw HTML, then returns the remaining visible text as a single
    clean string.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in BOILERPLATE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    # Collapse any run of whitespace left over from the tag removal.
    text = " ".join(text.split())
    return text


def crawl_website(start_url: str, max_pages: int = 12, delay_seconds: float = 0.5) -> list[dict]:
    """
    Breadth-first crawl of a site starting from start_url, staying on the
    same domain, up to max_pages pages.

    max_pages keeps this bounded and polite rather than crawling an entire
    site — enough to pick up the homepage plus its main linked pages
    (bootcamps, about, financing, etc.) without hammering the server.

    Returns a list of {"url": str, "text": str} for every page successfully
    fetched and cleaned. Pages that fail to load (network error, non-200
    status) are skipped rather than aborting the whole crawl.
    """
    root_domain = urlparse(start_url).netloc

    visited: set[str] = set()
    queue: list[str] = [start_url]
    pages: list[dict] = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        # Strip any #fragment so "/page#section" and "/page" aren't
        # treated as two different pages to crawl.
        url = url.split("#")[0].rstrip("/")

        if not url or url in visited:
            continue
        visited.add(url)

        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"  Skipping {url} ({exc})")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        text = clean_page_text(response.text)

        if text:
            pages.append({"url": url, "text": text})
            print(f"  Crawled {url} ({len(text)} chars)")

        # Queue up same-domain links found on this page for the next round.
        for link in soup.find_all("a", href=True):
            absolute = urljoin(url, link["href"])
            if (
                _same_domain(absolute, root_domain)
                and _is_crawlable(absolute)
                and absolute.split("#")[0].rstrip("/") not in visited
            ):
                queue.append(absolute)

        time.sleep(delay_seconds)  # be polite — don't hammer the server

    return pages
