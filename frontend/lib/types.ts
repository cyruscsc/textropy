/**
 * Shared request/response types (spec §6, §11).
 *
 * These mirror `backend/app/schemas/{requests,responses}.py`. Tier payloads are open
 * maps on the backend — the key set is driven by the feature registry — so they are
 * `Record<string, FeatureValue>` here rather than a closed shape. Adding a backend
 * feature must not require editing this file.
 */

export type Mode = "single" | "compare";
export type Tier = 1 | 2 | 3;
export const TIERS: readonly Tier[] = [1, 2, 3] as const;

export type FeatureScope = "single" | "comparison";

/** One entry of `GET /api/v1/features`. */
export interface FeatureCatalogEntry {
  name: string;
  tier: number;
  scope: FeatureScope;
  /** `null` for single-text features; comparison features are true/false. */
  symmetric: boolean | null;
  requires: string[];
  /**
   * The feature reads dependency-parse structure, so its value is only as good as
   * `en_core_web_sm`'s parse (specs_features.md §10, Decision 5). The results pane is
   * obliged to mark these as approximate (§11.1); it reads the flag from here rather
   * than keeping its own list of names, so a parser-derived feature added to the backend
   * arrives already carrying its caveat.
   */
  approximate: boolean;
}

export interface FeatureCatalogResponse {
  features: FeatureCatalogEntry[];
}

export interface AnalyzeRequest {
  mode: Mode;
  texts: string[];
  tiers: number[];
  feature_names: string[] | null;
}

/**
 * The one per-feature failure shape the backend emits today: a feature whose required
 * signal was backed by an optional model that failed to load (spec §13.4). A feature
 * computer that *raises* still fails the whole request, which surfaces as an `error`
 * state instead.
 */
export interface UnavailableFeature {
  available: false;
  reason?: string;
}

export type FeatureValue =
  | number
  | string
  | boolean
  | null
  | UnavailableFeature
  | { [key: string]: FeatureValue };

/** e.g. `{ word_count: 142, ttr: 0.61 }` — the contents of one `tierN` block. */
export type TierBlock = Record<string, FeatureValue>;

/** Keyed `tier1` | `tier2` | `tier3`; tiers that were not requested are absent. */
export type TieredFeatures = Record<string, TierBlock>;

export interface TextResult {
  text_index: number;
  features: TieredFeatures;
}

export interface Meta {
  elapsed_ms: Record<string, number>;
  tiers_computed: number[];
}

export interface AnalyzeResponse {
  mode: Mode;
  results: TextResult[];
  /** Populated in `compare` mode only. */
  comparison: TieredFeatures | null;
  meta: Meta;
}

/** One stored analysis (spec §13.1) — the full request *and* response. */
export interface HistoryEntry {
  id: string;
  /** Epoch milliseconds. */
  timestamp: number;
  mode: Mode;
  tiers: number[];
  texts: string[];
  featureNames: string[];
  response: AnalyzeResponse;
}

export function isUnavailable(value: FeatureValue): value is UnavailableFeature {
  return (
    typeof value === "object" &&
    value !== null &&
    "available" in value &&
    value.available === false
  );
}

export function isValueGroup(
  value: FeatureValue,
): value is { [key: string]: FeatureValue } {
  return typeof value === "object" && value !== null && !isUnavailable(value);
}
