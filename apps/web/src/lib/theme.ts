/**
 * Globe colors per theme. Kept in JS because three.js can't read CSS vars;
 * the values mirror the tokens in src/app/globals.css (brand = route/pins).
 */
export interface GlobeColors {
  water: string;
  land: string;
  coast: string;
  route: string;
  atmosphere: string;
}

export const GLOBE_COLORS: Record<"dark" | "light", GlobeColors> = {
  light: {
    water: "#c9dde8",
    land: "#f8f5ef",
    coast: "rgba(60, 52, 44, 0.35)",
    route: "#e8622c",
    atmosphere: "#cfe0ea",
  },
  dark: {
    water: "#13202a",
    land: "#2a2622",
    coast: "rgba(240, 230, 215, 0.25)",
    route: "#f4793d",
    atmosphere: "#1f3442",
  },
};
