import { describe, it, expect } from "vitest";
import {
  buildPlannerPrompt,
  extractPlan,
  buildOutlinePrompt,
  buildDaysPrompt,
  describePreferences,
} from "@/lib/planner";
import { DEFAULT_PREFERENCES } from "@/lib/trip/types";

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

describe("describePreferences", () => {
  it("spells out interests, budget and pace", () => {
    const line = describePreferences({ interests: ["Food", "Nightlife"], budget: "Luxury", pace: "Packed" });
    expect(line).toContain("Food, Nightlife");
    expect(line).toContain("luxury");
    expect(line).toContain("packed");
  });

  it("handles no interests", () => {
    expect(describePreferences(DEFAULT_PREFERENCES)).toContain("a bit of everything");
  });
});

describe("buildOutlinePrompt", () => {
  it("asks for strict JSON with stops and legs and includes the request", () => {
    const p = buildOutlinePrompt("5 days in Lisbon", DEFAULT_PREFERENCES);
    expect(p).toContain("5 days in Lisbon");
    expect(p).toContain('"stops"');
    expect(p).toContain('"legs"');
    expect(p.trimEnd().endsWith("JSON:")).toBe(true);
  });

  it("passes the traveller's preferences", () => {
    const p = buildOutlinePrompt("x", { interests: ["Nature"], budget: "Budget", pace: "Relaxed" });
    expect(p).toContain("interests Nature");
    expect(p).toContain("budget budget");
    expect(p).toContain("pace relaxed");
  });

  it("lists the previous attempt's problems on a retry", () => {
    const p = buildOutlinePrompt("x", DEFAULT_PREFERENCES, ["the title is too generic"]);
    expect(p).toContain("Fix all of them");
    expect(p).toContain("- the title is too generic");
  });
});

describe("buildDaysPrompt", () => {
  const stop = { city: "Kyoto", country: "Japan", dayStart: 3, dayEnd: 5 };

  it("asks for one entry per day with morning/afternoon/evening", () => {
    const p = buildDaysPrompt(stop, DEFAULT_PREFERENCES);
    expect(p).toContain("Plan 3 days in Kyoto, Japan (trip days 3-5)");
    expect(p).toContain("numbered 3 to 5");
    expect(p).toContain('"morning"');
    expect(p).toContain('"evening"');
  });

  it("uses singular wording for one day", () => {
    const p = buildDaysPrompt({ ...stop, dayEnd: 3 }, DEFAULT_PREFERENCES);
    expect(p).toContain("Plan 1 day in Kyoto, Japan (trip day 3)");
  });

  it("lists places to avoid", () => {
    const p = buildDaysPrompt(stop, DEFAULT_PREFERENCES, ["Senso-ji"]);
    expect(p).toContain("do not repeat): Senso-ji");
  });
});
