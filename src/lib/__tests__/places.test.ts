import { describe, it, expect } from "vitest";
import {
  matchNearby,
  matchScore,
  nameMatches,
  photoFrom,
  pickPage,
  tokens,
  type NearbyPage,
  type WikiPage,
} from "@/lib/trip/places";

describe("tokens", () => {
  it("lowercases, strips accents and punctuation", () => {
    expect(tokens("Sensō-ji, Asakusa")).toEqual(["senso", "ji", "asakusa"]);
    expect(tokens("Palácio da Bolsa")).toEqual(["palacio", "da", "bolsa"]);
  });
});

describe("nameMatches", () => {
  it.each([
    ["Kiyomizu-dera Temple", "Kiyomizu-dera"],
    ["Fushimi Inari Shrine", "Fushimi Inari-taisha"],
    ["Castelo de São Jorge", "São Jorge Castle"],
    ["Mercado do Bolhão", "Bolhão Market"],
    ["Museu Calouste Gulbenkian", "Calouste Gulbenkian Museum"],
    ["National Pantheon", "National Pantheon (Portugal)"],
    ["Philosopher's Path", "Philosopher's Walk"],
    ["Tokyo Tower", "Tokyo Tower"],
    ["Shinjuku Gyoen National Garden", "Shinjuku Gyo-en"],
    ["Omoide Yokocho", "Omoide Yokochō"],
  ])("matches %s -> %s", (name, title) => {
    expect(nameMatches(name, title)).toBe(true);
  });

  it.each([
    ["Gion Nanba", "Gion"], // restaurant vs district
    ["Meiji Shrine", "Meiji Gakuin University"], // title is about something else
    ["Mercado do Bolhão", "Bolhão station"], // market vs station
    ["Mercado da Ribeira", "Ribeira Palace"], // market vs palace
    ["Gelado de São Pedro", "São Pedro da Afurada"], // ice-cream shop vs parish
    ["National Pantheon", "Pantheon of the House of Braganza"],
    ["Jardim Botânico", "Lisbon Tropical Botanical Garden"], // only generic words: too ambiguous
  ])("rejects %s -> %s", (name, title) => {
    expect(nameMatches(name, title)).toBe(false);
  });

  it("scores an exact title above a longer one", () => {
    expect(matchScore("Meiji Shrine", "Meiji Shrine")).toBeGreaterThan(
      matchScore("Meiji Shrine", "Meiji Jingu Shrine")
    );
  });
});

describe("matchNearby", () => {
  const nearby: NearbyPage[] = [
    { title: "Kyoto", lat: 35.01, lon: 135.77 },
    { title: "Bolhão station", lat: 41.149, lon: -8.606 },
    { title: "Bolhão Market", lat: 41.1488, lon: -8.6067 },
    { title: "Gion", lat: 35.0037, lon: 135.775 },
  ];

  it("picks the right kind of place among similar titles", () => {
    expect(matchNearby("Mercado do Bolhão", nearby)?.title).toBe("Bolhão Market");
  });

  it("never matches the excluded city page", () => {
    expect(matchNearby("Kyoto", nearby, ["Kyoto", "Japan"])).toBeNull();
  });

  it("returns null when nothing matches", () => {
    expect(matchNearby("Gion Nanba", nearby)).toBeNull();
  });
});

describe("pickPage", () => {
  const kyoto = { lat: 35.0116, lng: 135.7681 };
  const pages: WikiPage[] = [
    { title: "Kyoto", index: 1, coordinates: [{ lat: 35.01, lon: 135.77 }] },
    { title: "Banshū Kiyomizu-dera", index: 3, coordinates: [{ lat: 34.97, lon: 135.08 }] },
    { title: "Kiyomizu-dera", index: 2, coordinates: [{ lat: 34.995, lon: 135.785 }] },
    { title: "Kiyomizu-dera (no coords)", index: 0 },
  ];

  it("takes the best-ranked matching page within the radius", () => {
    const p = pickPage(pages, { name: "Kiyomizu-dera Temple", near: kyoto, exclude: ["Kyoto"] });
    expect(p?.title).toBe("Kiyomizu-dera");
  });

  it("rejects matches that are too far from the stop", () => {
    const far = { lat: 43.06, lng: 141.35 }; // Sapporo
    expect(pickPage(pages, { name: "Kiyomizu-dera Temple", near: far })).toBeNull();
  });
});

describe("photoFrom", () => {
  it("strips the tracking query and links the file page for credit", () => {
    const photo = photoFrom(
      {
        title: "Sensō-ji",
        pageimage: "Sensoji_2023.jpg",
        thumbnail: { source: "https://upload.wikimedia.org/x/640px-Sensoji_2023.jpg?utm_source=x", width: 640, height: 400 },
      },
      "place"
    );
    expect(photo).toEqual({
      url: "https://upload.wikimedia.org/x/640px-Sensoji_2023.jpg",
      creditUrl: "https://en.wikipedia.org/wiki/File:Sensoji_2023.jpg",
      kind: "place",
    });
  });

  it("returns null without a thumbnail", () => {
    expect(photoFrom({ title: "x" }, "place")).toBeNull();
  });
});

describe("photo and area filters", () => {
  it("skips logos, maps and SVGs as photos", () => {
    const base = { title: "x", thumbnail: { source: "https://upload.wikimedia.org/a.png", width: 1, height: 1 } };
    expect(photoFrom({ ...base, pageimage: "Gulbenkian_Museum_logo.png" }, "place")).toBeNull();
    expect(photoFrom({ ...base, pageimage: "Lisbon_location_map.svg" }, "place")).toBeNull();
    expect(photoFrom({ ...base, pageimage: "Fado_Museum_facade.jpg" }, "place")).not.toBeNull();
  });

  it("matches neighborhoods only to plain place pages", () => {
    const nearby: NearbyPage[] = [
      { title: "Cais do Sodré station", lat: 38.706, lon: -9.146 },
      { title: "Cais do Sodré", lat: 38.707, lon: -9.144 },
    ];
    expect(matchNearby("Cais do Sodré", nearby, [], { area: true })?.title).toBe("Cais do Sodré");
    expect(matchNearby("Bolhão", [{ title: "Bolhão station", lat: 0, lon: 0 }], [], { area: true })).toBeNull();
  });
});

describe("city exclusion", () => {
  it("ignores qualifiers so the city page never verifies a place", () => {
    const nearby: NearbyPage[] = [{ title: "Nara (city)", lat: 34.685, lon: 135.805 }];
    expect(matchNearby("Nara Park", nearby, ["Nara", "Japan"])).toBeNull();
  });
});
