"use client";

/**
 * Destructive, so it asks first — clearing is unrecoverable given history lives only in
 * this browser's `localStorage` (spec §14).
 *
 * Icon-only, because it lives in the pane header now rather than a footer strip: the
 * header is a row of actions beside a title, and a labelled button there would crowd out
 * the theme and collapse controls at the 280px pane width.
 */

import { Trash2 } from "lucide-react";
export default function ClearHistoryButton({
  onClear,
  count,
}: {
  onClear: () => void;
  count: number;
}) {
  const confirmThenClear = () => {
    if (count === 0) return;
    if (
      typeof window !== "undefined" &&
      !window.confirm(
        `Delete all ${count} saved ${count === 1 ? "analysis" : "analyses"}? This cannot be undone.`,
      )
    ) {
      return;
    }
    onClear();
  };

  return (
    <button
      type="button"
      onClick={confirmThenClear}
      disabled={count === 0}
      aria-label="Clear all"
      title="Clear all"
      className="text-ink-muted hover:text-negative disabled:hover:text-ink-muted rounded p-1 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
    >
      <Trash2 size={16} strokeWidth={1.5} aria-hidden />
    </button>
  );
}
