"use client";

import { useItinerary } from "@/lib/store/itinerary";
import { cn } from "@/lib/utils";
import { Globe2, Plus, Settings } from "lucide-react";

export function NavRail() {
  const reset = useItinerary((s) => s.reset);

  return (
    <nav
      aria-label="Primary"
      className="flex w-14 shrink-0 flex-col items-center gap-1 border-r border-border bg-card py-3"
    >
      <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-md bg-primary/15 text-primary">
        <Globe2 className="h-4 w-4" />
      </div>

      <RailButton label="Trips" active>
        <Globe2 className="h-4 w-4" />
      </RailButton>
      <RailButton label="New trip" onClick={reset}>
        <Plus className="h-4 w-4" />
      </RailButton>

      <div className="mt-auto">
        <RailButton label="Settings">
          <Settings className="h-4 w-4" />
        </RailButton>
      </div>
    </nav>
  );
}

function RailButton({
  children,
  label,
  active = false,
  onClick,
}: {
  children: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-md border transition-smooth focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border-primary/40 bg-primary/10 text-primary"
          : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}
