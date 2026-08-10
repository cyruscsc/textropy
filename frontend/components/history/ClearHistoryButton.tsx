"use client";

/**
 * Destructive, so it asks first — clearing is unrecoverable given history lives only in
 * this browser's `localStorage` (spec §14).
 */
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
      className="text-ink-muted hover:text-negative disabled:hover:text-ink-muted w-full rounded px-3 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50"
    >
      Clear all
    </button>
  );
}
