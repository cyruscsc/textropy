"use client";

/**
 * Loading state during `analyzing` (spec §10).
 *
 * Tier 3 is synchronous and can take seconds, so the skeleton carries a note rather than
 * leaving the pane looking stalled (§13.2).
 */

import { cn } from "@/lib/format";

const ROWS = [
  ["w-24", "w-12"],
  ["w-32", "w-16"],
  ["w-28", "w-10"],
  ["w-36", "w-14"],
];

export default function ResultsSkeleton({ slow }: { slow: boolean }) {
  return (
    <div className="flex flex-1 flex-col gap-6 p-6" aria-busy="true" aria-live="polite">
      <span className="sr-only">Running analysis…</span>
      {[0, 1].map((section) => (
        <div key={section} className="flex flex-col gap-3">
          <div className="bg-border h-4 w-16 animate-pulse rounded" />
          {ROWS.map(([labelWidth, valueWidth], index) => (
            <div key={index} className="flex items-center justify-between gap-4">
              <div className={cn("bg-border h-3 animate-pulse rounded", labelWidth)} />
              <div className={cn("bg-border h-3 animate-pulse rounded", valueWidth)} />
            </div>
          ))}
        </div>
      ))}
      {slow ? (
        <p className="text-ink-muted text-sm">
          Tier 3 runs synchronously — this may take several seconds.
        </p>
      ) : null}
    </div>
  );
}
