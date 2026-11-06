/**
 * Planner prompt construction.
 *
 * Turns a free-form user goal into a structured prompt for the completions API,
 * then asks the model to return a clean, step-by-step plan in Markdown.
 *
 * Optionally accepts `context` (e.g. scraped page text) to ground the plan.
 */

import { formatDays } from "./itinerary";

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

/**
 * Prompt the model for a STRICT-JSON travel itinerary that can drive the globe.
 * Coordinates are requested but validated/back-filled server-side (see geo.ts),
 * so the model being slightly off is tolerable.
 */
export function buildItineraryPrompt(goal: string): string {
  return `You are a travel planner. Turn the request into a structured itinerary.

Return ONLY valid minified JSON (no prose, no code fences) matching exactly:
{"title": string, "destinations": [{
  "name": string,            // city/place name only, e.g. "Kyoto"
  "country": string,
  "lat": number,             // decimal degrees, -90..90
  "lng": number,             // decimal degrees, -180..180
  "dayStart": number,        // 1-based day the stop begins
  "dayEnd": number,          // day the stop ends (>= dayStart)
  "summary": string,         // one sentence
  "activities": string[]     // 2-4 short items
}]}

Rules:
- 2 to 6 destinations, ordered as the traveller would visit them.
- Real coordinates for each city. Days must be contiguous across the trip.
- No trailing commentary. JSON object only.

Request: ${goal.trim()}

JSON:`;
}

/** Fields of a trip stop the OpenUI detail panel is generated from. */
export interface DetailStop {
  name: string;
  country: string;
  dayStart: number;
  dayEnd: number;
  summary: string;
  activities: string[];
}

// The detail prompt ends mid-statement so the completion starts at the markup
// instead of continuing the data lines (which made the model invent activities).
const DETAIL_LEAD = "root = ";

/**
 * Prompt for the OpenUI detail panel of one trip stop. `systemPrompt` is the
 * OpenUI component-library description (see openui.ts).
 */
export function buildDetailPrompt(systemPrompt: string, stop: DetailStop): string {
  const activities = stop.activities.map((a, i) => `${i + 1}. ${a}`).join("\n");
  return `${systemPrompt}

Design a detail panel for this trip stop, shaped like the example: a Card with a CardHeader (title "${stop.name}${stop.country ? `, ${stop.country}` : ""}", subtitle "${formatDays(stop.dayStart, stop.dayEnd)}"), a one-sentence TextContent overview, and a ListBlock with one ListItem per activity. Give each ListItem a short, practical subtitle.

Overview: ${stop.summary}
Activities (use exactly these ${stop.activities.length}):
${activities}

OpenUI Lang:
${DETAIL_LEAD}`;
}

/** Drop a trailing `# ...` comment from one line, ignoring `#` inside strings. */
function stripComment(line: string): string {
  let inStr = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inStr && ch === "\\") i++;
    else if (ch === '"') inStr = !inStr;
    else if (ch === "#" && !inStr) return line.slice(0, i).trimEnd();
  }
  return line;
}

/**
 * Turn the detail completion back into OpenUI Lang: restore the `root = ` lead
 * the prompt ended with, drop anything after a closing code fence, and strip
 * `#` comments (8B tends to repeat one until it hits max_tokens; the API
 * ignores `stop`, so this is done here).
 */
export function extractDetailMarkup(raw: string): string {
  let text = raw.replace(/^\s*```[a-z-]*\s*/i, "");
  if (!/^\s*root\s*=/.test(text)) text = DETAIL_LEAD + text;
  return text.split("```")[0].split("\n").map(stripComment).join("\n").trim();
}
