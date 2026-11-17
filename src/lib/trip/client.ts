/**
 * Browser side of trip generation: POST /api/itinerary and feed each streamed
 * NDJSON event into the store as it arrives, so stops appear one by one.
 */
import { useTrip } from "@/lib/store/trip";
import type { Preferences, TripEvent } from "./types";

let current: AbortController | null = null;

/** Parse an NDJSON byte stream into events, calling `onEvent` per complete line. */
export async function readEvents(
  body: ReadableStream<Uint8Array>,
  onEvent: (e: TripEvent) => void
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    let nl: number;
    while ((nl = buffer.indexOf("\n")) !== -1) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) onEvent(JSON.parse(line) as TripEvent);
    }
    if (done) break;
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as TripEvent);
}

/** Generate a trip for `goal`, cancelling any generation already in flight. */
export async function planTrip(goal: string, preferences: Preferences): Promise<void> {
  current?.abort();
  const controller = new AbortController();
  current = controller;

  const store = useTrip.getState();
  store.start(goal);

  try {
    const res = await fetch("/api/itinerary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, preferences }),
      signal: controller.signal,
    });
    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      store.fail((data as { error?: string }).error ?? "Couldn't reach the planner.");
      return;
    }

    let finished = false;
    await readEvents(res.body, (e) => {
      if (controller.signal.aborted) return;
      const s = useTrip.getState();
      switch (e.type) {
        case "outline":
          s.setOutline(e.trip);
          break;
        case "stop":
          s.setStopDays(e.stopId, e.days, e.food);
          break;
        case "stopError":
          s.stopFailed(e.stopId);
          break;
        case "done":
          finished = true;
          s.finish(e.ms);
          rememberGenerationTime(e.ms);
          break;
        case "error":
          finished = true;
          s.fail(e.message);
          break;
      }
    });
    if (!finished && !controller.signal.aborted) {
      useTrip.getState().fail("The connection closed before the trip finished.");
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      useTrip.getState().fail("Network error contacting the planner.");
    }
  } finally {
    if (current === controller) current = null;
  }
}

export function cancelPlanning(): void {
  current?.abort();
  current = null;
}

// --- Real proof for the landing page: the visitor's own last generation time.

const LAST_MS_KEY = "planner:lastGenerationMs";

function rememberGenerationTime(ms: number) {
  try {
    localStorage.setItem(LAST_MS_KEY, String(ms));
  } catch {
    // storage unavailable (private mode); not important
  }
}

export function lastGenerationTime(): number | null {
  try {
    const v = Number(localStorage.getItem(LAST_MS_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}
