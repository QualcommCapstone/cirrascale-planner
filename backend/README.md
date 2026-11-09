# backend/ — Python backend (FastAPI + data/trust layer)

The Python side of the travel planner. It lives next to the Next.js app and
doesn't change it. Design notes: [`docs/data-layer.md`](../docs/data-layer.md).

## Setup (once)

Needs [uv](https://docs.astral.sh/uv/). It installs Python 3.12 for you.

```bash
cd backend
uv sync                      # creates .venv and installs everything
cp .env.example .env         # optional: put your team email in SCRAPER_USER_AGENT
```

## See the scraper work

```bash
uv run --env-file .env python -m app.scraping Sedona --no-districts   # small city, ~5s
uv run --env-file .env python -m app.scraping Tokyo --max-districts 3 # big city + 3 districts
```

(Drop `--env-file .env` if you skipped creating `.env`.)

It prints how many places it found by type, how many have coordinates, hours,
prices and so on, some sample places with their source links, and anything that
went wrong. Everything is saved to `data/raw/<city>.json` (gitignored).

Options: `--max-districts N`, `--no-districts`, `--out FILE`, `--delay SECONDS`,
`--samples N`, `-v` (show every request).

## Checks

```bash
uv run pytest                          # unit tests (no network)
RUN_LIVE_TESTS=1 uv run pytest -m live # one real request to Wikivoyage
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

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
app/scraping/__main__.py  The command-line tool above
tests/                    pytest; fixtures/ holds sample HTML
```
