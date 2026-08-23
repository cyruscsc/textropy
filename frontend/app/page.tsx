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

import { PanelLeftOpen, Plus } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import AnalysisFormPane from "@/components/analysis-form/AnalysisFormPane";
import HistoryPane from "@/components/history/HistoryPane";
import ResultsPane from "@/components/results/ResultsPane";
import Toast from "@/components/shared/Toast";
import { cn } from "@/lib/format";
import {
  getHistoryVisibleServerSnapshot,
  getHistoryVisibleSnapshot,
  setHistoryVisible,
  subscribe,
} from "@/lib/preferences";
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

  /**
   * Layout state, so it sits here beside `tab` rather than in the controller — but
   * persisted, because a pane the reader collapsed should stay collapsed across reloads.
   * It only governs the `lg` arrangement: below that, History is a tab and hiding it
   * would strand the saved analyses.
   */
  const historyVisible = useSyncExternalStore(
    subscribe,
    getHistoryVisibleSnapshot,
    getHistoryVisibleServerSnapshot,
  );

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
        {/*
          The collapsed pane's stand-in: the History header compressed to its two icons, in
          the same order and with the same `gap-4` between them. "New analysis" earns its
          place because it is the one header action that still means something with the
          list hidden — everything else there is *about* the list. `lg`-only, like the
          toggle, so the tabbed layout keeps its full-width button instead.
        */}
        <div
          className={cn(
            historyVisible ? "hidden" : "hidden lg:flex",
            "bg-surface border-border w-10 shrink-0 flex-col items-center gap-4 border-r pt-6",
          )}
        >
          <button
            type="button"
            onClick={() => setHistoryVisible(true)}
            aria-expanded={false}
            aria-controls="pane-history"
            aria-label="Show history"
            title="Show history"
            className="text-ink-muted hover:text-ink hover:bg-accent-soft rounded p-1 transition-colors"
          >
            <PanelLeftOpen size={16} strokeWidth={1.5} aria-hidden />
          </button>

          {/*
            Same guard `HistoryPane` puts on its own copy of this action. `opacity-50` for
            the disabled state rather than the pane button's `disabled:text-ink-muted`,
            which would be invisible on an icon that is already muted.
          */}
          <button
            type="button"
            onClick={controller.newAnalysis}
            disabled={controller.state === "analyzing"}
            aria-label="New analysis"
            title="New analysis"
            className="text-ink-muted hover:text-ink hover:bg-accent-soft rounded p-1 transition-colors disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
          >
            <Plus size={16} strokeWidth={1.5} aria-hidden />
          </button>
        </div>

        {/*
          One complete class string per branch: `cn` is a plain join with no
          `tailwind-merge`, so a conditional width layered over a static one would not
          win. Collapsing removes the pane from the `lg` row but leaves it mounted and
          reachable by the History tab below `lg`.
        */}
        <section
          id="pane-history"
          aria-label="History"
          className={
            historyVisible
              ? cn(
                  paneVisibility("history"),
                  "border-border min-h-0 w-full flex-1 flex-col lg:w-[280px] lg:flex-none lg:border-r",
                )
              : cn(
                  tab === "history" ? "flex lg:hidden" : "hidden",
                  "border-border min-h-0 w-full flex-1 flex-col",
                )
          }
        >
          <HistoryPane
            controller={controller}
            onHide={() => setHistoryVisible(false)}
          />
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
