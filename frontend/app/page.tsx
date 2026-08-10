"use client";

/**
 * Composes the three panes (spec §9).
 *
 * The state-machine value lives here rather than inside `AnalysisFormPane` for the
 * mechanical reason that React siblings cannot read each other's state: the form pane is
 * still the only component that *mutates* it, and History/Results only render from it,
 * which is the property §11 is protecting.
 *
 * The same three pane components serve both arrangements — three columns at ≥1024px, one
 * column behind tabs below it (§9). There is no separate mobile tree to keep in sync.
 */

import { useState } from "react";

import AnalysisFormPane from "@/components/analysis-form/AnalysisFormPane";
import HistoryPane from "@/components/history/HistoryPane";
import ResultsPane from "@/components/results/ResultsPane";
import Toast from "@/components/shared/Toast";
import { cn } from "@/lib/format";
import { useAnalysisState } from "@/lib/useAnalysisState";

type Tab = "history" | "analyze" | "results";

const TABS: { id: Tab; label: string }[] = [
  { id: "history", label: "History" },
  { id: "analyze", label: "Analyze" },
  { id: "results", label: "Results" },
];

export default function Page() {
  const controller = useAnalysisState();
  const [tab, setTab] = useState<Tab>("analyze");

  /** Hidden unless active below `lg`; always laid out at `lg` and above. */
  const paneVisibility = (id: Tab) => (tab === id ? "flex" : "hidden lg:flex");

  return (
    <div className="bg-bg flex h-full flex-col">
      <nav
        aria-label="Panes"
        className="border-border flex shrink-0 border-b lg:hidden"
        role="tablist"
      >
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            aria-controls={`pane-${id}`}
            onClick={() => setTab(id)}
            className={cn(
              "flex-1 px-4 py-3 text-sm transition-colors",
              tab === id
                ? "bg-accent-soft text-accent font-medium"
                : "text-ink-muted hover:text-ink",
            )}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <section
          id="pane-history"
          aria-label="History"
          className={cn(
            paneVisibility("history"),
            "border-border min-h-0 w-full flex-1 flex-col lg:w-[280px] lg:flex-none lg:border-r",
          )}
        >
          <HistoryPane controller={controller} />
        </section>

        <section
          id="pane-analyze"
          aria-label="Analysis configuration"
          className={cn(
            paneVisibility("analyze"),
            "border-border min-h-0 w-full flex-1 flex-col lg:w-2/5 lg:flex-none lg:border-r",
          )}
        >
          <AnalysisFormPane controller={controller} />
        </section>

        <section
          id="pane-results"
          aria-label="Results"
          className={cn(
            paneVisibility("results"),
            "min-h-0 w-full flex-1 flex-col",
          )}
        >
          <ResultsPane controller={controller} />
        </section>
      </div>

      <Toast message={controller.toast} onDismiss={controller.dismissToast} />
    </div>
  );
}
