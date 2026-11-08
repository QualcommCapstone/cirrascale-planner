"use client";

import { ArrowUpRight } from "lucide-react";
import { DESTINATIONS, destinationPhoto, type Destination } from "@/lib/destinations";
import { cn } from "@/lib/utils";

interface Props {
  onPick: (d: Destination) => void;
  disabled?: boolean;
  limit?: number;
  className?: string;
}

/** Sample prompts as photo cards: location tag, the prompt as the title. */
export function SampleTrips({ onPick, disabled, limit = DESTINATIONS.length, className }: Props) {
  return (
    <ul className={cn("grid gap-3 sm:grid-cols-2 xl:grid-cols-3", className)}>
      {DESTINATIONS.slice(0, limit).map((d) => (
        <li key={d.place}>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onPick(d)}
            className="group relative block aspect-[4/5] w-full overflow-hidden rounded-xl bg-muted text-left transition-smooth focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60 sm:aspect-[3/4]"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={destinationPhoto(d, 500)}
              alt=""
              loading="lazy"
              referrerPolicy="no-referrer"
              className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
            <span className="photo-scrim absolute inset-0" />
            <span className="absolute left-3 top-3 rounded-full bg-background/90 px-2.5 py-1 text-[11px] font-medium text-foreground backdrop-blur">
              {d.region}
            </span>
            <span className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-background/90 text-foreground opacity-0 transition-smooth group-hover:opacity-100">
              <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="absolute inset-x-0 bottom-0 p-4 text-white">
              <span className="block text-lg font-bold leading-tight tracking-display">{d.place}</span>
              <span className="mt-1 block text-[13px] leading-snug text-white/85">{d.prompt}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
