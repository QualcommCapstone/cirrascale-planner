import { NextResponse } from "next/server";
import { complete } from "@/lib/cirrascale";
import { getBackendUrl } from "@/lib/backend";
import { generateTrip } from "@/lib/trip/generate";
import { wikipediaPlaces } from "@/lib/trip/places";
import { openMeteoWeather } from "@/lib/trip/weather";
import { TripRequestSchema, type TripEvent } from "@/lib/trip/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const NDJSON_HEADERS = {
  "Content-Type": "application/x-ndjson; charset=utf-8",
  "Cache-Control": "no-store",
};

/**
 * POST { goal, preferences } -> NDJSON stream of TripEvent lines:
 * one "outline", then a "stop" (or "stopError") per stop as each finishes,
 * then "done". A fatal problem is sent as a final "error" line.
 *
 * Two backends, selected by the BACKEND_URL env (see src/lib/backend.ts):
 *  - set   -> proxy-stream from the FastAPI backend's /api/v1/plan (no buffering)
 *  - unset -> the in-Next pipeline (Cirrascale + Wikipedia, src/lib/trip/generate.ts)
 * Both speak the same TripEvent NDJSON contract, so the UI is unchanged.
 */
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const parsed = TripRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Send a 'goal' (up to 400 characters) and valid 'preferences'." },
      { status: 400 }
    );
  }

  const backendUrl = getBackendUrl();
  if (backendUrl) {
    try {
      const upstream = await fetch(`${backendUrl}/api/v1/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      if (!upstream.ok || !upstream.body) {
        return NextResponse.json(
          { error: "The planning backend is unavailable. Try again." },
          { status: 502 }
        );
      }
      // Pipe the NDJSON stream straight through — no buffering.
      return new Response(upstream.body, { headers: NDJSON_HEADERS });
    } catch (err) {
      console.error("[api/itinerary] backend proxy failed", err);
      return NextResponse.json(
        { error: "Couldn't reach the planning backend." },
        { status: 502 }
      );
    }
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let open = true;
      const emit = (event: TripEvent) => {
        if (!open) return;
        try {
          controller.enqueue(encoder.encode(JSON.stringify(event) + "\n"));
        } catch {
          open = false; // client went away; finish quietly
        }
      };
      try {
        await generateTrip(parsed.data, emit, { complete, places: wikipediaPlaces, weather: openMeteoWeather });
      } catch (err) {
        // Log the real error; upstream details stay off the client.
        console.error("[api/itinerary]", err);
        emit({ type: "error", message: "Couldn't build a trip from that. Try rephrasing or try again." });
      } finally {
        if (open) controller.close();
        open = false;
      }
    },
  });

  return new Response(stream, { headers: NDJSON_HEADERS });
}
