"use client";

/** Primary action: solid `--accent`, disabled treatment per spec §12.5. */

import { Loader2 } from "lucide-react";

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
          "flex items-center gap-2 rounded px-4 py-2 text-sm font-medium transition-colors",
          disabled
            ? "bg-border text-ink-muted cursor-not-allowed"
            : "bg-accent text-on-accent hover:opacity-90",
        )}
      >
        {analyzing ? (
          <Loader2 size={16} strokeWidth={1.5} className="animate-spin" aria-hidden />
        ) : null}
        {analyzing ? "Analyzing…" : "Analyze"}
      </button>
      <span className="text-ink-muted hidden font-mono text-xs sm:inline">⌘↵</span>
    </div>
  );
}
