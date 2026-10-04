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
