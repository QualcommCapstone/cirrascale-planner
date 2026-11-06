"use client";

import dynamic from "next/dynamic";
import { useItinerary } from "@/lib/store/itinerary";
import { ErrorBoundary } from "./ErrorBoundary";

// Code-split the OpenUI renderer (heavy) and keep it out of SSR. If anything in
// the OpenUI pipeline throws, the ErrorBoundary hides it — the structured
// itinerary cards above remain the reliable source of truth (hybrid design).
const AiItineraryInner = dynamic(() => import("./AiItineraryInner"), {
  ssr: false,
  loading: () => null,
});

export function AiItinerary() {
  const focusedId = useItinerary((s) => s.focusedId);
  // Keyed on the focused stop so one bad render doesn't hide the panel for good.
  return (
    <ErrorBoundary key={focusedId ?? "none"} fallback={null}>
      <AiItineraryInner />
    </ErrorBoundary>
  );
}
