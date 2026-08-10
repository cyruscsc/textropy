"use client";

/**
 * Label (sans, muted) + value (mono) pairing — the design signature (spec §12.5).
 *
 * Values arrive as open JSON, so this renders by *shape*, never by feature name: a
 * scalar becomes one row, an object becomes a labelled group of nested rows (which is
 * what turns `{a_given_b, b_given_a}` and `{label, score}` into readable output without
 * either being special-cased).
 */

import { cn, formatMetricValue, humanizeFeatureName, polarityOf } from "@/lib/format";
import type { FeatureValue } from "@/lib/types";
import { isUnavailable, isValueGroup } from "@/lib/types";

function ValueText({ value }: { value: number | string | boolean | null }) {
  const polarity = typeof value === "string" ? polarityOf(value) : null;
  return (
    <span
      className={cn(
        "font-mono text-base font-medium",
        polarity === "positive"
          ? "text-positive"
          : polarity === "negative"
            ? "text-negative"
            : "text-ink",
      )}
    >
      {formatMetricValue(value)}
    </span>
  );
}

export default function MetricRow({
  name,
  value,
  depth = 0,
}: {
  name: string;
  value: FeatureValue;
  depth?: number;
}) {
  const label = humanizeFeatureName(name);

  // The optional-model degradation path (spec §13.4): one feature reports itself
  // unavailable, and the rest of the tier still renders.
  if (isUnavailable(value)) {
    return (
      <div
        className="flex items-baseline justify-between gap-4 py-1.5"
        style={{ paddingLeft: depth * 16 }}
      >
        <span className="text-ink-muted text-sm">{label}</span>
        <span
          className="text-ink-muted font-mono text-sm"
          title={value.reason ?? undefined}
        >
          Unavailable
        </span>
      </div>
    );
  }

  if (isValueGroup(value)) {
    return (
      <div style={{ paddingLeft: depth * 16 }}>
        <p className="text-ink-muted py-1.5 text-sm">{label}</p>
        <div className="border-border ml-2 border-l pl-3">
          {Object.entries(value).map(([childName, childValue]) => (
            <MetricRow key={childName} name={childName} value={childValue} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex items-baseline justify-between gap-4 py-1.5"
      style={{ paddingLeft: depth * 16 }}
    >
      <span className="text-ink-muted text-sm">{label}</span>
      <ValueText value={value} />
    </div>
  );
}
