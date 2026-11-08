/**
 * Content quality checks for model output.
 *
 * Schema validation catches missing fields; these catch text that is present
 * but useless: travel-brochure filler, "Visit X" activities, titles that repeat
 * the city. Issues are phrased so they can be fed back to the model on retry.
 */

/** Phrases that say nothing about a specific place. */
const FILLER: RegExp[] = [
  /\bexplore the (city|area|town|streets|region|neighbou?rhood)\b/i,
  /\bimmerse yourself\b/i,
  /\bvibrant (culture|atmosphere|city)\b/i,
  /\btake in the (sights|views|atmosphere|scenery)\b/i,
  /\benjoy the local\b/i,
  /\bexperience the (local )?(culture|vibe|atmosphere)\b/i,
  /\ba (great|perfect|wonderful) (place|way|spot) to\b/i,
  /\bmust[- ](see|visit|do)\b/i,
  /\bsomething for everyone\b/i,
  /\bwander around\b/i,
  /\bfree time\b/i,
  /\bat your own pace\b/i,
  /\boff the beaten path\b/i,
  /\bhustle and bustle\b/i,
];

/** Activity names that are an instruction or a category, not a place. */
const GENERIC_NAME =
  /^(visit|explore|discover|enjoy|tour|see|check out|stroll|walk|relax|rest|free|lunch|dinner|breakfast|arrive|arrival|departure|depart|travel|day trip|local|city (tour|cent(er|re))|downtown|old town|the beach|beach day|hotel|shopping|sightseeing|nightlife)\b/i;

export function findFiller(text: string): string | null {
  for (const re of FILLER) {
    const m = text.match(re);
    if (m) return m[0];
  }
  return null;
}

function words(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function norm(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** True when two strings say the same thing (case, accents and punctuation ignored). */
export function sameText(a: string, b: string): boolean {
  return norm(a) !== "" && norm(a) === norm(b);
}

interface ActivityLike {
  name: string;
  reason: string;
  neighborhood: string;
}

/** Problems with one activity, as short sentences. Empty means it's good. */
export function activityIssues(a: ActivityLike, city: string): string[] {
  const issues: string[] = [];
  const label = a.name || "(unnamed)";

  if (!a.name.trim()) issues.push("an activity has no name");
  else if (GENERIC_NAME.test(a.name.trim()))
    issues.push(`"${label}" is not a specific named place`);
  else if (sameText(a.name, city)) issues.push(`"${label}" is just the city name`);

  if (!a.neighborhood.trim()) issues.push(`"${label}" has no neighborhood`);

  if (words(a.reason) < 6) issues.push(`the reason for "${label}" is too short`);
  else if (/^\s*visit\b/i.test(a.reason))
    issues.push(`the reason for "${label}" starts with "Visit"`);

  const filler = findFiller(`${a.name} ${a.reason}`);
  if (filler) issues.push(`"${label}" uses filler ("${filler}")`);

  return issues;
}

interface OutlineLike {
  title: string;
  summary: string;
  where: string;
  stops: { city: string; headline: string; intro: string; stay: { why: string } }[];
}

/** Problems with the trip outline, as short sentences. Empty means it's good. */
export function outlineIssues(o: OutlineLike): string[] {
  const issues: string[] = [];

  if (words(o.title) < 2 || sameText(o.title, o.where))
    issues.push("the title is too generic");
  if (words(o.summary) < 6) issues.push("the summary is too short");

  for (const [field, text] of [
    ["title", o.title],
    ["summary", o.summary],
  ] as const) {
    const filler = findFiller(text);
    if (filler) issues.push(`the ${field} uses filler ("${filler}")`);
  }

  for (const s of o.stops) {
    if (!s.headline.trim()) issues.push(`${s.city} has no headline`);
    else if (norm(s.headline).includes(norm(s.city)))
      issues.push(`the ${s.city} headline repeats the city name`);
    if (words(s.intro) < 6) issues.push(`the ${s.city} intro is too short`);
    else if (/^\s*visit\b/i.test(s.intro)) issues.push(`the ${s.city} intro starts with "Visit"`);
    const filler = findFiller(`${s.headline} ${s.intro} ${s.stay.why}`);
    if (filler) issues.push(`the ${s.city} text uses filler ("${filler}")`);
  }

  return issues;
}
