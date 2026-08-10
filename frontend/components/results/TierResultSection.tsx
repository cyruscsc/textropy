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
}: {
  tier: number;
  block: TierBlock;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const entries = Object.entries(block);
  if (entries.length === 0) return null;

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
              <MetricRow key={name} name={name} value={value} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
