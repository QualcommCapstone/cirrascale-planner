import { describe, it, expect } from "vitest";
import {
  buildPlannerPrompt,
  extractPlan,
  buildItineraryPrompt,
  buildDetailPrompt,
  extractDetailMarkup,
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
  const stop = {
    name: "Kyoto",
    country: "Japan",
    dayStart: 3,
    dayEnd: 5,
    summary: "Temples and gardens.",
    activities: ["Fushimi Inari", "Gion walk"],
  };

  it("puts the system prompt first and includes the stop's data", () => {
    const p = buildDetailPrompt("SYSTEM", stop);
    expect(p.startsWith("SYSTEM")).toBe(true);
    expect(p).toContain('"Kyoto, Japan"');
    expect(p).toContain('"Days 3–5"');
    expect(p).toContain("1. Fushimi Inari\n2. Gion walk");
  });

  it("ends mid-statement so the model starts at the markup", () => {
    expect(buildDetailPrompt("SYSTEM", stop).endsWith("root = ")).toBe(true);
  });
});

describe("extractDetailMarkup", () => {
  it("restores the root lead the prompt ended with", () => {
    expect(extractDetailMarkup("Stack([card])\ncard = Card([])")).toBe(
      "root = Stack([card])\ncard = Card([])"
    );
  });

  it("drops a code fence and the prose after it", () => {
    const raw = "```openui\nroot = Stack([card])\n```\n\nThis design uses a Card.";
    expect(extractDetailMarkup(raw)).toBe("root = Stack([card])");
  });

  it("strips repeated # comments but keeps # inside strings", () => {
    const raw = 'Stack([a1])\na1 = ListItem("#1 taco stand", "Go early.")  # fixed  # fixed  # fix';
    expect(extractDetailMarkup(raw)).toBe(
      'root = Stack([a1])\na1 = ListItem("#1 taco stand", "Go early.")'
    );
  });
});
