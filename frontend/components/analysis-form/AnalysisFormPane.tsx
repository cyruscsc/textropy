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
      {/*
        The pane's action sits in the header, level with `ResultsPane`'s "Copy results" —
        there is no footer to hold it, because the floating `PaneTabBar` covers the bottom
        of the pane below `lg`. A header slot is also the only placement that keeps the
        primary CTA reachable without scrolling past 35 feature checkboxes.

        All three panes share one header shape: a padded box wrapping a `min-h-9` title
        row. The minimum is what keeps the three `<h2>`s on one baseline — a row is
        otherwise only as tall as its contents, so a pane holding a button sits a few pixels
        lower than one holding none, and Results' title would shift the moment its "Copy
        results" appeared. It has to sit on the inner row rather than this padded box, whose
        40px of vertical padding would swallow it. Any value clearing the tallest action
        (34px) works, so drifting from it costs a pixel of alignment, not a layout.
      */}
      <div className="shrink-0 p-6 pb-4">
        <div className="flex min-h-9 items-center justify-between gap-4">
          <h2 className="text-ink text-lg font-semibold">Analysis</h2>
          <AnalyzeButton
            onClick={controller.runAnalysis}
            disabled={!validation.canAnalyze}
            analyzing={state === "analyzing"}
            title={validation.reason}
          />
        </div>
      </div>

      {/*
        `px-6 pt-6` split out of `p-6` on purpose: `cn` is a plain join with no
        `tailwind-merge`, so a `pb-*` layered over the shorthand would be relying on
        Tailwind's internal sort order to win. The reserved space is what lets the last row
        scroll clear of the floating menu; at `lg` there is no menu, so it reverts to 24px.
      */}
      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-6 pt-6 pb-[var(--pane-menu-space)] lg:pb-6">
        {viewingHistory ? (
          <p className="border-border text-ink-muted rounded border px-3 py-2 text-xs">
            Viewing saved analysis
          </p>
        ) : null}

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

        {/*
          Why the hint trails the text boxes rather than sitting beside the button it
          explains: it is pane-level ("2 of 35 features selected", "Both texts are
          required"), and compare mode renders *two* per-textbox counters, so folding it
          into one of them would attach a pane fact to an arbitrary half of the form. Here
          it reads as the last word on the whole form, directly under the final counter.
        */}
        <p className="text-ink-muted text-sm">
          {viewingHistory
            ? "Start a new analysis to edit these inputs."
            : (validation.reason ??
              `${effectiveSelection.length} features selected`)}
        </p>
      </div>
    </div>
  );
}
