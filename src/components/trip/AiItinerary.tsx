"use client";

import dynamic from "next/dynamic";
import { ErrorBoundary } from "./ErrorBoundary";

// Code-split the OpenUI renderer (heavy) and keep it out of SSR. If anything in
// the OpenUI pipeline throws, the ErrorBoundary hides it — the structured
// itinerary cards above remain the reliable source of truth (hybrid design).
const AiItineraryInner = dynamic(() => import("./AiItineraryInner"), {
  ssr: false,
  loading: () => null,
});

export function AiItinerary() {
  return (
    <ErrorBoundary fallback={null}>
      <AiItineraryInner />
    </ErrorBoundary>
  );
}
