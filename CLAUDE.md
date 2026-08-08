# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

The **backend is implemented** against `specifications/specs_mvp.md` (all 20 features across both modes and three tiers). `frontend/` is still an empty placeholder — no Next.js app yet, and no root `docker-compose.yml` (it needs the frontend service to be meaningful). The spec is the source of truth: follow its folder structure and architecture rather than inventing a different layout.

## Commands

All backend commands run from `backend/`, which uses **uv** with a project-local `.venv`.

```bash
uv sync                     # base install (includes en_core_web_sm via a pinned URL dep)
uv sync --extra coref       # + fastcoref, enabling the Tier 2 coreference feature

uv run uvicorn app.main:app --reload --port 8000    # dev server; docs at /docs

uv run pytest                       # full suite (downloads Tier 2/3 models on first run)
uv run pytest -m "not heavy"        # fast path: Tier 1 + pure-logic tests, no downloads
uv run pytest tests/test_alignment.py -v     # single file
uv run pytest -k test_cycles_are_detected    # single test

uv run ruff check app tests
uv run ruff format app tests
```

Tier 2/3 tests are marked `heavy` because they load transformer weights. Prefer
`-m "not heavy"` while iterating on architecture or Tier 1.

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
- **fastcoref is an optional extra pinned to `transformers<5`.** It reads transformers internals removed in v5 (`all_tied_weights_keys`). Without the extra, `coreference` returns `{"available": false, "reason": ...}` and everything else keeps working — see the degradation path in `services/analysis_service.run_signals` and the tests in `tests/test_optional_model_degradation.py`. Only optional models degrade; a missing required model still raises 503.

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
├── frontend/                 # NOT YET BUILT — Next.js App Router + lib/history.ts
└── docker-compose.yml        # NOT YET WRITTEN — api + frontend only, no db/cache/worker
```

## API contract

Single endpoint drives both modes, synchronous end-to-end (Tier 3 included — no job queue in MVP):

- `POST /api/v1/analyze` — body: `{ mode: "single"|"compare", texts: [...] (1 or 2 items), tiers: [1,2,3], feature_names: null | [...] }`. Response includes per-text `results[].features.tier{1,2,3}`, a `comparison` object (populated only in `compare` mode, mirroring the tiered shape), and `meta.elapsed_ms` / `meta.tiers_computed`. Full example payloads are in `specifications/specs_mvp.md` §6 — match that shape exactly.
- `GET /api/v1/features` — machine-readable catalog (name, tier, scope, symmetric flag) driving the frontend's tier/feature picker.
- `GET /api/v1/health` — liveness/readiness; readiness must reflect whether `models_ml` singletons have finished loading, not just process-up.

## Tech stack

- Backend: FastAPI + Uvicorn/Gunicorn, Pydantic v2, Python 3.11+
- NLP/ML: spaCy (`en_core_web_sm`), transformers (DistilBERT SST-2, DistilGPT2), fastcoref, sentence-transformers (`all-MiniLM-L6-v2`), rapidfuzz, scikit-learn (TF-IDF), scipy (JS divergence), gensim/POT (WMD)
- Frontend: Next.js (App Router) + TypeScript + Tailwind CSS; plain `fetch` against the API, no state management library
- Containerization: Docker + docker-compose (api, frontend only); Caddy as reverse proxy for automatic HTTPS

## Known MVP trade-offs (intentional, not oversights)

These are deferred to keep the MVP a single Docker service with no external dependencies, while keeping the multi-pass architecture so the upgrade path is additive rather than a rewrite:

- No cross-request caching → identical texts are reprocessed every request (deferred fix: Redis + content-hash `document_id`)
- Tier 3 runs synchronously in-request (deferred fix: Celery/RQ async job + polling endpoint)
- No auth/rate limiting (deferred fix: API key + `slowapi`)
- History is client-only, lost if browser storage is cleared
- No input length cap enforced yet (deferred fix: tier-dependent max-length validation)
- Models loaded per Gunicorn worker process multiplies RAM with multiple workers (mitigation: single-worker + async concurrency, or a shared model server)
