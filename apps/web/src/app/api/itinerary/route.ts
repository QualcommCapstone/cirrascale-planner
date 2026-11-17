import { NextResponse } from "next/server";
import { complete } from "@/lib/cirrascale";
import { generateTrip } from "@/lib/trip/generate";
import { wikipediaPlaces } from "@/lib/trip/places";
import { TripRequestSchema, type TripEvent } from "@/lib/trip/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * POST { goal, preferences } -> NDJSON stream of TripEvent lines:
 * one "outline", then a "stop" (or "stopError") per stop as each finishes,
 * then "done". A fatal problem is sent as a final "error" line.
 *
 * Uses the account's default model (Llama-3.1-8B; 70B returns 429 on the free
 * tier). See src/lib/trip/generate.ts for the pipeline.
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
        await generateTrip(parsed.data, emit, { complete, places: wikipediaPlaces });
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

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
