"use client";

/**
 * Right pane (spec §9, §10). Renders whichever of the five states the controller is in;
 * it owns no results of its own.
 */

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

function TieredBlocks({ features }: { features: TieredFeatures }) {
  const tiers = orderedTiers(features);
  if (tiers.length === 0) {
    return <p className="text-ink-muted text-sm">No features computed.</p>;
  }
  return (
    <div className="flex flex-col">
      {tiers.map(([tier, block]) => (
        <TierResultSection key={tier} tier={tier} block={block} />
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
        {isCompare ? (
          <>
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              {response.results.map((result) => (
                <div key={result.text_index} className="flex flex-col gap-2">
                  <h3 className="text-ink text-sm font-semibold">
                    Text {result.text_index === 0 ? "A" : "B"}
                  </h3>
                  <TieredBlocks features={result.features} />
                </div>
              ))}
            </div>

            {response.comparison ? (
              <div className="flex flex-col gap-2">
                <h3 className="text-ink text-sm font-semibold">Comparison</h3>
                <TieredBlocks features={response.comparison} />
              </div>
            ) : null}

            <ComparisonDiffView textA={texts[0]} textB={texts[1]} />
          </>
        ) : (
          response.results.map((result) => (
            <TieredBlocks key={result.text_index} features={result.features} />
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
      <div className="flex shrink-0 items-center justify-between gap-4 p-6 pb-0">
        <h2 className="text-ink text-lg font-semibold">Results</h2>
        {response && state !== "analyzing" ? (
          <CopyResultsButton response={response} onError={controller.showToast} />
        ) : null}
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">{body()}</div>
    </div>
  );
}
