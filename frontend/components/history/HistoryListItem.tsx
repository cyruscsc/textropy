"use client";

/** One stored analysis: snippet, mode badge, tier badges, relative time (spec §13.1). */

import { Copy, Trash2 } from "lucide-react";

import { cn, relativeTime, snippet } from "@/lib/format";
import type { HistoryEntry } from "@/lib/types";

function TierBadge({ tier }: { tier: number }) {
  return (
    <span className="border-border text-ink-muted rounded border px-1 font-mono text-xs">
      T{tier}
    </span>
  );
}

export default function HistoryListItem({
  entry,
  selected,
  onView,
  onDuplicate,
  onDelete,
}: {
  entry: HistoryEntry;
  selected: boolean;
  onView: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const [textA, textB] = entry.texts;

  return (
    // The row actions cannot nest inside the click-to-view button, so the button fills
    // the row and the actions sit above it — hover/focus-revealed (§13.1).
    <li className="group relative">
      <button
        type="button"
        onClick={onView}
        aria-current={selected ? "true" : undefined}
        className={cn(
          "w-full border-l-2 py-2 pr-16 pl-3 text-left transition-colors",
          selected
            ? "border-l-accent bg-accent-soft"
            : "hover:border-l-accent hover:bg-accent-soft border-l-transparent",
        )}
      >
        <p className="text-ink truncate text-sm">{snippet(textA)}</p>
        {entry.mode === "compare" && textB ? (
          <p className="text-ink-muted truncate text-sm">vs {snippet(textB)}</p>
        ) : null}
        <p className="text-ink-muted mt-1 flex items-center gap-1.5 text-xs">
          <span>{relativeTime(entry.timestamp)}</span>
          <span aria-hidden>·</span>
          <span>{entry.mode}</span>
          <span className="flex gap-1">
            {entry.tiers.map((tier) => (
              <TierBadge key={tier} tier={tier} />
            ))}
          </span>
        </p>
      </button>

      <div className="absolute top-2 right-2 flex gap-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        <button
          type="button"
          onClick={onDuplicate}
          title="Duplicate as new"
          aria-label={`Duplicate "${snippet(textA, 20)}" as a new analysis`}
          className="text-ink-muted hover:text-accent rounded p-1 transition-colors"
        >
          <Copy size={16} strokeWidth={1.5} aria-hidden />
        </button>
        <button
          type="button"
          onClick={onDelete}
          title="Delete"
          aria-label={`Delete "${snippet(textA, 20)}"`}
          className="text-ink-muted hover:text-negative rounded p-1 transition-colors"
        >
          <Trash2 size={16} strokeWidth={1.5} aria-hidden />
        </button>
      </div>
    </li>
  );
}
