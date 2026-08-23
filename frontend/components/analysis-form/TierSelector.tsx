"use client";

/**
 * Tier → feature picker (spec §9, §13.2).
 *
 * Built entirely from `GET /api/v1/features`: tiers, feature names and the per-text vs
 * comparison split all come from the catalog, so a feature added to the backend registry
 * appears here with no frontend change.
 */

import { ChevronRight, Clock } from "lucide-react";
import { useState } from "react";

import FeatureCheckbox from "@/components/analysis-form/FeatureCheckbox";
import { cn } from "@/lib/format";
import type { FeatureCatalogEntry, Mode } from "@/lib/types";
import { TIERS } from "@/lib/types";

/** Tier 3 runs synchronously in-request — there is no job queue in the MVP (§14). */
const SLOW_TIER = 3;

function FeatureGroup({
  label,
  features,
  selected,
  disabled,
  onToggle,
}: {
  label: string | null;
  features: FeatureCatalogEntry[];
  selected: string[];
  disabled: boolean;
  onToggle: (name: string) => void;
}) {
  if (features.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      {label ? (
        <p className="text-ink-muted text-xs tracking-wide uppercase">{label}</p>
      ) : null}
      {/*
        Columns follow the *pane's* width, which is not a monotonic function of the
        viewport's: at `lg` the pane is `w-2/5`, below it the pane is the full-width
        Analyze tab, so a 1000px window gives a wider pane than an 1100px one. No
        breakpoint variant can express that, so the column count comes from `auto-fill`
        reading the real container width. 12rem is the largest minimum that still yields
        two columns on a 1280 laptop.
      */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(12rem,1fr))] gap-x-6 gap-y-1">
        {features.map((feature) => (
          <FeatureCheckbox
            key={feature.name}
            feature={feature}
            checked={selected.includes(feature.name)}
            disabled={disabled}
            onToggle={() => onToggle(feature.name)}
          />
        ))}
      </div>
    </div>
  );
}

export default function TierSelector({
  features,
  selected,
  mode,
  disabled,
  onToggleFeature,
  onToggleTier,
}: {
  features: FeatureCatalogEntry[];
  selected: string[];
  mode: Mode;
  disabled: boolean;
  onToggleFeature: (name: string) => void;
  onToggleTier: (tier: number, selected: boolean) => void;
}) {
  const [expanded, setExpanded] = useState<number[]>([1]);

  return (
    <div className="flex flex-col">
      {TIERS.map((tier) => {
        const tierFeatures = features.filter((feature) => feature.tier === tier);
        if (tierFeatures.length === 0) return null;

        const selectedCount = tierFeatures.filter((feature) =>
          selected.includes(feature.name),
        ).length;
        const allSelected = selectedCount === tierFeatures.length;
        const isOpen = expanded.includes(tier);

        return (
          <div key={tier} className="border-border border-b last:border-b-0">
            <div className="flex items-center gap-2 py-2">
              <input
                type="checkbox"
                checked={allSelected}
                // Partially selected tiers read as indeterminate rather than unchecked.
                ref={(node) => {
                  if (node) node.indeterminate = selectedCount > 0 && !allSelected;
                }}
                disabled={disabled}
                onChange={() => onToggleTier(tier, !allSelected)}
                aria-label={`Select all Tier ${tier} features`}
                className="accent-accent h-4 w-4 shrink-0 cursor-pointer disabled:cursor-not-allowed"
              />
              <button
                type="button"
                onClick={() =>
                  setExpanded((current) =>
                    current.includes(tier)
                      ? current.filter((item) => item !== tier)
                      : [...current, tier],
                  )
                }
                aria-expanded={isOpen}
                className="flex flex-1 items-center gap-2 rounded py-1 text-left"
              >
                <ChevronRight
                  size={16}
                  strokeWidth={1.5}
                  aria-hidden
                  className={cn(
                    "text-ink-muted shrink-0 transition-transform",
                    isOpen && "rotate-90",
                  )}
                />
                {/* Tier labels stay text-only (§12.4). */}
                <span className="text-ink text-sm font-medium">Tier {tier}</span>
                <span className="text-ink-muted font-mono text-xs">
                  {selectedCount}/{tierFeatures.length}
                </span>
                {tier === SLOW_TIER ? (
                  <span className="text-ink-muted ml-auto flex items-center gap-1 text-xs">
                    <Clock size={14} strokeWidth={1.5} aria-hidden />
                    may take several seconds
                  </span>
                ) : null}
              </button>
            </div>

            {/* 150ms height transition on expand/collapse (§12.4). */}
            <div
              className={cn(
                "grid transition-[grid-template-rows] duration-150 ease-out",
                isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
              )}
            >
              <div className="overflow-hidden">
                <div className="flex flex-col gap-4 pt-1 pb-3 pl-8">
                  {mode === "single" ? (
                    <FeatureGroup
                      label={null}
                      features={tierFeatures}
                      selected={selected}
                      disabled={disabled}
                      onToggle={onToggleFeature}
                    />
                  ) : (
                    <>
                      <FeatureGroup
                        label="Per text"
                        features={tierFeatures.filter((f) => f.scope === "single")}
                        selected={selected}
                        disabled={disabled}
                        onToggle={onToggleFeature}
                      />
                      <FeatureGroup
                        label="Comparison"
                        features={tierFeatures.filter((f) => f.scope === "comparison")}
                        selected={selected}
                        disabled={disabled}
                        onToggle={onToggleFeature}
                      />
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
