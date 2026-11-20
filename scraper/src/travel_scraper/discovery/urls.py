"""URL normalization and the eligibility filter (pure functions).

Nothing is crawled unless it passes `eligibility()`. Rejected: social media and video,
booking/aggregator/review sites (their content is theirs, and they block bots), our own
dedicated sources (Wikipedia, Wikivoyage, OSM, Wikidata), and non-HTML files.
Official sites (government, tourism boards) are kept with top priority.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = frozenset({"fbclid", "gclid", "msclkid", "yclid", "mc_cid", "mc_eid", "ref"})

SOCIAL = (
    "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com", "youtube.com",
    "youtu.be", "pinterest.com", "reddit.com", "linkedin.com", "threads.net", "quora.com",
)  # fmt: skip
AGGREGATORS = (
    "tripadvisor.", "yelp.", "booking.com", "expedia.", "agoda.", "hotels.com", "airbnb.",
    "kayak.", "trip.com", "klook.com", "viator.com", "getyourguide.", "tabelog.com",
    "opentable.", "gurunavi.com", "hotpepper.jp", "jalan.net", "rakuten.", "google.",
    "bing.com", "duckduckgo.com", "yahoo.", "maps.apple.com",
)  # fmt: skip
OWN_SOURCES = (
    "wikipedia.org",
    "wikivoyage.org",
    "wikidata.org",
    "openstreetmap.org",
    "wikimedia.org",
)
NON_HTML = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".mp4",
    ".mp3",
    ".zip",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
)
OFFICIAL_SUFFIXES = (
    ".go.jp",
    ".lg.jp",
    ".gov",
    ".gov.uk",
    ".gouv.fr",
    ".gc.ca",
    ".gov.au",
    ".govt.nz",
    ".gob.mx",
    ".gov.sg",
)
OFFICIAL_WORDS = ("visit", "tourism", "tourist", "jnto", "gotokyo", "travel-japan")

REASON_OK_OFFICIAL = "official or tourism-board site"
REASON_OK = "eligible"
REASON_BAD_SCHEME = "not an http(s) link"
REASON_SOCIAL = "social media or video site"
REASON_AGGREGATOR = "booking, review, aggregator or search site"
REASON_OWN_SOURCE = "covered by a dedicated source (Wikipedia/Wikivoyage/OSM/Wikidata)"
REASON_NON_HTML = "not an HTML page"


def normalize_url(url: str) -> str | None:
    """The URL to crawl: lowercase host, no default port, fragment or tracking params.

    Host (`www.`) and path (trailing slash) are kept as found: some sites only answer on
    one form. `dedupe_key()` is the looser form used to spot the same page twice.
    None if the URL is unusable.
    """
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    host = parts.netloc.lower()
    if host.endswith(":80") or host.endswith(":443"):
        host = host.rsplit(":", 1)[0]
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((parts.scheme, host, parts.path or "/", urlencode(query), ""))


def dedupe_key(url: str) -> str:
    """Same page, ignoring scheme, `www.` and a trailing slash."""
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return f"{host}{path}?{parts.query}" if parts.query else f"{host}{path}"


def host_of(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def _matches(host: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if pattern.endswith("."):  # brand prefix: "tripadvisor." matches any TLD
            if host.startswith(pattern) or f".{pattern}" in f".{host}":
                return True
        elif host == pattern or host.endswith("." + pattern):
            return True
    return False


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reason: str
    priority: int = 1  # 0 = official, crawled first


def eligibility(url: str) -> Eligibility:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return Eligibility(False, REASON_BAD_SCHEME)
    host = host_of(url)
    if parts.path.lower().endswith(NON_HTML):
        return Eligibility(False, REASON_NON_HTML)
    if _matches(host, SOCIAL):
        return Eligibility(False, REASON_SOCIAL)
    if _matches(host, OWN_SOURCES):
        return Eligibility(False, REASON_OWN_SOURCE)
    if _matches(host, AGGREGATORS):
        return Eligibility(False, REASON_AGGREGATOR)
    if host.endswith(OFFICIAL_SUFFIXES) or any(word in host for word in OFFICIAL_WORDS):
        return Eligibility(True, REASON_OK_OFFICIAL, priority=0)
    return Eligibility(True, REASON_OK)
