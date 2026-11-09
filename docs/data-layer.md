# Data & trust layer

> Steering doc for the Python data layer in `backend/`: scraping, cleaning,
> verification, source tracking, and evals (features #11–13 in
> `feature-architecture.md`). Update this file in the same commit as any change.

## Status

| Piece | State |
| ----- | ----- |
| Scraper (Wikivoyage) | Done: `backend/app/scraping/` |
| Clean `Place` format + database | Next |
| Tags / prices / hours / indoor-outdoor | Planned |
| Source links (#13) | Planned (every raw record already has `source_url` + `fetched_at`) |
| Refresh job | Planned |
| Hallucination verifier (#12) | Planned |
| LLM evals | Planned |

## Scraping rules (all sources)

All requests go through `PoliteFetcher` (`backend/app/scraping/fetch.py`):

- **robots.txt is checked first.** Disallowed URLs are never requested. If
  robots.txt can't be loaded because of a server error, the whole site is
  skipped for that run. A missing robots.txt (404) means no rules.
- **At least 3s between requests to the same site** (`SCRAPER_MIN_DELAY_S`),
  or longer if the site's `Crawl-delay` asks for it.
- **Retries:** network errors, 429 and 5xx are retried up to 3 times with growing
  waits (2s, 4s…), or the site's `Retry-After`. Other errors (404) fail at once.
- **Honest User-Agent** (`SCRAPER_USER_AGENT`) with the project link. We don't
  fake browser headers or a Google referer.
- **A broken page never stops a run.** Bad listings are skipped and counted,
  failed pages go into `errors`, and the rest of the city is still saved.

### Which Scrapling fetcher

Scrapling 0.5 removed `DynamicFetcher`; `StealthyFetcher` now covers both cases
it used to.

| Site needs | `kind=` | Scrapling class |
| ---------- | ------- | --------------- |
| Plain HTML (Wikivoyage) | `"static"` | `Fetcher` |
| JavaScript to load, or blocks simple bots | `"browser"` | `StealthyFetcher` (run `uv run scrapling install` once) |

Use an official free API instead of scraping when one exists **and** the site's
rules allow it.

## Source: Wikivoyage

- **What we fetch:** `/wiki/<City>` article pages, plus district pages
  (`/wiki/Tokyo/Shinjuku`) linked from the "Districts" section for big cities.
- **Why not the MediaWiki API:** robots.txt disallows `/w/` (which includes
  `/w/api.php`) for general bots, but says "friendly, low-speed bots are welcome
  viewing article pages."
- **What we keep:** listings under See / Do / Buy / Eat / Drink / Sleep. A
  combined heading like "Eat and drink" uses each listing's own map-marker
  type. Listings under Get in, Connect, Cope (embassies) etc. are left out.
- **Fields:** name, alt name, address, directions, lat/lng, phone, email,
  website, hours, price, description, Wikidata ID, "updated" note, and the
  subsection heading (e.g. Budget / Mid-range / Splurge, which the clean step
  can turn into a price range).
- **Source link:** `source_url` = page URL + `#anchor` of that listing, plus
  `fetched_at`. Content is CC BY-SA 4.0, so the link doubles as attribution.

## Raw record: `RawListing`

The scraper saves text as the source wrote it (see
`backend/app/scraping/models.py`). The clean step turns it into the shared
`Place` format and maps it onto `docs/itinerary-schema.md`
(`location`, `cost`, `indoor`, `source`).
