"use client";

/** One collapsible tier block of metric rows (spec §11). */

import { ChevronRight } from "lucide-react";
import { useState } from "react";

import MetricRow from "@/components/results/MetricRow";
import { cn } from "@/lib/format";
import type { TierBlock } from "@/lib/types";

export default function TierResultSection({
  tier,
  block,
  defaultOpen = true,
  isApproximate = () => false,
}: {
  tier: number;
  block: TierBlock;
  defaultOpen?: boolean;
  /** Catalog-backed predicate, supplied by `ResultsPane` (specs_features.md §11.1). */
  isApproximate?: (name: string) => boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const entries = Object.entries(block);
  if (entries.length === 0) return null;

  const approximateCount = entries.filter(([name]) => isApproximate(name)).length;

  return (
    <section className="border-border border-b last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded py-2 text-left"
      >
        <ChevronRight
          size={16}
          strokeWidth={1.5}
          aria-hidden
          className={cn("text-ink-muted transition-transform", open && "rotate-90")}
        />
        <span className="text-ink text-sm font-medium">Tier {tier}</span>
        <span className="text-ink-muted font-mono text-xs">{entries.length}</span>
      </button>

      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-150 ease-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          <div className="pb-3 pl-6">
            {entries.map(([name, value]) => (
              <MetricRow
                key={name}
                name={name}
                value={value}
                approximate={isApproximate(name)}
              />
            ))}

            {/*
              specs_features.md §11.1 — the disclosure Decision 5 committed to. Scoped to
              the sections that actually contain marked rows, so a tier of exact metrics
              never carries a caveat that does not apply to it.
            */}
            {approximateCount > 0 ? (
              <p className="border-border text-ink-muted mt-2 border-t pt-2 text-xs leading-relaxed">
                <span className="font-mono">≈</span> Derived from the dependency parse.
                Textropy parses with <span className="font-mono">en_core_web_sm</span>,
                which mis-reads some ordinary relative and subordinate clauses, so these{" "}
                <span className="font-mono">{approximateCount}</span> values are
                approximate rather than authoritative.
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
