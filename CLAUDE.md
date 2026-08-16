# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

The **backend is implemented** against `specifications/specs_mvp.md` (all 20 spec features across both modes and three tiers, plus thirty Tier 1 features added afterwards — the lemma and density pairs plus the whole of `specs_features.md` §3-6 (clause, sentence, punctuation, complexity), taking Tier 1 from 5 features to 35 — `specs_mvp.md` has not been amended). **`specifications/specs_features.md` is the source of truth for linguistic features**: it defines every implemented and planned feature, and §11 records five accepted decisions that must not be silently reversed. Every feature in `specs_features.md` is now implemented, and its §11.1 UI-disclosure obligation is satisfied — the last open item on that document is the §11.1 benchmark of `en_core_web_sm` against `en_core_web_md`, which nothing depends on. The **frontend is scaffolded and working end-to-end** — Next.js 16 (App Router) + React 19 + Tailwind v4, all of §11's components and both layouts (three-pane and the sub-1024px tabbed fallback). A root `compose.yml` deploys both services. Still missing: any frontend tests.

The spec is the source of truth for **both** tracks: §2–8 are the backend architecture, §9–13 are the frontend UI spec (layout, state machine, component breakdown, design system, behavioral requirements). Follow its folder structure, component split and design tokens rather than inventing a different layout.

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

Frontend commands run from `frontend/` (npm, no monorepo tooling):

```bash
npm install
npm run dev                 # http://localhost:3000 — needs the API running too
npm run build               # production build; also typechecks
npm run lint                # eslint flat config
npx tsc --noEmit            # typecheck only
```

The UI calls `http://localhost:8000` unless `NEXT_PUBLIC_API_BASE_URL` says otherwise, and
the API's CORS allowlist is `http://localhost:3000` alone (`settings.cors_origins`,
override with `TEXTROPY_CORS_ORIGINS`) — change one and you must change the other. CORS
allows only `GET`/`POST` and sends no credentials.

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
- Tier 1 (spaCy `Doc` only) — *lexical* (`features/tier1/lexical.py`): word count, unique word count, lemma count, unique lemma count, content word count, function word count, content word density, function word density, type-token ratio (TTR); *clause* (`features/tier1/clause.py`): infinitive/noun/adjective/adverbial clause count; *sentence* (`features/tier1/sentence.py`): sentence count, simple/compound/complex/compound-complex counts + densities, sentence length mean/stdev; *punctuation* (`features/tier1/punctuation.py`): punctuation count, internal/terminal counts + ratios; *complexity* (`features/tier1/complexity.py`): MDD, dependency tree depth, phrasal elaboration (mean + stdev each). `features/tier1/stats.py` holds the shared `ratio`/`mean`/`stdev` conventions — use it rather than inlining a new one
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
- **Linux torch comes from the CPU-only wheel index.** PyPI's linux `torch` wheels are the CUDA build — `cuda-bindings`, `triton` and ~15 `nvidia-*` packages, several GB of GPU libraries in a deployment that runs `device="cpu"` everywhere. `[[tool.uv.index]] pytorch-cpu` (`explicit = true`) plus a `torch = [{ index = "pytorch-cpu", marker = "sys_platform == 'linux'" }]` source pins linux to `2.13.0+cpu`; the marker leaves macOS resolving from PyPI, where the wheels are already CPU-only. Removing this is what fills a small VPS's disk during `docker compose build`.
- **`specs_features.md` §11.1's "approximate" disclosure is published by the backend, not hardcoded in the UI.** Decision 5 keeps Tier 1 on `en_core_web_sm` and obliges the results pane to mark parser-derived values as approximate. That scope is a property of the *feature* — the twenty-one computers in `clause.py`, `sentence.py` and `complexity.py` read parse structure; `lexical.py` and `punctuation.py` read tags and surface forms — and only the backend knows it, so `FeatureComputer.approximate` declares it and the catalog carries it. The alternative was a list of twenty-one names in the frontend, which breaks the "never hardcode the feature list" rule and silently omits the caveat the first time a parser-derived feature is added. `tests/test_api_tier1.py::test_catalog_marks_exactly_the_parser_derived_features_approximate` pins the set as an equality, not a subset, so a new feature has to land on one side of the line deliberately.
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
│   ├── README.md               # orientation: setup, features, API, config, deployment
│   └── ARCHITECTURE.md         # pipeline internals: classes, data flow, invariants
├── frontend/                 # Next.js 16 App Router, per spec §11
│   ├── app/{layout.tsx, page.tsx, globals.css}   # page.tsx composes the 3 panes + tabs; globals.css holds the tokens
│   ├── components/
│   │   ├── history/{HistoryPane, HistoryListItem, NewAnalysisButton, ClearHistoryButton}.tsx
│   │   ├── analysis-form/{AnalysisFormPane, ModeToggle, TierSelector, FeatureCheckbox, TextInput, AnalyzeButton}.tsx
│   │   ├── results/{ResultsPane, ResultsEmptyState, ResultsSkeleton, TierResultSection, MetricRow, ComparisonDiffView, CopyResultsButton}.tsx
│   │   └── shared/{Toast, ErrorBanner}.tsx
│   ├── lib/{api.ts, history.ts, types.ts, useAnalysisState.ts, format.ts}   # format.ts is additive: label/number/relative-time helpers
│   ├── Dockerfile            # 3-stage → standalone server on node:24-alpine, uid 10001
│   ├── README.md             # orientation: commands, API/CORS pairing, Docker
│   └── ARCHITECTURE.md       # UI internals: design tokens, pane wiring, state machine
├── compose.yml               # api + frontend only, no db/cache/worker (spec §8 calls it
│                             # docker-compose.yml; compose.yml is the Compose Spec name)
└── .env.example              # copy to .env on the VPS — compose interpolation only
```

## API contract

Single endpoint drives both modes, synchronous end-to-end (Tier 3 included — no job queue in MVP):

- `POST /api/v1/analyze` — body: `{ mode: "single"|"compare", texts: [...] (1 or 2 items), tiers: [1,2,3], feature_names: null | [...] }`. Response includes per-text `results[].features.tier{1,2,3}`, a `comparison` object (populated only in `compare` mode, mirroring the tiered shape), and `meta.elapsed_ms` / `meta.tiers_computed`. Full example payloads are in `specifications/specs_mvp.md` §6 — match that shape exactly.
- `GET /api/v1/features` — machine-readable catalog (`name`, `tier`, `scope`, `symmetric`, `approximate`, plus a `requires` signal list) driving the frontend's tier/feature picker. The picker builds itself from this response; never hardcode the feature list in the frontend. `approximate` also carries `specs_features.md` §11.1's disclosure scope to the results pane — see the implementation decision below.
- `GET /api/v1/health` — liveness/readiness; readiness must reflect whether `models_ml` singletons have finished loading, not just process-up.

## Frontend (spec §9–13 — implemented)

Read §9–13 before changing any UI code; the notes below are what the implementation commits to, not a replacement for the spec.

**Stack specifics.** Next.js 16 (Turbopack by default), React 19.2, Tailwind v4 (CSS-first — there is no `tailwind.config.js`; tokens live in `@theme inline` in `globals.css`), `lucide-react` for icons. `frontend/AGENTS.md` is written by `next dev` and warns that v16 APIs differ from training data — the bundled docs in `node_modules/next/dist/docs/` are authoritative. React 19's lint rules ban synchronous `setState` in an effect body and ref writes during render; both shaped the hook below, so don't "simplify" them back.

**Layout (§9).** Three panes: History (fixed ~280px) · Analysis configuration (fluid ~40%) · Results (remaining). Panes are divided by a hairline `1px solid var(--border)`, never drop shadows. Below ~1024px the layout collapses to a single column with **History / Analyze / Results** as top-level tabs. The responsive fallback is a **first-pass requirement, not a fast-follow** — the spec flags cutting it under timeline pressure as a known risk, so build the layout primitives to serve both arrangements from the start.

**State machine (§10).** One explicit state — `idle` → `editing` → `analyzing` → (`error`) — plus `viewing_history`, owned by `AnalysisFormPane` via the `useAnalysisState` hook. `HistoryPane` and `ResultsPane` are driven by that single value (selected entry id, current results payload); they must not keep independent copies, which is what keeps the three panes from drifting. `viewing_history` is fully read-only: mode toggle, textboxes and Analyze are all disabled. Editing a loaded entry is out of scope for the first pass, but when it lands it must fork into a fresh `idle`/`editing` state rather than mutate the stored entry.

**Validation (§10, §13.2).** Analyze is enabled only when ≥1 feature is selected and every required textbox (1 for single, 2 for compare) is non-empty and under the client-side length cap. Cmd/Ctrl+Enter in a textbox triggers Analyze when valid. Live char/word counter under each box with a soft warning near the cap; confirm before a compare → single switch that would discard Text B; Tier 3 carries an inline "may take several seconds" note because it runs synchronously.

**History (§13.1).** `lib/history.ts` owns `localStorage`: one entry per analysis, `{id, timestamp, mode, tiers, texts[], response}` — the full request *and* response, so viewing an entry never re-hits the API. Cap at ~50 entries and evict oldest; surface a toast when a write fails on quota. Items show a ~40-char snippet, mode badge, tier badges and a relative timestamp; actions are click-to-view, hover-reveal per-item delete, "Clear all", and "Duplicate as new" (pre-fills an editable `idle` state).

**Design system (§12).** Minimalist editorial tool aesthetic — a linguist's notebook, not a SaaS dashboard. The one signature: **every numeric/metric value renders in monospace** (IBM Plex Mono / JetBrains Mono) against a sans UI face (Inter / IBM Plex Sans); `MetricRow` is a sans muted label plus a mono value. Colors are CSS variables in `globals.css` (`--bg` `#FAFAF9`, `--surface` `#FFFFFF`, `--border` `#E4E1DC`, `--ink` `#1C1B1A`, `--ink-muted` `#6B6862`, `--accent` `#3A5A73`, `--accent-soft` `#E8EEF2`, `--positive` `#3F7857`, `--negative` `#A14C43`) — use the tokens, don't hardcode hexes in components. 4px radius everywhere; 4px spacing base (4/8/12/16/24/32, pane padding 24px); flat by default with `shadow-sm` only for dropdowns/skeletons and `shadow-md` only for toasts/modals; 120–150ms ease-out transitions and no page-load or scroll animation. Outline icons (Lucide/Phosphor, 16–20px, 1.5px stroke) used sparingly — the mode toggle and tier labels stay text-only. Visible 2px `--accent` focus outlines on every interactive element are non-negotiable.

**Talking to the API (§13.4).** `lib/api.ts` wraps `POST /api/v1/analyze` and `GET /api/v1/features`; the tier/feature picker is built from the catalog endpoint, never a hardcoded feature list, so backend features stay the single source. Network/5xx → `error` state with input preserved and retry. A single feature reporting `available: false` must degrade to an "Unavailable" `MetricRow`, not take down the results pane.

### Frontend implementation decisions

Same rule as the backend list: these resolve real ambiguities, so read the reasoning before changing them.

- **`useAnalysisState` is called in `app/page.tsx`, not `AnalysisFormPane`.** §11 names the form pane as the state owner, but React siblings cannot read a sibling's state — History and Results would have to duplicate it, which is the exact drift §11 is preventing. The form pane remains the only component that *mutates* the value; the other two only render from it.
- **History is a `useSyncExternalStore` source, not React state synced by an effect** (`lib/history.ts` exports `subscribe`/`getSnapshot`/`getServerSnapshot`). `localStorage` genuinely is external state; this also keeps the server and hydrating client renders in agreement (both see an empty list) and makes a write in one tab update the others. The snapshot must stay cached — returning a fresh array per call would loop forever.
- **`feature_names` is always sent, and `tiers` is derived from it.** The picker's selection *is* the request, so a half-selected tier never silently expands to the whole tier. This leans on the backend's "override, not filter" semantics.
- **Results render by value *shape*, never by feature name.** `MetricRow` maps a scalar to a row and an object to a nested group, so `{label, score}` and `{a_given_b, b_given_a}` both work with no per-feature code. Value-derived styling follows the same rule: a string reading `positive`/`negative` gets the polarity colour, whatever feature produced it. The one thing a row cannot derive from its own value is whether it is parser-derived (`specs_features.md` §11.1), so `ResultsPane` builds an `isApproximate` predicate from the catalog and threads it down as a prop — `MetricRow` renders a flag it is handed and still maps no name to behaviour. If the catalog failed to load, a stored history entry would lose its markers silently, so the pane says so rather than rendering the values bare.
- **`MAX_TEXT_CHARS = 20_000` in `lib/useAnalysisState.ts` is currently the only length cap in the system**, since `TEXTROPY_MAX_TEXT_CHARS` defaults to 0/disabled. Soft warning at 90%, hard block above.
- **`ComparisonDiffView` re-derives its own alignment client-side** and caps at 1200 words per side (the LCS table is O(n·m)). It is illustrative only — the `lcs_length` metric shown alongside it comes from the API like every other value.
- **The compare → single mode-switch confirmation uses `window.confirm`.** §11 lists no modal component, and inventing one to hold a single sentence seemed worse than the placeholder. Replace it when a modal exists.
- **`frontend/CLAUDE.md` (`@AGENTS.md`) is generated by `next dev`,** not hand-written — leave both files in place; deleting them only recreates an uncommitted change.
- **`next.config.ts` sets `output: "standalone"` for the Dockerfile's benefit.** The runtime stage copies `.next/standalone` *and* `.next/static` separately — the standalone bundle deliberately omits static assets, and skipping that second copy 404s every stylesheet and chunk while the page still returns 200. There is no `public/` directory today; add the matching `COPY` if one appears.
- **`NEXT_PUBLIC_API_BASE_URL` is baked into the client bundle at build time**, so it is a Docker `--build-arg`, not a runtime `-e`. Retargeting a deployment means rebuilding the image, and the value must match the backend's `TEXTROPY_CORS_ORIGINS`. This is the one config knob that does not follow the backend's env-var pattern.

## Tech stack

- Backend: FastAPI + Uvicorn via the `fastapi` CLI (`fastapi[standard-no-fastapi-cloud-cli]` — the `standard` extra minus the FastAPI Cloud deploy client), Pydantic v2, Python 3.11+. No gunicorn: the deployment is deliberately one worker, so its process manager bought nothing.
- NLP/ML: spaCy (`en_core_web_sm`), transformers (DistilBERT SST-2, DistilGPT2), fastcoref, sentence-transformers (`all-MiniLM-L6-v2`), rapidfuzz, scikit-learn (TF-IDF), scipy (JS divergence), gensim/POT (WMD)
- Frontend: Next.js 16 (App Router, Turbopack) + React 19.2 + TypeScript + Tailwind v4; plain `fetch` against the API, no state management library (a `useAnalysisState` hook is the whole state layer). Inter (UI) and IBM Plex Mono (metrics) via `next/font/google`, `lucide-react` for icons
- Containerization: Docker + Compose V2 (api, frontend only). Spec §8 assumes Caddy in front for automatic HTTPS; `compose.yml` does not ship it — see Deployment below

## Deployment (`compose.yml`)

`DEPLOYMENT.md` is the step-by-step VPS runbook (nginx + certbot on `textropy.dev`, single origin with `/api/` proxied to the backend). The notes below are the reasoning behind it.

Production runs on a VPS from a git checkout of this repo — `git pull && docker compose up -d --build`. Both images are built on the host; nothing is pushed to a registry and there is no CI. Settings come from a root `.env` (gitignored, template in `.env.example`) that Compose interpolates into the file; the backend still receives everything as `TEXTROPY_*` in `environment:`, so `.env` is never read by the app itself.

- **`--build` is part of the deploy command, not an optimisation.** `NEXT_PUBLIC_API_BASE_URL` is inlined into the client bundle at build time, so editing `.env` and running plain `up -d` keeps serving the old API URL with no error anywhere.
- **No reverse proxy in the file.** Both services publish host ports directly (`BIND_ADDRESS:PORT:PORT`) and TLS is out of scope for the compose file. `BIND_ADDRESS=127.0.0.1` is the hook for a proxy already living on the host — spec §8's Caddy is compatible with that, just not bundled.
- **`PUBLIC_API_URL` and `FRONTEND_ORIGIN` are browser-facing addresses, never service names.** Every API call is client-side `fetch` from the visitor's browser; the Next server never talks to `api`. That is also why `frontend` has no `depends_on` — gating it on the api healthcheck (up to 90s while models load) would delay startup for a dependency that does not exist.
- **List-typed settings must be JSON in the environment.** pydantic-settings parses `cors_origins` and `eager_tiers` as JSON, hence `'["${FRONTEND_ORIGIN}"]'` and `[1]`, not comma-separated strings.
- **The api image installs the `coref` extra and bakes `biu-nlp/f-coref`.** `backend/Dockerfile` passes `--extra coref` to both `uv sync` steps and instantiates `FCoref` in the weight-bake layer. Both halves are required: the runtime stage sets `HF_HUB_OFFLINE=1`, so an installed fastcoref with unbaked weights still fails to load. Drop both together to go back to a smaller image whose `/api/v1/health` reports `"coref": "error"`.
- **`MAX_TEXT_CHARS` defaults to 20000 here**, matching the frontend's client-side hard block — the app default is still `0`/off, so the cap exists only in deployment. It is what stops a direct `curl` from bypassing the UI's limit.

## Known MVP trade-offs (intentional, not oversights)

These are deferred to keep the MVP a single Docker service with no external dependencies, while keeping the multi-pass architecture so the upgrade path is additive rather than a rewrite:

- No cross-request caching → identical texts are reprocessed every request (deferred fix: Redis + content-hash `document_id`)
- Tier 3 runs synchronously in-request (deferred fix: Celery/RQ async job + polling endpoint)
- No auth/rate limiting (deferred fix: API key + `slowapi`)
- History is client-only, lost if browser storage is cleared
- No input length cap enforced yet server-side — the `TEXTROPY_MAX_TEXT_CHARS` hook exists but defaults to `0` (off); the frontend is meant to enforce a soft warning + hard block client-side ahead of it (deferred fix: tier-dependent max-length validation)
- Models are loaded per worker process, so multiple workers multiply RAM (mitigation: single-worker + async concurrency, or a shared model server)
- No general per-feature `status`/`error` in the response, so the frontend can only distinguish "feature failed" from "feature absent" for the optional-model degradation path (deferred fix: extend `AnalyzeResponse` — see the implementation decision above)
