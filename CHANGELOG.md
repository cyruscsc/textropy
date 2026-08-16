# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Backend and frontend are versioned together and released as one unit: `backend/pyproject.toml`
`[project] version` and `frontend/package.json` `version` always carry the same number, and a
git tag `vX.Y.Z` marks the pair.

## [Unreleased]

## [0.2.0] — 2026-08-16

Tier 1 grows from 5 features to 35, and parser-derived values now reach the reader marked as
approximate. Purely additive: no feature changed its value or its shape, and no request or
response key was removed.

### Added

#### Tier 1 features

`specifications/specs_features.md` is now the source of truth for linguistic features, and
every feature it defines is implemented. Thirty new computers, all reading the same
`spacy.doc` the existing five read, so selecting all of Tier 1 still costs one parse.

- Lexical (`features/tier1/lexical.py`) — `lemma_count`, `unique_lemma_count`,
  `content_word_density`, `function_word_density`.
- Clause (`features/tier1/clause.py`) — `infinitive_clause_count`, `noun_clause_count`,
  `adjective_clause_count`, `adverbial_clause_count`.
- Sentence (`features/tier1/sentence.py`) — `sentence_count`; count and density for each of
  `simple_sentence`, `compound_sentence`, `complex_sentence`, `compound_complex_sentence`;
  `sentence_length_mean`, `sentence_length_stdev`.
- Punctuation (`features/tier1/punctuation.py`) — `punctuation_count`,
  `internal_punctuation_count`, `internal_punctuation_ratio`, `terminal_punctuation_count`,
  `terminal_punctuation_ratio`.
- Complexity (`features/tier1/complexity.py`) — mean and standard deviation of each of mean
  dependency distance (`mdd_mean`, `mdd_stdev`), dependency tree depth
  (`dependency_depth_mean`, `dependency_depth_stdev`) and phrasal elaboration
  (`phrasal_elaboration_mean`, `phrasal_elaboration_stdev`).

#### Approximation disclosure

- Feature catalog entries carry an `approximate` flag, set by the twenty-one computers that
  read dependency-parse structure rather than tags or surface forms. It is a property of the
  feature, so only the backend can state it.
- The results pane marks those values with a `≈` footnote, built from the catalog rather than
  a hand-maintained list of feature names — a parser-derived feature added later arrives in
  the UI already carrying its caveat. When the catalog cannot be loaded the pane says the
  markers are missing instead of presenting the values bare.

This satisfies `specs_features.md` §11.1, the disclosure obligation attached to Decision 5's
choice of `en_core_web_sm`.

#### Shared conventions

- `features/tier1/stats.py` — one definition of ratio (`0.0`, never `null`, on a zero
  denominator), mean, and population standard deviation (`ddof=0`), rounded to 4 decimal
  places at the point of return and never on an intermediate. Two feature groups can no
  longer quietly disagree about what a ratio does with an empty text.
- `signals/spacy_extractor.content_sentences` — one definition of "a sentence" (a span
  holding at least one word token, so a punctuation-only span such as `"..."` does not count),
  shared by the sentence and complexity groups so their per-sentence series describe the same
  population.

#### Documentation

- `specifications/specs_features.md` — every implemented and planned linguistic feature, with
  §11 recording five accepted decisions.
- `backend/ARCHITECTURE.md` and `frontend/ARCHITECTURE.md` — pipeline internals and UI
  internals respectively, alongside the orientation-level READMEs.

### Changed

- `ttr` is computed through the shared `stats.ratio` helper. Output is identical, including
  its `0.0` for an empty text; it is noted only because it is the sole edit to a feature that
  shipped in 0.1.0.

### Upgrading

Deploy both services together, as the versioning policy above requires. A 0.2.0 frontend
against a 0.1.0 backend loses every approximation marker silently, because the flag arrives
from the catalog rather than the bundle; a 0.1.0 frontend against a 0.2.0 backend ignores the
new field and renders the new features unmarked. Nothing else in the contract moved, so no
stored history entry or client is invalidated.

## [0.1.0] — 2026-08-12

First release: the MVP defined by `specifications/specs_mvp.md`, deployable to a single VPS.

### Added

#### Analysis engine

- Multi-pass, per-request pipeline with no persistence. An in-memory `AnalysisContext` per
  text carries Pass 1 signals, Pass 2 single-text features and Pass 3 cross-text metrics, so a
  signal shared by several features is extracted at most once per text and nothing is written
  to disk or a database.
- Declared feature/signal dependencies: each computer states the signals it requires and the
  orchestrator resolves their union before Pass 1 runs, rather than letting computers extract
  their own inputs.
- Seven signal extractors — spaCy `Doc`, DistilGPT2 token log-probabilities, MiniLM sentence
  and word vectors, a deterministic LM-to-spaCy token alignment, DistilBERT SST-2 sentiment,
  and fastcoref clusters.
- Ten single-text features across three tiers: `word_count`, `unique_word_count`,
  `content_word_count`, `function_word_count`, `ttr` (Tier 1); `sentiment`, `coreference`,
  `cohesion` (Tier 2); `perplexity`, `mean_surprisal` (Tier 3).
- Ten comparison features across three tiers: `levenshtein`, `lcs_length`, `ngram_overlap`,
  `tfidf_cosine` (Tier 1); `semantic_similarity`, `wmd`, `pos_divergence`, `dep_divergence`
  (Tier 2); `cross_perplexity`, `conditional_surprisal` (Tier 3, asymmetric — reported as
  `a_given_b` / `b_given_a`).
- Comparison mode reuses each text's single-text pipeline output instead of re-parsing either
  side.

#### API

- `POST /api/v1/analyze` — one endpoint for both single and compare modes, synchronous
  end-to-end including Tier 3. Accepts `tiers` or a `feature_names` override that selects
  exactly the named features and addresses both registries.
- `GET /api/v1/features` — machine-readable catalog (`name`, `tier`, `scope`, `symmetric`,
  `requires`) that the UI's tier and feature picker builds itself from.
- `GET /api/v1/health` — readiness reflects whether the models this deployment preloads have
  finished loading, not merely that the process is up.
- `TEXTROPY_ENVIRONMENT=production` unmounts `/docs`, `/redoc` and `/openapi.json`.
- CORS restricted to a configurable origin allowlist, `GET`/`POST` only, no credentials.

#### Models

- Process-wide singletons in `models_ml/model_registry.py`, never per-request. Loading is
  configurable via `TEXTROPY_MODEL_LOADING` (`eager`/`lazy`) and `TEXTROPY_EAGER_TIERS`.
- Graceful degradation for optional models: when fastcoref is absent or fails to load, the
  `coreference` feature reports `{"available": false, "reason": ...}` and every other feature
  keeps working. A missing required model still fails the request with 503.

#### Frontend

- Next.js 16 (App Router) + React 19 + Tailwind v4 three-pane layout — History, Analysis
  configuration, Results — collapsing to History/Analyze/Results tabs below ~1024px.
- Single explicit state machine (`idle` → `editing` → `analyzing` → `error`, plus a read-only
  `viewing_history`) owned by one hook, with the History and Results panes rendering from that
  one value rather than keeping copies.
- Client-side history in `localStorage`: full request and response per entry, so viewing an
  entry never re-hits the API. Capped at ~50 entries with oldest-first eviction, click to view,
  per-item delete, clear all, and duplicate-as-new.
- Results render by value shape rather than by feature name, so new backend features appear
  without frontend changes, and a feature reporting itself unavailable degrades to a single
  row instead of taking down the pane.
- Validation with a 20,000-character cap, live char/word counters, Cmd/Ctrl+Enter to analyze,
  and an inline warning that Tier 3 runs synchronously.
- Editorial design system in CSS variables, with every metric value set in monospace.

#### Deployment

- `compose.yml` running the api and frontend services only — no database, cache or worker.
  Configuration comes from a root `.env`; `.env.example` is the template.
- Multi-stage Dockerfiles for both services, each running as uid 10001 with a healthcheck. The
  api image bakes the Hugging Face weights so container start does not depend on the network.
- `DEPLOYMENT.md`: VPS runbook for nginx + certbot on a single origin, with `/api/` proxied to
  the backend.
- Linux installs resolve `torch` from the CPU-only wheel index, keeping the CUDA runtime and
  ~15 `nvidia-*` packages out of a deployment that runs on CPU.

### Known limitations

Accepted MVP trade-offs, documented in `specifications/specs_mvp.md` §14: no cross-request
caching, Tier 3 runs synchronously in-request, no auth or rate limiting, history is client-only
and lost if browser storage is cleared, server-side input length capping is off by default,
models are loaded per worker process, and the response carries no general per-feature
`status`/`error` field. The frontend has no test suite yet.

[Unreleased]: https://github.com/cyruscsc/textropy/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/cyruscsc/textropy/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cyruscsc/textropy/releases/tag/v0.1.0
