"use client";

/**
 * The `≈` chip marking a parser-derived value (specs_features.md §11.1).
 *
 * Shared by the two places that must agree on it: `MetricRow` puts one beside each
 * affected metric, and `TierResultSection`'s footnote opens with the same chip as the
 * legend explaining it. Rendering the legend from this component rather than a bare glyph
 * is what keeps the two from drifting apart when the badge is restyled.
 *
 * Styled as `TierBadge` in the history list is — bordered, muted, mono — so it reads as
 * the app's existing badge language rather than a new one.
 *
 * Purely visual: it is `aria-hidden`, and each caller supplies its own accessible text.
 * In the footnote that text is the sentence beside it; in a metric row it is an `sr-only`
 * word, since there is nothing else there to carry the caveat.
 */

import { cn } from "@/lib/format";

export default function ApproximateBadge({
  className,
  title,
}: {
  className?: string;
  /** Omitted in the footnote, where the sentence beside the chip already says this. */
  title?: string;
}) {
  return (
    <span
      aria-hidden
      title={title}
      className={cn(
        "border-border text-ink-muted inline-flex shrink-0 items-center rounded border px-1 align-middle font-mono text-[0.625rem] leading-4",
        className,
      )}
    >
      ≈
    </span>
  );
}
