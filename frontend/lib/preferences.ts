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
}

const DEFAULTS: Preferences = { historyVisible: true };

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

export function setHistoryVisible(visible: boolean): void {
  const next: Preferences = { ...snapshot(), historyVisible: visible };
  cache = next;
  const store = storage();
  // A preference that cannot be persisted is not worth surfacing to the user — the
  // toggle still works for this session, it just will not survive a reload.
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* quota or blocked storage; the in-memory cache above still holds the change */
  }
  emit();
}
