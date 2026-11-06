"use client";

import { useItinerary } from "@/lib/store/itinerary";
import ModeToggle from "@/app/components/ModeToggle";
import { Sparkles } from "lucide-react";

export function Header() {
  const title = useItinerary((s) => s.title);
  const status = useItinerary((s) => s.status);

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-4">
      <div className="flex min-w-0 items-center gap-2">
        <span className="text-sm font-semibold tracking-display">Cirrascale Planner</span>
        {status === "ready" && title ? (
          <>
            <span className="text-muted-foreground/50">/</span>
            <span className="truncate text-sm text-muted-foreground">{title}</span>
          </>
        ) : null}
      </div>

      <div className="flex items-center gap-3">
        <span className="hidden items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground sm:flex">
          <Sparkles className="h-3 w-3 text-primary" />
          Llama-3.1-8B · Cirrascale
        </span>
        <ModeToggle />
      </div>
    </header>
  );
}
