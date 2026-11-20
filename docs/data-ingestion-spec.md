# Data Ingestion: Feature Spec (SCRUM-63)

Nov 17, 2026 · Drew · Status: **Approved for implementation** (team decisions in section 2)

Jira: [SCRUM-63](https://qualcomm-ai100-travel.atlassian.net/browse/SCRUM-63), under epic SCRUM-37.
Branch: `SCRUM-63-data-ingestion` (contains `backend/tags-and-details`, `main`, and PR #10).

## 1. Goal

Collect real, sourced places for a city and export them as JSONL that the FastAPI
ingestion CLI from PR #10 (`apps/api`: `python -m app.ingest`) accepts unchanged.
The backend embeds the records into Qdrant for RAG.

This feeds the **retrieval/ranking** stage of the sponsor's pipeline
(`docs/sponsor-spec.md`). Retrieval hands the LLM real candidates instead of the
LLM inventing places from memory.

**Success:** `apps/api`'s ingest CLI, in mock mode, accepts every line of
`tokyo.jsonl` with zero failures.

## 2. Team decisions (Nov 17)

| # | Decision |
|---|---|
| D1 | Vector store is **Qdrant** (owned by the backend developer). |
| D2 | New standalone Python package at **`scraper/`**. Reuse Aayush's `backend/` (cleaning, dedupe, enrichment, database), don't duplicate it. |
| D4 | LLM tagging deferred. |
| D5 | The JSONL contract is **PR #10's `Place`** (`apps/api/app/schemas/place.py`). Don't change it; adapt to it. |
| D6 | `httpx` approved for APIs. **Scrapy** for crawling, **Playwright** only where JavaScript rendering is required. |
| D7 | Don't modify Aayush's `find_match`. If matching needs to change: failing fixture test + written proposal + Aayush's review. |

## 3. What already exists (reused, not rewritten)

| Piece | Where | Owner |
|---|---|---|
| Wikivoyage scraper, polite fetcher | `backend/app/scraping/` | Aayush |
| `RawListing` / `ScrapeResult` (raw handoff format) | `backend/app/scraping/models.py` | Aayush |
| Clean → dedupe → Postgres/SQLite `places` | `backend/app/places/{clean,dedupe,ingest,repo,db}.py` | Aayush |
| Tags, price level, indoor, structured hours | `backend/app/places/{tags,price,hours,enrich}.py` | Aayush |
| JSONL contract + ingest CLI, mock embeddings | `apps/api/app/schemas/place.py`, `apps/api/app/ingest.py` | Backend developer (PR #10) |

## 4. Architecture

```
scraper/ (new, Drew)                         backend/ (Aayush, reused)               apps/api/ (PR #10)
─────────────────────                        ────────────────────────               ──────────────────
DuckDuckGo discovery ─► eligibility filter
        │                       │
        ▼                       ▼
   OSM (Overpass)        Scrapy crawl (+Playwright)
        │                       │
        └───► ScrapeResult JSON ◄┘   (+ Wikidata coordinate fill)
                    │
                    ▼
              ingest  ─►  enrich  ─►  places table
                                          │
                                          ▼
                           export (new file, contract adapter) ─► <city>.jsonl ─► app.ingest ─► Qdrant
```

**Handoff format:** every `scraper/` source writes a `ScrapeResult` JSON file with
`RawListing`s, the same format Aayush's Wikivoyage scraper writes. Aayush's
`python -m app.places ingest` and `enrich` then process it with no changes.

`backend/` isn't an installable package (`package = false`), and both `backend/`
and `apps/api/` use the top-level package name `app`. So `scraper/` doesn't import
either. It writes JSON in their format and tests check compatibility by running
their CLIs in their own environments.

**Changes to Aayush's code:** none to existing files. The export adapter is a
**new file**, `backend/app/places/export.py`, run as
`python -m app.places.export`. It needs Aayush's review.

## 5. `scraper/` package

```
scraper/
├── pyproject.toml          uv project; deps isolated from backend/ and apps/api/
├── README.md
├── .env.example
├── src/travel_scraper/
│   ├── cli.py              python -m travel_scraper {osm,discover,crawl,fill-coords,collect}
│   ├── config.py           settings from env (User-Agent, delays, limits)
│   ├── handoff.py          ScrapeResult/RawListing JSON writer (mirrors backend shape)
│   ├── http.py             ApiClient (httpx): per-host delay, retries, 200-with-error detection
│   ├── osm/                Overpass query builder + element parser (pure)
│   ├── wikidata.py         batched entity lookup, coordinate fill (pure parser + client)
│   ├── discovery/          provider interface, DuckDuckGo provider, URL normalize/filter
│   └── crawl/              Scrapy settings, spider, JSON-LD + HTML extraction (pure)
└── tests/                  offline, fixtures only
```

### 5.1 Fetch policy

| Kind | Rules followed | Client |
|---|---|---|
| Website pages (crawl) | robots.txt (`ROBOTSTXT_OBEY = True`), site terms | Scrapy |
| Official APIs (Overpass, Wikidata) | each API's usage policy: honest User-Agent, serial requests, `maxlag` for Wikidata | `ApiClient` (httpx) |
| Search provider (DuckDuckGo) | provider's terms; low volume, delay between queries | discovery provider |

Never bypass CAPTCHAs, logins, paywalls, or anti-bot measures, and never fake
browser headers. Playwright renders JavaScript; it is not a tool for getting past
bot blocking.

**HTTP 200 that is really an error is a failure:** an Overpass `remark` reporting a
timeout or memory error (partial data), or a Wikidata `maxlag` error. Retry with
growing waits; if retries run out, that query fails and its partial data is
discarded, never written.

### 5.2 OpenStreetMap source

`python -m travel_scraper osm <city> --country <country> [--center lat,lng] [--radius-km 15] [--max-per-section 300]`

- **Center:** `--center`, or else the median coordinates of the newest Wikivoyage
  raw file for that city in `backend/data/raw/`. Neither means exit with an error
  before any request.
- **One Overpass query per section**, with quality filters inside the query:

| Section | OSM tags | Also requires |
|---|---|---|
| `see` | `tourism=attraction\|museum\|gallery\|viewpoint\|zoo\|aquarium\|theme_park`; `historic=*`; `amenity=place_of_worship` | `wikidata` for `historic` and `place_of_worship` |
| `do` | `leisure=park\|garden\|nature_reserve`; `amenity=theatre\|cinema\|arts_centre` | `wikidata` or `website` |
| `buy` | `shop=mall\|department_store`; `amenity=marketplace` | |
| `eat` | `amenity=restaurant\|cafe\|food_court` | `wikidata`, or `website` + `opening_hours` |
| `drink` | `amenity=bar\|pub\|nightclub` | `wikidata`, or `website` + `opening_hours` |
| `sleep` | `tourism=hotel\|hostel\|guest_house` | `wikidata` or `website` |

- `--max-per-section` caps every section, keeping `wikidata`-tagged elements first,
  then the ones with the most filled tags.
- **Names:** keep an element if it has `name:en` or `name`. `name` = `name:en` if
  present, else `name`. A differing local `name` goes to `alt_name`. Neither means
  skip and count.
- **Mapping to `RawListing`:** `source="osm"`, `source_url` = the element's
  openstreetmap.org page, `page_url` = same, coordinates from the node or the
  way/relation center, `address` from `addr:*`, `website`, `phone`, `hours` from
  `opening_hours`, `wikidata_id`, `description` if present. For Aayush's tag rules,
  OSM type information (cuisine, `tourism=museum`, ...) goes into `subsection` as a
  short readable label ("Museum", "Ramen restaurant") since `RawListing` has no
  free-form tag field.
- **License:** ODbL 1.0, "© OpenStreetMap contributors".

### 5.3 Discovery (DuckDuckGo)

`python -m travel_scraper discover <city> --country <country> --categories attractions,restaurants,activities [--max-results 30]`

- **Provider interface** (`discovery/base.py`): `search(query, max_results) -> list[SearchHit]`.
  The DuckDuckGo provider uses a maintained library (`ddgs`). Swapping providers
  (an authorized search API) needs no crawler change.
- **Queries per category**, e.g. "Tokyo Japan museums official website", "Tokyo Japan
  restaurants".
- **Normalize:** lowercase host, drop `www.`, fragments, tracking parameters
  (`utm_*`, `fbclid`, `gclid`), trailing slashes. Deduplicate.
- **Eligibility filter** before anything is crawled:
  - **Rejected:** social media, video sites, booking/aggregator and review sites
    (TripAdvisor, Yelp, Booking.com, Expedia, ...), Wikipedia/Wikivoyage (covered by
    their own sources), and non-HTML files (`.pdf`, images, ...).
  - **Preferred and kept:** official sites (`.go.jp`, `.gov`, tourism boards) and
    attraction/restaurant domains.
  - Every decision is recorded with a reason.
- **Output:** `data/discovery/<city>.jsonl`: `{url, query, provider, discovered_at, eligible, reason}`.
- **Failures:** a search error or rate limit is logged and that query is skipped.
  Discovery never fails the whole run.

### 5.4 Crawl (Scrapy, optional Playwright)

`python -m travel_scraper crawl <city> --country <country> [--max-pages 50] [--max-depth 1] [--playwright]`

- Starts from eligible discovered URLs. `allowed_domains` is limited to those hosts.
- **Settings:** `ROBOTSTXT_OBEY=True`, `AUTOTHROTTLE_ENABLED=True`,
  `CONCURRENT_REQUESTS_PER_DOMAIN=1`, `DOWNLOAD_DELAY` from config (default 3 s),
  `DOWNLOAD_TIMEOUT=30`, retry middleware on, `DEPTH_LIMIT` = `--max-depth`,
  `CLOSESPIDER_PAGECOUNT` = `--max-pages`, honest `USER_AGENT`.
- **Follow** only same-domain links whose path suggests a place or listing
  (`/attractions`, `/museum`, `/restaurant`, `/spot`, `/see`, `/eat`, `/things-to-do`,
  pagination `?page=`).
- **Extraction (pure functions):**
  1. **JSON-LD** first: `schema.org` types `TouristAttraction`, `Museum`, `Park`,
     `LandmarksOrHistoricalBuildings`, `PlaceOfWorship`, `Restaurant`, `FoodEstablishment`,
     `CafeOrCoffeeShop`, `BarOrPub`, `LocalBusiness`, `Hotel`, `LodgingBusiness`.
     Reads `name`, `address`, `geo`, `openingHours`/`openingHoursSpecification`,
     `priceRange`, `url`, `telephone`, `sameAs` (Wikidata ID).
  2. **Microdata fallback** when there's no JSON-LD (`itemscope itemtype="https://schema.org/…"`
     with `itemprop` name, address, geo, ...). A page with neither gives nothing: without a
     schema.org type we can't tell a museum page from a blog post. Plain `LocalBusiness` /
     `Organization` are also skipped as too vague.
- **Section** from the schema.org type (Restaurant → `eat`, BarOrPub → `drink`,
  Hotel → `sleep`, Museum → `see`, ...).
- **Descriptions are not copied** from crawled sites (copyright on commercial
  content; this repo is public). Only facts are kept: name, address, coordinates,
  hours, price, phone, website. `source_url` links the page.
- **Playwright:** only with `--playwright`, and only for a page whose HTML has
  neither JSON-LD nor a name (a sign it's rendered client-side). Requires the
  optional `playwright` extra and a one-time `playwright install chromium`.
- **Output:** a `ScrapeResult` (`source="web"`) in `backend/data/raw/<city>-web.json`.

### 5.5 Wikidata coordinate fill

`python -m travel_scraper fill-coords <raw.json>`

For `RawListing`s with a `wikidata_id` and no coordinates, batched `wbgetentities`
lookups (50 IDs per request) read P625 and fill `lat`/`lng`. The file is rewritten
in place, and the count of filled listings is reported. `RawListing` has no provenance
field, so a filled coordinate isn't marked as coming from Wikidata (CC0, so attribution
is unaffected). Runs on any raw file,
including Aayush's Wikivoyage output, before ingest. The contract requires
coordinates (section 6), so this decides how many Wikivoyage places can be exported.

### 5.6 `collect`

`python -m travel_scraper collect <city> --country <country> [--discover] [--playwright] [--dry-run]`

Runs, in order: Wikivoyage scrape (Aayush's CLI) → `fill-coords` → `osm` →
(`discover` → `crawl` if `--discover`) → `ingest` each raw file → `enrich` →
`export`. Backend steps run as subprocesses (`uv run --project backend ...`), so each
package keeps its own environment. A failed source stops before its `ingest`.
`--dry-run` stops after writing raw files and reports. It prints the section 9
report at the end.

## 6. JSONL export (contract adapter)

New file `backend/app/places/export.py`:

`python -m app.places.export --city Tokyo --country Japan [--out data/export/tokyo.jsonl]`

Reads `places` (after `enrich`) and writes one PR #10 `Place` per line:

| Contract field | From Aayush's `Place` |
|---|---|
| `id` | `str(id)` (stable UUID) |
| `name`, `city`, `address`, `opening_hours` | same |
| `country` | `--country` (Aayush's `Place` has no country) |
| `description` | `description` or `""` |
| `category` | see mapping below |
| `lat`, `lng` | same; **required**, so places without them are skipped and counted |
| `price_level` | `price_range`: free→`free`, low→`$`, mid→`$$`, high→`$$$`, null→null |
| `source_url` | `source_url` |
| `source_attribution` | each distinct source, joined with "; ": "Wikivoyage contributors", "© OpenStreetMap contributors", or the site's host for `web` |
| `license` | each distinct license, joined with "; ": `CC BY-SA 4.0` (wikivoyage), `ODbL 1.0` (osm), `see source` (web) |
| `collected_at` | `fetched_at` |

**Category mapping**, from Aayush's `category`/`source_section`/`tags` to the
contract's `sight|food|nature|culture|nightlife|shopping`:

1. `source_section` `drink` → `nightlife`
2. `source_section` `buy` → `shopping`
3. `category` `eat` → `food`
4. `category` `sleep` → **not exported** (no contract category; flagged to the backend developer)
5. `see`/`do` with tags `nature`, `outdoors`, `hiking`, `beach`, or `views` → `nature`
6. `see`/`do` with tags `museum`, `art`, `history`, `culture`, `religious`, or `architecture` → `culture`
7. `see`/`do` with `nightlife` → `nightlife`; with `shopping` → `shopping`
8. any other `see`/`do` → `sight`

Rules apply in order; first match wins.

Every line is validated against a local copy of the contract's field rules before
writing. The integration test (section 8) validates against the real
`apps/api` model. Lines sort by `city`, `category`, `name`, `id`. The command
reports exported, skipped (no coordinates), and skipped (`sleep`).

**Lost at export:** tags, indoor, structured hours, Wikidata ID, and the full
source list. The contract has no fields for them. Suggest optional `tags` to the
backend developer; don't change the contract here.

## 7. Dedupe (D7)

Problem: `find_match` checks the place kind before the Wikidata ID, so an OSM
`amenity=marketplace` (`buy` → `do`) and a Wikivoyage Eat listing for the same
market never merge, even with the same Wikidata ID.

This ticket only adds:
- a fixture-based test in `backend/tests/test_dedupe_proposal.py`, marked
  `xfail(strict=True)`, showing the miss
- a proposal in `docs/data-layer.md`: check the Wikidata ID before the kind

`find_match` stays unchanged pending Aayush's review.

## 8. Tests

All offline, fixtures only. Live checks stay behind `RUN_LIVE_TESTS=1`.

- **`scraper/`:** Overpass query building; element parsing (names, centers, address,
  caps, skipped counts); `ApiClient` retries, `Retry-After`, 200-with-error;
  Wikidata parsing and fill; URL normalization, eligibility filter, DuckDuckGo
  provider with a mocked library; JSON-LD and HTML extraction from fixture pages;
  schema.org → section mapping; Playwright selection logic; handoff JSON writer.
- **Handoff compatibility:** run `backend`'s `ingest --dry-run` on files written by
  each `scraper/` source (subprocess).
- **`backend/`:** export adapter mapping table, category rules, skips, sort order,
  contract validation; the D7 xfail test.
- **Integration:** export a fixture database → run `apps/api` `python -m app.ingest`
  in mock mode (subprocess) → `failed == 0`.
- `ruff` (and `mypy` where the package uses it) pass in each package.

## 9. Proof of concept: Tokyo

Run `collect Tokyo --country Japan --discover` and post the report on SCRUM-63:

- URLs discovered, eligible, rejected (by reason)
- pages crawled, skipped by robots.txt, failed
- raw listings per source; coordinates filled from Wikidata
- after ingest: cleaned, dropped, duplicates merged
- exported, skipped (no coordinates), skipped (`sleep`)
- **accepted by `apps/api` ingest** (target: all exported lines)
- fill rates: description, price level, opening hours
- source failures and restrictions

Target up to 100 legitimate places. No padding to reach it.

## 10. Rules

- Respect robots.txt, API usage policies, site terms, and licenses.
- Never fabricate a field. Unknown stays null or the record is skipped.
- Keep source URL, collection time, attribution, and license on every record.
- Scraped and exported data stays out of git (`data/` gitignored in each package).
- No FastAPI endpoints, embeddings, Qdrant, Cirrascale calls, LLM tagging, or
  frontend changes.

## 11. Acceptance criteria

- [ ] `scraper/` package with `osm`, `discover`, `crawl`, `fill-coords`, `collect`
- [ ] OSM extraction works with server-side filters and caps
- [ ] DuckDuckGo discovery works through the provider interface, with eligibility filtering
- [ ] Scrapy crawls eligible URLs with the section 5.4 settings; Playwright fallback available
- [ ] Raw output from every source passes Aayush's `ingest --dry-run` unchanged
- [ ] `python -m app.places.export` writes contract JSONL; `apps/api` ingest accepts it with 0 failures
- [ ] D7 xfail test + proposal written; `find_match` unchanged
- [ ] All tests offline and passing; linters pass
- [ ] `scraper/README.md` covers install, config, sources, and running; `docs/data-layer.md` updated
- [ ] Tokyo report posted on SCRUM-63

## 12. Spec pipeline check

| Stage | Effect |
|---|---|
| Preference capture | Contract categories match the frontend's activity categories |
| **Retrieval/ranking** | **Supplies the Qdrant corpus** |
| Itinerary generation | Grounds the RAG service in real places |
| Visual presentation | Real coordinates for globe pins |
| Iteration/refinement | No direct effect |

**Drift to flag:** hotels (`sleep`) can't be exported under the current contract, and
tags/indoor are dropped at export. Both limit preference-based ranking until the
backend developer extends the contract.
