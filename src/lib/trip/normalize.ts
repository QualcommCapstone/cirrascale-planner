/**
 * Model JSON -> validated trip data.
 *
 * Parsing is lenient (a bad field becomes empty instead of failing the whole
 * answer) and every parse also returns `issues`: problems worth a retry. After
 * the last attempt, finalize* functions blank or drop whatever is still bad so
 * filler never reaches the UI.
 */
import { z } from "zod";
import { distanceKm, isValidLatLng, lookupLatLng, type LatLng } from "../geo";
import { activityIssues, outlineIssues, findFiller, sameText } from "./quality";
import {
  CATEGORIES,
  COSTS,
  MODES,
  SLOTS,
  type Activity,
  type Day,
  type Leg,
  type Mode,
  type Photo,
  type Preferences,
  type Stop,
  type Trip,
} from "./types";

// --- Lenient field parsers -------------------------------------------------

const Text = (max: number) =>
  z
    .string()
    .transform((s) => s.trim().replace(/\s+/g, " ").slice(0, max))
    .catch("");

const Num = z.unknown().optional().transform((v) => {
  const n = typeof v === "string" ? Number(v) : v;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
});

const OneOf = <T extends readonly [string, ...string[]]>(values: T, fallback: T[number]) =>
  z
    .string()
    .transform((s) => s.trim().toLowerCase())
    .pipe(z.enum(values))
    .catch(fallback);

const List = <T extends z.ZodTypeAny>(item: T, max: number) =>
  z
    .array(z.unknown())
    .transform((a) =>
      a.flatMap((v) => {
        const r = item.safeParse(v);
        return r.success ? [r.data as z.infer<T>] : [];
      }).slice(0, max)
    )
    .catch([]);

const RawStop = z.object({
  city: Text(60),
  country: Text(60),
  lat: Num,
  lng: Num,
  days: Num,
  headline: Text(80),
  intro: Text(260),
  stay: z.object({ area: Text(60), why: Text(140) }).catch({ area: "", why: "" }),
  food: List(z.object({ name: Text(80), note: Text(160) }), 2),
});

const RawLeg = z.object({
  mode: OneOf(MODES, "train"),
  durationMins: Num,
  notes: Text(140),
});

const RawOutline = z.object({
  title: Text(80),
  summary: Text(240),
  where: Text(60),
  when: Text(60),
  vibes: List(Text(30), 4),
  stops: List(RawStop, 5),
  legs: List(RawLeg, 4),
});

const RawActivity = z.object({
  name: Text(80),
  neighborhood: Text(60),
  durationMins: Num,
  cost: OneOf(COSTS, "$"),
  category: OneOf(CATEGORIES, "sight"),
  reason: Text(240),
});

const RawDays = z.object({
  days: List(
    z.object({
      day: Num,
      morning: RawActivity.nullable().catch(null),
      afternoon: RawActivity.nullable().catch(null),
      evening: RawActivity.nullable().catch(null),
    }),
    10
  ),
});

export type OutlineDraft = z.infer<typeof RawOutline>;
export type StopDraft = z.infer<typeof RawStop>;

// --- Outline ---------------------------------------------------------------

export interface Parsed<T> {
  value: T | null;
  issues: string[];
}

export function parseOutline(raw: unknown): Parsed<OutlineDraft> {
  const r = RawOutline.safeParse(raw);
  if (!r.success) return { value: null, issues: ["the answer was not the requested JSON object"] };

  const o = mergeRepeatedStops({ ...r.data, stops: r.data.stops.filter((s) => s.city) });
  if (o.stops.length === 0) return { value: null, issues: ["the answer has no stops"] };

  const issues = outlineIssues(o);
  if (o.vibes.filter(Boolean).length < 2) issues.push("vibes needs 2-4 tags");
  if (o.legs.length < o.stops.length - 1)
    issues.push(`legs needs ${o.stops.length - 1} entries, one per gap between stops`);
  for (const s of o.stops) {
    if (!s.stay.area) issues.push(`${s.city} has no stay.area`);
    if (s.food.filter((f) => f.name).length === 0) issues.push(`${s.city} has no food picks`);
  }
  return { value: o, issues };
}

/**
 * The model sometimes splits one city into back-to-back stops ("Tokyo 1-2",
 * "Tokyo 3-4"). Merge them: days add up, the first stop's text wins, and the
 * leg between them goes away.
 */
export function mergeRepeatedStops(o: OutlineDraft): OutlineDraft {
  const stops: StopDraft[] = [];
  const legs: OutlineDraft["legs"] = [];
  o.stops.forEach((s, i) => {
    const prev = stops[stops.length - 1];
    if (prev && sameText(prev.city, s.city)) {
      prev.days = (prev.days ?? 2) + (s.days ?? 2);
      prev.food = [...prev.food, ...s.food].slice(0, 2);
      return;
    }
    if (i > 0 && o.legs[i - 1]) legs.push(o.legs[i - 1]);
    stops.push({ ...s, food: [...s.food] });
  });
  return { ...o, stops, legs: stops.length === o.stops.length ? o.legs : legs };
}

/** Blank out any text that still fails the quality checks after the last retry. */
export function finalizeOutline(o: OutlineDraft): OutlineDraft {
  const clean = (t: string) => (findFiller(t) ? "" : t);
  const where = o.where || o.stops[0]?.city || "";
  const title =
    o.title && !findFiller(o.title) && !sameText(o.title, where) && o.title.split(" ").length > 1
      ? o.title
      : `${where} at a glance`.trim();

  return {
    ...o,
    title,
    where,
    summary: clean(o.summary),
    vibes: o.vibes.filter((v) => v && !findFiller(v)),
    stops: o.stops.map((s) => ({
      ...s,
      headline:
        s.headline && !findFiller(s.headline) && !sameText(s.headline, s.city) ? s.headline : "",
      intro: clean(s.intro),
      stay: { area: s.stay.area, why: clean(s.stay.why) },
      food: s.food.filter((f) => f.name && !findFiller(f.note)),
    })),
  };
}

const MAX_TRIP_DAYS = 14;

/** Days per stop: 1-5 each, at most MAX_TRIP_DAYS in total. */
export function allocateDays(requested: (number | null)[]): number[] {
  const days = requested.map((d) => Math.min(5, Math.max(1, Math.round(d ?? 2))));
  while (days.reduce((a, b) => a + b, 0) > MAX_TRIP_DAYS) {
    const i = days.indexOf(Math.max(...days));
    days[i]--;
  }
  return days;
}

function slug(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/** Where a stop is on the map: Wikipedia first, then the model, then the built-in table. */
export function resolveStopLocation(
  s: StopDraft,
  located: { lat: number; lng: number } | null
): LatLng | null {
  if (located) return located;
  if (isValidLatLng(s.lat, s.lng)) return { lat: s.lat as number, lng: s.lng as number };
  return lookupLatLng(s.city) ?? lookupLatLng(s.country);
}

const SPEED: Record<Mode, { kmh: number; overheadMins: number }> = {
  train: { kmh: 140, overheadMins: 20 },
  flight: { kmh: 750, overheadMins: 120 },
  bus: { kmh: 60, overheadMins: 15 },
  car: { kmh: 75, overheadMins: 0 },
  ferry: { kmh: 30, overheadMins: 30 },
};

/** Rough door-to-door estimate from straight-line distance. */
export function estimateLegMins(mode: Mode, km: number): number {
  const { kmh, overheadMins } = SPEED[mode];
  return Math.max(10, Math.round(((km / kmh) * 60 + overheadMins) / 5) * 5);
}

/** Keep the model's leg if its duration is plausible for the distance, otherwise estimate. */
export function makeLeg(
  from: Stop,
  to: Stop,
  draft: z.infer<typeof RawLeg> | undefined
): Leg {
  const km = distanceKm(from, to);
  const mode: Mode = draft?.mode ?? (km > 800 ? "flight" : "train");
  const estimate = estimateLegMins(mode, km);
  const given = draft?.durationMins ?? null;
  const plausible = given !== null && given >= estimate * 0.5 && given <= estimate * 2;
  return {
    fromId: from.id,
    toId: to.id,
    mode,
    durationMins: plausible ? Math.round(given) : estimate,
    notes: draft && !findFiller(draft.notes) ? draft.notes : "",
    estimated: !plausible,
  };
}

/**
 * Turn a finalized outline into a Trip with ids, day numbers, coordinates and
 * legs. Stops that can't be placed on the map are dropped. Days are empty
 * until each stop's plan arrives.
 */
export function buildTrip(
  o: OutlineDraft,
  prefs: Preferences,
  located: ({ lat: number; lng: number; photo: Photo | null } | null)[]
): Trip | null {
  const placed = o.stops
    .map((s, i) => ({ s, i, at: resolveStopLocation(s, located[i]), photo: located[i]?.photo ?? null }))
    .filter((x): x is typeof x & { at: LatLng } => x.at !== null);
  if (placed.length === 0) return null;

  const counts = allocateDays(placed.map((x) => x.s.days));
  let day = 1;
  const stops: Stop[] = placed.map(({ s, i, at, photo }, k) => {
    const dayStart = day;
    const dayEnd = day + counts[k] - 1;
    day = dayEnd + 1;
    return {
      id: `s${i}-${slug(s.city)}`,
      city: s.city,
      country: s.country,
      lat: at.lat,
      lng: at.lng,
      dayStart,
      dayEnd,
      headline: s.headline,
      intro: s.intro,
      stay: s.stay,
      food: s.food,
      photo,
      days: [],
    };
  });

  // A leg drafted for original gap i belongs between original stops i and i+1;
  // if a stop in between was dropped, fall back to an estimate.
  const legs = stops.slice(1).map((to, k) => {
    const fromIdx = placed[k].i;
    const toIdx = placed[k + 1].i;
    return makeLeg(stops[k], to, toIdx === fromIdx + 1 ? o.legs[fromIdx] : undefined);
  });

  return {
    title: o.title,
    summary: o.summary,
    where: o.where,
    when: o.when,
    days: day - 1,
    vibes: o.vibes,
    preferences: prefs,
    stops,
    legs,
  };
}

// --- Days ------------------------------------------------------------------

export interface ParsedDays {
  days: Day[];
  issues: string[];
  /** Activities that failed a check; dropped by finalizeDays. */
  bad: Set<string>;
}

function clampDuration(n: number | null): number {
  return Math.min(600, Math.max(15, Math.round(n ?? 90)));
}

/** Parse one stop's day plan. Days are matched by number, falling back to position. */
export function parseDays(
  raw: unknown,
  stop: Pick<Stop, "id" | "city" | "dayStart" | "dayEnd">,
  exclude: string[] = []
): ParsedDays {
  const r = RawDays.safeParse(raw);
  const rawDays = r.success ? r.data.days : [];
  const issues: string[] = r.success ? [] : ["the answer was not the requested JSON object"];
  const bad = new Set<string>();
  const seen = [...exclude];
  const days: Day[] = [];

  for (let d = stop.dayStart; d <= stop.dayEnd; d++) {
    const src = rawDays.find((x) => x.day === d) ?? rawDays[d - stop.dayStart];
    if (!src) {
      issues.push(`day ${d} is missing`);
      days.push({ day: d, activities: [] });
      continue;
    }

    const activities: Activity[] = [];
    for (const slot of SLOTS) {
      const a = src[slot];
      if (!a || !a.name) {
        issues.push(`day ${d} has no ${slot} activity`);
        continue;
      }
      const id = `${stop.id}-d${d}-${slot}`;
      const problems = activityIssues(a, stop.city);
      if (seen.some((n) => sameText(n, a.name))) problems.push(`"${a.name}" appears twice`);
      if (problems.length) {
        issues.push(...problems);
        bad.add(id);
      }
      seen.push(a.name);
      activities.push({
        id,
        slot,
        name: a.name,
        neighborhood: a.neighborhood,
        durationMins: clampDuration(a.durationMins),
        cost: a.cost,
        category: a.category,
        reason: a.reason,
        lat: null,
        lng: null,
        verified: false,
        photo: null,
        sourceUrl: null,
      });
    }
    days.push({ day: d, activities });
  }

  return { days, issues, bad };
}

/** Drop activities that still fail after the last retry. Days stay, even if emptied. */
export function finalizeDays(parsed: ParsedDays): Day[] {
  return parsed.days.map((d) => ({
    ...d,
    activities: d.activities.filter((a) => !parsed.bad.has(a.id)),
  }));
}
