import { NextResponse } from "next/server";
import { complete } from "@/lib/cirrascale";
import { buildItineraryPrompt } from "@/lib/planner";
import { extractJson } from "@/lib/json";
import { normalizeTrip, type RawTrip } from "@/lib/itinerary";

export const runtime = "nodejs";

interface ItineraryRequest {
  goal?: string;
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
