"use client";

/**
 * Centre pane (spec §9) and the only component that drives the state machine (§10, §11).
 *
 * Every other pane reads the controller; this one is where mode, text, selection and
 * "Analyze" mutate it.
 */

import AnalyzeButton from "@/components/analysis-form/AnalyzeButton";
import ModeToggle from "@/components/analysis-form/ModeToggle";
import TextInput from "@/components/analysis-form/TextInput";
import TierSelector from "@/components/analysis-form/TierSelector";
import ErrorBanner from "@/components/shared/ErrorBanner";
import type { AnalysisController } from "@/lib/useAnalysisState";

export default function AnalysisFormPane({
  controller,
}: {
  controller: AnalysisController;
}) {
  const {
    state,
    mode,
    texts,
    readOnly,
    validation,
    visibleFeatures,
    effectiveSelection,
    requiredTextCount,
  } = controller;

  const viewingHistory = state === "viewing_history";

  return (
    <div className="bg-surface flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-4 p-6 pb-0">
        <h2 className="text-ink text-lg font-semibold">Analysis</h2>
        {viewingHistory ? (
          <span className="border-border text-ink-muted rounded border px-2 py-1 text-xs">
            Viewing saved analysis
          </span>
        ) : null}
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-6">
        <ModeToggle
          mode={mode}
          onChange={controller.setMode}
          disabled={readOnly}
        />

        <section className="flex flex-col gap-2">
          <h3 className="text-ink-muted text-sm">Features</h3>
          {controller.catalogLoading ? (
            <p className="text-ink-muted text-sm">Loading feature catalog…</p>
          ) : controller.catalogError ? (
            <ErrorBanner
              title="Feature catalog unavailable"
              message={controller.catalogError}
              onRetry={controller.reloadCatalog}
            />
          ) : (
            <TierSelector
              features={visibleFeatures}
              selected={effectiveSelection}
              mode={mode}
              disabled={readOnly}
              onToggleFeature={controller.toggleFeature}
              onToggleTier={controller.setTierSelected}
            />
          )}
        </section>

        <section className="flex flex-col gap-4">
          <TextInput
            id="text-a"
            label={mode === "compare" ? "Text A" : "Text"}
            value={texts[0]}
            onChange={(value) => controller.setText(0, value)}
            onSubmit={controller.runAnalysis}
            disabled={state === "analyzing"}
            readOnly={viewingHistory}
          />
          {requiredTextCount === 2 ? (
            <TextInput
              id="text-b"
              label="Text B"
              value={texts[1]}
              onChange={(value) => controller.setText(1, value)}
              onSubmit={controller.runAnalysis}
              disabled={state === "analyzing"}
              readOnly={viewingHistory}
            />
          ) : null}
        </section>
      </div>

      {/*
        89px = 24px padding × 2 + a two-line `text-sm` hint (40px) + the 1px border, i.e.
        the height this bar already reaches when the validation message wraps — which it
        does between 1024px and ~1124px, where the space beside the button drops below the
        ~274px the longest message needs. Flooring it there keeps the hairline still
        instead of jumping 4px, and keeps it level with `HistoryPane`'s footer, which
        carries the same value. `min-h` rather than `h` so a longer future message wraps
        instead of clipping.
      */}
      <div className="border-border flex min-h-[89px] shrink-0 items-center justify-between gap-4 border-t p-6">
        {viewingHistory ? (
          <p className="text-ink-muted text-sm">
            Start a new analysis to edit these inputs.
          </p>
        ) : (
          <p className="text-ink-muted text-sm">
            {validation.reason ?? `${effectiveSelection.length} features selected`}
          </p>
        )}
        <AnalyzeButton
          onClick={controller.runAnalysis}
          disabled={!validation.canAnalyze}
          analyzing={state === "analyzing"}
          title={validation.reason}
        />
      </div>
    </div>
  );
}
