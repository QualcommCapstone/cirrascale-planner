import { describe, expect, it } from "vitest";

import { buildPlannerPrompt, extractPlan } from "./planner";

describe("extractPlan", () => {
  it("keeps only the first plan when the model repeats itself", () => {
    const raw = "## Goal\nFirst plan\n\n## Goal\nRepeated plan";
    expect(extractPlan(raw)).toBe("## Goal\nFirst plan");
  });

  it("strips an echoed guardrail line and anything after it", () => {
    const raw = "## Goal\nTrip\nReturn ONLY the Markdown plan described above.\njunk";
    expect(extractPlan(raw)).toBe("## Goal\nTrip");
  });
});

describe("buildPlannerPrompt", () => {
  it("includes the user's goal", () => {
    expect(buildPlannerPrompt("  5 days in Lisbon  ")).toContain(
      "## User goal\n5 days in Lisbon"
    );
  });

  // TODO(you): add a test that passing `context` puts it in the prompt,
  // and one that a context longer than 6000 chars gets truncated.
});
