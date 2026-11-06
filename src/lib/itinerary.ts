/**
 * Turn the model's raw JSON into a safe, globe-ready Trip.
 *
 * Extracted from the /api/itinerary route so it can be unit-tested without the
 * network: validation, day-range coercion, and coordinate back-fill via geo.ts.
 */
import { isValidLatLng, lookupLatLng } from "./geo";
import type { Destination, Trip } from "./store/itinerary";

export interface RawDestination {
  name?: unknown;
  country?: unknown;
  lat?: unknown;
  lng?: unknown;
  dayStart?: unknown;
  dayEnd?: unknown;
  summary?: unknown;
  activities?: unknown;
}

export interface RawTrip {
  title?: unknown;
  destinations?: RawDestination[];
}

/** "Day 3" or "Days 1–3", as shown on itinerary cards and the AI panel. */
export function formatDays(dayStart: number, dayEnd: number): string {
  return dayStart === dayEnd ? `Day ${dayStart}` : `Days ${dayStart}–${dayEnd}`;
}

function num(v: unknown, fallback: number): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function str(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

export function normalizeTrip(raw: RawTrip | null, goal: string): Trip | null {
  if (!raw || !Array.isArray(raw.destinations)) return null;

  const destinations: Destination[] = [];
  raw.destinations.forEach((d, i) => {
    const name = str(d.name).trim();
    if (!name) return;

    let lat = d.lat;
    let lng = d.lng;
    if (!isValidLatLng(lat, lng)) {
      const fallback = lookupLatLng(name) ?? lookupLatLng(str(d.country));
      if (!fallback) return; // can't place it on the globe; skip
      lat = fallback.lat;
      lng = fallback.lng;
    }

    const dayStart = Math.max(1, Math.round(num(d.dayStart, i + 1)));
    const dayEnd = Math.max(dayStart, Math.round(num(d.dayEnd, dayStart)));

    destinations.push({
      id: `${i}-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
      name,
      country: str(d.country),
      lat: lat as number,
      lng: lng as number,
      dayStart,
      dayEnd,
      summary: str(d.summary),
      activities: Array.isArray(d.activities)
        ? d.activities.filter((a): a is string => typeof a === "string").slice(0, 6)
        : [],
    });
  });

  if (destinations.length === 0) return null;
  return { title: str(raw.title) || goal, destinations };
}
