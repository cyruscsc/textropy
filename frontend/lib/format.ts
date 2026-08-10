/**
 * Presentation helpers shared by the results and history panes.
 *
 * Nothing here may key off a specific feature name: the catalog is the single source of
 * truth for which features exist (spec §13.4), so labels are derived from the name
 * string and values from their runtime type.
 */

/** Tokens that should not be title-cased when humanising a feature name. */
const ACRONYMS: Record<string, string> = {
  ttr: "TTR",
  lcs: "LCS",
  tfidf: "TF-IDF",
  wmd: "WMD",
  pos: "POS",
  dep: "Dependency",
  lm: "LM",
  ngram: "N-gram",
  a: "A",
  b: "B",
};

/** `mean_adjacent_similarity` → `Mean adjacent similarity`; `ttr` → `TTR`. */
export function humanizeFeatureName(name: string): string {
  const words = name.split("_");
  return words
    .map((word, index) => {
      const acronym = ACRONYMS[word.toLowerCase()];
      if (acronym) return acronym;
      if (index === 0) return word.charAt(0).toUpperCase() + word.slice(1);
      return word;
    })
    .join(" ");
}

/**
 * Format a numeric metric for the mono column.
 *
 * Counts stay integers with thousands separators; ratios and scores are trimmed to at
 * most four decimals so a column of them stays scannable.
 */
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  if (Number.isInteger(value)) return value.toLocaleString("en-US");
  const rounded = Number(value.toFixed(4));
  return String(rounded);
}

export function formatMetricValue(value: number | string | boolean | null): string {
  if (value === null) return "—";
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return value;
}

/**
 * Sentiment-style polarity, derived from the *value* rather than the feature name so a
 * future polarity-bearing feature colours itself for free.
 */
export function polarityOf(value: string): "positive" | "negative" | null {
  const normalized = value.toLowerCase();
  if (normalized === "positive") return "positive";
  if (normalized === "negative") return "negative";
  return null;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** `2h ago`, `1d ago` — the history list format from the spec §9 sketch. */
export function relativeTime(timestamp: number, now: number = Date.now()): string {
  const elapsed = Math.max(0, now - timestamp);
  if (elapsed < MINUTE) return "just now";
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)}m ago`;
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)}h ago`;
  if (elapsed < 7 * DAY) return `${Math.floor(elapsed / DAY)}d ago`;
  return new Date(timestamp).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

/** Date-header grouping for the history list ("Today" / "Yesterday" / a date). */
export function dayLabel(timestamp: number, now: number = Date.now()): string {
  const startOfToday = new Date(now);
  startOfToday.setHours(0, 0, 0, 0);
  const start = startOfToday.getTime();
  if (timestamp >= start) return "Today";
  if (timestamp >= start - DAY) return "Yesterday";
  return new Date(timestamp).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
  });
}

export function snippet(text: string, maxLength = 40): string {
  const collapsed = text.replace(/\s+/g, " ").trim();
  if (collapsed.length <= maxLength) return collapsed;
  return `${collapsed.slice(0, maxLength).trimEnd()}…`;
}

export function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
}

/** Minimal class-name joiner — avoids pulling in clsx for a handful of call sites. */
export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}
