"use client";

/**
 * Left pane (spec §9). Renders entirely from the controller — it holds no copy of the
 * history list, the selected id, or the current results.
 */

import { PanelLeftClose } from "lucide-react";
import { Fragment } from "react";

import ClearHistoryButton from "@/components/history/ClearHistoryButton";
import HistoryListItem from "@/components/history/HistoryListItem";
import NewAnalysisButton from "@/components/history/NewAnalysisButton";
import { dayLabel } from "@/lib/format";
import type { AnalysisController } from "@/lib/useAnalysisState";
import type { HistoryEntry } from "@/lib/types";

/** History arrives newest-first, so day groups fall out in order. */
function groupByDay(entries: HistoryEntry[]): [string, HistoryEntry[]][] {
  const groups: [string, HistoryEntry[]][] = [];
  for (const entry of entries) {
    const label = dayLabel(entry.timestamp);
    const last = groups[groups.length - 1];
    if (last && last[0] === label) last[1].push(entry);
    else groups.push([label, [entry]]);
  }
  return groups;
}

export default function HistoryPane({
  controller,
  onHide,
}: {
  controller: AnalysisController;
  /**
   * Collapses the pane to the rail in `page.tsx`. Layout state lives there, not here —
   * this component only asks for the change.
   */
  onHide: () => void;
}) {
  const groups = groupByDay(controller.history);

  return (
    <div className="bg-surface flex min-h-0 flex-1 flex-col">
      <div className="flex flex-col gap-4 p-6 pb-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-ink text-lg font-semibold">History</h2>
          {/*
            Hidden below `lg`, where the tab bar governs which pane is showing and
            collapsing this one would strand the saved analyses.
          */}
          <button
            type="button"
            onClick={onHide}
            aria-expanded
            aria-label="Hide history"
            title="Hide history"
            className="text-ink-muted hover:text-ink hover:bg-accent-soft hidden rounded p-1 transition-colors lg:inline-flex"
          >
            <PanelLeftClose size={16} strokeWidth={1.5} aria-hidden />
          </button>
        </div>
        <NewAnalysisButton
          onClick={controller.newAnalysis}
          disabled={controller.state === "analyzing"}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pb-4">
        {controller.history.length === 0 ? (
          <p className="text-ink-muted px-6 text-sm">
            Analyses you run are saved here, in this browser only.
          </p>
        ) : (
          <ul className="flex flex-col">
            {groups.map(([label, entries]) => (
              <Fragment key={label}>
                <li className="text-ink-muted px-6 pt-4 pb-1 text-xs tracking-wide uppercase">
                  {label}
                </li>
                {entries.map((entry) => (
                  <HistoryListItem
                    key={entry.id}
                    entry={entry}
                    selected={controller.selectedHistoryId === entry.id}
                    onView={() => controller.viewHistoryEntry(entry.id)}
                    onDuplicate={() => controller.duplicateHistoryEntry(entry.id)}
                    onDelete={() => controller.removeHistoryEntry(entry.id)}
                  />
                ))}
              </Fragment>
            ))}
          </ul>
        )}
      </div>

      <div className="border-border shrink-0 border-t p-3">
        <ClearHistoryButton
          onClear={controller.clearAllHistory}
          count={controller.history.length}
        />
      </div>
    </div>
  );
}
