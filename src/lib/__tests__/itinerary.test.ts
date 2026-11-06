import { describe, it, expect, beforeEach } from "vitest";
import { normalizeTrip, type RawTrip } from "@/lib/itinerary";
import { useItinerary, selectArcs, selectFocused, type Trip } from "@/lib/store/itinerary";

describe("normalizeTrip", () => {
  it("returns null for empty / malformed input", () => {
    expect(normalizeTrip(null, "g")).toBeNull();
    expect(normalizeTrip({} as RawTrip, "g")).toBeNull();
    expect(normalizeTrip({ destinations: [] }, "g")).toBeNull();
  });

  it("normalizes a valid trip and generates ids", () => {
    const raw: RawTrip = {
      title: "Japan",
      destinations: [
        { name: "Tokyo", country: "Japan", lat: 35.6, lng: 139.7, dayStart: 1, dayEnd: 3, summary: "s", activities: ["a", "b"] },
      ],
    };
    const trip = normalizeTrip(raw, "goal");
    expect(trip?.title).toBe("Japan");
    expect(trip?.destinations[0].id).toBe("0-tokyo");
    expect(trip?.destinations[0].activities).toEqual(["a", "b"]);
  });

  it("back-fills missing coordinates from the city name", () => {
    const raw: RawTrip = { destinations: [{ name: "Kyoto", country: "Japan" }] };
    const trip = normalizeTrip(raw, "goal");
    expect(trip?.destinations[0].lat).toBeCloseTo(35.0116, 2);
    expect(trip?.destinations[0].lng).toBeCloseTo(135.7681, 2);
  });

  it("skips a destination that can't be placed on the globe", () => {
    const raw: RawTrip = {
      destinations: [
        { name: "Nowhereville" }, // no coords, not in geo table -> skipped
        { name: "Paris" }, // back-filled
      ],
    };
    const trip = normalizeTrip(raw, "goal");
    expect(trip?.destinations).toHaveLength(1);
    expect(trip?.destinations[0].name).toBe("Paris");
  });

  it("coerces day ranges (dayEnd >= dayStart >= 1)", () => {
    const raw: RawTrip = {
      destinations: [{ name: "Tokyo", lat: 35.6, lng: 139.7, dayStart: 0, dayEnd: -2 }],
    };
    const d = normalizeTrip(raw, "goal")?.destinations[0];
    expect(d?.dayStart).toBe(1);
    expect(d?.dayEnd).toBeGreaterThanOrEqual(d!.dayStart);
  });

  it("falls back to the goal when title is missing", () => {
    const raw: RawTrip = { destinations: [{ name: "Rome", lat: 41.9, lng: 12.5 }] };
    expect(normalizeTrip(raw, "a roman holiday")?.title).toBe("a roman holiday");
  });
});

describe("selectArcs", () => {
  it("creates an arc between each consecutive pair", () => {
    const trip = normalizeTrip(
      {
        destinations: [
          { name: "Tokyo", lat: 35.6, lng: 139.7 },
          { name: "Kyoto", lat: 35.0, lng: 135.8 },
          { name: "Osaka", lat: 34.7, lng: 135.5 },
        ],
      },
      "g"
    )!;
    const arcs = selectArcs(trip.destinations);
    expect(arcs).toHaveLength(2);
    expect(arcs[0]).toMatchObject({ startLat: 35.6, endLat: 35.0 });
  });

  it("returns no arcs for a single destination", () => {
    const trip = normalizeTrip({ destinations: [{ name: "Tokyo", lat: 35.6, lng: 139.7 }] }, "g")!;
    expect(selectArcs(trip.destinations)).toHaveLength(0);
  });
});

describe("useItinerary store", () => {
  beforeEach(() => useItinerary.getState().reset());

  const sample: Trip = {
    title: "Trip",
    destinations: [
      { id: "a", name: "A", country: "", lat: 1, lng: 1, dayStart: 1, dayEnd: 1, summary: "", activities: [] },
      { id: "b", name: "B", country: "", lat: 2, lng: 2, dayStart: 2, dayEnd: 2, summary: "", activities: [] },
    ],
  };

  it("setTrip stores the trip and focuses the first stop", () => {
    useItinerary.getState().setTrip(sample);
    const s = useItinerary.getState();
    expect(s.status).toBe("ready");
    expect(s.focusedId).toBe("a");
    expect(selectFocused(s)?.name).toBe("A");
  });

  it("focus() changes the focused destination", () => {
    useItinerary.getState().setTrip(sample);
    useItinerary.getState().focus("b");
    expect(selectFocused(useItinerary.getState())?.name).toBe("B");
  });

  it("setStatus records an error", () => {
    useItinerary.getState().setStatus("error", "boom");
    const s = useItinerary.getState();
    expect(s.status).toBe("error");
    expect(s.error).toBe("boom");
  });

  it("reset clears everything", () => {
    useItinerary.getState().setTrip(sample);
    useItinerary.getState().reset();
    const s = useItinerary.getState();
    expect(s.destinations).toHaveLength(0);
    expect(s.focusedId).toBeNull();
    expect(s.status).toBe("idle");
  });
});
