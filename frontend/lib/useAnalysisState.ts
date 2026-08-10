"use client";

/**
 * The whole state layer (spec §10, §11) — one explicit state value, no state library.
 *
 * `HistoryPane` and `ResultsPane` render from the value this hook returns rather than
 * keeping copies of the mode, the texts or the current results, which is what stops the
 * three panes drifting out of sync.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { ApiError, analyze, fetchFeatureCatalog } from "./api";
import {
  HistoryQuotaError,
  clearHistory,
  createEntry,
  deleteEntry,
  getServerSnapshot,
  getSnapshot,
  saveEntry,
  subscribe,
} from "./history";
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  FeatureCatalogEntry,
  HistoryEntry,
  Mode,
} from "./types";

/**
 * Client-side hard cap (spec §13.4). The server-side equivalent
 * (`TEXTROPY_MAX_TEXT_CHARS`) defaults to 0 / disabled, so today this is the only cap in
 * the system — Tier 3 runs synchronously and a very long text will hold the request open.
 */
export const MAX_TEXT_CHARS = 20_000;

/** Fraction of the cap at which the counter starts warning. */
export const SOFT_WARNING_RATIO = 0.9;

export type UiState = "idle" | "editing" | "analyzing" | "error" | "viewing_history";

export interface Validation {
  canAnalyze: boolean;
  /** Why the Analyze button is disabled, surfaced as its `title`. */
  reason: string | null;
}

export interface AnalysisController {
  state: UiState;
  mode: Mode;
  /** Always length 2; index 1 is ignored in `single` mode but preserved across toggles. */
  texts: [string, string];
  selectedFeatures: string[];
  catalog: FeatureCatalogEntry[];
  catalogLoading: boolean;
  catalogError: string | null;
  response: AnalyzeResponse | null;
  error: string | null;
  history: HistoryEntry[];
  selectedHistoryId: string | null;
  toast: string | null;

  /** Features from the catalog that apply to the current mode. */
  visibleFeatures: FeatureCatalogEntry[];
  /** Selection intersected with `visibleFeatures` — what a request would actually send. */
  effectiveSelection: string[];
  /** 1 in `single` mode, 2 in `compare`. */
  requiredTextCount: number;
  readOnly: boolean;
  validation: Validation;

  setMode: (mode: Mode) => void;
  setText: (index: number, value: string) => void;
  toggleFeature: (name: string) => void;
  setTierSelected: (tier: number, selected: boolean) => void;
  runAnalysis: () => void;
  newAnalysis: () => void;
  viewHistoryEntry: (id: string) => void;
  duplicateHistoryEntry: (id: string) => void;
  removeHistoryEntry: (id: string) => void;
  clearAllHistory: () => void;
  showToast: (message: string) => void;
  dismissToast: () => void;
  reloadCatalog: () => void;
}

function tiersOf(names: string[], catalog: FeatureCatalogEntry[]): number[] {
  const byName = new Map(catalog.map((entry) => [entry.name, entry]));
  const tiers = new Set<number>();
  for (const name of names) {
    const entry = byName.get(name);
    if (entry) tiers.add(entry.tier);
  }
  return [...tiers].sort((a, b) => a - b);
}

export function useAnalysisState(): AnalysisController {
  const [state, setState] = useState<UiState>("idle");
  const [mode, setModeValue] = useState<Mode>("single");
  const [texts, setTexts] = useState<[string, string]>(["", ""]);
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<FeatureCatalogEntry[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogAttempt, setCatalogAttempt] = useState(0);
  const [response, setResponse] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Subscribed rather than copied: localStorage is the store, so a write in this tab or
  // another one re-renders the history pane without any effect-based mirroring.
  const history = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  /** Guards against a stale in-flight response overwriting a newer one. */
  const requestId = useRef(0);

  useEffect(() => {
    const controller = new AbortController();

    fetchFeatureCatalog(controller.signal)
      .then((entries) => {
        setCatalog(entries);
        // Tier 1 is cheap and needs no model beyond spaCy — a sensible default so the
        // form is valid as soon as text is entered.
        setSelectedFeatures((current) =>
          current.length > 0
            ? current
            : entries.filter((entry) => entry.tier === 1).map((entry) => entry.name),
        );
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setCatalogError(
          cause instanceof ApiError ? cause.message : "Could not load the feature catalog.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setCatalogLoading(false);
      });

    return () => controller.abort();
  }, [catalogAttempt]);

  const visibleFeatures = useMemo(
    () =>
      catalog.filter((entry) =>
        mode === "single" ? entry.scope === "single" : true,
      ),
    [catalog, mode],
  );

  const effectiveSelection = useMemo(() => {
    const visible = new Set(visibleFeatures.map((entry) => entry.name));
    return selectedFeatures.filter((name) => visible.has(name));
  }, [selectedFeatures, visibleFeatures]);

  const requiredTextCount = mode === "single" ? 1 : 2;
  const readOnly = state === "analyzing" || state === "viewing_history";

  const validation = useMemo<Validation>(() => {
    if (readOnly) {
      return {
        canAnalyze: false,
        reason:
          state === "analyzing"
            ? "Analysis in progress."
            : "Viewing a saved analysis — start a new one to edit.",
      };
    }
    if (effectiveSelection.length === 0) {
      return { canAnalyze: false, reason: "Select at least one feature." };
    }
    const required = texts.slice(0, requiredTextCount);
    if (required.some((text) => text.trim().length === 0)) {
      return {
        canAnalyze: false,
        reason:
          requiredTextCount === 1
            ? "Enter some text to analyze."
            : "Both texts are required in compare mode.",
      };
    }
    if (required.some((text) => text.length > MAX_TEXT_CHARS)) {
      return {
        canAnalyze: false,
        reason: `Texts must be under ${MAX_TEXT_CHARS.toLocaleString("en-US")} characters.`,
      };
    }
    return { canAnalyze: true, reason: null };
  }, [effectiveSelection, readOnly, requiredTextCount, state, texts]);

  const showToast = useCallback((message: string) => setToast(message), []);
  const dismissToast = useCallback(() => setToast(null), []);

  const textB = texts[1];
  const setMode = useCallback(
    (next: Mode) => {
      // Confirm before a compare → single switch would strand Text B (spec §13.2).
      // `window.confirm` is a placeholder for the styled modal the design system implies
      // (§12.4 reserves `shadow-md` for modals) — §11 defines no modal component yet.
      if (
        mode === "compare" &&
        next === "single" &&
        textB.trim().length > 0 &&
        typeof window !== "undefined" &&
        !window.confirm("Switching to single-text mode discards Text B. Continue?")
      ) {
        return;
      }
      setModeValue(next);
      setState((current) => (current === "idle" ? "idle" : "editing"));
    },
    [mode, textB],
  );

  const setText = useCallback((index: number, value: string) => {
    setTexts((current) => {
      const next: [string, string] = [current[0], current[1]];
      next[index] = value;
      return next;
    });
    setState((current) => (current === "analyzing" ? current : "editing"));
  }, []);

  const toggleFeature = useCallback((name: string) => {
    setSelectedFeatures((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name],
    );
    setState((current) => (current === "analyzing" ? current : "editing"));
  }, []);

  const setTierSelected = useCallback(
    (tier: number, selected: boolean) => {
      const names = visibleFeatures
        .filter((entry) => entry.tier === tier)
        .map((entry) => entry.name);
      setSelectedFeatures((current) => {
        if (selected) return [...new Set([...current, ...names])];
        const dropped = new Set(names);
        return current.filter((name) => !dropped.has(name));
      });
      setState((current) => (current === "analyzing" ? current : "editing"));
    },
    [visibleFeatures],
  );

  const runAnalysis = useCallback(() => {
    if (!validation.canAnalyze) return;

    const payload: AnalyzeRequest = {
      mode,
      texts: texts.slice(0, requiredTextCount),
      tiers: tiersOf(effectiveSelection, catalog),
      // Always an explicit override: the picker's selection *is* the request, so a
      // half-selected tier never silently expands to the whole tier.
      feature_names: effectiveSelection,
    };

    const id = ++requestId.current;
    setState("analyzing");
    setError(null);
    setResponse(null);
    setSelectedHistoryId(null);

    analyze(payload)
      .then((result) => {
        if (id !== requestId.current) return;
        setResponse(result);
        setState("editing");

        // The analysis succeeded; a storage failure must not present as one.
        try {
          const entry = createEntry(payload, result);
          saveEntry(entry);
          setSelectedHistoryId(entry.id);
        } catch (cause) {
          showToast(
            cause instanceof HistoryQuotaError
              ? cause.message
              : "Could not save this analysis to history.",
          );
        }
      })
      .catch((cause: unknown) => {
        if (id !== requestId.current) return;
        setError(
          cause instanceof ApiError
            ? cause.message
            : "Something went wrong running the analysis.",
        );
        setState("error");
      });
  }, [
    catalog,
    effectiveSelection,
    mode,
    requiredTextCount,
    showToast,
    texts,
    validation.canAnalyze,
  ]);

  const newAnalysis = useCallback(() => {
    requestId.current += 1;
    setState("idle");
    setTexts(["", ""]);
    setResponse(null);
    setError(null);
    setSelectedHistoryId(null);
  }, []);

  const viewHistoryEntry = useCallback(
    (id: string) => {
      const entry = history.find((item) => item.id === id);
      if (!entry) return;
      requestId.current += 1;
      setState("viewing_history");
      setModeValue(entry.mode);
      setTexts([entry.texts[0] ?? "", entry.texts[1] ?? ""]);
      setSelectedFeatures(entry.featureNames);
      setResponse(entry.response);
      setError(null);
      setSelectedHistoryId(entry.id);
    },
    [history],
  );

  const duplicateHistoryEntry = useCallback(
    (id: string) => {
      const entry = history.find((item) => item.id === id);
      if (!entry) return;
      requestId.current += 1;
      // "Duplicate as new": a fresh editable state pre-filled from the entry, never a
      // mutation of the stored one (spec §10, §13.1).
      setState("editing");
      setModeValue(entry.mode);
      setTexts([entry.texts[0] ?? "", entry.texts[1] ?? ""]);
      setSelectedFeatures(entry.featureNames);
      setResponse(null);
      setError(null);
      setSelectedHistoryId(null);
    },
    [history],
  );

  const removeHistoryEntry = useCallback(
    (id: string) => {
      try {
        deleteEntry(id);
      } catch {
        showToast("Could not update history.");
      }
      if (selectedHistoryId === id) {
        setSelectedHistoryId(null);
        if (state === "viewing_history") {
          setState("idle");
          setTexts(["", ""]);
          setResponse(null);
        }
      }
    },
    [selectedHistoryId, showToast, state],
  );

  const clearAllHistory = useCallback(() => {
    clearHistory();
    setSelectedHistoryId(null);
    if (state === "viewing_history") {
      setState("idle");
      setTexts(["", ""]);
      setResponse(null);
    }
  }, [state]);

  // Loading/error are reset here rather than in the effect body: setting state
  // synchronously inside an effect triggers a cascading render.
  const reloadCatalog = useCallback(() => {
    setCatalogLoading(true);
    setCatalogError(null);
    setCatalogAttempt((attempt) => attempt + 1);
  }, []);

  return {
    state,
    mode,
    texts,
    selectedFeatures,
    catalog,
    catalogLoading,
    catalogError,
    response,
    error,
    history,
    selectedHistoryId,
    toast,
    visibleFeatures,
    effectiveSelection,
    requiredTextCount,
    readOnly,
    validation,
    setMode,
    setText,
    toggleFeature,
    setTierSelected,
    runAnalysis,
    newAnalysis,
    viewHistoryEntry,
    duplicateHistoryEntry,
    removeHistoryEntry,
    clearAllHistory,
    showToast,
    dismissToast,
    reloadCatalog,
  };
}
