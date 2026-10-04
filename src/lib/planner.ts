/**
 * Planner prompt construction.
 *
 * Turns a free-form user goal into a structured prompt for the completions API,
 * then asks the model to return a clean, step-by-step plan in Markdown.
 *
 * Optionally accepts `context` (e.g. scraped page text) to ground the plan.
 */

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
