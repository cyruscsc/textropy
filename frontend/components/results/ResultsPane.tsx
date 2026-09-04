"use client";

/**
 * Right pane (spec §9, §10). Renders whichever of the five states the controller is in;
 * it owns no results of its own.
 */

import { useCallback, useMemo } from "react";

import ComparisonDiffView from "@/components/results/ComparisonDiffView";
import CopyResultsButton from "@/components/results/CopyResultsButton";
import ResultsEmptyState from "@/components/results/ResultsEmptyState";
import ResultsSkeleton from "@/components/results/ResultsSkeleton";
import TierResultSection from "@/components/results/TierResultSection";
import ErrorBanner from "@/components/shared/ErrorBanner";
import type { AnalysisController } from "@/lib/useAnalysisState";
import type { TieredFeatures } from "@/lib/types";

/** `{tier2: {...}, tier1: {...}}` → `[[1, {...}], [2, {...}]]`, tier order guaranteed. */
function orderedTiers(features: TieredFeatures): [number, TieredFeatures[string]][] {
  return Object.entries(features)
    .map(([key, block]) => [Number(key.replace("tier", "")), block] as const)
    .filter(([tier]) => Number.isFinite(tier))
    .sort((a, b) => a[0] - b[0])
    .map(([tier, block]) => [tier, block]);
}

function TieredBlocks({
  features,
  isApproximate,
}: {
  features: TieredFeatures;
  isApproximate: (name: string) => boolean;
}) {
  const tiers = orderedTiers(features);
  if (tiers.length === 0) {
    return <p className="text-ink-muted text-sm">No features computed.</p>;
  }
  return (
    <div className="flex flex-col">
      {tiers.map(([tier, block]) => (
        <TierResultSection
          key={tier}
          tier={tier}
          block={block}
          isApproximate={isApproximate}
        />
      ))}
    </div>
  );
}

export default function ResultsPane({
  controller,
}: {
  controller: AnalysisController;
}) {
  const { state, response, mode, texts, effectiveSelection, catalog } = controller;

  const tier3Selected = catalog.some(
    (entry) => entry.tier === 3 && effectiveSelection.includes(entry.name),
  );

  /**
   * specs_features.md §11.1: parser-derived values must reach the reader marked as
   * approximate. Which features those are comes from the catalog — the same source the
   * picker builds from — so the pane never carries its own list of feature names and a
   * new parser-derived backend feature is disclosed without a frontend change.
   */
  const approximateNames = useMemo(
    () => new Set(catalog.filter((entry) => entry.approximate).map((entry) => entry.name)),
    [catalog],
  );
  const isApproximate = useCallback(
    (name: string) => approximateNames.has(name),
    [approximateNames],
  );

  /**
   * A stored history entry renders against whatever catalog this session loaded, so if
   * the catalog fetch failed the markers silently vanish from values that still need
   * them. Saying so is the honest fallback: §11.1 forbids presenting these as
   * authoritative, not merely rendering them.
   */
  const disclosureUnresolved = catalog.length === 0;

  const body = () => {
    if (state === "analyzing") return <ResultsSkeleton slow={tier3Selected} />;

    if (state === "error") {
      return (
        <div className="p-6">
          <ErrorBanner
            message={controller.error ?? "The request failed."}
            onRetry={controller.runAnalysis}
          />
        </div>
      );
    }

    if (!response) return <ResultsEmptyState mode={mode} />;

    const isCompare = response.mode === "compare" && response.results.length === 2;

    return (
      <div className="flex flex-col gap-6 p-6">
        {disclosureUnresolved ? (
          <p className="border-border text-ink-muted rounded border border-dashed p-3 text-xs leading-relaxed">
            Feature metadata could not be loaded, so approximate metrics are not marked
            below. Values derived from the dependency parse are only as accurate as it is.
          </p>
        ) : null}

        {isCompare ? (
          <>
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              {response.results.map((result) => (
                <div key={result.text_index} className="flex flex-col gap-2">
                  <h3 className="text-ink text-sm font-semibold">
                    Text {result.text_index === 0 ? "A" : "B"}
                  </h3>
                  <TieredBlocks
                    features={result.features}
                    isApproximate={isApproximate}
                  />
                </div>
              ))}
            </div>

            {response.comparison ? (
              <div className="flex flex-col gap-2">
                <h3 className="text-ink text-sm font-semibold">Comparison</h3>
                <TieredBlocks
                  features={response.comparison}
                  isApproximate={isApproximate}
                />
              </div>
            ) : null}

            <ComparisonDiffView textA={texts[0]} textB={texts[1]} />
          </>
        ) : (
          response.results.map((result) => (
            <TieredBlocks
              key={result.text_index}
              features={result.features}
              isApproximate={isApproximate}
            />
          ))
        )}

        <dl className="text-ink-muted flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {Object.entries(response.meta.elapsed_ms).map(([phase, ms]) => (
            <div key={phase} className="flex gap-1">
              <dt>{phase}</dt>
              <dd className="font-mono">{ms.toFixed(0)}ms</dd>
            </div>
          ))}
          <div className="flex gap-1">
            <dt>tiers</dt>
            <dd className="font-mono">{response.meta.tiers_computed.join(", ") || "—"}</dd>
          </div>
        </dl>
      </div>
    );
  };

  return (
    <div className="bg-surface flex min-h-0 flex-1 flex-col">
      {/*
        `min-h-9` on the title row, per the pane-header contract in `AnalysisFormPane`. It
        matters most here: this is the one action that comes and goes, so without a floor
        the "Results" title would drop a few pixels the moment a response arrived.
      */}
      <div className="shrink-0 p-6 pb-4">
        <div className="flex min-h-9 items-center justify-between gap-4">
          <h2 className="text-ink text-lg font-semibold">Results</h2>
          {response && state !== "analyzing" ? (
            <CopyResultsButton response={response} onError={controller.showToast} />
          ) : null}
        </div>
      </div>
      {/*
        Reserves the floating `PaneTabBar`'s footprint below `lg` so the last metric row
        can be scrolled clear of it. This pane has no footer to displace — its action is
        already in the header, which is the shape the other two now follow.
      */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto pb-[var(--pane-menu-space)] lg:pb-0">
        {body()}
      </div>
    </div>
  );
}
