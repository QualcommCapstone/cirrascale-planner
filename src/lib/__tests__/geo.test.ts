import { describe, it, expect } from "vitest";
import { lookupLatLng, isValidLatLng } from "@/lib/geo";

describe("lookupLatLng", () => {
  it("finds a city by exact name", () => {
    expect(lookupLatLng("Tokyo")).toEqual({ lat: 35.6762, lng: 139.6503 });
  });

  it("is case-insensitive", () => {
    expect(lookupLatLng("KYOTO")).toEqual(lookupLatLng("kyoto"));
  });

  it("matches a substring (e.g. 'Kyoto, Japan')", () => {
    expect(lookupLatLng("Kyoto, Japan")).toEqual(lookupLatLng("kyoto"));
  });

  it("returns null for an unknown place", () => {
    expect(lookupLatLng("Atlantis")).toBeNull();
    expect(lookupLatLng("")).toBeNull();
  });
});

describe("isValidLatLng", () => {
  it("accepts real coordinates", () => {
    expect(isValidLatLng(35.6, 139.7)).toBe(true);
    expect(isValidLatLng(-33.86, 151.2)).toBe(true);
  });

  it("rejects the null island (0,0)", () => {
    expect(isValidLatLng(0, 0)).toBe(false);
  });

  it("rejects out-of-range values", () => {
    expect(isValidLatLng(91, 0)).toBe(false);
    expect(isValidLatLng(0, 181)).toBe(false);
  });

  it("rejects non-numbers and NaN", () => {
    expect(isValidLatLng("35" as unknown, 139)).toBe(false);
    expect(isValidLatLng(NaN, 139)).toBe(false);
    expect(isValidLatLng(undefined as unknown, undefined as unknown)).toBe(false);
  });
});
