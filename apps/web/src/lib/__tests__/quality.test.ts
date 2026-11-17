import { describe, it, expect } from "vitest";
import { activityIssues, findFiller, outlineIssues, sameText } from "@/lib/trip/quality";

describe("findFiller", () => {
  it.each([
    "Explore the city at your leisure",
    "Immerse yourself in the local life",
    "A great place to unwind",
    "This must-visit spot",
    "Take in the sights from the top",
  ])("flags %s", (text) => {
    expect(findFiller(text)).not.toBeNull();
  });

  it("passes specific copy", () => {
    expect(findFiller("Its nightingale floors squeak to warn of intruders.")).toBeNull();
  });
});

describe("sameText", () => {
  it("ignores case, accents and punctuation", () => {
    expect(sameText("Sensō-ji", "senso ji")).toBe(true);
    expect(sameText("Kyoto", "Osaka")).toBe(false);
    expect(sameText("", "")).toBe(false);
  });
});

describe("activityIssues", () => {
  const good = {
    name: "Nijo Castle",
    neighborhood: "Nakagyo",
    reason: "Its nightingale floors squeak underfoot to warn the shogun of intruders.",
  };

  it("accepts a specific, well-described place", () => {
    expect(activityIssues(good, "Kyoto")).toEqual([]);
  });

  it.each([
    [{ ...good, name: "Explore the city" }, "not a specific named place"],
    [{ ...good, name: "Visit a temple" }, "not a specific named place"],
    [{ ...good, name: "Local market" }, "not a specific named place"],
    [{ ...good, name: "Kyoto" }, "just the city name"],
    [{ ...good, reason: "Nice views." }, "too short"],
    [{ ...good, reason: "Visit the castle and see the famous floors." }, 'starts with "Visit"'],
    [{ ...good, reason: "It is a great place to learn about samurai history." }, "filler"],
    [{ ...good, neighborhood: "" }, "no neighborhood"],
  ])("flags %o", (activity, expected) => {
    expect(activityIssues(activity, "Kyoto").join(" ")).toContain(expected);
  });
});

describe("outlineIssues", () => {
  const good = {
    title: "Neon, Shrines and Mountain Air",
    summary: "Six days from Tokyo's izakaya alleys to Kyoto's quiet moss gardens.",
    where: "Japan",
    stops: [
      {
        city: "Kyoto",
        headline: "Lanterns and Moss Gardens",
        intro: "Kyoto keeps 1,600 temples and the best tofu kaiseki in Japan.",
        stay: { why: "Walkable to Gion's teahouses" },
      },
    ],
  };

  it("accepts a specific outline", () => {
    expect(outlineIssues(good)).toEqual([]);
  });

  it("flags a generic title", () => {
    expect(outlineIssues({ ...good, title: "Japan" }).join(" ")).toContain("title is too generic");
  });

  it("flags a headline that repeats the city", () => {
    const stops = [{ ...good.stops[0], headline: "Discover Kyoto" }];
    expect(outlineIssues({ ...good, stops }).join(" ")).toContain("repeats the city name");
  });

  it("flags filler in stop text", () => {
    const stops = [{ ...good.stops[0], stay: { why: "Immerse yourself in tradition" } }];
    expect(outlineIssues({ ...good, stops }).join(" ")).toContain("filler");
  });
});

describe("outlineIssues intro", () => {
  it("flags an intro that starts with Visit", () => {
    const o = {
      title: "Neon, Shrines and Mountain Air",
      summary: "Six days from Tokyo's izakaya alleys to Kyoto's quiet moss gardens.",
      where: "Japan",
      stops: [{ city: "Nara", headline: "Deer and Giant Buddhas", intro: "Visit Todai-ji Temple, home to Japan's largest bronze Buddha.", stay: { why: "" } }],
    };
    expect(outlineIssues(o).join(" ")).toContain('intro starts with "Visit"');
  });
});
