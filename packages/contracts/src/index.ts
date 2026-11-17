/**
 * Shared API contract types, generated from the FastAPI OpenAPI schema.
 *
 * `api.ts` is generated — do not edit it. Regenerate with:
 *   npm run contracts:generate   (from the repo root)
 *
 * These aliases give ergonomic names and keep the public surface stable even if
 * the generator's internal shape changes.
 */
import type { components } from "./api";

export type Schemas = components["schemas"];

export type Preferences = Schemas["Preferences"];
export type TripRequest = Schemas["TripRequest"];
export type SimplePlanRequest = Schemas["SimplePlanRequest"];
export type ChatRequest = Schemas["ChatRequest"];

export type Photo = Schemas["Photo"];
export type Activity = Schemas["Activity"];
export type Day = Schemas["Day"];
export type FoodPick = Schemas["FoodPick"];
export type Stay = Schemas["Stay"];
export type Stop = Schemas["Stop"];
export type Leg = Schemas["Leg"];
export type Trip = Schemas["Trip"];

/** One NDJSON line from POST /api/v1/plan (and the /api/itinerary proxy). */
export type TripEvent =
  | Schemas["OutlineEvent"]
  | Schemas["StopEvent"]
  | Schemas["StopErrorEvent"]
  | Schemas["DoneEvent"]
  | Schemas["ErrorEvent"];

export type { components, paths } from "./api";
