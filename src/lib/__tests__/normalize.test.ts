import { describe, it, expect } from "vitest";
import {
  allocateDays,
  buildTrip,
  estimateLegMins,
  finalizeDays,
  finalizeOutline,
  parseDays,
  parseOutline,
} from "@/lib/trip/normalize";
import { DEFAULT_PREFERENCES } from "@/lib/trip/types";

const stop = (city: string, lat: number, lng: number, days: number) => ({
  city,
  country: "Japan",
  lat,
  lng,
  days,
  headline: `Headline for the ${days}-day stop`,
  intro: "A specific sentence about why this place is worth the trip.",
  stay: { area: "Central", why: "Close to the station" },
  food: [{ name: "Ramen Alley", note: "Rich tonkotsu broth" }],
});

const rawOutline = {
  title: "Neon, Shrines and Mountain Air",
  summary: "Six days from Tokyo's izakaya alleys to Kyoto's quiet moss gardens.",
  where: "Japan",
  when: "Best in late spring",
  vibes: ["Local Culture", "Street Food"],
  stops: [stop("Tokyo", 35.68, 139.69, 3), stop("Kyoto", 35.01, 135.77, 3)],
  legs: [{ mode: "train", durationMins: 135, notes: "Shinkansen Nozomi" }],
};

describe("parseOutline", () => {
  it("parses a good outline with no issues", () => {
    const { value, issues } = parseOutline(rawOutline);
    expect(issues).toEqual([]);
    expect(value?.stops.map((s) => s.city)).toEqual(["Tokyo", "Kyoto"]);
  });

  it("returns null for non-objects and outlines without stops", () => {
    expect(parseOutline(null).value).toBeNull();
    expect(parseOutline({ ...rawOutline, stops: [] }).value).toBeNull();
  });

  it("tolerates bad field types instead of failing the whole answer", () => {
    const { value } = parseOutline({ ...rawOutline, vibes: "oops", legs: [{ mode: "Teleport" }] });
    expect(value?.vibes).toEqual([]);
    expect(value?.legs[0].mode).toBe("train");
  });

  it("reports missing legs and food as issues", () => {
    const { issues } = parseOutline({
      ...rawOutline,
      legs: [],
      stops: [rawOutline.stops[0], { ...rawOutline.stops[1], food: [] }],
    });
    expect(issues.join(" ")).toContain("legs needs 1");
    expect(issues.join(" ")).toContain("Kyoto has no food picks");
  });
});

describe("finalizeOutline", () => {
  it("blanks filler and replaces a generic title", () => {
    const draft = parseOutline({
      ...rawOutline,
      title: "Japan",
      summary: "Immerse yourself in Japan.",
      stops: [{ ...rawOutline.stops[0], headline: "Tokyo" }],
    }).value!;
    const out = finalizeOutline(draft);
    expect(out.title).toBe("Japan at a glance");
    expect(out.summary).toBe("");
    expect(out.stops[0].headline).toBe("");
  });
});

describe("allocateDays", () => {
  it("clamps each stop to 1-5 days and the trip to 14", () => {
    expect(allocateDays([0, 9, null])).toEqual([1, 5, 2]);
    expect(allocateDays([5, 5, 5, 5]).reduce((a, b) => a + b)).toBe(14);
  });
});

describe("estimateLegMins", () => {
  it("adds travel time and overhead, rounded to 5 minutes", () => {
    expect(estimateLegMins("train", 140)).toBe(80); // 60 + 20
    expect(estimateLegMins("flight", 750)).toBe(180); // 60 + 120
  });
});

describe("buildTrip", () => {
  const draft = finalizeOutline(parseOutline(rawOutline).value!);

  it("numbers days contiguously and gives stops ids", () => {
    const trip = buildTrip(draft, DEFAULT_PREFERENCES, [null, null])!;
    expect(trip.days).toBe(6);
    expect(trip.stops.map((s) => [s.id, s.dayStart, s.dayEnd])).toEqual([
      ["s0-tokyo", 1, 3],
      ["s1-kyoto", 4, 6],
    ]);
  });

  it("prefers located (Wikipedia) coordinates and photos", () => {
    const photo = { url: "u", creditUrl: "c", kind: "city" as const };
    const trip = buildTrip(draft, DEFAULT_PREFERENCES, [{ lat: 35.6, lng: 139.6, photo }, null])!;
    expect(trip.stops[0]).toMatchObject({ lat: 35.6, lng: 139.6, photo });
    expect(trip.stops[1]).toMatchObject({ lat: 35.01, lng: 135.77, photo: null });
  });

  it("keeps a plausible leg and replaces an implausible one", () => {
    const ok = buildTrip(draft, DEFAULT_PREFERENCES, [null, null])!;
    expect(ok.legs[0]).toMatchObject({ mode: "train", durationMins: 135, estimated: false });

    const bad = finalizeOutline(
      parseOutline({ ...rawOutline, legs: [{ mode: "train", durationMins: 900, notes: "x" }] }).value!
    );
    const fixed = buildTrip(bad, DEFAULT_PREFERENCES, [null, null])!;
    expect(fixed.legs[0].estimated).toBe(true);
    expect(fixed.legs[0].durationMins).toBeLessThan(300);
  });

  it("drops stops that can't be placed and estimates the leg across the gap", () => {
    const withGhost = finalizeOutline(
      parseOutline({
        ...rawOutline,
        stops: [rawOutline.stops[0], { ...stop("Nowhereville", NaN, NaN, 2), country: "" }, rawOutline.stops[1]],
        legs: [rawOutline.legs[0], rawOutline.legs[0]],
      }).value!
    );
    const trip = buildTrip(withGhost, DEFAULT_PREFERENCES, [null, null, null])!;
    expect(trip.stops.map((s) => s.city)).toEqual(["Tokyo", "Kyoto"]);
    expect(trip.legs).toHaveLength(1);
    expect(trip.legs[0].estimated).toBe(true);
  });
});

describe("parseDays", () => {
  const kyoto = { id: "s1-kyoto", city: "Kyoto", dayStart: 4, dayEnd: 5 };
  const act = (name: string) => ({
    name,
    neighborhood: "Higashiyama",
    durationMins: 90,
    cost: "$$",
    category: "sight",
    reason: "Its wooden stage hangs over a forest of maples and cherry trees.",
  });

  it("builds one Day per trip day with slot-ordered activities", () => {
    const { days, issues } = parseDays(
      {
        days: [
          { day: 4, morning: act("Kiyomizu-dera"), afternoon: act("Sannenzaka"), evening: act("Pontocho") },
          { day: 5, morning: act("Fushimi Inari-taisha"), afternoon: act("Tofuku-ji"), evening: act("Nishiki Market") },
        ],
      },
      kyoto
    );
    expect(issues).toEqual([]);
    expect(days.map((d) => d.day)).toEqual([4, 5]);
    expect(days[0].activities.map((a) => a.slot)).toEqual(["morning", "afternoon", "evening"]);
    expect(days[0].activities[0]).toMatchObject({
      id: "s1-kyoto-d4-morning",
      verified: false,
      lat: null,
      photo: null,
    });
  });

  it("reports missing days and slots", () => {
    const { days, issues } = parseDays({ days: [{ day: 4, morning: act("Kiyomizu-dera") }] }, kyoto);
    expect(days).toHaveLength(2);
    expect(issues).toContain("day 4 has no afternoon activity");
    expect(issues).toContain("day 5 is missing");
  });

  it("marks filler and duplicates as bad, and finalizeDays drops them", () => {
    const parsed = parseDays(
      {
        days: [
          { day: 4, morning: act("Kiyomizu-dera"), afternoon: act("Explore the city"), evening: act("Kiyomizu-dera") },
          { day: 5, morning: act("Tofuku-ji"), afternoon: act("Sannenzaka"), evening: act("Pontocho") },
        ],
      },
      kyoto
    );
    expect(parsed.bad.size).toBe(2);
    const final = finalizeDays(parsed);
    expect(final[0].activities.map((a) => a.name)).toEqual(["Kiyomizu-dera"]);
    expect(final[1].activities).toHaveLength(3);
  });
});

describe("mergeRepeatedStops", () => {
  it("merges back-to-back stops in the same city and drops the leg between", () => {
    const { value } = parseOutline({
      ...rawOutline,
      stops: [stop("Tokyo", 35.68, 139.69, 2), stop("Tokyo", 35.68, 139.69, 2), stop("Kyoto", 35.01, 135.77, 2)],
      legs: [
        { mode: "train", durationMins: 20, notes: "Tokyo to Tokyo" },
        { mode: "train", durationMins: 135, notes: "Shinkansen Nozomi" },
      ],
    });
    expect(value?.stops.map((s) => [s.city, s.days])).toEqual([
      ["Tokyo", 4],
      ["Kyoto", 2],
    ]);
    expect(value?.legs.map((l) => l.notes)).toEqual(["Shinkansen Nozomi"]);
  });
});
