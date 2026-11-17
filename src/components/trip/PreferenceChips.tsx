"use client";

import { Leaf, Moon, Landmark, UtensilsCrossed } from "lucide-react";
import { cn } from "@/lib/utils";
import { BUDGETS, INTERESTS, PACES, type Preferences } from "@/lib/trip/types";

const INTEREST_ICON = {
  Food: UtensilsCrossed,
  Nature: Leaf,
  Culture: Landmark,
  Nightlife: Moon,
} as const;

interface Props {
  value: Preferences;
  onChange: (p: Preferences) => void;
  disabled?: boolean;
}

/** Interests (multi-select), budget and pace. Sent with the prompt and shown on the trip header. */
export function PreferenceChips({ value, onChange, disabled }: Props) {
  const toggleInterest = (i: Preferences["interests"][number]) =>
    onChange({
      ...value,
      interests: value.interests.includes(i)
        ? value.interests.filter((x) => x !== i)
        : [...value.interests, i],
    });

  return (
    <div className="space-y-2.5">
      <Group label="Interests">
        {INTERESTS.map((i) => {
          const Icon = INTEREST_ICON[i];
          return (
            <Chip key={i} active={value.interests.includes(i)} disabled={disabled} onClick={() => toggleInterest(i)}>
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              {i}
            </Chip>
          );
        })}
      </Group>
      <div className="flex flex-wrap gap-x-6 gap-y-2.5">
        <Group label="Budget" single>
          {BUDGETS.map((b) => (
            <Chip key={b} active={value.budget === b} disabled={disabled} onClick={() => onChange({ ...value, budget: b })} single>
              {b}
            </Chip>
          ))}
        </Group>
        <Group label="Pace" single>
          {PACES.map((p) => (
            <Chip key={p} active={value.pace === p} disabled={disabled} onClick={() => onChange({ ...value, pace: p })} single>
              {p}
            </Chip>
          ))}
        </Group>
      </div>
    </div>
  );
}

function Group({ label, children, single }: { label: string; children: React.ReactNode; single?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5" role={single ? "radiogroup" : "group"} aria-label={label}>
      <span className="mr-1 w-[62px] text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}

function Chip({
  active,
  disabled,
  onClick,
  single,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  single?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      role={single ? "radio" : undefined}
      aria-checked={single ? active : undefined}
      aria-pressed={single ? undefined : active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-smooth",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
        active
          ? "border-foreground bg-foreground text-background"
          : "border-border bg-card text-foreground hover:border-foreground/40"
      )}
    >
      {children}
    </button>
  );
}
