import { describe, it, expect, vi } from "vitest";
import { generateTrip, type GenerateDeps } from "@/lib/trip/generate";
import type { PlacesApi } from "@/lib/trip/places";
import { DEFAULT_PREFERENCES, type TripEvent } from "@/lib/trip/types";

const outline = {
  title: "Neon, Shrines and Mountain Air",
  summary: "Four days from Tokyo's izakaya alleys to Kyoto's quiet moss gardens.",
  where: "Japan",
  when: "Best in late spring",
  vibes: ["Local Culture", "Street Food"],
  stops: [
    {
      city: "Tokyo", country: "Japan", lat: 35.68, lng: 139.69, days: 2,
      headline: "Neon Nights and Dawn Markets",
      intro: "Tokyo pairs 5am tuna auctions with tiny six-seat bars in Golden Gai.",
      stay: { area: "Asakusa", why: "Old-town lanes near Senso-ji" },
      food: [{ name: "Ichiran Shibuya", note: "Solo-booth tonkotsu ramen" }],
    },
    {
      city: "Kyoto", country: "Japan", lat: 35.01, lng: 135.77, days: 2,
      headline: "Lanterns and Moss Gardens",
      intro: "Kyoto keeps 1,600 temples and the best tofu kaiseki in Japan.",
      stay: { area: "Gion", why: "Walkable to the teahouse lanes" },
      food: [{ name: "Pontocho Alley", note: "Riverside yakitori" }],
    },
  ],
  legs: [{ mode: "train", durationMins: 135, notes: "Shinkansen Nozomi, JR Pass" }],
};

const activity = (name: string) => ({
  name,
  neighborhood: "Central",
  durationMins: 90,
  cost: "$",
  category: "sight",
  reason: `${name} rewards an early start with quiet paths and morning light.`,
});

function daysFor(start: number, names: string[][]) {
  return {
    days: names.map(([m, a, e], i) => ({
      day: start + i,
      morning: activity(m),
      afternoon: activity(a),
      evening: activity(e),
    })),
  };
}

const places: PlacesApi = {
  locateCity: async (city) =>
    city === "Tokyo"
      ? { lat: 35.6762, lng: 139.6503, photo: { url: "tokyo.jpg", creditUrl: "c", kind: "city" } }
      : null,
  verifyActivities: async (activities) =>
    new Map(
      activities.map((a) => [
        a.id,
        a.name === "Senso-ji"
          ? { verified: true, lat: 35.71, lng: 139.79, photo: { url: "s.jpg", creditUrl: "c", kind: "place" as const }, sourceUrl: "w" }
          : { verified: false, lat: null, lng: null, photo: null, sourceUrl: null },
      ])
    ),
};

function fakeModel(responses: Record<string, string[]>) {
  const calls: string[] = [];
  const complete = vi.fn(async (prompt: string) => {
    calls.push(prompt);
    const key = prompt.includes("expert travel writer")
      ? "outline"
      : prompt.match(/in (\w+), Japan/)?.[1] ?? "?";
    const queue = responses[key];
    if (!queue?.length) throw new Error(`no fake response for ${key}`);
    return queue.length > 1 ? queue.shift()! : queue[0];
  });
  return { complete, calls };
}

async function run(deps: GenerateDeps) {
  const events: TripEvent[] = [];
  let t = 0;
  await generateTrip(
    { goal: "4 days in Japan", preferences: DEFAULT_PREFERENCES },
    (e) => events.push(e),
    { ...deps, now: () => (t += 1000) }
  );
  return events;
}

describe("generateTrip", () => {
  it("emits the outline, then each stop, then done", async () => {
    const { complete } = fakeModel({
      outline: [JSON.stringify(outline)],
      Tokyo: [JSON.stringify(daysFor(1, [["Senso-ji", "Ueno Park", "Golden Gai"], ["Meiji Jingu", "Takeshita Street", "Omoide Yokocho"]]))],
      Kyoto: [JSON.stringify(daysFor(3, [["Kiyomizu-dera", "Sannenzaka", "Pontocho Alley"], ["Fushimi Inari-taisha", "Tofuku-ji", "Nishiki Market"]]))],
    });
    const events = await run({ complete, places });

    expect(events[0].type).toBe("outline");
    const trip = events[0].type === "outline" ? events[0].trip : null;
    expect(trip?.stops.map((s) => [s.city, s.dayStart, s.dayEnd])).toEqual([
      ["Tokyo", 1, 2],
      ["Kyoto", 3, 4],
    ]);
    // Wikipedia coordinates win over the model's
    expect(trip?.stops[0]).toMatchObject({ lat: 35.6762, lng: 139.6503 });

    const stops = events.filter((e) => e.type === "stop");
    expect(stops).toHaveLength(2);

    const tokyo = stops.find((e) => e.type === "stop" && e.stopId === "s0-tokyo");
    if (tokyo?.type !== "stop") throw new Error("missing Tokyo");
    const senso = tokyo.days[0].activities[0];
    expect(senso).toMatchObject({ name: "Senso-ji", verified: true, lat: 35.71 });
    // Unverified activities fall back to the city photo and get no pin
    expect(tokyo.days[0].activities[1]).toMatchObject({ verified: false, lat: null, photo: { url: "tokyo.jpg" } });

    // A food pick that became an activity leaves the food list
    const kyoto = stops.find((e) => e.type === "stop" && e.stopId === "s1-kyoto");
    if (kyoto?.type !== "stop") throw new Error("missing Kyoto");
    expect(kyoto.food).toEqual([]);

    expect(events[events.length - 1]).toEqual({ type: "done", ms: 1000 });
  });

  it("retries the outline with the problems listed and keeps the better answer", async () => {
    const bad = { ...outline, title: "Japan", summary: "Immerse yourself in Japan." };
    const { complete, calls } = fakeModel({
      outline: [JSON.stringify(bad), JSON.stringify(outline)],
      Tokyo: [JSON.stringify(daysFor(1, [["Senso-ji", "Ueno Park", "Golden Gai"], ["Meiji Jingu", "Takeshita Street", "Omoide Yokocho"]]))],
      Kyoto: [JSON.stringify(daysFor(3, [["Kiyomizu-dera", "Sannenzaka", "Gion Corner"], ["Fushimi Inari-taisha", "Tofuku-ji", "Nishiki Market"]]))],
    });
    const events = await run({ complete, places });

    const outlineCalls = calls.filter((c) => c.includes("expert travel writer"));
    expect(outlineCalls).toHaveLength(2);
    expect(outlineCalls[1]).toContain("the title is too generic");
    expect(events[0].type === "outline" && events[0].trip.title).toBe(outline.title);
  });

  it("salvages days from a truncated, looping answer", async () => {
    const full = JSON.stringify(daysFor(1, [["Senso-ji", "Ueno Park", "Golden Gai"], ["Meiji Jingu", "Takeshita Street", "Omoide Yokocho"]]));
    const looping = full.slice(0, -2) + "," + full.slice(9, 200); // never closes the array
    const { complete } = fakeModel({
      outline: [JSON.stringify(outline)],
      Tokyo: [looping],
      Kyoto: [JSON.stringify(daysFor(3, [["Kiyomizu-dera", "Sannenzaka", "Gion Corner"], ["Fushimi Inari-taisha", "Tofuku-ji", "Nishiki Market"]]))],
    });
    const events = await run({ complete, places });
    const tokyo = events.find((e) => e.type === "stop" && e.stopId === "s0-tokyo");
    expect(tokyo?.type === "stop" && tokyo.days.map((d) => d.activities.length)).toEqual([3, 3]);
  });

  it("reports a stop whose plan is unusable without failing the trip", async () => {
    const { complete } = fakeModel({
      outline: [JSON.stringify(outline)],
      Tokyo: ["no json here"],
      Kyoto: [JSON.stringify(daysFor(3, [["Kiyomizu-dera", "Sannenzaka", "Gion Corner"], ["Fushimi Inari-taisha", "Tofuku-ji", "Nishiki Market"]]))],
    });
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const events = await run({ complete, places });
    spy.mockRestore();
    expect(events).toContainEqual({ type: "stopError", stopId: "s0-tokyo" });
    expect(events.some((e) => e.type === "stop" && e.stopId === "s1-kyoto")).toBe(true);
    expect(events[events.length - 1].type).toBe("done");
  });

  it("throws when no outline is usable", async () => {
    const { complete } = fakeModel({ outline: ["sorry"] });
    await expect(run({ complete, places })).rejects.toThrow("No usable trip outline");
  });
});
