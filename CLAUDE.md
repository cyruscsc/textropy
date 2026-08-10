# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

The **backend is implemented** against `specifications/specs_mvp.md` (all 20 features across both modes and three tiers). `frontend/` is still an empty placeholder — no Next.js app yet, and no root `docker-compose.yml` (it needs the frontend service to be meaningful).

The spec is the source of truth for **both** tracks: §2–8 are the backend architecture, §9–13 are the frontend UI spec (layout, state machine, component breakdown, design system, behavioral requirements). Follow its folder structure, component split and design tokens rather than inventing a different layout — building the frontend means implementing §9–13, not designing from scratch.

## Commands

All backend commands run from `backend/`, which uses **uv** with a project-local `.venv`.

```bash
uv sync                     # base install (includes en_core_web_sm via a pinned URL dep)
uv sync --extra coref       # + fastcoref, enabling the Tier 2 coreference feature

uv run fastapi dev app/main.py                      # dev server, reload; docs at /docs

# production: 0.0.0.0:8000, no reload, proxy headers on, one worker (models are per-process)
TEXTROPY_ENVIRONMENT=production uv run fastapi run app/main.py

uv run pytest                       # full suite (downloads Tier 2/3 models on first run)
uv run pytest -m "not heavy"        # fast path: Tier 1 + pure-logic tests, no downloads
uv run pytest tests/test_alignment.py -v     # single file
uv run pytest -k test_cycles_are_detected    # single test

uv run ruff check app tests
uv run ruff format app tests
```

Tier 2/3 tests are marked `heavy` because they load transformer weights. Prefer
`-m "not heavy"` while iterating on architecture or Tier 1.

No frontend commands yet — `frontend/` is empty. When it is scaffolded, the API expects it
on `http://localhost:3000` (the sole default in `settings.cors_origins`; override with
`TEXTROPY_CORS_ORIGINS`). CORS allows only `GET`/`POST` and sends no credentials.

## What Textropy is

Textropy is a web app for linguistic text analysis, supporting **single-text** analysis and **double-text** comparison across three feature tiers (increasing computational cost/model complexity). The MVP is intentionally **stateless**: no database, no server-side cache (Redis), no background job queue (Celery/RQ), no auth, no rate limiting. History is stored client-side only, in browser `localStorage`.

## Core architectural principle: multi-pass, no persistence

Even with no cross-request cache, redundant computation must be avoided **within a single request**. This is done via an in-memory `AnalysisContext` per text, computed in three passes:

1. **Pass 1 — Signals** (`backend/app/signals/`): extract fundamental linguistic signals — spaCy `Doc`, per-token LM surprisal, sentence embeddings, etc. Each signal is computed **at most once per text**, and only if some selected tier/feature actually requires it.
2. **Pass 2 — Features** (`backend/app/features/`): single-text features computed by reading from the already-populated context. Feature computers never re-trigger signal extraction.
3. **Pass 3 — Comparison** (`backend/app/comparison/`): for double-text mode, cross-text metrics computed from the Pass 1/2 outputs of *both* texts. Never re-parses either text — a double-text request reuses each text's single-text pipeline output rather than reimplementing extraction.

Feature/signal dependency is **declared, not hardcoded**: each feature computer states which signal(s) it needs, and an orchestration service (`services/analysis_service.py` for one text, `services/comparison_service.py` which calls it for A & B then runs Pass 3) resolves the *union* of required signals per text before running any feature computer. This is what guarantees a shared signal (e.g. the spaCy `Doc` needed by both `word_count` and `type_token_ratio`) is computed once — purely through module boundaries and orchestration logic, no cache involved. Preserve this pattern when adding new features/signals; don't let a feature computer reach around the context to extract its own signal.

The context and all intermediate signals are **discarded after the response is sent** — nothing is written to disk or a database server-side.

## Feature registry (MVP scope)

Only the features below are in scope; everything else discussed previously is deferred post-MVP. Full detail (required signals, backing package) is in `specifications/specs_mvp.md` §3 — consult it before adding/modifying a feature.

**Single-text**, by tier:
- Tier 1 (spaCy `Doc` only): word count, unique word count, content word count, function word count, type-token ratio (TTR)
- Tier 2: sentiment (DistilBERT SST-2), coreference (fastcoref), cohesion / sentence-to-sentence similarity (MiniLM sentence embeddings)
- Tier 3: perplexity, mean per-token surprisal (both via DistilGPT2 + a custom LM-to-spaCy token alignment)

**Double-text (comparison)**, by tier:
- Tier 1 (symmetric): Levenshtein distance, LCS, n-gram overlap, TF-IDF cosine similarity
- Tier 2 (symmetric): semantic similarity (MiniLM), Word Mover's Distance, POS/dependency distribution divergence (Jensen-Shannon)
- Tier 3 (**asymmetric** — computed in both directions and returned as `a_given_b`/`b_given_a`): cross-perplexity, conditional surprisal

## Signal extractors (Pass 1)

| Signal | Extractor | Model |
|---|---|---|
| `spacy.doc` | `signals/spacy_extractor.py` | `en_core_web_sm` |
| `lm.token_logprobs` | `signals/lm_extractor.py` | `distilgpt2` |
| `embedding.sentence_vectors` | `signals/embedding_extractor.py` | `all-MiniLM-L6-v2` |
| `embedding.word_vectors` | `signals/embedding_extractor.py` (type-level) | `all-MiniLM-L6-v2` |
| `alignment.lm_to_spacy` | `signals/alignment.py` | deterministic, no model |
| `sentiment.document` | `signals/sentiment_transformer.py` | DistilBERT SST-2 |
| `coref.clusters` | `signals/coreference.py` | fastcoref |

Signal names are constants in `signals/base.py` — import them rather than writing string
literals, so a typo is an ImportError instead of a missing signal at runtime.

All ML models are loaded **once per process** as singletons in `models_ml/model_registry.py` — never instantiate a model per-request. Total resident memory with everything loaded is ~1.5–2GB. Loading strategy is configurable, not hardcoded: `TEXTROPY_MODEL_LOADING=eager|lazy` and `TEXTROPY_EAGER_TIERS` (default `[1]`, i.e. only spaCy is preloaded).

## Implementation decisions

Resolutions of spec ambiguities and non-obvious choices — don't silently "fix" these without reading the reasoning:

- **Sentiment and coreference are signals *and* features.** Spec §4 lists them as Pass 1 extractors; §5 puts them in `features/tier2/`. Both are implemented: the model call is a signal (`sentiment.document`, `coref.clusters`) so it runs once per text no matter how many features read it, and the Tier 2 feature is the thin computer that shapes it for the response.
- **Surprisal is per spaCy token, in nats.** The alignment signal maps DistilGPT2 subwords onto words and sums them. Nats (not bits) keeps `mean_surprisal` consistent with `perplexity`, and matches the spec §6 example values (`ln(24.7) ≈ 3.2` against a shown `mean_surprisal` of 3.1).
- **`pos_divergence` and `dep_divergence` are two computers**, not one, matching the two keys in the spec §6 response and letting `feature_names` address them separately. Both live in `comparison/tier2/distribution_divergence.py`. Values are JS *divergence* (squared JS distance, base 2), range 0–1.
- **Tier 3 comparison computers may call the LM directly.** Cross-perplexity conditions B on A, which no per-text signal holds; `lm_extractor.score_continuation` is the cross-text primitive. The rule that stays enforced is never recomputing something a per-text signal already has.
- **WMD uses POT (`ot.emd2`) over type-level MiniLM vectors**, not gensim. Spec §8 allows either; POT avoids gensim's stricter scipy pin, and type-level vectors are truer to WMD's classical definition than contextual ones.
- **`feature_names` is an override, not a filter within `tiers`.** When supplied it selects exactly those features and `meta.tiers_computed` is derived from them. It addresses both registries — `features/registry.py` and `comparison/registry.py` each ignore names belonging to the other.
- **`TEXTROPY_ENVIRONMENT=production` unmounts `/docs`, `/redoc` and `/openapi.json`** (`main.create_app` passes `None` for each URL, so they 404 rather than render empty). Default is `development`, where all three are served. The MVP has no auth or rate limiting, so a public Swagger UI is a convenient way to aim synchronous Tier 3 requests at the host; the frontend uses `/api/v1/features` for its tier picker and never needs `/docs`. `backend/Dockerfile` sets the production value by default.
- **fastcoref is an optional extra pinned to `transformers<5`.** It reads transformers internals removed in v5 (`all_tied_weights_keys`). Without the extra, `coreference` returns `{"available": false, "reason": ...}` and everything else keeps working — see the degradation path in `services/analysis_service.run_signals` and the tests in `tests/test_optional_model_degradation.py`. Only optional models degrade; a missing required model still raises 503.
- **`{"available": false, "reason": ...}` is the *only* per-feature failure shape today.** It is emitted by `analysis_service.run_features` when a required signal was marked unavailable — i.e. the optional-model path above. A feature computer that raises still fails the whole request. So the frontend's per-feature "Unavailable" row (spec §13.4) should key off `available === false` on a feature's value object, and treat request-level failure as the `error` state; the general per-feature `status`/`error` field the spec asks for is still an open gap (spec §14).

## Folder structure

```
textropy/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/{config.py, logging.py}
│   │   ├── api/v1/routers/{analyze.py, catalog.py, health.py}, api/v1/deps.py
│   │   ├── schemas/{requests.py, responses.py}          # Pydantic v2
│   │   ├── pipeline/context.py                          # AnalysisContext (in-memory, per-request)
│   │   ├── signals/                                      # Pass 1 — base.py, *_extractor.py, alignment.py, registry.py
│   │   ├── features/                                     # Pass 2 (single-text) — tier1/, tier2/, tier3/, registry.py
│   │   ├── comparison/                                    # Pass 3 (double-text) — tier1/, tier2/, tier3/, registry.py
│   │   ├── services/{analysis_service.py, comparison_service.py}
│   │   └── models_ml/{spacy_model.py, causal_lm.py, sentence_embedder.py, sentiment_model.py, coref_model.py, model_registry.py}
│   ├── tests/
│   ├── Dockerfile
│   ├── pyproject.toml + uv.lock
│   └── README.md
├── frontend/                 # NOT YET BUILT — target shape below is spec §11, follow it
│   ├── app/{layout.tsx, page.tsx, globals.css}   # page.tsx composes the 3 panes; globals.css holds the tokens
│   ├── components/
│   │   ├── history/{HistoryPane, HistoryListItem, NewAnalysisButton, ClearHistoryButton}.tsx
│   │   ├── analysis-form/{AnalysisFormPane, ModeToggle, TierSelector, FeatureCheckbox, TextInput, AnalyzeButton}.tsx
│   │   ├── results/{ResultsPane, ResultsEmptyState, ResultsSkeleton, TierResultSection, MetricRow, ComparisonDiffView, CopyResultsButton}.tsx
│   │   └── shared/{Toast, ErrorBanner}.tsx
│   └── lib/{history.ts, api.ts, types.ts, useAnalysisState.ts}
└── docker-compose.yml        # NOT YET WRITTEN — api + frontend only, no db/cache/worker
```

## API contract

Single endpoint drives both modes, synchronous end-to-end (Tier 3 included — no job queue in MVP):

- `POST /api/v1/analyze` — body: `{ mode: "single"|"compare", texts: [...] (1 or 2 items), tiers: [1,2,3], feature_names: null | [...] }`. Response includes per-text `results[].features.tier{1,2,3}`, a `comparison` object (populated only in `compare` mode, mirroring the tiered shape), and `meta.elapsed_ms` / `meta.tiers_computed`. Full example payloads are in `specifications/specs_mvp.md` §6 — match that shape exactly.
- `GET /api/v1/features` — machine-readable catalog (`name`, `tier`, `scope`, `symmetric`, plus a `requires` signal list) driving the frontend's tier/feature picker. The picker builds itself from this response; never hardcode the feature list in the frontend.
- `GET /api/v1/health` — liveness/readiness; readiness must reflect whether `models_ml` singletons have finished loading, not just process-up.

## Frontend (spec §9–13 — not yet built)

Read §9–13 before writing any UI code; the notes below are the parts worth having in mind up front, not a replacement for the spec.

**Layout (§9).** Three panes: History (fixed ~280px) · Analysis configuration (fluid ~40%) · Results (remaining). Panes are divided by a hairline `1px solid var(--border)`, never drop shadows. Below ~1024px the layout collapses to a single column with **History / Analyze / Results** as top-level tabs. The responsive fallback is a **first-pass requirement, not a fast-follow** — the spec flags cutting it under timeline pressure as a known risk, so build the layout primitives to serve both arrangements from the start.

**State machine (§10).** One explicit state — `idle` → `editing` → `analyzing` → (`error`) — plus `viewing_history`, owned by `AnalysisFormPane` via the `useAnalysisState` hook. `HistoryPane` and `ResultsPane` are driven by that single value (selected entry id, current results payload); they must not keep independent copies, which is what keeps the three panes from drifting. `viewing_history` is fully read-only: mode toggle, textboxes and Analyze are all disabled. Editing a loaded entry is out of scope for the first pass, but when it lands it must fork into a fresh `idle`/`editing` state rather than mutate the stored entry.

**Validation (§10, §13.2).** Analyze is enabled only when ≥1 feature is selected and every required textbox (1 for single, 2 for compare) is non-empty and under the client-side length cap. Cmd/Ctrl+Enter in a textbox triggers Analyze when valid. Live char/word counter under each box with a soft warning near the cap; confirm before a compare → single switch that would discard Text B; Tier 3 carries an inline "may take several seconds" note because it runs synchronously.

**History (§13.1).** `lib/history.ts` owns `localStorage`: one entry per analysis, `{id, timestamp, mode, tiers, texts[], response}` — the full request *and* response, so viewing an entry never re-hits the API. Cap at ~50 entries and evict oldest; surface a toast when a write fails on quota. Items show a ~40-char snippet, mode badge, tier badges and a relative timestamp; actions are click-to-view, hover-reveal per-item delete, "Clear all", and "Duplicate as new" (pre-fills an editable `idle` state).

**Design system (§12).** Minimalist editorial tool aesthetic — a linguist's notebook, not a SaaS dashboard. The one signature: **every numeric/metric value renders in monospace** (IBM Plex Mono / JetBrains Mono) against a sans UI face (Inter / IBM Plex Sans); `MetricRow` is a sans muted label plus a mono value. Colors are CSS variables in `globals.css` (`--bg` `#FAFAF9`, `--surface` `#FFFFFF`, `--border` `#E4E1DC`, `--ink` `#1C1B1A`, `--ink-muted` `#6B6862`, `--accent` `#3A5A73`, `--accent-soft` `#E8EEF2`, `--positive` `#3F7857`, `--negative` `#A14C43`) — use the tokens, don't hardcode hexes in components. 4px radius everywhere; 4px spacing base (4/8/12/16/24/32, pane padding 24px); flat by default with `shadow-sm` only for dropdowns/skeletons and `shadow-md` only for toasts/modals; 120–150ms ease-out transitions and no page-load or scroll animation. Outline icons (Lucide/Phosphor, 16–20px, 1.5px stroke) used sparingly — the mode toggle and tier labels stay text-only. Visible 2px `--accent` focus outlines on every interactive element are non-negotiable.

**Talking to the API (§13.4).** `lib/api.ts` wraps `POST /api/v1/analyze` and `GET /api/v1/features`; the tier/feature picker is built from the catalog endpoint, never a hardcoded feature list, so backend features stay the single source. Network/5xx → `error` state with input preserved and retry. A single feature reporting `available: false` must degrade to an "Unavailable" `MetricRow`, not take down the results pane.

## Tech stack

- Backend: FastAPI + Uvicorn via the `fastapi` CLI (`fastapi[standard-no-fastapi-cloud-cli]` — the `standard` extra minus the FastAPI Cloud deploy client), Pydantic v2, Python 3.11+. No gunicorn: the deployment is deliberately one worker, so its process manager bought nothing.
- NLP/ML: spaCy (`en_core_web_sm`), transformers (DistilBERT SST-2, DistilGPT2), fastcoref, sentence-transformers (`all-MiniLM-L6-v2`), rapidfuzz, scikit-learn (TF-IDF), scipy (JS divergence), gensim/POT (WMD)
- Frontend: Next.js (App Router) + TypeScript + Tailwind CSS; plain `fetch` against the API, no state management library (a `useAnalysisState` hook is the whole state layer). Inter / IBM Plex Sans for UI, IBM Plex Mono / JetBrains Mono for metrics, Lucide or Phosphor for icons
- Containerization: Docker + docker-compose (api, frontend only); Caddy as reverse proxy for automatic HTTPS

## Known MVP trade-offs (intentional, not oversights)

These are deferred to keep the MVP a single Docker service with no external dependencies, while keeping the multi-pass architecture so the upgrade path is additive rather than a rewrite:

- No cross-request caching → identical texts are reprocessed every request (deferred fix: Redis + content-hash `document_id`)
- Tier 3 runs synchronously in-request (deferred fix: Celery/RQ async job + polling endpoint)
- No auth/rate limiting (deferred fix: API key + `slowapi`)
- History is client-only, lost if browser storage is cleared
- No input length cap enforced yet server-side — the `TEXTROPY_MAX_TEXT_CHARS` hook exists but defaults to `0` (off); the frontend is meant to enforce a soft warning + hard block client-side ahead of it (deferred fix: tier-dependent max-length validation)
- Models are loaded per worker process, so multiple workers multiply RAM (mitigation: single-worker + async concurrency, or a shared model server)
- No general per-feature `status`/`error` in the response, so the frontend can only distinguish "feature failed" from "feature absent" for the optional-model degradation path (deferred fix: extend `AnalyzeResponse` — see the implementation decision above)
