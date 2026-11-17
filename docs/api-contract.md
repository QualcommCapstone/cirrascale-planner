# API Contract

> Canonical shapes for the planner. The Pydantic models in `apps/api/app/schemas`
> are the source of truth; `@cirrascale/contracts` is generated from them
> (`npm run contracts:generate`). The web Zod model
> (`apps/web/src/lib/trip/types.ts`) mirrors the same shapes — a compile-time gate
> (`apps/web/src/lib/trip/contract-check.ts`) fails the build if they drift.

## Endpoints

| Method | Path                | Body                         | Response |
| ------ | ------------------- | ---------------------------- | -------- |
| GET    | `/health`           | —                            | `{status, service}` |
| GET    | `/ready`            | —                            | provider names + per-dependency status (no secrets) |
| POST   | `/api/v1/plan`      | `TripRequest {goal, preferences}` | **NDJSON stream** of `TripEvent` |
| POST   | `/api/v1/chat`      | `ChatRequest {trip, message, preferences?}` | full updated `Trip` (JSON) |

The web app calls its own `/api/itinerary` (same `TripRequest` → same `TripEvent`
NDJSON); with `BACKEND_URL` set it proxy-streams to `/api/v1/plan`.

## Request

```json
{ "goal": "6 days in Japan for temples and ramen",
  "preferences": { "interests": ["Food","Culture"], "budget": "Mid", "pace": "Balanced" } }
```

Enums: `interests` ∈ Food|Nature|Culture|Nightlife · `budget` ∈ Budget|Mid|Luxury ·
`pace` ∈ Relaxed|Balanced|Packed. An optional adapter also accepts
`{destination, days, budget, currency, preferences[]}` (`SimplePlanRequest`).

## Streaming protocol (NDJSON, one JSON object per line)

```
{"type":"outline","trip": Trip}            # the shell: stops with empty days[]
{"type":"stop","stopId": "...","days":[Day],"food":[FoodPick]}   # per stop, as ready
{"type":"stopError","stopId":"..."}        # a stop failed (stream continues)
{"type":"done","ms": 1234,"estimatedCostUsd": 980.0}
{"type":"error","message":"..."}           # fatal
```

`Trip` → `stops[] (Stop)` → `days[] (Day)` → `activities[] (Activity)`. An
`Activity` is `verified: true` only when grounded in a retrieved place; its
`sourceUrl` and coordinates come from that place. See `openapi.json` /
`packages/contracts/src/api.ts` for exact field types.

## JSONL ingestion contract (scraper → vector store)

The scraper (separate work) emits one JSON object per line matching `Place`
(`apps/api/app/schemas/place.py`):

```json
{"id":"stable-id","name":"...","description":"...","city":"...","country":"...",
 "category":"sight|food|nature|culture|nightlife|shopping","lat":0.0,"lng":0.0,
 "address":"...","source_url":"...","source_attribution":"...",
 "collected_at":"2026-01-01T00:00:00Z","price_level":"$","opening_hours":"...","license":"..."}
```

Ingest it (idempotent — a place id always maps to the same vector id):

```bash
cd apps/api && uv run python -m app.ingest path/to/places.jsonl
```

Ingestion validates each line, embeds in batches, upserts to the vector store, and
reports `{total, succeeded, failed, errors[]}`. It never runs inside `/plan`.

## Qdrant collection

Collection `QDRANT_COLLECTION` (default `places`), vectors sized to the embedding
model (`VECTOR_DIM`, Cosine distance). Every payload carries `model_version`;
searches filter on it so vectors from different embedding models never mix.
