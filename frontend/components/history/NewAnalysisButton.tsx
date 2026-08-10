"use client";

import { Plus } from "lucide-react";

/** Ghost secondary button (spec §12.5) that resets the form to `idle` (§10). */
export default function NewAnalysisButton({
  onClick,
  disabled,
}: {
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="border-border text-ink hover:border-accent hover:bg-accent-soft disabled:text-ink-muted flex w-full items-center gap-2 rounded border px-3 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:hover:bg-transparent"
    >
      <Plus size={16} strokeWidth={1.5} aria-hidden />
      New analysis
    </button>
  );
}
