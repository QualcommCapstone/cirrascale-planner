/** Globe colors per theme. Kept in JS because three.js can't read CSS vars. */
export interface GlobeColors {
  marker: string;
  markerGlow: string;
  arc: [string, string];
  graticule: string;
  hexLand: string;
  atmosphere: string;
  background: string;
}

export const GLOBE_COLORS: Record<"dark" | "light", GlobeColors> = {
  dark: {
    marker: "#c4b5fd", // lavender-300
    markerGlow: "#a78bfa", // lavender-400
    arc: ["#a78bfa", "#e9d5ff"],
    graticule: "rgba(167, 139, 250, 0.16)",
    hexLand: "rgba(167, 139, 250, 0.30)",
    atmosphere: "#8b5cf6",
    background: "rgba(0,0,0,0)",
  },
  light: {
    marker: "#6d28d9", // violet-700
    markerGlow: "#7c3aed",
    arc: ["#7c3aed", "#a78bfa"],
    graticule: "rgba(109, 40, 217, 0.18)",
    hexLand: "rgba(124, 58, 237, 0.22)",
    atmosphere: "#7c3aed",
    background: "rgba(0,0,0,0)",
  },
};
