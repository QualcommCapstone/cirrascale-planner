/**
 * Compile-time contract regression gate.
 *
 * The frontend's `Trip` (Zod/TS source of truth) must be a valid instance of the
 * generated backend contract (`@cirrascale/contracts`, from the FastAPI OpenAPI).
 * If the backend adds a required field, renames one, or changes a type
 * incompatibly, this file fails `npm run build:web` / tsc — a loud, early signal
 * to regenerate (`npm run contracts:generate`) and reconcile.
 *
 * Type-only: erased at runtime, enforced by the type checker.
 */
import type { Trip as ContractTrip } from "@cirrascale/contracts";
import type { Trip as WebTrip } from "./types";

type WebTripSatisfiesContract = WebTrip extends ContractTrip ? true : never;

// If WebTrip is not assignable to the contract, this becomes `never` and errors.
export const _contractCheck: WebTripSatisfiesContract = true;
