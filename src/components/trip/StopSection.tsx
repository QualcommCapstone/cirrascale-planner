"use client";

import { useEffect, useRef } from "react";
import { AlertCircle, ArrowUpRight, BedDouble, MapPin, Utensils } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTrip } from "@/lib/store/trip";
import { usePrefersReducedMotion } from "@/lib/use-reduced-motion";
import { formatDays } from "@/lib/trip/format";
import type { Stop } from "@/lib/trip/types";
import { ActivityCard } from "./ActivityCard";
import { Photo } from "./Photo";

interface Props {
  stop: Stop;
  number: number;
  pending: boolean;
  failed: boolean;
}

export function StopSection({ stop, number, pending, failed }: Props) {
  const ref = useRef<HTMLElement>(null);
  const reducedMotion = usePrefersReducedMotion();
  const focused = useTrip((s) => s.focusedStopId === stop.id && !s.focusedActivityId);
  const fromGlobe = useTrip((s) => s.focusSource === "globe");
  const focusTick = useTrip((s) => s.focusTick);
  const focusStop = useTrip((s) => s.focusStop);

  // A city marker clicked on the globe scrolls to its section.
  useEffect(() => {
    if (focused && fromGlobe) {
      ref.current?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusTick]);

  const place = [stop.city, stop.country].filter(Boolean).join(", ");

  return (
    <section ref={ref} id={`stop-${stop.id}`} aria-labelledby={`stop-title-${stop.id}`} className="scroll-mt-4">
      {/* Hero card */}
      <div
        className={cn(
          "print-avoid-break group relative overflow-hidden rounded-xl bg-muted transition-smooth animate-rise-in",
          focused ? "ring-2 ring-brand ring-offset-2 ring-offset-background" : ""
        )}
      >
        <div className="relative aspect-[16/9] sm:aspect-[21/9]">
          <Photo photo={stop.photo} alt={place} credit priority={number === 1} />
          <div className="photo-scrim pointer-events-none absolute inset-0" />
          <div className="pointer-events-none absolute left-4 top-4 flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-background text-xs font-bold text-foreground">
              {number}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-background/90 px-2.5 py-1 text-xs font-medium text-foreground backdrop-blur">
              <MapPin className="h-3 w-3" aria-hidden="true" />
              {place}
            </span>
          </div>
          <div className="pointer-events-none absolute inset-x-0 bottom-0 p-4 text-white sm:p-5">
            <p className="text-xs font-medium uppercase tracking-wider text-white/75">
              {formatDays(stop.dayStart, stop.dayEnd)}
            </p>
            <h3
              id={`stop-title-${stop.id}`}
              className="mt-1 text-2xl font-bold leading-tight tracking-display text-balance sm:text-3xl"
            >
              {stop.headline || stop.city}
            </h3>
            {stop.intro ? (
              <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-white/85">{stop.intro}</p>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          onClick={() => focusStop(stop.id, "story")}
          aria-label={`Fly to ${stop.city} on the map`}
          className="absolute inset-0 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="print-hidden absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full bg-background/90 text-foreground opacity-0 transition-smooth group-hover:opacity-100">
            <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
          </span>
        </button>
      </div>

      {/* Stay + eat */}
      {(stop.stay.area || stop.food.length > 0) && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {stop.stay.area ? (
            <InfoTile icon={<BedDouble className="h-4 w-4" />} label="Stay in" title={stop.stay.area} note={stop.stay.why} />
          ) : null}
          {stop.food.length > 0 ? (
            <InfoTile
              icon={<Utensils className="h-4 w-4" />}
              label="Eat"
              title={stop.food.map((f) => f.name).join(" · ")}
              note={stop.food.map((f) => f.note).filter(Boolean).join(" · ")}
            />
          ) : null}
        </div>
      )}

      {/* Days */}
      <div className="mt-6 space-y-7">
        {failed ? (
          <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
            <span>We couldn&apos;t plan the days in {stop.city} this time. Try generating the trip again.</span>
          </div>
        ) : pending ? (
          <DaySkeleton day={stop.dayStart} city={stop.city} />
        ) : (
          stop.days.map((d) => (
            <div key={d.day}>
              <div className="mb-3 flex items-baseline gap-3">
                <h4 className="text-lg font-bold tracking-display">Day {d.day}</h4>
                <span className="h-px flex-1 bg-border" />
              </div>
              {d.activities.length > 0 ? (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {d.activities.map((a) => (
                    <ActivityCard key={a.id} activity={a} city={stop.city} />
                  ))}
                </div>
              ) : (
                <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                  Nothing we could stand behind for this day. Leave it open, or regenerate the trip.
                </p>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function InfoTile({ icon, label, title, note }: { icon: React.ReactNode; label: string; title: string; note: string }) {
  return (
    <div className="print-avoid-break flex gap-3 rounded-xl border border-border bg-card p-3.5">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-foreground" aria-hidden="true">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className="text-sm font-semibold leading-snug">{title}</p>
        {note ? <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{note}</p> : null}
      </div>
    </div>
  );
}

function DaySkeleton({ day, city }: { day: number; city: string }) {
  return (
    <div aria-live="polite">
      <div className="mb-3 flex items-baseline gap-3">
        <h4 className="text-lg font-bold tracking-display text-muted-foreground">Day {day}</h4>
        <span className="text-xs text-muted-foreground">Finding real places in {city}…</span>
        <span className="h-px flex-1 bg-border" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="aspect-[4/3] animate-pulse bg-muted" />
            <div className="space-y-2 p-3.5">
              <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
              <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
              <div className="h-3 w-full animate-pulse rounded bg-muted" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
