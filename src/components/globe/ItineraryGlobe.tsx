"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Globe, { GlobeMethods } from "react-globe.gl";
import * as THREE from "three";
import { useTheme } from "next-themes";
import { GLOBE_COLORS } from "@/lib/theme";
import { usePrefersReducedMotion } from "@/lib/use-reduced-motion";
import { pinnedActivities, useTrip } from "@/lib/store/trip";
import type { Trip } from "@/lib/trip/types";

/** City markers: numbered to match the stop sections in the story. */
interface StopMarker {
  kind: "stop";
  id: string;
  lat: number;
  lng: number;
  label: string;
  number: number;
  focused: boolean;
}

/** Activity pins: only for places verified against Wikipedia. */
interface ActivityPin {
  kind: "activity";
  id: string;
  lat: number;
  lng: number;
  label: string;
  active: boolean;
}

type Marker = StopMarker | ActivityPin;

interface RouteArc {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
}

type CountryFeatureCollection = { features: object[] };

// Camera altitudes (globe radii above the surface).
const ALT_STOP = 0.09; // a city and its day trips
const ALT_ACTIVITY = 0.035; // one neighborhood
const SHOW_PINS_BELOW = 0.6; // activity pins only once zoomed in on a city

/** Point of view that frames every stop. */
function overview(trip: Trip): { lat: number; lng: number; altitude: number } {
  const rad = Math.PI / 180;
  let x = 0;
  let y = 0;
  let z = 0;
  for (const s of trip.stops) {
    x += Math.cos(s.lat * rad) * Math.cos(s.lng * rad);
    y += Math.cos(s.lat * rad) * Math.sin(s.lng * rad);
    z += Math.sin(s.lat * rad);
  }
  const lat = Math.atan2(z, Math.hypot(x, y)) / rad;
  const lng = Math.atan2(y, x) / rad;
  const spread = Math.max(
    ...trip.stops.map((s) => Math.hypot(s.lat - lat, ((s.lng - lng + 540) % 360) - 180))
  );
  return { lat, lng, altitude: Math.min(2.4, Math.max(0.7, spread / 14)) };
}

function stopElement(m: StopMarker, onClick: () => void): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  el.title = m.label;
  el.textContent = String(m.number);
  el.style.cssText = [
    "pointer-events:auto",
    "cursor:pointer",
    "display:flex",
    "align-items:center",
    "justify-content:center",
    `width:${m.focused ? 30 : 24}px`,
    `height:${m.focused ? 30 : 24}px`,
    "border-radius:9999px",
    "font:600 12px/1 var(--font-sans), system-ui, sans-serif",
    `background:${m.focused ? "hsl(var(--brand))" : "hsl(var(--foreground))"}`,
    `color:${m.focused ? "hsl(var(--brand-foreground))" : "hsl(var(--background))"}`,
    "border:2px solid hsl(var(--background))",
    "box-shadow:0 1px 4px rgb(0 0 0 / 0.25)",
    "transform:translate(0,-50%)",
    "transition:width .18s, height .18s, background .18s",
  ].join(";");
  el.onclick = (e) => {
    e.stopPropagation();
    onClick();
  };
  return el;
}

function activityElement(m: ActivityPin, onClick: () => void): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  el.title = m.label;
  el.style.cssText = [
    "pointer-events:auto",
    "cursor:pointer",
    "display:flex",
    "align-items:center",
    "gap:6px",
    "padding:0",
    "background:none",
    "border:0",
    "transform:translate(0,-50%)",
  ].join(";");
  const dot = document.createElement("span");
  dot.style.cssText = [
    `width:${m.active ? 14 : 10}px`,
    `height:${m.active ? 14 : 10}px`,
    "border-radius:9999px",
    `background:${m.active ? "hsl(var(--brand))" : "hsl(var(--background))"}`,
    "border:2.5px solid hsl(var(--brand))",
    "box-shadow:0 1px 3px rgb(0 0 0 / 0.3)",
    "flex:none",
  ].join(";");
  el.appendChild(dot);
  if (m.active) {
    const tag = document.createElement("span");
    tag.textContent = m.label;
    tag.style.cssText = [
      "padding:3px 8px",
      "border-radius:9999px",
      "background:hsl(var(--foreground))",
      "color:hsl(var(--background))",
      "font:500 11px/1.2 var(--font-sans), system-ui, sans-serif",
      "white-space:nowrap",
      "box-shadow:0 1px 4px rgb(0 0 0 / 0.25)",
    ].join(";");
    el.appendChild(tag);
  }
  el.onclick = (e) => {
    e.stopPropagation();
    onClick();
  };
  return el;
}

export default function ItineraryGlobe() {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [countries, setCountries] = useState<object[]>([]);
  const [zoomedIn, setZoomedIn] = useState(false);

  const { resolvedTheme } = useTheme();
  const colors = GLOBE_COLORS[resolvedTheme === "dark" ? "dark" : "light"];
  const reducedMotion = usePrefersReducedMotion();
  const ms = (n: number) => (reducedMotion ? 0 : n);

  const trip = useTrip((s) => s.trip);
  const pending = useTrip((s) => s.pendingStopIds);
  const focusedStopId = useTrip((s) => s.focusedStopId);
  const focusedActivityId = useTrip((s) => s.focusedActivityId);
  const hoveredActivityId = useTrip((s) => s.hoveredActivityId);
  const focusTick = useTrip((s) => s.focusTick);
  const focusStop = useTrip((s) => s.focusStop);
  const focusActivity = useTrip((s) => s.focusActivity);

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

  // Country shapes for the land fill (client-only).
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

  const globeMaterial = useMemo(
    // Emissive keeps the water a clean wash instead of shading to gray on the dark side.
    () =>
      new THREE.MeshLambertMaterial({ color: colors.water, emissive: colors.water, emissiveIntensity: 0.22 }),
    [colors.water]
  );

  const markers: Marker[] = useMemo(() => {
    if (!trip) return [];
    const stops: StopMarker[] = trip.stops.map((s, i) => ({
      kind: "stop",
      id: s.id,
      lat: s.lat,
      lng: s.lng,
      label: s.city,
      number: i + 1,
      focused: s.id === focusedStopId && !focusedActivityId,
    }));
    if (!zoomedIn) return stops;
    const pins: ActivityPin[] = pinnedActivities(trip).map((a) => ({
      kind: "activity",
      id: a.id,
      lat: a.lat,
      lng: a.lng,
      label: a.name,
      active: a.id === hoveredActivityId || a.id === focusedActivityId,
    }));
    return [...stops, ...pins];
  }, [trip, zoomedIn, focusedStopId, focusedActivityId, hoveredActivityId]);

  // The route draws leg by leg as each stop's plan arrives.
  const arcs: RouteArc[] = useMemo(() => {
    if (!trip) return [];
    const out: RouteArc[] = [];
    for (let i = 0; i < trip.stops.length - 1; i++) {
      const a = trip.stops[i];
      const b = trip.stops[i + 1];
      if (pending.includes(a.id) || pending.includes(b.id)) continue;
      out.push({ startLat: a.lat, startLng: a.lng, endLat: b.lat, endLng: b.lng });
    }
    return out;
  }, [trip, pending]);

  // Spin gently while idle or waiting for the outline.
  useEffect(() => {
    const g = globeRef.current;
    if (!g) return;
    const controls = g.controls() as { autoRotate: boolean; autoRotateSpeed: number };
    controls.autoRotate = !reducedMotion && !trip;
    controls.autoRotateSpeed = 0.4;
  }, [reducedMotion, trip, size.width]);

  // Frame the whole route when a new trip's outline arrives.
  const tripKey = trip ? trip.stops.map((s) => s.id).join("|") + trip.title : "";
  useEffect(() => {
    const g = globeRef.current;
    if (!g || !trip) return;
    g.pointOfView(overview(trip), ms(1400));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripKey, size.width > 0]);

  // Fly to whatever was focused, from the story or the globe.
  useEffect(() => {
    const g = globeRef.current;
    if (!g || !trip || focusTick === 0) return;
    if (focusedActivityId) {
      const a = pinnedActivities(trip).find((x) => x.id === focusedActivityId);
      if (a) {
        g.pointOfView({ lat: a.lat, lng: a.lng, altitude: ALT_ACTIVITY }, ms(1100));
        return;
      }
    }
    const s = trip.stops.find((x) => x.id === focusedStopId);
    if (s) g.pointOfView({ lat: s.lat, lng: s.lng, altitude: ALT_STOP }, ms(1300));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusTick]);

  return (
    <div ref={wrapRef} className="absolute inset-0" aria-hidden="true">
      {size.width > 0 && (
        <Globe
          ref={globeRef}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          globeMaterial={globeMaterial}
          showAtmosphere
          atmosphereColor={colors.atmosphere}
          atmosphereAltitude={0.12}
          polygonsData={countries}
          polygonCapColor={() => colors.land}
          polygonSideColor={() => "rgba(0,0,0,0)"}
          polygonStrokeColor={() => colors.coast}
          polygonAltitude={0.004}
          polygonsTransitionDuration={0}
          arcsData={arcs}
          arcStartLat={(a) => (a as RouteArc).startLat}
          arcStartLng={(a) => (a as RouteArc).startLng}
          arcEndLat={(a) => (a as RouteArc).endLat}
          arcEndLng={(a) => (a as RouteArc).endLng}
          arcColor={() => colors.route}
          // A wide stroke is in globe units, so it smears into a band up close: go thin when zoomed in.
          arcStroke={zoomedIn ? null : 0.55}
          arcDashLength={0.4}
          arcDashGap={0.14}
          arcDashInitialGap={1}
          arcDashAnimateTime={ms(3200)}
          arcAltitudeAutoScale={0.35}
          arcsTransitionDuration={ms(900)}
          htmlElementsData={markers}
          htmlLat={(d) => (d as Marker).lat}
          htmlLng={(d) => (d as Marker).lng}
          htmlAltitude={(d) => ((d as Marker).kind === "stop" ? 0.012 : 0.006)}
          htmlTransitionDuration={0}
          htmlElement={(d) => {
            const m = d as Marker;
            return m.kind === "stop"
              ? stopElement(m, () => focusStop(m.id, "globe"))
              : activityElement(m, () => focusActivity(m.id, "globe"));
          }}
          htmlElementVisibilityModifier={(el, visible) => {
            el.style.opacity = visible ? "1" : "0";
            el.style.pointerEvents = visible ? "auto" : "none";
          }}
          onZoom={({ altitude }) => {
            const inside = altitude < SHOW_PINS_BELOW;
            setZoomedIn((prev) => (prev === inside ? prev : inside));
          }}
        />
      )}
    </div>
  );
}
