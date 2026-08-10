"use client";

/** Request-level failure with the input preserved and a retry (spec §13.4). */

import { AlertCircle } from "lucide-react";

export default function ErrorBanner({
  title = "Analysis failed",
  message,
  onRetry,
  retryLabel = "Retry",
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div
      role="alert"
      className="border-border bg-surface flex flex-col gap-3 rounded border p-4"
    >
      <div className="flex items-start gap-3">
        <AlertCircle
          size={18}
          strokeWidth={1.5}
          className="text-negative mt-0.5 shrink-0"
          aria-hidden
        />
        <div className="flex flex-col gap-1">
          <p className="text-ink text-sm font-medium">{title}</p>
          <p className="text-ink-muted text-sm">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="border-border text-ink hover:bg-accent-soft hover:border-accent self-start rounded border px-3 py-1.5 text-sm transition-colors"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
