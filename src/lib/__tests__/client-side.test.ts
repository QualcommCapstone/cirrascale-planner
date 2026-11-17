import { describe, it, expect, beforeEach } from "vitest";
import { formatDays, formatDuration, safeUrl } from "@/lib/trip/format";
import { decodeTrip, encodeTrip } from "@/lib/trip/share";
import { readEvents } from "@/lib/trip/client";
import { allActivities, pinnedActivities, stopOf, useTrip } from "@/lib/store/trip";
import { DEFAULT_PREFERENCES, type Activity, type Trip, type TripEvent } from "@/lib/trip/types";

const activity = (id: string, verified: boolean): Activity => ({
  id,
  slot: "morning",
  name: `Place ${id}`,
  neighborhood: "Central",
  durationMins: 90,
  cost: "$",
  category: "sight",
  reason: "A specific reason that is long enough to pass.",
  lat: verified ? 35 : null,
  lng: verified ? 139 : null,
  verified,
  photo: null,
  sourceUrl: verified ? "https://en.wikipedia.org/wiki/X" : null,
});

const trip: Trip = {
  title: "Neon and Moss",
  summary: "A short, specific summary of this trip.",
  where: "Japan",
  when: "Best in late spring",
  days: 3,
  vibes: ["Street Food"],
  preferences: DEFAULT_PREFERENCES,
  stops: [
    {
      id: "s0-tokyo", city: "Tokyo", country: "Japan", lat: 35.67, lng: 139.65, dayStart: 1, dayEnd: 2,
      headline: "Neon Nights", intro: "Intro.", stay: { area: "Asakusa", why: "Old town" }, food: [],
      photo: { url: "https://upload.wikimedia.org/a.jpg", creditUrl: "https://en.wikipedia.org/wiki/File:a.jpg", kind: "city" },
      days: [{ day: 1, activities: [activity("a1", true), activity("a2", false)] }],
    },
    {
      id: "s1-kyoto", city: "Kyoto", country: "Japan", lat: 35.01, lng: 135.77, dayStart: 3, dayEnd: 3,
      headline: "Moss Gardens", intro: "Intro.", stay: { area: "Gion", why: "" }, food: [], photo: null, days: [],
    },
  ],
  legs: [{ fromId: "s0-tokyo", toId: "s1-kyoto", mode: "train", durationMins: 135, notes: "", estimated: false }],
};

describe("format", () => {
  it("formats durations", () => {
    expect(formatDuration(45)).toBe("45m");
    expect(formatDuration(120)).toBe("2h");
    expect(formatDuration(135)).toBe("2h 15m");
  });

  it("formats day ranges", () => {
    expect(formatDays(3, 3)).toBe("Day 3");
    expect(formatDays(1, 3)).toBe("Days 1–3");
  });

  it("only lets https URLs through", () => {
    expect(safeUrl("https://en.wikipedia.org/wiki/X")).toBe("https://en.wikipedia.org/wiki/X");
    expect(safeUrl("javascript:alert(1)")).toBeUndefined();
    expect(safeUrl("http://example.com")).toBeUndefined();
    expect(safeUrl("not a url")).toBeUndefined();
    expect(safeUrl(null)).toBeUndefined();
  });
});

describe("share links", () => {
  it("round-trips a trip through the URL hash", async () => {
    const hash = await encodeTrip(trip);
    expect(hash.startsWith("trip=")).toBe(true);
    expect(await decodeTrip(`#${hash}`)).toEqual(trip);
  });

  it("rejects garbage and wrong shapes", async () => {
    expect(await decodeTrip("#nope")).toBeNull();
    expect(await decodeTrip("#trip=!!!")).toBeNull();
    const bad = await encodeTrip({ ...trip, stops: [] });
    expect(await decodeTrip(bad)).toBeNull();
    const evil = await encodeTrip({ ...trip, stops: [{ ...trip.stops[0], days: "<script>" as never }] });
    expect(await decodeTrip(evil)).toBeNull();
  });
});

describe("readEvents", () => {
  it("parses NDJSON split across chunks", async () => {
    const lines = '{"type":"stopError","stopId":"a"}\n{"type":"done","ms":5}\n';
    const enc = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(enc.encode(lines.slice(0, 20)));
        c.enqueue(enc.encode(lines.slice(20)));
        c.close();
      },
    });
    const seen: TripEvent[] = [];
    await readEvents(body, (e) => seen.push(e));
    expect(seen).toEqual([
      { type: "stopError", stopId: "a" },
      { type: "done", ms: 5 },
    ]);
  });
});

describe("trip store", () => {
  beforeEach(() => useTrip.getState().reset());

  it("tracks a streaming generation from outline to done", () => {
    const s = useTrip.getState();
    s.start("3 days in Japan");
    expect(useTrip.getState().status).toBe("loading");

    s.setOutline({ ...trip, stops: trip.stops.map((st) => ({ ...st, days: [] })) });
    expect(useTrip.getState().pendingStopIds).toEqual(["s0-tokyo", "s1-kyoto"]);

    s.setStopDays("s0-tokyo", trip.stops[0].days, [{ name: "Ramen", note: "" }]);
    expect(useTrip.getState().pendingStopIds).toEqual(["s1-kyoto"]);
    expect(useTrip.getState().trip?.stops[0].food).toEqual([{ name: "Ramen", note: "" }]);

    s.stopFailed("s1-kyoto");
    s.finish(12000);
    expect(useTrip.getState()).toMatchObject({
      status: "ready",
      failedStopIds: ["s1-kyoto"],
      generationMs: 12000,
    });
  });

  it("keeps preferences across a reset and a new generation", () => {
    useTrip.getState().setPreferences({ interests: ["Food"], budget: "Luxury", pace: "Packed" });
    useTrip.getState().start("x");
    useTrip.getState().reset();
    expect(useTrip.getState().preferences.budget).toBe("Luxury");
  });

  it("focusing an activity also focuses its stop and bumps the tick", () => {
    useTrip.getState().loadTrip(trip);
    const before = useTrip.getState().focusTick;
    useTrip.getState().focusActivity("a1", "globe");
    expect(useTrip.getState()).toMatchObject({
      focusedActivityId: "a1",
      focusedStopId: "s0-tokyo",
      focusSource: "globe",
      focusTick: before + 1,
    });
  });

  it("selects activities and pins only verified ones", () => {
    expect(allActivities(trip).map((a) => a.id)).toEqual(["a1", "a2"]);
    expect(pinnedActivities(trip).map((a) => a.id)).toEqual(["a1"]);
    expect(stopOf(trip, "a2")?.id).toBe("s0-tokyo");
  });
});
