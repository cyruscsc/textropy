# Textropy — MVP Technical Specification

## 1. Overview

Textropy is a web app for linguistic text analysis, supporting **single-text** analysis and **double-text** comparison across three feature tiers (increasing computational cost). This document specifies the **MVP scope**: a stateless, no-database, no-cache implementation that still follows a multi-pass architecture to avoid redundant computation *within a single request*.

**Explicitly out of scope for MVP:** persistence/database, server-side caching (Redis), background job queue (Celery/RQ), authentication, rate limiting. History is stored client-side only (browser `localStorage`).

This document covers both the **backend architecture** (Sections 2–8) and the **frontend UI specification** (Sections 9–13), serving as the shared reference for both tracks of MVP development.

---

## 2. Architectural Principle: Multi-Pass, No Persistence

Even without a cache, redundant computation must be avoided **within one request's lifecycle**. This is achieved via an in-memory `AnalysisContext` per text:

- **Pass 1 (Signals):** extract fundamental linguistic signals (spaCy `Doc`, per-token LM surprisal, sentence embeddings) — each signal computed **at most once per text**, only if required by a selected tier.
- **Pass 2 (Features):** compute single-text features by reading from the already-populated context — never re-triggers extraction.
- **Pass 3 (Comparison):** for double-text mode, computes cross-text metrics using the Pass 1/2 outputs of both texts — never re-parses either text.

Feature/signal dependency is declared, not hardcoded: each feature computer states which signal(s) it needs, and the orchestration service resolves the union of required signals per text before running any feature computer. This guarantees single-computation of shared signals (e.g., both `word_count` and `type_token_ratio` reuse the same spaCy `Doc`) purely through module boundaries and orchestration logic — no cache required.

The context and all intermediate signals are **discarded after the response is sent**. Nothing is written to disk or a database server-side.

---

## 3. Feature Registry (MVP Scope)

Only the features listed below are implemented in the MVP. All other features discussed previously are deferred to post-MVP expansion.

### 3.1 Single-Text Mode

| Tier | Feature | Required Signal(s) | Package |
|---|---|---|---|
| 1 | Word count | `spacy.doc` | spaCy |
| 1 | Unique word count | `spacy.doc` | spaCy |
| 1 | Content word count | `spacy.doc` (POS tags) | spaCy |
| 1 | Function word count | `spacy.doc` (POS tags) | spaCy |
| 1 | Type-token ratio (TTR) | `spacy.doc` | spaCy |
| 2 | Sentiment | `spacy.doc` (sentences) | transformers (DistilBERT SST-2) |
| 2 | Coreference | `spacy.doc` | fastcoref |
| 2 | Cohesion (sentence-to-sentence similarity) | `embedding.sentence_vectors` | sentence-transformers (MiniLM) |
| 3 | Perplexity | `lm.token_logprobs` | transformers (DistilGPT2) |
| 3 | Surprisal (mean, per-token) | `lm.token_logprobs`, `spacy.doc`, `alignment.lm_to_spacy` | transformers (DistilGPT2) + custom alignment |

**Note:** All Tier 1 features depend only on `spacy.doc` → parsed exactly once per text regardless of how many Tier 1 features are requested.

### 3.2 Double-Text Mode (Comparison)

| Tier | Feature | Required Signal(s) (per text A & B) | Package | Symmetric? |
|---|---|---|---|---|
| 1 | Levenshtein distance | raw text | rapidfuzz | Yes |
| 1 | Longest common subsequence (LCS) | raw text | difflib / rapidfuzz | Yes |
| 1 | N-gram overlap | `spacy.doc` (tokens) | nltk / custom | Yes |
| 1 | TF-IDF cosine similarity | raw text (both texts, joint vectorizer) | scikit-learn | Yes |
| 2 | Semantic similarity | `embedding.sentence_vectors` | sentence-transformers (MiniLM) | Yes |
| 2 | Word Mover's Distance (WMD) | `embedding.word_vectors` | gensim / POT | Yes |
| 2 | POS/dependency distribution divergence | `spacy.doc` (POS + dep tags) | scipy (Jensen-Shannon) | Yes |
| 3 | Cross-perplexity | `lm.token_logprobs` (B conditioned on A as context) | transformers (DistilGPT2) | **No** |
| 3 | Conditional surprisal | `lm.token_logprobs`, `alignment.lm_to_spacy` | transformers (DistilGPT2) | **No** |

Comparison features reuse each text's Pass 1/2 outputs (computed via the same single-text pipeline) — a double-text request never re-implements single-text signal extraction. Asymmetric Tier 3 features are computed in both directions (`a_given_b`, `b_given_a`) and returned as such.

---

## 4. Signal Extractors (Pass 1)

| Signal | Extractor | Model | Approx. RAM |
|---|---|---|---|
| `spacy.doc` | `spacy_extractor.py` | `en_core_web_sm` | ~150–200MB |
| `lm.token_logprobs` | `lm_extractor.py` | `distilgpt2` | ~500–700MB |
| `embedding.sentence_vectors` | `embedding_extractor.py` | `all-MiniLM-L6-v2` | ~300MB |
| `embedding.word_vectors` | `embedding_extractor.py` (word-level pooling) | `all-MiniLM-L6-v2` or GloVe | shared w/ above |
| `alignment.lm_to_spacy` | `alignment.py` | — (deterministic mapping, no model) | negligible |
| `sentiment` model | `sentiment_transformer.py` | DistilBERT SST-2 | ~500MB |
| coreference | `coreference.py` | fastcoref | ~200–300MB |

All ML models are loaded **once at application startup** as singletons (`models_ml/model_registry.py`), not per-request. Total resident memory with all models loaded: **~1.5–2GB**. Tier 2/3 models may be lazy-loaded on first use instead of eagerly at startup if VPS memory is constrained (configurable).

---

## 5. Folder Structure

```
textropy/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   ├── api/v1/
│   │   │   ├── routers/
│   │   │   │   ├── analyze.py
│   │   │   │   ├── catalog.py
│   │   │   │   └── health.py
│   │   │   └── deps.py
│   │   ├── schemas/
│   │   │   ├── requests.py
│   │   │   └── responses.py
│   │   ├── pipeline/
│   │   │   └── context.py          # AnalysisContext (in-memory, per-request)
│   │   ├── signals/                # Pass 1
│   │   │   ├── base.py
│   │   │   ├── spacy_extractor.py
│   │   │   ├── lm_extractor.py
│   │   │   ├── embedding_extractor.py
│   │   │   ├── alignment.py
│   │   │   └── registry.py
│   │   ├── features/                # Pass 2 — single-text
│   │   │   ├── base.py
│   │   │   ├── tier1/ (lexical.py)
│   │   │   ├── tier2/ (sentiment.py, coreference.py, cohesion.py)
│   │   │   ├── tier3/ (perplexity.py, surprisal.py)
│   │   │   └── registry.py
│   │   ├── comparison/              # Pass 3 — double-text
│   │   │   ├── base.py
│   │   │   ├── tier1/ (edit_distance.py, lcs.py, ngram_overlap.py, tfidf_similarity.py)
│   │   │   ├── tier2/ (semantic_similarity.py, wmd.py, distribution_divergence.py)
│   │   │   ├── tier3/ (cross_perplexity.py, conditional_surprisal.py)
│   │   │   └── registry.py
│   │   ├── services/
│   │   │   ├── analysis_service.py     # Pass 1 → Pass 2 orchestration, one text
│   │   │   └── comparison_service.py   # calls analysis_service for A & B, then Pass 3
│   │   └── models_ml/
│   │       ├── spacy_model.py
│   │       ├── causal_lm.py
│   │       ├── sentence_embedder.py
│   │       ├── sentiment_model.py
│   │       ├── coref_model.py
│   │       └── model_registry.py
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/
│   ├── app/                          # Next.js App Router
│   ├── lib/
│   │   └── history.ts                # localStorage read/write wrapper
│   └── ...
│
├── docker-compose.yml                 # api + frontend services only
└── README.md
```

---

## 6. API Endpoints

### `POST /api/v1/analyze`

Single endpoint for both modes; synchronous (including Tier 3 — no job queue in MVP).

**Request:**
```json
{
  "mode": "single",                 // "single" | "compare"
  "texts": ["..."],                 // length 1 (single) or 2 (compare)
  "tiers": [1, 2, 3],                // tiers to compute
  "feature_names": null              // optional explicit subset override
}
```

**Response (single mode):**
```json
{
  "mode": "single",
  "results": [
    {
      "text_index": 0,
      "features": {
        "tier1": { "word_count": 142, "unique_word_count": 98, "content_word_count": 76,
                   "function_word_count": 66, "ttr": 0.61 },
        "tier2": { "sentiment": {"label": "positive", "score": 0.87},
                   "coreference": {"chain_count": 4},
                   "cohesion": {"mean_adjacent_similarity": 0.42} },
        "tier3": { "perplexity": 24.7, "mean_surprisal": 3.1 }
      }
    }
  ],
  "comparison": null,
  "meta": { "elapsed_ms": {"signals": 320, "features": 45}, "tiers_computed": [1,2,3] }
}
```

**Response (compare mode):** `results` has two entries (each text's own features, per the single-text schema above); `comparison` is populated:
```json
"comparison": {
  "tier1": { "levenshtein": 87, "lcs_length": 54, "ngram_overlap": 0.33, "tfidf_cosine": 0.74 },
  "tier2": { "semantic_similarity": 0.81, "wmd": 1.42, "pos_divergence": 0.09, "dep_divergence": 0.15 },
  "tier3": { "cross_perplexity": {"a_given_b": 31.2, "b_given_a": 28.9},
             "conditional_surprisal": {"a_given_b": 3.4, "b_given_a": 3.1} }
}
```

### `GET /api/v1/features`
Returns the machine-readable catalog (name, tier, scope, symmetric flag) for the features listed in Section 3 — drives the frontend's tier/feature selection UI.

### `GET /api/v1/health`
Liveness/readiness; readiness reflects whether `models_ml` singletons have finished loading.

---

## 7. Frontend & History

- **Framework:** Next.js (App Router) + TypeScript + Tailwind CSS.
- **Data fetching:** plain `fetch` against `/api/v1/analyze`; no state management library needed at this scope.
- **History:** on each successful analysis, the frontend stores the full request + response payload in `localStorage` (via `lib/history.ts`), keyed by a client-generated UUID and timestamp. No server-side history endpoint exists in the MVP.

---

## 8. Tech Stack Summary

| Layer | Choice |
|---|---|
| Backend framework | FastAPI + Uvicorn/Gunicorn |
| Validation | Pydantic v2 |
| Python | 3.11+ |
| NLP core | spaCy (`en_core_web_sm`) |
| Sentiment | transformers + DistilBERT SST-2 |
| Coreference | fastcoref |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Causal LM (perplexity/surprisal) | transformers + `distilgpt2` |
| Similarity/distance | rapidfuzz, scikit-learn (TF-IDF), scipy (JS divergence), gensim/POT (WMD) |
| Frontend | Next.js + TypeScript + Tailwind |
| Containerization | Docker + docker-compose (api, frontend — no db/cache/worker) |
| Reverse proxy | Caddy (automatic HTTPS) |

---

## 9. UI Layout — Three-Pane Structure

```
┌────────────────┬────────────────────────────────┬──────────────────────────┐
│  HISTORY       │  ANALYSIS CONFIGURATION        │  RESULTS                 │
│  (left)        │  (center)                      │  (right)                 │
│                │                                │                          │
│  + New Analysis│  [Single text | Compare]       │  (empty state until      │
│                │                                │   an analysis is run     │
│  ─ Today ─     │  ▸ Tier 1  [expand for         │   or loaded)             │
│  • "The quick..│    individual features]        │                          │
│    2h ago      │  ▸ Tier 2                      │  Tier 1 results          │
│    single·T1,T2│  ▸ Tier 3 ⚠ may take longer    │  Tier 2 results          │
│                │                                │  Tier 3 results          │
│  • "Lorem ip.. │  ┌──────────────────────────┐  │                          │
│    vs "Dolor.. │  │ Text A textbox           │  │  (compare mode:          │
│    1d ago      │  └──────────────────────────┘  │   Text A / Text B        │
│    compare·T1  │  ┌──────────────────────────┐  │   side-by-side, then     │
│                │  │ Text B textbox (compare) │  │   comparison metrics     │
│  [Clear all]   │  └──────────────────────────┘  │   below)                 │
│                │                                │                          │
│                │          [ Analyze ]           │  [Copy results]          │
└────────────────┴────────────────────────────────┴──────────────────────────┘
```

- Fixed-width left pane (~280px), center pane fluid (~40%), right pane fluid (remaining space). Hairline `1px solid var(--border)` divides panes — no drop shadows between them.
- Below ~1024px viewport width, the layout collapses to a single-column tabbed view: **History / Analyze / Results** as top-level tabs, since three fixed columns aren't viable on tablet/mobile. This is a hard requirement, not a nice-to-have — plan the layout primitives (see Section 12) to support both from the start.

---

## 10. UI State Machine

The center and right panes' behavior is driven by one explicit state, not just an implicit "history loaded?" flag:

| State | Trigger | Mode toggle | Textbox(es) | Analyze button | Right pane |
|---|---|---|---|---|---|
| `idle` (new analysis) | App load, or "New Analysis" clicked | Active | Editable, empty | Enabled once valid input + ≥1 tier selected | Empty state |
| `editing` | User typing / selecting tiers | Active | Editable | Enabled/disabled per validation | Empty state |
| `analyzing` | Analyze clicked | Disabled | Disabled (read-only during request) | Disabled, shows spinner | Loading skeleton |
| `error` | Request failed | Active | Editable (input preserved) | Enabled (retry) | Error message + retry action |
| `viewing_history` | History item clicked | **Disabled**, shows original mode | **View-only**, shows original text(s) | **Disabled** | Populated with that entry's results |

**Note on edit-after-load:** if a future iteration allows editing text loaded from history, that edit should transition the app to a fresh `idle`/`editing` state (effectively "fork as new"), not mutate the historical entry in place. Out of scope for first pass, but the state model above is designed to accommodate it without rework.

Validation rule gating the Analyze button in `idle`/`editing`: at least one feature (from any tier) selected, and all required textboxes (one for single, two for compare) non-empty and under the max length (Section 13.4).

---

## 11. Component Breakdown

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                     # composes the three panes
│   └── globals.css                  # design tokens (CSS variables)
│
├── components/
│   ├── history/
│   │   ├── HistoryPane.tsx
│   │   ├── HistoryListItem.tsx      # snippet, mode badge, tier badges, relative time
│   │   ├── NewAnalysisButton.tsx
│   │   └── ClearHistoryButton.tsx
│   │
│   ├── analysis-form/
│   │   ├── AnalysisFormPane.tsx     # owns app state machine (Section 10)
│   │   ├── ModeToggle.tsx           # segmented control: Single text / Compare
│   │   ├── TierSelector.tsx         # expandable tier → feature checkboxes
│   │   ├── FeatureCheckbox.tsx
│   │   ├── TextInput.tsx            # shared editable/view-only textbox, char counter
│   │   └── AnalyzeButton.tsx
│   │
│   ├── results/
│   │   ├── ResultsPane.tsx
│   │   ├── ResultsEmptyState.tsx
│   │   ├── ResultsSkeleton.tsx      # loading state during `analyzing`
│   │   ├── TierResultSection.tsx    # collapsible, one per tier
│   │   ├── MetricRow.tsx            # label (sans) + value (mono) pairing
│   │   ├── ComparisonDiffView.tsx   # word/char-level diff for Tier 1 compare
│   │   └── CopyResultsButton.tsx
│   │
│   └── shared/
│       ├── Toast.tsx                # quota/error notifications
│       └── ErrorBanner.tsx
│
├── lib/
│   ├── history.ts                   # localStorage read/write/evict wrapper
│   ├── api.ts                       # fetch wrapper for POST /analyze, GET /features
│   ├── types.ts                     # shared request/response TypeScript types
│   └── useAnalysisState.ts          # state machine hook (Section 10)
│
└── ...
```

`AnalysisFormPane` is the single owner of the state-machine value; `HistoryPane` and `ResultsPane` are driven by it (selected history entry ID, current results payload) rather than each maintaining independent state — avoids the three panes drifting out of sync.

---

## 12. Design System

### 12.1 Direction
Minimalist, editorial-adjacent tool aesthetic — a linguist's notebook rather than a SaaS dashboard. The one deliberate signature: **all numeric/metric output uses a monospace face** against a sans-serif UI, functionally justified by tabular alignment of scannable numbers and thematically apt for a text-measurement tool.

### 12.2 Color

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#FAFAF9` | App background |
| `--surface` | `#FFFFFF` | Pane/card backgrounds |
| `--border` | `#E4E1DC` | Pane dividers, input borders |
| `--ink` | `#1C1B1A` | Primary text |
| `--ink-muted` | `#6B6862` | Secondary text, labels, metadata |
| `--accent` | `#3A5A73` | Primary actions, active/selected states |
| `--accent-soft` | `#E8EEF2` | Accent backgrounds (selected row, active tab) |
| `--positive` | `#3F7857` | Success states, positive sentiment |
| `--negative` | `#A14C43` | Errors, negative sentiment |

### 12.3 Typography

| Role | Face | Notes |
|---|---|---|
| UI / body | Inter or IBM Plex Sans | Headings use the same face at heavier weight — no separate display face |
| Metrics / data / code | IBM Plex Mono or JetBrains Mono | All numeric feature values, tier labels, JSON export view |

Scale: `text-xs` 12px (metadata/timestamps) · `text-sm` 14px (body/labels) · `text-base` 16px (textbox content) · `text-lg` 18px/600 (pane headers).

### 12.4 Radius, Icons, Spacing, Elevation, Motion

- **Radius:** 4px everywhere (buttons, inputs, cards, badges) — consistent, not zero, not soft-rounded.
- **Icons:** Lucide or Phosphor, outline, 16–20px, 1.5px stroke. Used sparingly (history pane actions, expand chevrons); mode toggle and tier labels stay text-only.
- **Spacing:** 4px base unit, scale 4/8/12/16/24/32. Pane padding 24px; between form sections 24px; within a checkbox list 8px.
- **Elevation:** flat by default; `shadow-sm` for dropdowns/skeletons, `shadow-md` for toasts/modals only.
- **Motion:** 120–150ms ease-out on hover/active/state transitions; 150ms height transition for tier expand/collapse; subtle skeleton-pulse in results pane during Tier 3 computation. No page-load or scroll animation.

### 12.5 Key Component Treatments

- **Buttons:** solid `--accent` fill (primary/Analyze), outline/ghost (secondary/New Analysis, Clear History). Disabled: `--border` background, `--ink-muted` text.
- **Checkboxes:** square, 4px radius, `--accent` when checked.
- **History list items:** no card border; 2px `--accent` left bar + `--accent-soft` background when selected/hovered.
- **Metric display:** label in sans (`--ink-muted`, `text-sm`) + value in mono (`--ink`, `text-base`, medium weight).
- **Focus states:** visible 2px `--accent` outline on all interactive elements (non-negotiable — keyboard support, see Section 13.3).

---

## 13. Frontend Behavioral Considerations

### 13.1 History (localStorage)
- Storage key structure: one entry per analysis — `{id, timestamp, mode, tiers, texts[], response}`.
- **Cap history length** (e.g., 50 most recent entries); evict oldest on overflow. Show a toast if a `localStorage` write fails due to quota.
- History list item displays: text snippet (~40 chars), mode badge, tier badges, relative timestamp.
- Actions: click to view (Section 10 `viewing_history` state), per-item delete (hover-reveal), "Clear all," and "Duplicate as new" (pre-fills an editable `idle` state with that entry's text/tiers for re-run).

### 13.2 Validation & Feedback
- Live character/word counter under each textbox; soft warning near the max-length threshold (Section 13.4).
- Analyze button disabled until validation passes (Section 10).
- Mode-switch confirmation if switching from compare → single would discard entered text in the second textbox.
- Tier 3 selection shows an inline note ("may take several seconds") since it runs synchronously with no job queue (per Section 9 limitations).

### 13.3 Accessibility & Keyboard
- Cmd/Ctrl+Enter in a focused textbox triggers Analyze (when valid).
- Visible focus outlines on all interactive elements.
- Responsive collapse to tabbed layout below ~1024px (Section 9).

### 13.4 Error & Partial-Failure Handling
- Request-level failure (network/5xx): `error` state (Section 10), input preserved, retry available.
- Feature-level failure (e.g., coreference fails on very short text): affected `MetricRow` renders "Unavailable" rather than failing the whole results pane. Requires the backend response to carry a per-feature `status`/`error` field (see Section 6 API response — to be extended when this is implemented) rather than only a request-level success/failure.
- Input length cap: enforced client-side (soft warning + hard block) ahead of the server-side validation noted in Section 9's limitations table.

---

## 14. Known MVP Limitations (Accepted Trade-offs)

| Limitation | Consequence | Deferred Fix |
|---|---|---|
| No cross-request caching | Identical texts reprocessed every request | Redis + content-hash `document_id` |
| Tier 3 runs synchronously | Slower response for perplexity/surprisal/cross-perplexity | Celery/RQ async job + polling endpoint |
| No auth/rate limiting | Vulnerable to abuse on public VPS | API key + `slowapi` rate limiting |
| History is client-only | Lost if browser storage is cleared; not shareable across devices | Optional server-side persistence |
| No input length cap enforced yet | Large inputs risk high latency/memory spikes | Tier-dependent max-length validation |
| Models loaded per Gunicorn worker process | Multiple workers multiply RAM usage | Consider single-worker + async concurrency, or shared model server |
| No per-feature status in API response | Frontend can't yet distinguish "feature failed" from "feature absent" (Section 13.4) | Extend `AnalyzeResponse` schema with per-feature `status`/`error` |
| Responsive tabbed fallback (Section 9) not yet built | If deferred, three-pane layout is unusable below ~1024px | Required in the first UI pass, not a fast-follow — flagged here as a risk if timeline pressure tempts cutting it |

These are intentionally deferred — not oversights — to keep the MVP's operational footprint minimal (single Docker service, no external dependencies) while preserving the multi-pass architecture so the upgrade path to the full design (Section referenced in prior discussion) is additive rather than a rewrite. Sections 9–13 extend this same reference to the frontend, so backend and UI development can proceed against one shared source of truth.