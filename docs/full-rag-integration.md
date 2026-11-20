# Full RAG integration — scraped data → Qdrant → grounded itinerary

How the pieces connect into one data-grounded planner, and how to run it locally.
This is the **active** demo path; the legacy in-Next pipeline (Wikipedia) stays only
as an unselected fallback.

## Architecture

```
Browser → Next.js /planner → /api/itinerary (proxy)
        → FastAPI /api/v1/plan
            → Cirrascale BGE query embedding (768D)
            → Qdrant semantic search (filtered by city + category)
            → grounded context from real Place records
            → Cirrascale Llama 3.1 8B  (outline, then one call per day, concurrent)
            → validated Trip/Stop/Activity
        → NDJSON stream (outline → stop… → done) → globe + itinerary cards
```

Offline ingestion (run once; re-runnable):

```
OSM + Wikivoyage + Wikidata  →  backend clean/dedupe/enrich  →  tokyo.jsonl
   →  apps/api ingestion CLI  →  Cirrascale BGE embeddings  →  Qdrant (tokyo_dev)
```

There is one RAG architecture. The FastAPI providers, Pydantic `Place`/`Trip`
contracts, ingestion CLI and Next.js streaming proxy are all reused unchanged.

## One-time local setup

```bash
# 0. Docker runtime (macOS uses Colima here)
colima start                       # if `docker ps` fails
docker compose -f infra/docker-compose.yml up -d qdrant
curl -s localhost:6333/ | grep qdrant      # health

# 1. Generate the real Tokyo dataset (scraper → backend → JSONL)
cd scraper && uv sync
cp .env.example .env               # set a contact in SCRAPER_USER_AGENT (no personal email)
uv run python -m travel_scraper collect Tokyo --country Japan \
    --database-url sqlite:///data/planner.db
# → backend/data/export/tokyo.jsonl  (~1,300 contract-valid places; lodging + no-coords skipped)
```

## Embedding configuration

| Env | Value | Note |
|---|---|---|
| `EMBEDDING_PROVIDER` | `cirrascale` | real `/embeddings`; never falls back to mock |
| `CIRRASCALE_EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | 768D (default). `bge-large` = 1024D |
| `EMBEDDING_BATCH_SIZE` | `64` | batched ingestion |
| `EMBEDDING_QUERY_INSTRUCTION` | *(empty)* | off — hosted BGE scored worse with the usual BGE instruction |

The vector dimension is **fixed by the model**, so the Qdrant collection and store
match automatically — there is no `VECTOR_DIM` to set for real embeddings (that knob
is only for the mock). Switching models (e.g. to `bge-large`) means re-embedding the
collection, since the two spaces are not comparable; payloads carry `model_version`
and searches filter on it to enforce this.

## Ingest into Qdrant

```bash
cd apps/api
EMBEDDING_PROVIDER=cirrascale CIRRASCALE_EMBEDDING_MODEL=BAAI/bge-base-en-v1.5 \
VECTOR_STORE_PROVIDER=qdrant QDRANT_URL=http://localhost:6333 QDRANT_COLLECTION=tokyo_dev \
  uv run python -m app.ingest ../../backend/data/export/tokyo.jsonl
```

Reports `total / succeeded / failed` and never silently drops a record. **Idempotent:**
ids are a stable `uuid5` of the place id, so re-running upserts in place — the point
count does not grow. The payload preserves id, name, city, country, category, lat,
lng, description, address, source_url, source_attribution, license and `model_version`.

Verify:

```bash
curl -s localhost:6333/collections/tokyo_dev | python3 -m json.tool | grep -E 'points_count|size|distance'
```

## Run the app on the real path

`apps/api/.env`:

```env
LLM_PROVIDER=cirrascale
EMBEDDING_PROVIDER=cirrascale
VECTOR_STORE_PROVIDER=qdrant
CIRRASCALE_API_KEY=…              # server-only, never sent to the browser
CIRRASCALE_MODEL=Llama-3.1-8B
CIRRASCALE_EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=tokyo_dev
```

`apps/web/.env.local`:

```env
BACKEND_URL=http://localhost:8000   # set → /api/itinerary proxies to FastAPI (the active path)
```

```bash
cd apps/api && uv run uvicorn app.main:app --port 8000   # /ready shows all providers "ok"
npm run dev:web                                           # http://localhost:3000/planner
```

With `BACKEND_URL` unset the frontend uses the legacy in-Next pipeline instead; it is
never a silent fallback — if the backend is unreachable the proxy returns 502.

## Semantic-search sanity check

Category filters matter: plain vector similarity will mix a food blurb into a
"temples" query, so retrieval is always filtered by `city` + `category`.

```bash
cd apps/api
EMBEDDING_PROVIDER=cirrascale VECTOR_STORE_PROVIDER=qdrant QDRANT_COLLECTION=tokyo_dev \
  uv run python - <<'PY'
import asyncio
from app.config import get_settings
from app.providers import build_providers
from app.schemas.place import SearchFilters
async def main():
    p = build_providers(get_settings())
    v = await p.embedding.embed_query("traditional Japanese food and sushi")
    for r in await p.vector_store.search(v, SearchFilters(city="Tokyo", categories=["food"]), 5):
        print(f"{r.score:.3f}  {r.place.name}  [{r.place.category}]")
    await p.embedding.aclose()
asyncio.run(main())
PY
```

## The demo

```bash
scripts/demo-full-rag.sh            # PASS/FAIL per stage + a real generated trip
scripts/demo-full-rag.sh --step     # pause between stages (sponsor walk-through)
scripts/demo-full-rag.sh --help
```

It only prints PASS when a check genuinely succeeds, and saves the generated NDJSON
(secrets redacted) under the git-ignored `demo-output/`.

## Tests

- `apps/api`, `backend`, `scraper` and `web` suites are hermetic — they use mock
  providers / offline fixtures, so **no CIRRASCALE key or running Qdrant is needed**.
- The real pipeline has one **opt-in** live test, skipped unless you ask for it:

  ```bash
  cd apps/api
  RUN_LIVE_RAG=1 CIRRASCALE_API_KEY=… QDRANT_COLLECTION=tokyo_dev \
    uv run pytest tests/test_live_rag.py -v
  ```

## Known limitations

- `bge-base` retrieval is modest on sparse OSM text; most places have no description,
  so embeddings lean on name + category. Filters carry the quality. `bge-large` or
  richer descriptions would help — worth an eval pass.
- The 8B reliably emits a **single** day object but mangles a multi-day JSON array
  (dropped `},{`), so days are planned one call at a time (concurrently) and grounded
  per day. Outline-level `food` picks are not yet grounded to retrieved places.
- A stop's cross-day and cross-stop variety comes from slicing a larger retrieved pool
  and a trip-wide used-set; it is heuristic, not an optimizer.
- The pinned `qdrant-client` (1.20) logs a benign version-skew warning against the
  1.12 server image; search uses `query_points` (the current API).
```
