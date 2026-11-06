import { NextResponse } from "next/server";
import { complete } from "@/lib/cirrascale";
import { buildItineraryPrompt } from "@/lib/planner";
import { extractJson } from "@/lib/json";
import { isValidLatLng, lookupLatLng } from "@/lib/geo";
import type { Destination, Trip } from "@/lib/store/itinerary";

export const runtime = "nodejs";

interface ItineraryRequest {
  goal?: string;
}

interface RawDestination {
  name?: unknown;
  country?: unknown;
  lat?: unknown;
  lng?: unknown;
  dayStart?: unknown;
  dayEnd?: unknown;
  summary?: unknown;
  activities?: unknown;
}

interface RawTrip {
  title?: unknown;
  destinations?: RawDestination[];
}

function num(v: unknown, fallback: number): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function str(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

/** Validate + normalize the model's JSON into a safe Trip (coords back-filled). */
function normalizeTrip(raw: RawTrip | null, goal: string): Trip | null {
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

export async function POST(req: Request) {
  let body: ItineraryRequest;
  try {
    body = (await req.json()) as ItineraryRequest;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const goal = body.goal?.trim();
  if (!goal) {
    return NextResponse.json({ error: "Missing 'goal'." }, { status: 400 });
  }

  try {
    // Use the account's default model. (Llama-3.1-70B returns 429 "model not
    // configured" on the free tier, so we rely on the strict-JSON prompt +
    // server-side extraction/validation/geo-fallback to tame the 8B output.)
    const raw = await complete(buildItineraryPrompt(goal), {
      maxTokens: 1200,
    });
    const trip = normalizeTrip(extractJson<RawTrip>(raw), goal);
    if (!trip) {
      return NextResponse.json(
        { error: "Could not parse an itinerary from the model response." },
        { status: 502 }
      );
    }
    return NextResponse.json(trip);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
