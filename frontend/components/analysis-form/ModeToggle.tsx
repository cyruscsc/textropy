"use client";

/** Segmented control, text-only by design — no icons here (spec §12.4). */

import { cn } from "@/lib/format";
import type { Mode } from "@/lib/types";

const OPTIONS: { id: Mode; label: string }[] = [
  { id: "single", label: "Single text" },
  { id: "compare", label: "Compare" },
];

export default function ModeToggle({
  mode,
  onChange,
  disabled,
}: {
  mode: Mode;
  onChange: (mode: Mode) => void;
  disabled?: boolean;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Analysis mode"
      className={cn(
        "border-border inline-flex rounded border p-0.5",
        disabled && "opacity-60",
      )}
    >
      {OPTIONS.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={mode === id}
          disabled={disabled}
          onClick={() => onChange(id)}
          className={cn(
            "rounded px-3 py-1.5 text-sm transition-colors",
            mode === id
              ? "bg-accent-soft text-accent font-medium"
              : "text-ink-muted hover:text-ink",
            disabled && "cursor-not-allowed",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
