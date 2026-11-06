import { describe, it, expect } from "vitest";
import {
  buildPlannerPrompt,
  extractPlan,
  buildItineraryPrompt,
  buildDetailPrompt,
} from "@/lib/planner";

describe("buildPlannerPrompt", () => {
  it("includes the user goal", () => {
    const p = buildPlannerPrompt("Learn to sail");
    expect(p).toContain("Learn to sail");
    expect(p).toContain("## User goal");
  });

  it("embeds grounding context when provided", () => {
    const p = buildPlannerPrompt("Goal", "some reference text");
    expect(p).toContain("some reference text");
  });
});

describe("extractPlan", () => {
  it("keeps only the first plan when the model loops", () => {
    const looped =
      "## Goal\nA\n## Plan\n1. x\n## Goal\nA\n## Plan\n1. x";
    const out = extractPlan(looped);
    expect(out.match(/## Goal/g)?.length).toBe(1);
  });

  it("strips an echoed guardrail line and anything after it", () => {
    const raw = "## Goal\nA\n## Plan\n1. x\n\nReturn ONLY the Markdown plan described above";
    expect(extractPlan(raw)).not.toContain("Return ONLY the Markdown plan");
  });
});

describe("buildItineraryPrompt", () => {
  it("asks for strict JSON and includes the request", () => {
    const p = buildItineraryPrompt("3 days in Lisbon");
    expect(p).toContain("3 days in Lisbon");
    expect(p).toContain('"destinations"');
    expect(p.toLowerCase()).toContain("json");
  });
});

describe("buildDetailPrompt", () => {
  it("puts the system prompt first and includes the stop's data", () => {
    const p = buildDetailPrompt("SYSTEM", {
      name: "Kyoto",
      country: "Japan",
      dayStart: 3,
      dayEnd: 5,
      summary: "Temples and gardens.",
      activities: ["Fushimi Inari", "Gion walk"],
    });
    expect(p.startsWith("SYSTEM")).toBe(true);
    expect(p).toContain("Destination: Kyoto, Japan");
    expect(p).toContain("Days: 3-5");
    expect(p).toContain("Fushimi Inari; Gion walk");
  });
});
