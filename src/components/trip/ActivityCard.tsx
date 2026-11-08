"use client";

import { useEffect, useRef } from "react";
import { Clock, ExternalLink, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTrip } from "@/lib/store/trip";
import { usePrefersReducedMotion } from "@/lib/use-reduced-motion";
import { CATEGORY_LABEL, COST_LABEL, SLOT_LABEL, formatDuration, safeUrl } from "@/lib/trip/format";
import type { Activity } from "@/lib/trip/types";
import { Photo } from "./Photo";

export function ActivityCard({ activity, city }: { activity: Activity; city: string }) {
  const ref = useRef<HTMLElement>(null);
  const reducedMotion = usePrefersReducedMotion();
  const focused = useTrip((s) => s.focusedActivityId === activity.id);
  const hovered = useTrip((s) => s.hoveredActivityId === activity.id);
  const fromGlobe = useTrip((s) => s.focusSource === "globe");
  const focusTick = useTrip((s) => s.focusTick);
  const focusActivity = useTrip((s) => s.focusActivity);
  const hoverActivity = useTrip((s) => s.hoverActivity);

  // A pin clicked on the globe scrolls its card into view.
  useEffect(() => {
    if (focused && fromGlobe) {
      ref.current?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusTick]);

  const source = safeUrl(activity.sourceUrl);
  const onMap = activity.lat !== null;

  return (
    <article
      ref={ref}
      id={`activity-${activity.id}`}
      onMouseEnter={() => hoverActivity(activity.id)}
      onMouseLeave={() => hoverActivity(null)}
      className={cn(
        "print-avoid-break group relative flex flex-col overflow-hidden rounded-xl border bg-card transition-smooth animate-rise-in",
        focused || hovered
          ? "border-brand/70 shadow-[0_6px_24px_-12px_hsl(var(--brand)/0.6)]"
          : "border-border hover:border-foreground/20"
      )}
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-muted">
        <Photo photo={activity.photo} alt={activity.name} credit className="transition-transform duration-500 group-hover:scale-[1.03]" />
        <span className="pointer-events-none absolute left-2.5 top-2.5 z-10 rounded-full bg-background/90 px-2.5 py-1 text-[11px] font-semibold text-foreground backdrop-blur">
          {SLOT_LABEL[activity.slot]}
        </span>
        {!activity.verified ? (
          <span
            title={`We couldn't match this place on Wikipedia, so it isn't pinned on the map. ${
              activity.photo?.kind === "area" ? "Photo shows the neighborhood." : activity.photo?.kind === "city" ? `Photo shows ${city}.` : ""
            }`}
            className="absolute right-2.5 top-2.5 z-10 rounded-full bg-black/55 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur"
          >
            Not verified
          </span>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col gap-1.5 p-3.5">
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <MapPin className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span className="truncate">{activity.neighborhood || city}</span>
        </p>
        <h4 className="font-display text-[15px] font-semibold leading-snug tracking-tightish">{activity.name}</h4>
        <p className="text-[13px] leading-relaxed text-muted-foreground">{activity.reason}</p>
        <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" aria-hidden="true" />
            {formatDuration(activity.durationMins)}
          </span>
          <span>{COST_LABEL[activity.cost]}</span>
          <span>{CATEGORY_LABEL[activity.category]}</span>
          {source ? (
            <a
              href={source}
              target="_blank"
              rel="noopener noreferrer"
              className="relative z-10 ml-auto inline-flex items-center gap-1 hover:text-foreground"
            >
              Wikipedia <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </a>
          ) : null}
        </div>
      </div>

      {/* Whole-card hit area: focus the place (and fly the globe to it). */}
      <button
        type="button"
        onClick={() => focusActivity(activity.id, "story")}
        onFocus={() => hoverActivity(activity.id)}
        onBlur={() => hoverActivity(null)}
        aria-label={onMap ? `Show ${activity.name} on the map` : `Select ${activity.name}`}
        aria-pressed={focused}
        className="absolute inset-0 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
    </article>
  );
}
