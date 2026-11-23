import { describe, it, expect } from "vitest";
import { conditionFromCode, indoorAdvised } from "@/lib/trip/weather";

describe("conditionFromCode", () => {
  it.each([
    [0, 22, "clear"],
    [2, 22, "cloudy"],
    [45, 20, "cloudy"],
    [63, 18, "rain"],
    [82, 19, "rain"],
    [73, -2, "snow"],
    [96, 25, "stormy"],
    [1, 35, "hot"], // heat wins over "mostly clear"
  ] as const)("code %d at %d°C -> %s", (code, highC, expected) => {
    expect(conditionFromCode(code, highC)).toBe(expected);
  });
});

describe("indoorAdvised", () => {
  it.each(["rain", "snow", "stormy", "hot"] as const)("advises indoors for %s", (c) => {
    expect(indoorAdvised(c)).toBe(true);
  });

  it.each(["clear", "cloudy"] as const)("does not flag %s", (c) => {
    expect(indoorAdvised(c)).toBe(false);
  });
});
