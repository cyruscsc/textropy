/**
 * `localStorage` UI preferences.
 *
 * A second external store alongside `lib/history.ts`, following the same contract for the
 * same reason: `localStorage` genuinely is external state, so it is exposed to React via
 * `useSyncExternalStore` rather than mirrored into component state by an effect. That
 * keeps the server render and the hydrating client render in agreement, and makes a
 * change in one browser tab reach the others.
 *
 * These are *layout* preferences, not analysis state — they deliberately stay out of
 * `AnalysisController` (see ARCHITECTURE.md §13). Reads are defensive: the store is
 * user-writable and survives across deploys, so malformed JSON degrades to the defaults
 * rather than crashing the layout.
 */

const STORAGE_KEY = "textropy.preferences.v1";

interface Preferences {
  /** Whether the History pane is expanded at `lg` and above. */
  historyVisible: boolean;
  /**
   * Width of the Analysis pane as a percentage of the pane row, which is what the divider
   * between it and Results actually moves. The default matches the `w-2/5` the pane used
   * before it became adjustable, so a first load looks unchanged.
   */
  analysisPanePercent: number;
}

const DEFAULTS: Preferences = { historyVisible: true, analysisPanePercent: 40 };

/**
 * Bounds for the stored percentage. The pixel minimums that stop either pane collapsing
 * are CSS (`min-width` / `max-width` in `page.tsx`); this band only keeps a hand-edited or
 * stale value from being wildly out of range before CSS ever sees it.
 */
export const MIN_ANALYSIS_PERCENT = 15;
export const MAX_ANALYSIS_PERCENT = 75;
export const DEFAULT_ANALYSIS_PERCENT = DEFAULTS.analysisPanePercent;

export function clampAnalysisPercent(value: number): number {
  return Math.min(MAX_ANALYSIS_PERCENT, Math.max(MIN_ANALYSIS_PERCENT, value));
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

function readFromStorage(): Preferences {
  const store = storage();
  if (!store) return DEFAULTS;
  try {
    const raw = store.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return DEFAULTS;
    const value = parsed as Partial<Preferences>;
    return {
      historyVisible:
        typeof value.historyVisible === "boolean"
          ? value.historyVisible
          : DEFAULTS.historyVisible,
      analysisPanePercent:
        typeof value.analysisPanePercent === "number" &&
        Number.isFinite(value.analysisPanePercent)
          ? clampAnalysisPercent(value.analysisPanePercent)
          : DEFAULTS.analysisPanePercent,
    };
  } catch {
    return DEFAULTS;
  }
}

/**
 * Cached so a `JSON.parse` does not run on every render. The referential stability
 * `useSyncExternalStore` demands is satisfied by the snapshots below returning primitives,
 * but the cache is still what keeps repeated reads cheap.
 */
const listeners = new Set<() => void>();
let cache: Preferences | null = null;

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

function snapshot(): Preferences {
  if (cache === null) cache = readFromStorage();
  return cache;
}

export function getHistoryVisibleSnapshot(): boolean {
  return snapshot().historyVisible;
}

/**
 * No preference is readable server-side, so the pane renders expanded during SSR and
 * hydration and collapses on the first post-hydration render — the same one-frame
 * behaviour the history list has starting from an empty array.
 */
export function getHistoryVisibleServerSnapshot(): boolean {
  return DEFAULTS.historyVisible;
}

function write(next: Preferences): void {
  const store = storage();
  // A preference that cannot be persisted is not worth surfacing to the user — the
  // setting still works for this session, it just will not survive a reload.
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* quota or blocked storage; the in-memory cache still holds the change */
  }
}

export function setHistoryVisible(visible: boolean): void {
  const next: Preferences = { ...snapshot(), historyVisible: visible };
  cache = next;
  write(next);
  emit();
}

export function getAnalysisPanePercentSnapshot(): number {
  return snapshot().analysisPanePercent;
}

/** See `getHistoryVisibleServerSnapshot` — the pane renders at its default width first. */
export function getAnalysisPanePercentServerSnapshot(): number {
  return DEFAULTS.analysisPanePercent;
}

let writeTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Unlike `setHistoryVisible`, the `localStorage` write is debounced. A keyboard nudge on
 * the divider can repeat at key-repeat rate, and `setItem` is synchronous main-thread
 * I/O — the in-memory cache and the `emit` still happen immediately, so the UI is never
 * behind, only the disk is.
 */
export function setAnalysisPanePercent(percent: number): void {
  const next: Preferences = {
    ...snapshot(),
    analysisPanePercent: clampAnalysisPercent(percent),
  };
  cache = next;
  if (writeTimer !== null) clearTimeout(writeTimer);
  writeTimer = setTimeout(() => {
    writeTimer = null;
    write(next);
  }, 150);
  emit();
}
