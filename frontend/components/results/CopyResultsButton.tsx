"use client";

/** Copies the raw response JSON (spec §9 pane sketch). */

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import type { AnalyzeResponse } from "@/lib/types";

export default function CopyResultsButton({
  response,
  onError,
}: {
  response: AnalyzeResponse;
  onError: (message: string) => void;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(response, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access is origin- and permission-gated; say so rather than no-op.
      onError("Could not copy to the clipboard.");
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      className="border-border text-ink hover:border-accent hover:bg-accent-soft flex items-center gap-2 rounded border px-3 py-1.5 text-sm transition-colors"
    >
      {copied ? (
        <Check size={16} strokeWidth={1.5} aria-hidden />
      ) : (
        <Copy size={16} strokeWidth={1.5} aria-hidden />
      )}
      {copied ? "Copied" : "Copy results"}
    </button>
  );
}
