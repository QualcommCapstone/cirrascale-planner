"""Scrape place listings from Wikivoyage city articles.

Why the article HTML and not the MediaWiki API? Wikivoyage's robots.txt blocks
bots from `/w/` (which includes `/w/api.php`) but says "friendly, low-speed bots
are welcome viewing article pages". So we fetch normal `/wiki/<City>` pages
with Scrapling's plain `Fetcher` and read the listings out of the HTML.

How a Wikivoyage page is laid out:
- Each place is a "listing": `<bdi class="vcard">` with child spans such as
  `.listing-name`, `.listing-address`, `.listing-hours`, `.listing-price`,
  `.listing-content` (the description), and `abbr.latitude` / `abbr.longitude`.
- Listings sit inside `<section>` tags, one per heading. The top heading tells
  us the type (See / Do / Buy / Eat / Drink / Sleep); a nested heading gives a
  subsection like "Budget", "Splurge", or "Museums".
- Big cities (Tokyo, London...) put most listings on district pages such as
  `Tokyo/Shinjuku`, linked from the "Districts" section. We follow those.

Content is CC BY-SA 4.0 (Wikivoyage); `source_url` keeps the attribution link.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any, cast, get_args
from urllib.parse import quote, unquote, urlsplit

from pydantic import ValidationError

from app.scraping.fetch import FetchFailed, PoliteFetcher, RobotsDisallowed
from app.scraping.models import ListingSection, RawListing, ScrapeResult

log = logging.getLogger(__name__)

SOURCE = "wikivoyage"
BASE_URL = "https://en.wikivoyage.org/wiki/"
LISTING_SECTIONS: frozenset[str] = frozenset(get_args(ListingSection))

_WS = re.compile(r"\s+")
_WIKIDATA_ID = re.compile(r"^Q\d+$")
_HEADING_SPLIT = re.compile(r"\s*(?:,|&|\band\b)\s*")

# Reasons a listing card is not kept. Shown in the CLI summary.
SKIP_NOT_A_PLACE = "not a place to visit (e.g. Get in, Connect, embassies)"
SKIP_NO_NAME = "no name on the page"
SKIP_BAD_DATA = "bad data"


# ---- URLs -------------------------------------------------------------------


def article_url(title: str) -> str:
    """'San Diego' -> 'https://en.wikivoyage.org/wiki/San_Diego'."""
    title = title.strip().replace(" ", "_")
    if title:
        title = title[0].upper() + title[1:]  # MediaWiki capitalizes the first letter
    return BASE_URL + quote(title, safe="/_(),'-.")


def title_from_url(url: str) -> str:
    """'https://en.wikivoyage.org/wiki/Tokyo/Shinjuku' -> 'Tokyo/Shinjuku'."""
    path = urlsplit(url).path
    if path.startswith("/wiki/"):
        path = path[len("/wiki/") :]
    return unquote(path).replace("_", " ")


# ---- parsing (pure functions; no network) -----------------------------------


def canonical_url(page: Any, fallback: str) -> str:
    """The page's real URL (follows redirects like 'NYC' -> 'New York City')."""
    href = page.css('link[rel="canonical"]::attr(href)').get()
    return str(href) if href else fallback


def find_district_titles(page: Any, city_title: str) -> list[str]:
    """Titles of district pages linked from the 'Districts' section, in page order."""
    prefix = f"{city_title}/"
    titles: list[str] = []
    for link in page.css('section[aria-labelledby="Districts"] a[title]'):
        title = _clean(link.attrib.get("title"))
        if title and title.startswith(prefix) and title not in titles:
            titles.append(title)
    return titles


def parse_listings(
    page: Any,
    *,
    page_url: str,
    city: str,
    district: str | None,
    fetched_at: datetime,
) -> tuple[list[RawListing], Counter[str]]:
    """Read every See/Do/Buy/Eat/Drink/Sleep listing on one page.

    Returns (listings, skipped) where `skipped` counts each reason a listing was
    left out. A bad listing is skipped, never fatal.
    """
    listings: list[RawListing] = []
    skipped: Counter[str] = Counter()
    for card in page.css("bdi.vcard"):
        try:
            outcome = _parse_card(
                card, page_url=page_url, city=city, district=district, fetched_at=fetched_at
            )
        except (ValidationError, ValueError) as exc:
            log.warning("Skipping malformed listing on %s: %s", page_url, exc)
            outcome = SKIP_BAD_DATA
        if isinstance(outcome, str):
            skipped[outcome] += 1
        else:
            listings.append(outcome)
    return listings, skipped


def _parse_card(
    card: Any, *, page_url: str, city: str, district: str | None, fetched_at: datetime
) -> RawListing | str:
    """Return the listing, or the reason it was skipped."""
    section, subsection = _sections_for(card)
    if section is None:
        return SKIP_NOT_A_PLACE

    name_el = card.css(".listing-name").first
    name = _text(name_el)
    if not name:
        return SKIP_NO_NAME

    anchor = name_el.attrib.get("id") if name_el is not None else None
    source_url = f"{page_url}#{anchor}" if anchor else page_url

    return RawListing(
        source=SOURCE,
        source_url=source_url,
        page_url=page_url,
        fetched_at=fetched_at,
        city=city,
        district=district,
        section=cast(ListingSection, section),
        subsection=subsection,
        name=name,
        alt_name=_field(card, ".listing-alt"),
        address=_field(card, ".listing-address"),
        directions=_field(card, ".listing-directions"),
        lat=_coordinate(_field(card, "abbr.latitude"), limit=90),
        lng=_coordinate(_field(card, "abbr.longitude"), limit=180),
        phone=_field(card, ".listing-phone"),
        email=_field(card, ".listing-email"),
        website=_website(card),
        hours=_field(card, ".listing-hours"),
        price=_field(card, ".listing-price"),
        description=_field(card, ".listing-content"),
        wikidata_id=_wikidata_id(card),
        last_edit=_field(card, ".listing-lastedit"),
    )


def _sections_for(card: Any) -> tuple[str | None, str | None]:
    """Find (section, subsection) from the `<section aria-labelledby=...>` ancestors."""
    headings: list[str] = []
    for ancestor in card.iterancestors():
        if ancestor.tag == "section" and ancestor.attrib.get("aria-labelledby"):
            text = _heading_text(ancestor)
            if text:
                headings.append(text)
    # `headings` runs from the closest heading outward, so the last one is the top level.
    if not headings:
        return None, None
    section = _section_type(headings[-1], card)
    if section is None:
        return None, None
    subsection = headings[0] if len(headings) > 1 else None
    return section, subsection


def _section_type(heading: str, card: Any) -> str | None:
    """'See' -> 'see'. Combined headings like 'Eat and drink' use the listing's own type."""
    key = heading.lower().strip()
    if key in LISTING_SECTIONS:
        return key
    parts = [p for p in _HEADING_SPLIT.split(key) if p]
    if len(parts) < 2 or not all(p in LISTING_SECTIONS for p in parts):
        return None
    marker = _marker_group(card)
    return marker if marker in parts else parts[0]


def _marker_group(card: Any) -> str | None:
    """The listing type stored on its map marker, e.g. 'drink'. Not every listing has one."""
    raw = card.css("a.mw-kartographer-maplink::attr(data-mw)").get()
    if not raw:
        return None
    try:
        group = json.loads(str(raw)).get("attrs", {}).get("group")
    except (ValueError, AttributeError):
        return None
    return str(group).lower() if group else None


def _heading_text(section: Any) -> str | None:
    """Visible heading text of a section. Falls back to its id ('Budget_2' -> 'Budget 2').

    We prefer the visible text because MediaWiki adds '_2', '_3' to repeated ids.
    """
    label = str(section.attrib.get("aria-labelledby", ""))
    heading = section.css(f'[id="{label}"]').first if '"' not in label else None
    return _text(heading) or _clean(unquote(label).replace("_", " "))


def _website(card: Any) -> str | None:
    href = card.css(".listing-name a.external::attr(href)").get()
    if not href:
        href = card.css(".listing-url a::attr(href)").get()
    href = _clean(href)
    return href if href and href.startswith(("http://", "https://")) else None


def _wikidata_id(card: Any) -> str | None:
    for el in card.css("span[id]"):
        value = str(el.attrib.get("id", ""))
        if _WIKIDATA_ID.match(value):
            return value
    href = card.css(".listing-sister-wikidata a::attr(href)").get()
    if href:
        match = re.search(r"(Q\d+)", str(href))
        if match:
            return match.group(1)
    return None


def _coordinate(value: str | None, *, limit: float) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if number != number or abs(number) > limit:  # NaN or out of range
        return None
    return number


def _field(card: Any, selector: str) -> str | None:
    return _text(card.css(selector).first)


def _text(el: Any) -> str | None:
    if el is None:
        return None
    return _clean(el.get_all_text(separator="", strip=False))


def _clean(value: Any) -> str | None:
    """Collapse whitespace and trim stray punctuation. Empty -> None."""
    if value is None:
        return None
    text = _WS.sub(" ", str(value)).strip().strip(",;").strip()
    return text or None


# ---- the scrape run (uses the network through PoliteFetcher) ----------------


def scrape_city(
    city: str,
    fetcher: PoliteFetcher,
    *,
    include_districts: bool = True,
    max_districts: int | None = None,
) -> ScrapeResult:
    """Scrape a city article, plus its district pages for big cities.

    Never raises for a bad page: problems are recorded in `result.errors` so
    one broken district doesn't lose the rest of the city.
    """
    result = ScrapeResult(source=SOURCE, city=city, started_at=_now())

    main = _scrape_page(article_url(city), fetcher, city=city, district=None, result=result)
    if main is not None and include_districts:
        city_title = title_from_url(canonical_url(main, article_url(city)))
        districts = find_district_titles(main, city_title)
        if max_districts is not None:
            districts = districts[:max_districts]
        for title in districts:
            district_name = title.split("/", 1)[1]
            _scrape_page(
                article_url(title), fetcher, city=city, district=district_name, result=result
            )

    result.finished_at = _now()
    return result


def _scrape_page(
    url: str, fetcher: PoliteFetcher, *, city: str, district: str | None, result: ScrapeResult
) -> Any | None:
    try:
        page = fetcher.fetch(url, kind="static")
    except RobotsDisallowed:
        result.errors.append(f"{url}: blocked by robots.txt")
        return None
    except FetchFailed as exc:
        result.errors.append(str(exc))
        return None

    fetched_at = _now()
    real_url = canonical_url(page, url)
    try:
        listings, skipped = parse_listings(
            page, page_url=real_url, city=city, district=district, fetched_at=fetched_at
        )
    except Exception as exc:  # truly broken HTML: record it and move on
        log.exception("Could not parse %s", url)
        result.errors.append(f"{url}: parse error ({type(exc).__name__}: {exc})")
        return page

    result.pages_fetched.append(real_url)
    result.listings.extend(listings)
    for reason, count in skipped.items():
        result.skipped[reason] = result.skipped.get(reason, 0) + count
    log.info("%s: %d listings (%d skipped)", real_url, len(listings), skipped.total())
    return page


def _now() -> datetime:
    return datetime.now(UTC)
