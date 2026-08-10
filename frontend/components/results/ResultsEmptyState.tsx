"use client";

/** Right pane before anything has been run or loaded (spec §10). */
export default function ResultsEmptyState({ mode }: { mode: "single" | "compare" }) {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="max-w-xs text-center">
        <p className="text-ink text-sm">No results yet</p>
        <p className="text-ink-muted mt-1 text-sm">
          {mode === "compare"
            ? "Enter both texts, pick the features to compute, then run the analysis."
            : "Enter a text, pick the features to compute, then run the analysis."}
        </p>
      </div>
    </div>
  );
}
