import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";
import { PreferencesSchema, TripRequestSchema } from "@/lib/trip/types";

// Canonical sample shared with the backend's pytest contract test.
const sampleTrip = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL("../../../../../packages/contracts/examples/sample-trip.json", import.meta.url)
    ),
    "utf8"
  )
);

describe("API contract compatibility", () => {
  it("preferences in the sample pass the Zod schema", () => {
    const parsed = PreferencesSchema.parse(sampleTrip.preferences);
    expect(parsed.budget).toBe("Mid");
    expect(parsed.interests).toContain("Food");
  });

  it("the request contract accepts {goal, preferences}", () => {
    const req = TripRequestSchema.parse({
      goal: "6 days in Japan",
      preferences: sampleTrip.preferences,
    });
    expect(req.goal).toBe("6 days in Japan");
  });

  it("required Trip + Activity fields are present (name parity with the backend)", () => {
    for (const key of ["title", "summary", "where", "when", "days", "preferences", "stops", "legs"]) {
      expect(sampleTrip).toHaveProperty(key);
    }
    const act = sampleTrip.stops[0].days[0].activities[0];
    for (const key of [
      "id", "slot", "name", "neighborhood", "durationMins",
      "cost", "category", "reason", "verified", "lat", "lng", "sourceUrl",
    ]) {
      expect(act).toHaveProperty(key);
    }
  });
});
