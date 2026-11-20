# scraper/ — travel place collection

Collects real, sourced places for a city and hands them to Aayush's data layer in
`backend/`, which cleans, de-duplicates and enriches them and exports JSONL for the
FastAPI ingestion in `apps/api`. Spec: [`docs/data-ingestion-spec.md`](../docs/data-ingestion-spec.md).

```
Wikivoyage (backend/) ─┐
OpenStreetMap ─────────┼─► backend/data/raw/*.json ─► backend ingest ─► enrich ─► export ─► <city>.jsonl ─► apps/api ingest ─► Qdrant
DuckDuckGo ─► crawl ───┘        (+ Wikidata coordinates)
```

## Setup

Needs [uv](https://docs.astral.sh/uv/) (it installs Python 3.12). `backend/` and
`apps/api/` need their own `uv sync` too, since `collect` runs them.

```bash
cd scraper
uv sync
cp .env.example .env          # put your team email in SCRAPER_USER_AGENT

# optional, only for --playwright (JavaScript-rendered pages)
uv sync --extra playwright
uv run playwright install chromium
```

## Run it

```bash
# Everything for one city. Uses backend's DATABASE_URL unless you pass one.
uv run python -m travel_scraper collect Tokyo --country Japan \
    --database-url sqlite:///data/planner.db --ingest-api
uv run python -m travel_scraper collect Tokyo --country Japan --discover   # + web crawl
uv run python -m travel_scraper collect Tokyo --country Japan --dry-run    # no database

# One step at a time
uv run python -m travel_scraper osm Tokyo --country Japan [--center 35.68,139.76] [--radius-km 15]
uv run python -m travel_scraper fill-coords ../backend/data/raw/tokyo.json
uv run python -m travel_scraper discover Tokyo --country Japan --categories museums,restaurants
uv run python -m travel_scraper crawl Tokyo --country Japan --max-pages 40 [--playwright]
```

`--database-url` is a path relative to `backend/` for SQLite. The JSONL lands in
`backend/data/export/<city>.jsonl`. `--ingest-api` checks it with apps/api's ingest in
mock mode (mock embeddings, in-memory store): nothing reaches Qdrant.

## Sources

| Source | What | How | License |
|---|---|---|---|
| Wikivoyage | See/Do/Eat/... listings | Aayush's scraper in `backend/` (HTML, robots.txt) | CC BY-SA 4.0 |
| OpenStreetMap | Attractions, parks, food, bars, hotels with coordinates | Overpass API, one query per section, filters in the query | ODbL 1.0 |
| Wikidata | Coordinates (P625) for listings without them | `wbgetentities`, 50 IDs/request, `maxlag` | CC0 1.0 |
| Web pages | Places on official/attraction/restaurant sites | DuckDuckGo finds URLs → Scrapy crawls eligible ones → JSON-LD / microdata | the site's own; facts only, no descriptions copied |

### Rules

- Websites: `ROBOTSTXT_OBEY`, AutoThrottle, 1 request at a time per site, 3 s delay,
  page and depth limits, honest User-Agent. Never bypass CAPTCHAs, logins or bot blocks.
- APIs: their usage policies (serial requests, delays, `maxlag`, `Retry-After`).
- A response that is HTTP 200 but really an error (Overpass partial data, Wikidata
  `maxlag`) is retried, then discarded. Partial data is never saved.
- Discovery only finds URLs. Social, booking/review/aggregator, search engines and our own
  sources (Wikipedia/Wikivoyage/OSM/Wikidata) are rejected before anything is crawled.
- Crawled pages without schema.org place data give nothing: we don't guess places from text.
- `ddgs` calls DuckDuckGo's public web endpoints (not an official API). Keep volume low;
  swap in another `SearchProvider` (e.g. an authorized search API) if it grows.

## Code

```
src/travel_scraper/
  cli.py, collect.py     commands; collect runs every step
  handoff.py             RawListing/ScrapeResult (the shape backend/ reads)
  http.py                ApiClient: delays, retries, 200-with-error detection
  osm/                   query.py (Overpass QL), parse.py (elements -> listings), scrape.py
  wikidata.py            coordinate fill
  discovery/             base.py (provider interface), duckduckgo.py, urls.py (filter), discover.py
  crawl/                 extract.py (JSON-LD/microdata), spider.py (Scrapy), run.py
  backends.py            runs backend/ and apps/api CLIs in their own environments
```

## Checks

```bash
uv run pytest                    # all offline; includes integration tests (needs uv)
uv run pytest -m "not integration"
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

The integration tests run fixture data through backend's real `ingest`/`enrich`/`export`
and apps/api's real `ingest` (mock mode), and require 0 failed lines.

## Known limits

- **DuckDuckGo blocks automated searches** (Nov 17, 2026 test): `html.duckduckgo.com` answers
  `ddgs` with HTTP 202, its anti-bot challenge, so every query returns "No results found".
  We don't work around bot blocks. The fix is an authorized search API (Brave Search API,
  Google Programmable Search) as another `SearchProvider` in `discovery/`; the crawler
  doesn't change. Until then `collect --discover` finds nothing and the rest still runs.

- The contract (`apps/api/app/schemas/place.py`) has no category for hotels and requires
  coordinates, so `sleep` places and places without lat/lng aren't exported.
  Tags, indoor/outdoor and structured hours are dropped at export (no contract fields).
- Coordinates filled from Wikidata aren't marked as such in the raw file (`RawListing` has
  no provenance field). Wikidata is CC0, so attribution isn't affected.
- Dedupe across sources by Wikidata ID misses places the sources file under different
  kinds; see the D7 proposal in `docs/data-layer.md`.
