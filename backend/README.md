# backend/ — Python backend (FastAPI + data/trust layer)

The Python side of the travel planner. It lives next to the Next.js app and
doesn't change it. Design notes: [`docs/data-layer.md`](../docs/data-layer.md).

## Setup (once)

Needs [uv](https://docs.astral.sh/uv/). It installs Python 3.12 for you.

```bash
cd backend
uv sync                      # creates .venv and installs everything
cp .env.example .env         # then set DATABASE_URL (below) and your email in SCRAPER_USER_AGENT
```

## See the scraper work

```bash
uv run python -m app.scraping Sedona --no-districts
uv run python -m app.scraping Tokyo --max-districts 3
```

It prints how many places it found by type, how many have coordinates, hours,
prices and so on, some sample places with their source links, and anything that
went wrong. Everything is saved to `data/raw/<city>.json` (gitignored).

Options: `--max-districts N`, `--no-districts`, `--out FILE`, `--delay SECONDS`,
`--samples N`, `-v` (show every request).

## Clean the data and save it to the database

One-time database setup, pick one:

```bash
docker compose up -d                  # Docker: Postgres + pgvector, matches .env.example
createdb planner                      # or Postgres already on your Mac (Homebrew)
```

Then set `DATABASE_URL` in `backend/.env` (see `.env.example`; it can also be
`sqlite:///data/planner.db` to try things with no server). Then:

```bash
uv run python -m app.places ingest data/raw/sedona.json --dry-run
uv run python -m app.places ingest data/raw/sedona.json
uv run python -m app.places stats
uv run python -m app.places show Sedona --category eat --limit 5
uv run python -m app.places enrich
uv run python -m app.places init-db --reset
```

`enrich` re-computes tags, price level, hours and indoor/outdoor for places already saved,
after you change a rule in `app/places/tags.py`, `price.py` or `hours.py`.
If you pull new code and get "tables look out of date", run `init-db --reset` and ingest
again (there is no migration tool yet).

`--dry-run` cleans and de-duplicates without touching a database. `ingest` prints how
many listings were kept, what was dropped and why, and each duplicate it merged
(with the name score and distance). Running it twice changes nothing. `--reset`
erases all places.

## Checks

```bash
uv run pytest                          # unit tests, SQLite, no network
TEST_DATABASE_URL=postgresql+psycopg:///planner_test uv run pytest   # also on real Postgres
RUN_LIVE_TESTS=1 uv run pytest -m live # one real request to Wikivoyage
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

The Postgres tests erase the `places` table, so they refuse to run unless the
database name contains `test` (create one with `createdb planner_test`).

## API

```bash
uv run uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Only `GET /health` exists for now.

## Layout

```
app/main.py               FastAPI app
app/scraping/fetch.py     PoliteFetcher: robots.txt, delays, retries, honest User-Agent
app/scraping/wikivoyage.py  Wikivoyage city + district pages -> RawListing
app/scraping/models.py    RawListing / ScrapeResult (Pydantic)
app/scraping/__main__.py  The scraper command-line tool
app/config.py             Settings from env vars / backend/.env
app/places/models.py      Place: the shared clean format
app/places/clean.py       RawListing -> Place
app/places/dedupe.py      Duplicate detection and merging (RapidFuzz)
app/places/db.py, repo.py The places table and save/load functions
app/places/enrich.py      tags, price level, structured hours, indoor/outdoor
app/places/{tags,price,hours}.py  the rules behind enrich
app/places/ingest.py      clean -> de-duplicate -> enrich -> save
app/places/__main__.py    The ingest / show / stats command-line tool
docker-compose.yml        Postgres + pgvector for local development
tests/                    pytest; fixtures/ holds sample HTML
```
