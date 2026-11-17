/**
 * Trip generation pipeline (server-side).
 *
 *   1. Outline call  -> title, voice, stops, stay/food, legs   (retry once on issues)
 *   2. Locate stops on Wikipedia (real coordinates + city photo)
 *   3. emit "outline" so the UI and globe can show the route right away
 *   4. Per stop, in parallel: days call (retry once) -> verify places -> emit "stop"
 *   5. emit "done" with the wall-clock time
 *
 * Splitting the work keeps each completion small enough for Llama-3.1-8B to
 * follow the schema, and lets the UI reveal stops as they finish.
 */
import { buildDaysPrompt, buildOutlinePrompt } from "../planner";
import { extractArrayItems, extractJson } from "../json";
import type { CompletionOptions } from "../cirrascale";
import type { PlacesApi } from "./places";
import { sameText } from "./quality";
import {
  buildTrip,
  finalizeDays,
  finalizeOutline,
  parseDays,
  parseOutline,
  type ParsedDays,
  type Parsed,
  type OutlineDraft,
} from "./normalize";
import type { Day, Preferences, Stop, TripEvent, TripRequest } from "./types";

export interface GenerateDeps {
  complete: (prompt: string, options?: CompletionOptions) => Promise<string>;
  places: PlacesApi;
  now?: () => number;
}

const OUTLINE_TOKENS = 1100;
const TOKENS_PER_DAY = 420;

/** Run `attempt`, and once more with its issues if it had any; keep the better result. */
async function withRetry<T extends { issues: string[] }>(
  attempt: (issues: string[]) => Promise<T>,
  score: (r: T) => number
): Promise<T> {
  const first = await attempt([]);
  if (first.issues.length === 0) return first;
  let second: T;
  try {
    second = await attempt(first.issues);
  } catch {
    return first;
  }
  return score(second) <= score(first) ? second : first;
}

async function generateOutline(
  goal: string,
  prefs: Preferences,
  deps: GenerateDeps
): Promise<OutlineDraft | null> {
  const result = await withRetry<Parsed<OutlineDraft>>(
    async (issues) => {
      const raw = await deps.complete(buildOutlinePrompt(goal, prefs, issues), {
        maxTokens: OUTLINE_TOKENS,
      });
      return parseOutline(extractJson(raw));
    },
    (r) => (r.value ? r.issues.length : Infinity)
  );
  return result.value ? finalizeOutline(result.value) : null;
}

/** Days planned per completion. Longer asks make 8B repeat day 1 and drop the rest. */
const DAYS_PER_CALL = 2;

/**
 * Plan a stop's days in chunks of DAYS_PER_CALL, in order, telling each chunk
 * which places earlier chunks already used so nothing repeats.
 */
async function generateDays(
  stop: Stop,
  prefs: Preferences,
  exclude: string[],
  deps: GenerateDeps
): Promise<Day[]> {
  const days: Day[] = [];
  const used = [...exclude];
  for (let start = stop.dayStart; start <= stop.dayEnd; start += DAYS_PER_CALL) {
    const chunk = { ...stop, dayStart: start, dayEnd: Math.min(stop.dayEnd, start + DAYS_PER_CALL - 1) };
    const planned = await generateDayChunk(chunk, prefs, used, deps);
    days.push(...planned);
    used.push(...planned.flatMap((d) => d.activities.map((a) => a.name)));
  }
  return days;
}

async function generateDayChunk(
  stop: Stop,
  prefs: Preferences,
  exclude: string[],
  deps: GenerateDeps
): Promise<Day[]> {
  const count = stop.dayEnd - stop.dayStart + 1;
  const result = await withRetry<ParsedDays>(
    async (issues) => {
      const raw = await deps.complete(buildDaysPrompt(stop, prefs, exclude, issues), {
        maxTokens: Math.min(2400, 250 + TOKENS_PER_DAY * count),
      });
      // 8B often never closes the days array (it repeats days until max_tokens),
      // so fall back to the complete day objects it did write.
      const json = extractJson<{ days?: unknown }>(raw) ?? { days: extractArrayItems(raw, "days") };
      const parsed = parseDays(json, stop, exclude);
      if (parsed.issues.length) {
        console.warn(`[generateTrip] ${stop.city} issues:`, parsed.issues.slice(0, 6));
      }
      return parsed;
    },
    // Fewest missing-or-bad activities wins; issue count breaks ties.
    (r) => {
      const good = r.days.reduce((n, d) => n + d.activities.length, 0) - r.bad.size;
      return (count * 3 - good) * 10 + r.issues.length;
    }
  );
  return finalizeDays(result);
}

/**
 * Attach real coordinates/photos to every activity of one stop (one batch per
 * stop). Two names that resolve to the same article ("Shinjuku Golden Gai" and
 * "Golden Gai's Bar 3") are the same place: only the first is kept. `seen`
 * holds article URLs already used anywhere in the trip.
 */
async function verifyDays(
  days: Day[],
  stop: Stop,
  places: PlacesApi,
  seen: Set<string>
): Promise<Day[]> {
  const all = days.flatMap((d) => d.activities);
  const found = await places.verifyActivities(all, stop).catch(() => new Map());
  return days.map((d) => ({
    ...d,
    activities: d.activities.flatMap((a) => {
      const place = found.get(a.id);
      if (place?.verified && place.sourceUrl) {
        if (seen.has(place.sourceUrl)) return [];
        seen.add(place.sourceUrl);
      }
      // Every card gets a picture: the place, its area, or at least the city.
      return [place ? { ...a, ...place, photo: place.photo ?? stop.photo } : { ...a, photo: stop.photo }];
    }),
  }));
}

/**
 * Generate a trip, reporting progress through `emit`. Throws only if no usable
 * outline comes back; a stop whose days fail is reported as "stopError".
 */
export async function generateTrip(
  req: TripRequest,
  emit: (event: TripEvent) => void,
  deps: GenerateDeps
): Promise<void> {
  const now = deps.now ?? Date.now;
  const started = now();
  const { goal, preferences } = req;

  const outline = await generateOutline(goal, preferences, deps);
  if (!outline) throw new Error("No usable trip outline from the model.");

  const located = await Promise.all(
    outline.stops.map((s) => deps.places.locateCity(s.city, s.country).catch(() => null))
  );
  const trip = buildTrip(outline, preferences, located);
  if (!trip) throw new Error("None of the trip's stops could be placed on the map.");
  emit({ type: "outline", trip });

  // Stops are planned in parallel. A place another stop already emitted is
  // dropped, and a food pick that became an activity leaves the food list, so
  // nothing appears twice.
  const emitted: string[] = [];
  const seenArticles = new Set<string>();
  await Promise.all(
    trip.stops.map(async (stop) => {
      try {
        const planned = await generateDays(stop, preferences, [], deps);
        const days = planned.map((d) => ({
          ...d,
          activities: d.activities.filter((a) => !emitted.some((n) => sameText(n, a.name))),
        }));
        if (days.every((d) => d.activities.length === 0)) throw new Error("empty plan");
        const names = days.flatMap((d) => d.activities.map((a) => a.name));
        emitted.push(...names);
        const food = stop.food.filter((f) => !names.some((n) => sameText(n, f.name)));
        emit({
          type: "stop",
          stopId: stop.id,
          days: await verifyDays(days, stop, deps.places, seenArticles),
          food,
        });
      } catch (err) {
        console.error(`[generateTrip] ${stop.city}:`, err);
        emit({ type: "stopError", stopId: stop.id });
      }
    })
  );

  emit({ type: "done", ms: now() - started });
}
