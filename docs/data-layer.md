# Data & trust layer

> Steering doc for the Python data layer in `backend/`: scraping, cleaning,
> verification, source tracking, and evals (features #11–13 in
> `feature-architecture.md`). Update this file in the same commit as any change.

## Status

| Piece | State |
| ----- | ----- |
| Scraper (Wikivoyage) | Done: `backend/app/scraping/` |
| Clean `Place` format + database + duplicate removal | Done: `backend/app/places/` |
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
`backend/app/scraping/models.py`). The ingest step turns it into `Place`.

## The shared format: `Place`

One clean record per real-world place (`backend/app/places/models.py`), stored in
the Postgres table `places`. It maps onto `docs/itinerary-schema.md`:
`id` = `location.place_id`, `price_range` = `cost.level`, `indoor` = `indoor`,
`source_url` + `fetched_at` = `source`.

| Field | Notes |
| ----- | ----- |
| `id` | UUID. Stable: made from the first source link, and never changes when the place is re-scraped or merged. |
| `name`, `city`, `district` | |
| `address`, `directions` | Real street address vs "near X station" hints (sources mix them up). |
| `lat`, `lng` | Both or neither. About 60–80% of places have them today. |
| `category` | `see` / `do` / `eat` / `sleep`. |
| `source_section`, `subsection` | The source's own type (`buy`, `drink`) and heading (`Budget`), kept for step 3. |
| `description` | |
| `opening_hours`, `price_text` | As written by the source. Step 3 turns them into structured data. |
| `price_range` (`free/low/mid/high`), `tags`, `indoor` | Columns exist, **empty until step 3**. |
| `website`, `phone`, `wikidata_id` | |
| `source`, `source_url`, `fetched_at` | The main source. A `Place` cannot be created without a web link. |
| `sources` | Every page that mentioned the place (JSON list of `{source, url, fetched_at}`). |

Category mapping: see→see, do→do, **buy→do**, eat→eat, **drink→eat**, sleep→sleep.

### For the embeddings teammate

Read from the `places` table (or `repo.search_places()`), embed
`Place.embedding_text()`, and key your vectors by `places.id`. Put vectors in
**your own table** pointing at `places.id`; you don't need to change this one.
`backend/docker-compose.yml` uses the `pgvector/pgvector` image, so the `vector`
extension is available there.

## Cleaning (`app/places/clean.py`)

Unicode normalized (full-width → normal), footnote marks and extra spaces removed,
placeholders (`?`, `n/a`, `TBD`) become empty, "addresses" that are really directions
move to `directions`, coordinates of (0, 0) are dropped. A listing with no usable name
or no web link is dropped and counted, never saved.

## Duplicates (`app/places/dedupe.py`)

Wrongly merging two real places is worse than keeping a duplicate, so the rules are
cautious. Two places are the same only if:

1. They have the same `id` (the same listing seen again, e.g. a "see also" stub), or
2. They share a Wikidata ID, or
3. They are the same kind (`see` and `do` count as one), in the same city, and
   - both have coordinates, are within 250 m, and the names match (RapidFuzz 80+/100,
     or 90+ if a name is under 10 characters), or
   - a coordinate is missing, the names match 95+/100, **and** the address, phone or a
     place-specific web page also matches. A chain's bare homepage does not count
     (this once merged two different Don Quijote stores).

On a merge, each field comes from the best source (`SOURCE_PRIORITY`), then the newest
fetch; gaps are filled from the other copy, and `sources` lists every page.
Known miss: "Kanda Shrine" vs "Kanda Myojin Shrine" (28 m apart, name score 77) stay
separate. Step 3's geocoding should help.

## Database

PostgreSQL via SQLAlchemy (SQLite also works, for tests). `DATABASE_URL` is set in
`backend/.env`. Tables are created by `python -m app.places init-db`; there is no
migration tool yet (add Alembic when more than one person changes the schema).
`ingest` loads the city's existing places first and de-duplicates old + new together,
so a second source or a re-scrape merges into existing rows and keeps their ids.
Places that disappear from a source are not removed yet (the refresh job, step 5).
