/**
 * Prompt construction for every model call.
 *
 * - Markdown plan (legacy /planner/chat): buildPlannerPrompt + extractPlan.
 * - Trip generation (/planner): buildOutlinePrompt for the trip shell, then
 *   buildDaysPrompt once per stop. Both ask for strict JSON that
 *   src/lib/trip/normalize.ts validates.
 */

import type { Preferences } from "./trip/types";

const SYSTEM_ROLE = `You are a precise planning assistant. Given a goal, you produce a
clear, actionable, step-by-step plan. Rules:
- Output GitHub-flavored Markdown only. No preamble, no sign-off.
- Start with a one-line "## Goal" restating the objective.
- Then "## Plan" as a numbered list of concrete steps.
- Each step is a short imperative sentence; add sub-bullets for detail when useful.
- End with "## Risks & notes" (2-4 bullets) covering blockers or assumptions.
- Be specific and realistic. Do not invent facts you were not given.`;

const GUARDRAILS = `\n\nReturn ONLY the Markdown plan described above.`;

export function buildPlannerPrompt(goal: string, context?: string): string {
  const grounding = context?.trim()
    ? `\n\nReference material to ground the plan (may be partial):\n"""\n${context.trim().slice(0, 6000)}\n"""`
    : "";

  return `${SYSTEM_ROLE}${grounding}\n\n## User goal\n${goal.trim()}${GUARDRAILS}\n\n`;
}

/**
 * Clean up a raw completion into a single plan.
 *
 * The completions models (e.g. Llama-3.1-8B) tend to keep generating past one
 * answer: they repeat the whole plan and echo prompt text. We keep only the
 * first plan and strip any echoed guardrail line.
 */
export function extractPlan(raw: string): string {
  let out = raw.trim();

  // The model loops by re-emitting a fresh "## Goal". Keep only the first block.
  const first = out.indexOf("## Goal");
  if (first !== -1) {
    const second = out.indexOf("## Goal", first + 1);
    if (second !== -1) out = out.slice(0, second).trim();
  }

  // Drop any echoed guardrail / instruction remnant and anything after it.
  out = out.replace(/Return ONLY the Markdown plan[\s\S]*$/i, "").trim();

  return out;
}

// ---------------------------------------------------------------------------
// Trip generation
// ---------------------------------------------------------------------------

const PACE_HINT: Record<Preferences["pace"], string> = {
  Relaxed: "relaxed: unhurried, long stays at each place, few transfers",
  Balanced: "balanced: a full day without rushing",
  Packed: "packed: ambitious days that fit in as much as possible",
};

const BUDGET_HINT: Record<Preferences["budget"], string> = {
  Budget: "budget: free sights, street food, hostels and simple inns",
  Mid: "mid-range: a mix of paid sights and good local restaurants",
  Luxury: "luxury: top restaurants, premium experiences, upscale areas",
};

/** One line describing the traveller, shared by both trip prompts. */
export function describePreferences(p: Preferences): string {
  const interests = p.interests.length ? p.interests.join(", ") : "a bit of everything";
  return `Traveller: interests ${interests}; budget ${BUDGET_HINT[p.budget]}; pace ${PACE_HINT[p.pace]}.`;
}

/** Appended on a retry so the model knows exactly what to fix. */
function retryNote(issues: string[]): string {
  if (issues.length === 0) return "";
  const list = issues.slice(0, 8).map((i) => `- ${i}`).join("\n");
  return `\nYour previous answer had these problems. Fix all of them:\n${list}\n`;
}

const NO_FILLER = `Never use filler like "explore the city", "immerse yourself", "vibrant culture", "a great place to", "must-visit".`;

/**
 * Trip outline: title, voice, stops, where to stay and eat, and the legs
 * between stops. Days are planned separately per stop (buildDaysPrompt) so
 * each call stays small enough for the 8B model to get right.
 */
export function buildOutlinePrompt(
  goal: string,
  prefs: Preferences,
  issues: string[] = []
): string {
  return `You are an expert travel writer and planner. Plan the trip below as JSON.

Return ONLY one minified JSON object, no prose, no code fences, with exactly these keys:
{"title":string,"summary":string,"where":string,"when":string,"vibes":string[],
 "stops":[{"city":string,"country":string,"lat":number,"lng":number,"days":number,
   "headline":string,"intro":string,"stay":{"area":string,"why":string},
   "food":[{"name":string,"note":string}]}],
 "legs":[{"mode":"train"|"flight"|"bus"|"car"|"ferry","durationMins":number,"notes":string}]}

Writing rules:
- title: 3-7 words with personality. summary: one vivid sentence about this exact trip.
- where: the country or region. when: the traveller's dates if given, otherwise the best season, e.g. "Best in late spring".
- vibes: 2-4 short tags like "Local Culture", "Hidden Gems", "Street Food", "Slow Mornings".
- 1-4 stops in travel order. days per stop (1-5) must add up to the trip length; if no length is given, choose a sensible one (max 14).
- headline: a punchy 3-6 word title for the stop that does NOT contain the city name.
- intro: one sentence on why this place is worth it, with a specific detail.
- stay.area: a real neighborhood; stay.why: what makes it a good base, in a few words.
- food: 1-2 real, specific dishes or eateries with a short note.
- legs: exactly one per gap between stops (number of stops minus 1). notes name the real service, e.g. "Shinkansen Nozomi, covered by the JR Pass".
- ${NO_FILLER}
${retryNote(issues)}
Trip request: ${goal.trim()}
${describePreferences(prefs)}

JSON:`;
}

export interface DaysPromptStop {
  city: string;
  country: string;
  dayStart: number;
  dayEnd: number;
}

/**
 * Day-by-day plan for one stop: one entry per day, each with a morning,
 * afternoon and evening activity. `exclude` lists places already used
 * elsewhere in the trip.
 */
export function buildDaysPrompt(
  stop: DaysPromptStop,
  prefs: Preferences,
  exclude: string[] = [],
  issues: string[] = []
): string {
  const count = stop.dayEnd - stop.dayStart + 1;
  const range =
    count === 1 ? `trip day ${stop.dayStart}` : `trip days ${stop.dayStart}-${stop.dayEnd}`;
  const avoid = exclude.length ? `\nAlready planned elsewhere (do not repeat): ${exclude.join(", ")}` : "";

  return `You are an expert local guide. Plan ${count} day${count === 1 ? "" : "s"} in ${stop.city}, ${stop.country} (${range}) as JSON.

Return ONLY one minified JSON object, no prose, no code fences:
{"days":[{"day":number,"morning":A,"afternoon":A,"evening":A}]}
where A = {"name":string,"neighborhood":string,"durationMins":number,"cost":"free"|"$"|"$$"|"$$$","category":"sight"|"food"|"nature"|"culture"|"nightlife"|"shopping","reason":string,"lat":number,"lng":number}

Rules:
- Exactly ${count} day${count === 1 ? "" : "s"}, numbered ${stop.dayStart} to ${stop.dayEnd}. Every slot filled.
- name: a real, specific, well-known place with its proper name (a temple, market, museum, park, street, restaurant). Never generic like "Local market", and never start with a verb like "Visit".
- neighborhood: the real district it is in.
- reason: one sentence with a concrete detail on why it is worth going, written with personality. Do not start with "Visit" or "This".
- Evenings: a specific food street, restaurant, bar or night spot.
- No place may appear twice. Keep each day's places close together.
- lat/lng: the place's real coordinates.
${fitRules(prefs)}
- ${NO_FILLER}
${retryNote(issues)}
${describePreferences(prefs)}${avoid}

JSON:`;
}

const COST_FOR_BUDGET: Record<Preferences["budget"], string> = {
  Budget: `mostly "free" and "$"`,
  Mid: `mostly "$" and "$$"`,
  Luxury: `mostly "$$" and "$$$"`,
};

const DURATION_FOR_PACE: Record<Preferences["pace"], string> = {
  Relaxed: "long, unhurried visits (2-3 hours each)",
  Balanced: "visits of about 1.5-2 hours",
  Packed: "brisk visits (about 1 hour) so the day covers more ground",
};

/** Explicit rules so the chips visibly change the plan, not just the outline. */
function fitRules(p: Preferences): string {
  const lines = [
    `- Cost: ${COST_FOR_BUDGET[p.budget]}.`,
    `- Pace: ${DURATION_FOR_PACE[p.pace]}.`,
  ];
  if (p.interests.length) {
    const cats = p.interests.map((i) => i.toLowerCase()).join(", ");
    lines.unshift(`- At least 2 of every 3 activities must have category ${cats}.`);
  }
  return lines.join("\n");
}
