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
import ThemeToggle from "@/components/shared/ThemeToggle";
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

      {/*
        Both panes' footers are pinned to the bottom of the viewport, so a height
        difference shows up as their top hairlines failing to line up. `min-h` keeps this
        one level with `AnalysisFormPane`'s footer — change the value in both or neither.
        `px-3` stays: with `ClearHistoryButton`'s own `px-3` it puts the label at a 24px
        inset, level with the pane's `p-6` header and the day-group labels. (The entry
        rows sit at 14px instead — `border-l-2 pl-3` — so they can carry a full-bleed
        hover band; that is deliberate and not what this aligns to.)
      */}
      <div className="border-border flex min-h-[89px] shrink-0 items-center justify-between gap-2 border-t px-3 py-6">
        {/*
          `ClearHistoryButton` is `w-full`, so it needs a flex parent of its own to keep
          its full-bleed hover band and left-aligned label beside a sibling.
        */}
        <div className="min-w-0 flex-1">
          <ClearHistoryButton
            onClear={controller.clearAllHistory}
            count={controller.history.length}
          />
        </div>
        {/*
          The app has no header at any breakpoint (§9), so this footer is its only
          persistent chrome — and the one strip that is present in both arrangements, since
          below `lg` History is a tab rather than a column.
        */}
        <ThemeToggle />
      </div>
    </div>
  );
}
