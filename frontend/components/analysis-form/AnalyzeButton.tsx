"use client";

/** Primary action: solid `--accent`, disabled treatment per spec §12.5. */

import { Loader2, Play } from "lucide-react";

import { cn } from "@/lib/format";

export default function AnalyzeButton({
  onClick,
  disabled,
  analyzing,
  title,
}: {
  onClick: () => void;
  disabled: boolean;
  analyzing: boolean;
  /** The validation reason, so a disabled button explains itself on hover. */
  title: string | null;
}) {
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        title={title ?? undefined}
        className={cn(
          // `px-3 py-1.5` matches `CopyResultsButton`, so the Analysis and Results
          // header actions share a baseline when the two panes sit side by side. It stays
          // filled rather than a ghost button: this is the primary CTA, not a header
          // affordance.
          "flex items-center gap-2 rounded px-3 py-1.5 text-sm font-medium transition-colors",
          disabled
            ? "bg-border text-ink-muted cursor-not-allowed"
            : "bg-accent text-on-accent hover:opacity-90",
        )}
      >
        {analyzing ? (
          <Loader2
            size={16}
            strokeWidth={1.5}
            className="animate-spin"
            aria-hidden
          />
        ) : (
          <Play size={16} strokeWidth={1.5} aria-hidden />
        )}
        {analyzing ? "Analyzing…" : "Analyze"}
      </button>
      <span className="text-ink-muted hidden font-mono text-xs sm:inline">⌘↵</span>
    </div>
  );
}
