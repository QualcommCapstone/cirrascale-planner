# @cirrascale/contracts

Shared API contract types for the frontend, **generated from the backend's
OpenAPI schema** — a single source of truth so the Pydantic models (`apps/api`)
and the TypeScript the web app consumes never drift.

## Regenerate

```bash
npm run contracts:generate   # from the repo root
```

That runs `apps/api/scripts/export_openapi.py` (dumps `openapi.json` with every
contract model) then `openapi-typescript` → `src/api.ts`. Both `openapi.json` and
`src/api.ts` are committed; do not hand-edit them.

## Use (in apps/web)

```ts
import type { Trip, TripEvent, TripRequest } from "@cirrascale/contracts";
```

## Compatibility

`src/api.ts` mirrors the Zod model in `apps/web/src/lib/trip/types.ts`. A
regression test (`apps/web`) validates a sample `Trip` against both the generated
type and the Zod schema; a pytest validates the same sample against the Pydantic
models. If they diverge, regenerate and reconcile — don't edit generated files.
