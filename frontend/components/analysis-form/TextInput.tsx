"use client";

/**
 * Shared editable / view-only textbox with the live counter (spec §13.2).
 *
 * The same component serves `viewing_history` (read-only, showing the stored text) so
 * there is no second, drifting rendering of a text pane.
 */

import { cn, countWords } from "@/lib/format";
import { MAX_TEXT_CHARS, SOFT_WARNING_RATIO } from "@/lib/useAnalysisState";

export default function TextInput({
  id,
  label,
  value,
  onChange,
  onSubmit,
  disabled,
  readOnly,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Cmd/Ctrl+Enter submits when the form is valid (§13.3). */
  onSubmit: () => void;
  disabled?: boolean;
  readOnly?: boolean;
}) {
  const chars = value.length;
  const overCap = chars > MAX_TEXT_CHARS;
  const nearCap = !overCap && chars >= MAX_TEXT_CHARS * SOFT_WARNING_RATIO;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-ink-muted text-sm">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        disabled={disabled}
        readOnly={readOnly}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault();
            onSubmit();
          }
        }}
        rows={6}
        spellCheck={false}
        aria-describedby={`${id}-counter`}
        placeholder={readOnly ? undefined : "Paste or type text…"}
        className={cn(
          "bg-surface min-h-32 rounded border p-3 text-base transition-colors",
          "placeholder:text-ink-muted",
          overCap ? "border-negative" : "border-border",
          disabled && "text-ink-muted cursor-not-allowed",
          readOnly && "bg-bg",
        )}
      />
      <p
        id={`${id}-counter`}
        className={cn(
          "flex gap-3 font-mono text-xs",
          overCap ? "text-negative" : nearCap ? "text-ink" : "text-ink-muted",
        )}
      >
        <span>{chars.toLocaleString("en-US")} chars</span>
        <span>{countWords(value).toLocaleString("en-US")} words</span>
        {overCap ? (
          <span className="font-sans">
            Over the {MAX_TEXT_CHARS.toLocaleString("en-US")} character limit
          </span>
        ) : nearCap ? (
          <span className="font-sans">
            Approaching the {MAX_TEXT_CHARS.toLocaleString("en-US")} character limit
          </span>
        ) : null}
      </p>
    </div>
  );
}
