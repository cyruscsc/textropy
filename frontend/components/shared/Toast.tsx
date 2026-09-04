"use client";

/** Transient notification — quota failures, copy confirmations (spec §13.1). */

import { X } from "lucide-react";
import { useEffect } from "react";

const AUTO_DISMISS_MS = 5000;

export default function Toast({
  message,
  onDismiss,
}: {
  message: string | null;
  onDismiss: () => void;
}) {
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  if (!message) return null;

  return (
    /*
      `shadow-md` is reserved for toasts and modals (§12.4).

      Below `lg` the bottom of the screen belongs to `PaneTabBar`, so the toast has to
      clear it — `bottom-28` is that menu's height plus its gutter, rounded up. At `lg`
      the menu is gone and the toast returns to §12's 24px offset.
    */
    <div
      role="status"
      aria-live="polite"
      className="border-border bg-surface fixed bottom-28 left-1/2 z-50 flex max-w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 items-start gap-3 rounded border px-4 py-3 shadow-md lg:bottom-6"
    >
      <p className="text-ink text-sm">{message}</p>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="text-ink-muted hover:text-ink shrink-0 transition-colors"
      >
        <X size={16} strokeWidth={1.5} />
      </button>
    </div>
  );
}
