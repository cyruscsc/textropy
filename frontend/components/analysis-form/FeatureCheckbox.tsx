"use client";

/** Square, 4px radius, `--accent` when checked (spec §12.5). */

import { Check } from "lucide-react";

import { cn, humanizeFeatureName } from "@/lib/format";
import type { FeatureCatalogEntry } from "@/lib/types";

export default function FeatureCheckbox({
  feature,
  checked,
  disabled,
  onToggle,
}: {
  feature: FeatureCatalogEntry;
  checked: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={cn(
        // `items-start`, not `items-center`: in a narrow column a long label wraps to two
        // lines, and the box belongs beside the first one.
        "flex cursor-pointer items-start gap-2 py-1 text-sm",
        disabled && "cursor-not-allowed opacity-60",
      )}
    >
      {/* 2px centres the 16px box on `text-sm`'s 20px line box. */}
      <span className="relative mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={onToggle}
          className="peer absolute h-4 w-4 cursor-pointer opacity-0 disabled:cursor-not-allowed"
        />
        <span
          aria-hidden
          className={cn(
            "flex h-4 w-4 items-center justify-center rounded border transition-colors",
            checked ? "border-accent bg-accent" : "border-border bg-surface",
            "peer-focus-visible:outline-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2",
          )}
        >
          {checked ? (
            <Check size={12} strokeWidth={2} className="text-surface" />
          ) : null}
        </span>
      </span>
      <span className="text-ink">{humanizeFeatureName(feature.name)}</span>
      {feature.symmetric === false ? (
        // Asymmetric Tier 3 comparisons return both directions (spec §3.2).
        <span
          title="Computed in both directions (A given B, B given A)"
          className="text-ink-muted font-mono text-xs"
        >
          ↔
        </span>
      ) : null}
    </label>
  );
}
