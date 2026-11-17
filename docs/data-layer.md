# Data & trust layer

> Steering doc for the Python data layer in `backend/`: scraping, cleaning,
> verification, source tracking, and evals (features #11–13 in
> `feature-architecture.md`). Update this file in the same commit as any change.

## Status

| Piece | State |
| ----- | ----- |
| Scraper (Wikivoyage) | Done: `backend/app/scraping/` |
| Clean `Place` format + database + duplicate removal | Done: `backend/app/places/` |
| Interest tags, price level, indoor/outdoor, structured hours | Done: `backend/app/places/{tags,price,hours,enrich}.py` |
| More sources: OpenStreetMap, web crawl (DuckDuckGo discovery + Scrapy) | Done: `scraper/` (SCRUM-63), writes `RawListing` files that `ingest` reads unchanged |
| JSONL export to the backend contract (`apps/api`) | Done: `python -m app.places.export` (SCRUM-63), see [Export](#export-to-the-backend-contract) |
| Places read API (`GET /places`) | Next (Sem 1: teammates can't read the data yet) |
| Coordinates for every place | Improved: OSM places always have them; `scraper/ fill-coords` fills Wikivoyage listings from Wikidata |
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

> **Proposed change (SCRUM-63, for review):** use `"browser"` only for pages that need
> JavaScript to render. If a site blocks simple bots, don't scrape it: getting past bot
> blocking conflicts with "never bypass anti-bot measures" (team rule, and the scraper's
> rules in `scraper/README.md`).

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
| `source_section`, `subsection` | The source's own type (`buy`, `drink`) and heading (`Budget`). Used for tags and price level. |
| `description` | |
| `opening_hours`, `price_text` | As written by the source. |
| `opening_hours_osm` | The hours in OpenStreetMap format, only when fully understood. `Place.is_open_at(local_datetime)` answers "open then?" (`None` = unknown). |
| `price_range` | `free` / `low` / `mid` / `high`. Empty when unknown. |
| `price_estimate`, `price_currency` | Rough per-person cost: the **first** amount in `price_text` (a range gives its middle). |
| `tags` | Interest tags (list below). |
| `indoor` | `true` indoors, `false` outdoors, `null` unknown or mixed. |
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

## Enrichment (`app/places/enrich.py`)

Runs on every ingest, after duplicates are merged, and again on demand with
`python -m app.places enrich`. It is **always recomputed from the place's own text**, so
fixing a rule and re-running it fixes old rows too (no re-scrape). It never invents data:
when the text doesn't support an answer the field stays empty. Because it recomputes,
anything written by hand into `tags`, `indoor` or the price fields will be overwritten.

**Opening hours** (`hours.py`) turn text like `Tue-Sun 10:00-17:00 (closed Mon)` into
`Tu-Su 10:00-17:00`. It only converts text it fully understands, including 12-hour times,
overnight hours (`17:00-03:00`), day lists (`Fri Sat`), `closed ...` clauses and `24 hours`.
It refuses anything with seasons, exceptions ("until 19:00 on Fridays"), "happy hour",
`10-5`, or hours that look like typos. "Last order/entry" notes are ignored. About two
thirds of the hours text in Tokyo is understood. "Closed on holidays" is not put into the
structured hours (we have no holiday calendar, and the planner's hours parser rejects a whole
string containing `PH`); the original text keeps it.

**Price level** (`price.py`), first match wins: the text says free; for eat/sleep the
Wikivoyage heading (`Budget` = low, `Mid-range` = mid, `Splurge` = high); the amount
converted to US dollars at a fixed rough rate (JPY, USD, EUR, GBP) against typical prices
for that type (meal under $12 = low, under $35 = mid; night under $90 / $220; ticket under
$15 / $50). Amounts in other currencies get no level. Long text (over 200 characters) is
ignored, since it is usually a paragraph of exceptions.

**Tags and indoor/outdoor** (`tags.py`) are readable keyword rules. They look at the
name and heading first; the start of the description is used only for sights and
activities that aren't shops. Mixed evidence ("garden museum") gives `indoor = null`.
Eating and sleeping places default to indoor unless the name says "food truck", "camp" etc.
Tags: `food nightlife shopping museum art history culture religious outdoors nature hiking
beach views family entertainment music sports wellness architecture camping` plus lodging
types `hotel hostel ryokan`. Known weak spots: no cuisine tags yet, and "kid-friendly" or
"wheelchair-accessible" from `docs/itinerary-schema.md` are not set (the text rarely says).

Real-data coverage (Tokyo, 761 places): price level 50%, tags 96%, indoor/outdoor 77%.

## Who needs what (from the Feature List sheet)

| Sheet item (timeline) | Data it needs | State |
| --------------------- | ------------- | ----- |
| 2 Prompt to itinerary (Sem 1) | Real places per demo city, with source links | Tokyo, Sedona loaded; **no read API yet** |
| 4 Personalized picks (Sem 1) | Tags, price level, coordinates (distance), embedding text | Done except missing coordinates |
| 5 Edit by chat (Sem 1) | Look up replacement stops by city, type, tag | Needs the read API |
| 7 Smart routing (Sem 1/2) | lat/lng on every stop | 20–40% missing |
| 9 Weather-aware (Sem 1/2) | `indoor` | Done |
| 6 Budget tracker, 8 Opening hours, 10 Backups, 14 Plan validation, 18 Evals (Sem 2) | `price_estimate`, `is_open_at`, enough places per area, the verifier, evals | Data fields done; verifier and evals not started |
| 3 Visual itinerary photos (Sem 2) | Photo URL per place | Not collected yet |

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
separate.

## Not built yet, and why

- **OpenStreetMap as a second source / geocoding.** Public servers either disallow bots in
  robots.txt (`overpass-api.de` blocks `/api/`; `nominatim.openstreetmap.org` blocks
  `/search`) or didn't answer from our network (`overpass.private.coffee`,
  `overpass.kumi.systems`). Their usage policies do allow API clients, so this needs a team
  decision (or our own Overpass instance) before we use it. Data is ODbL (needs
  "© OpenStreetMap contributors" credit).
- **Cuisine / accessibility tags**, and **photos** for places.

## Database

PostgreSQL via SQLAlchemy (SQLite also works, for tests). `DATABASE_URL` is set in
`backend/.env`. Tables are created by `python -m app.places init-db`; there is no
migration tool yet (add Alembic when more than one person changes the schema).
`ingest` loads the city's existing places first and de-duplicates old + new together,
so a second source or a re-scrape merges into existing rows and keeps their ids.
Places that disappear from a source are not removed yet (the refresh job, step 5).

## More sources from `scraper/` (SCRUM-63)

`scraper/` (its own uv package; see `scraper/README.md`) writes the same `ScrapeResult`
JSON as the Wikivoyage scraper, into `backend/data/raw/`:

| File | Source | `source` value | License |
| ---- | ------ | -------------- | ------- |
| `<city>-osm.json` | OpenStreetMap via Overpass | `osm` | ODbL 1.0 |
| `<city>-web.json` | Crawled official/attraction/restaurant sites (JSON-LD / microdata) | `web` | the site's own; facts only, no descriptions |

`ingest` and `enrich` handle them with no changes. OSM puts a readable label of what the
place is ("Museum", "Ramen restaurant", "Shinto shrine") in `subsection`, so the tag
rules pick it up. `scraper/ fill-coords <raw.json>` fills missing lat/lng from Wikidata
(P625) for listings that have a Wikidata ID; run it before `ingest`.

## Export to the backend contract

```bash
uv run python -m app.places.export --city Tokyo --country Japan   # -> data/export/tokyo.jsonl
```

Writes one record per line in the shape of `apps/api/app/schemas/place.py` (PR #10), which
`apps/api`'s `python -m app.ingest` reads. Run after `ingest` and `enrich`.

| Contract field | From `Place` |
| -------------- | ------------ |
| `id` | `str(id)` |
| `country` | `--country` (`Place` has no country) |
| `category` | `drink`→nightlife, `buy`→shopping, eat→food; see/do by tags: nature/outdoors/hiking/beach/views→nature, museum/art/history/culture/religious/architecture→culture, nightlife, shopping, else sight |
| `lat`, `lng` | required: places without them are skipped and counted |
| `price_level` | `price_range` free/low/mid/high → free/$/$$/$$$ |
| `description` | `description` or `""` |
| `source_attribution`, `license` | one entry per source (Wikivoyage contributors / © OpenStreetMap contributors / site host; CC BY-SA 4.0 / ODbL 1.0 / see source) |
| `collected_at` | `fetched_at` |

**Not exported:** `sleep` places (the contract has no lodging category), and tags,
indoor/outdoor, structured hours, Wikidata ID, and the full `sources` list (no contract
fields). Raise with the backend developer before changing the contract.

## Proposal: Wikidata match before kind (D7, needs review)

`find_match` returns "different places" for different kinds before it looks at the
Wikidata ID, and `dedupe` only compares places of the same kind. So an OSM market
(`amenity=marketplace` → buy → do) and a Wikivoyage Eat listing for the same market never
merge, even with the same Wikidata ID. `backend/tests/test_dedupe_proposal.py` shows it
(strict xfail).

Proposed change: in `find_match`, check the Wikidata ID right after the same-id check; in
`dedupe`, also union places of one city that share a Wikidata ID before blocking by kind.
When merged, keep the category of the best source (`SOURCE_PRIORITY`). Remove the xfail
markers in the same commit.
