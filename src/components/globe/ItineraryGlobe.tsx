"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Globe, { GlobeMethods } from "react-globe.gl";
import * as THREE from "three";
import { useTheme } from "next-themes";
import { GLOBE_COLORS } from "@/lib/theme";
import { usePrefersReducedMotion } from "@/lib/use-reduced-motion";
import {
  selectArcs,
  useItinerary,
  type Destination,
} from "@/lib/store/itinerary";

interface MarkerDatum {
  id: string;
  lat: number;
  lng: number;
  name: string;
  focused: boolean;
}

type CountryFeatureCollection = { features: object[] };

export default function ItineraryGlobe() {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [countries, setCountries] = useState<object[]>([]);

  const { resolvedTheme } = useTheme();
  const colors = GLOBE_COLORS[resolvedTheme === "light" ? "light" : "dark"];
  const reducedMotion = usePrefersReducedMotion();

  const destinations = useItinerary((s) => s.destinations);
  const focusedId = useItinerary((s) => s.focusedId);
  const focus = useItinerary((s) => s.focus);

  // Responsive sizing.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Load country outlines for the wireframe land hexes (client-only).
  useEffect(() => {
    let active = true;
    fetch("/geo/countries-110m.json")
      .then((r) => r.json())
      .then((geo: CountryFeatureCollection) => {
        if (active) setCountries(geo.features ?? []);
      })
      .catch(() => void 0);
    return () => {
      active = false;
    };
  }, []);

  // A subtle dark sphere so the graticule + hexes read as a wireframe globe.
  const globeMaterial = useMemo(() => {
    const isLight = resolvedTheme === "light";
    return new THREE.MeshPhongMaterial({
      color: isLight ? "#f4f3fb" : "#111018",
      transparent: true,
      opacity: isLight ? 0.9 : 0.85,
    });
  }, [resolvedTheme]);

  const markers: MarkerDatum[] = useMemo(
    () =>
      destinations.map((d) => ({
        id: d.id,
        lat: d.lat,
        lng: d.lng,
        name: d.name,
        focused: d.id === focusedId,
      })),
    [destinations, focusedId]
  );

  const arcs = useMemo(() => selectArcs(destinations), [destinations]);

  const rings = useMemo(
    () => markers.filter((m) => m.focused).map((m) => ({ lat: m.lat, lng: m.lng })),
    [markers]
  );

  // Auto-rotate unless reduced motion; pause once a trip is loaded.
  useEffect(() => {
    const g = globeRef.current;
    if (!g) return;
    const controls = g.controls() as { autoRotate: boolean; autoRotateSpeed: number };
    controls.autoRotate = !reducedMotion && destinations.length === 0;
    controls.autoRotateSpeed = 0.5;
  }, [reducedMotion, destinations.length, size.width]);

  // Fly to the focused destination (whether clicked on globe or in the panel).
  useEffect(() => {
    const g = globeRef.current;
    if (!g || !focusedId) return;
    const d = destinations.find((x) => x.id === focusedId);
    if (!d) return;
    g.pointOfView(
      { lat: d.lat, lng: d.lng, altitude: 1.6 },
      reducedMotion ? 0 : 1200
    );
  }, [focusedId, destinations, reducedMotion]);

  if (size.width === 0) {
    // Still measure via the wrapper; render nothing heavy until we have a size.
    return <div ref={wrapRef} className="h-full w-full" aria-hidden="true" />;
  }

  return (
    <div ref={wrapRef} className="h-full w-full" aria-hidden="true">
      <Globe
        ref={globeRef}
        width={size.width}
        height={size.height}
        backgroundColor={colors.background}
        globeMaterial={globeMaterial}
        showGraticules
        showAtmosphere
        atmosphereColor={colors.atmosphere}
        atmosphereAltitude={0.18}
        hexPolygonsData={countries}
        hexPolygonResolution={3}
        hexPolygonMargin={0.4}
        hexPolygonAltitude={0.008}
        hexPolygonColor={() => colors.hexLand}
        pointsData={markers}
        pointLat={(d) => (d as MarkerDatum).lat}
        pointLng={(d) => (d as MarkerDatum).lng}
        pointColor={(d) =>
          (d as MarkerDatum).focused ? colors.markerGlow : colors.marker
        }
        pointAltitude={(d) => ((d as MarkerDatum).focused ? 0.12 : 0.06)}
        pointRadius={(d) => ((d as MarkerDatum).focused ? 0.45 : 0.3)}
        pointLabel={(d) => (d as MarkerDatum).name}
        onPointClick={(d) => focus((d as MarkerDatum).id)}
        ringsData={rings}
        ringColor={() => colors.markerGlow}
        ringMaxRadius={3}
        ringPropagationSpeed={reducedMotion ? 0 : 2}
        ringRepeatPeriod={reducedMotion ? 0 : 900}
        arcsData={arcs}
        arcStartLat={(a) => (a as { startLat: number }).startLat}
        arcStartLng={(a) => (a as { startLng: number }).startLng}
        arcEndLat={(a) => (a as { endLat: number }).endLat}
        arcEndLng={(a) => (a as { endLng: number }).endLng}
        arcColor={() => colors.arc}
        arcStroke={0.5}
        arcDashLength={0.4}
        arcDashGap={0.15}
        arcDashAnimateTime={reducedMotion ? 0 : 2600}
        arcAltitudeAutoScale={0.4}
      />
    </div>
  );
}

// Re-export the type for consumers that need it.
export type { Destination };
