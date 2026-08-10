/**
 * `localStorage` history (spec §13.1).
 *
 * One entry per analysis holding the full request *and* response, so re-viewing an entry
 * never re-hits the API. Capped at `MAX_ENTRIES`, oldest evicted first. Every read is
 * defensive: the store is user-writable and survives across deploys, so malformed or
 * stale JSON must degrade to "no history" rather than crash the pane.
 */

import type { AnalyzeRequest, AnalyzeResponse, HistoryEntry } from "./types";

const STORAGE_KEY = "textropy.history.v1";
export const MAX_ENTRIES = 50;

/** Raised when a write could not be completed even after evicting older entries. */
export class HistoryQuotaError extends Error {
  constructor() {
    super("Browser storage is full — the oldest analyses were dropped.");
    this.name = "HistoryQuotaError";
  }
}

function storage(): Storage | null {
  // Guard for SSR and for browsers where storage access throws (private mode, blocked
  // third-party cookies).
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

function isEntry(value: unknown): value is HistoryEntry {
  if (!value || typeof value !== "object") return false;
  const entry = value as Partial<HistoryEntry>;
  return (
    typeof entry.id === "string" &&
    typeof entry.timestamp === "number" &&
    (entry.mode === "single" || entry.mode === "compare") &&
    Array.isArray(entry.texts) &&
    Array.isArray(entry.tiers) &&
    Boolean(entry.response)
  );
}

/** Newest first. */
function readFromStorage(): HistoryEntry[] {
  const store = storage();
  if (!store) return EMPTY;
  try {
    const raw = store.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return EMPTY;
    return parsed.filter(isEntry).sort((a, b) => b.timestamp - a.timestamp);
  } catch {
    return EMPTY;
  }
}

/**
 * `localStorage` is external state, so it is exposed as a `useSyncExternalStore` source
 * rather than mirrored into React state by an effect. That keeps the server render and
 * the hydrating client render in agreement (both see `EMPTY`), and makes a write in one
 * browser tab show up in the others.
 *
 * The snapshot is cached because `useSyncExternalStore` requires a referentially stable
 * value between notifications — re-parsing JSON on every render would loop forever.
 */
const EMPTY: HistoryEntry[] = [];
const listeners = new Set<() => void>();
let cache: HistoryEntry[] | null = null;

function emit(): void {
  for (const listener of listeners) listener();
}

function onStorageEvent(event: StorageEvent): void {
  if (event.key !== null && event.key !== STORAGE_KEY) return;
  cache = null;
  emit();
}

export function subscribe(listener: () => void): () => void {
  if (listeners.size === 0 && typeof window !== "undefined") {
    window.addEventListener("storage", onStorageEvent);
  }
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", onStorageEvent);
    }
  };
}

export function getSnapshot(): HistoryEntry[] {
  if (cache === null) cache = readFromStorage();
  return cache;
}

/** No history exists server-side; the MVP stores it client-only (spec §7). */
export function getServerSnapshot(): HistoryEntry[] {
  return EMPTY;
}

/** Escape hatch for non-React callers; prefer the store above inside components. */
export function loadHistory(): HistoryEntry[] {
  return getSnapshot();
}

function isQuotaError(error: unknown): boolean {
  return (
    error instanceof DOMException &&
    (error.name === "QuotaExceededError" ||
      error.name === "NS_ERROR_DOM_QUOTA_REACHED")
  );
}

/**
 * Persist `entries`, shedding the oldest until the write fits.
 *
 * A single Tier 3 compare response is large enough that a full history can exceed the
 * ~5MB budget, so quota failure is an expected path, not an exceptional one.
 */
function persist(entries: HistoryEntry[]): HistoryEntry[] {
  const store = storage();
  if (!store) return entries;

  let candidates = entries.slice(0, MAX_ENTRIES);
  while (candidates.length > 0) {
    try {
      store.setItem(STORAGE_KEY, JSON.stringify(candidates));
      return candidates;
    } catch (error) {
      if (!isQuotaError(error)) throw error;
      candidates = candidates.slice(0, candidates.length - 1);
    }
  }

  // Even one entry did not fit — leave whatever was already stored untouched.
  throw new HistoryQuotaError();
}

export function createEntry(
  request: AnalyzeRequest,
  response: AnalyzeResponse,
): HistoryEntry {
  return {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    timestamp: Date.now(),
    mode: request.mode,
    tiers: response.meta.tiers_computed,
    texts: request.texts,
    featureNames: request.feature_names ?? [],
    response,
  };
}

/** Commit a new list to storage and publish it to subscribers. */
function commit(entries: HistoryEntry[]): HistoryEntry[] {
  try {
    cache = persist(entries);
    return cache;
  } finally {
    emit();
  }
}

/**
 * Prepend `entry` and return the stored list.
 *
 * Throws `HistoryQuotaError` when nothing could be written; callers surface that as a
 * toast (spec §13.1) rather than failing the analysis, which already succeeded.
 */
export function saveEntry(entry: HistoryEntry): HistoryEntry[] {
  const existing = getSnapshot().filter((item) => item.id !== entry.id);
  return commit([entry, ...existing]);
}

export function deleteEntry(id: string): HistoryEntry[] {
  return commit(getSnapshot().filter((entry) => entry.id !== id));
}

export function clearHistory(): HistoryEntry[] {
  const store = storage();
  if (store) {
    try {
      store.removeItem(STORAGE_KEY);
    } catch {
      // Nothing actionable — the list is cleared in memory either way.
    }
  }
  cache = EMPTY;
  emit();
  return EMPTY;
}
