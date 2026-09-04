# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Backend and frontend are versioned together and released as one unit: `backend/pyproject.toml`
`[project] version` and `frontend/package.json` `version` always carry the same number, and a
git tag `vX.Y.Z` marks the pair.

## [Unreleased]

## [0.2.3] — 2026-09-04

Bottom navigation on small screens. Frontend only: the backend is unchanged from 0.2.2, no API
contract moved, and no stored history entry is affected. One change is visible at every width,
not just below 1024px — the Analysis and History panes no longer have a bottom action bar, and
the actions that lived there are now in the pane headers.

### Added

- `frontend/components/shared/PaneTabBar.tsx` — below 1024px the **History / Analyze /
  Results** tabs are a rounded-pill menu of icon-and-label buttons floating over the bottom of
  the viewport, rather than a strip across the top. On a phone this is the app's primary
  navigation and the top edge is the hardest place on the screen for a thumb to reach. Analyze
  is the centre item and the pane the app opens on; the active tab is deliberately not
  persisted, so every visit starts there.
- Pane content scrolls underneath the menu. Its footprint is one new token,
  **`--pane-menu-space`** in `globals.css` — the pill's height plus its gutter — reserved as
  bottom padding by all three panes' scroll containers and by `Toast`, each with a
  1024px-and-above reset. One definition, because the menu and everything dodging it have to
  agree.
- The menu hides itself while a textarea has focus. A fixed element is anchored to the layout
  viewport, which the soft keyboard does not shrink, so it would otherwise sit stranded behind
  the keyboard — and iOS Safari displaces fixed elements outright while the keyboard animates.
  Dismissing the keyboard brings it back; nobody navigates panes mid-sentence.

### Changed

- Both pane footers are gone, and every pane is now a header plus a scroll body. Nothing can
  sit statically under a floating menu — reserving space only helps scrolling content, while a
  pinned bar is simply covered. The `min-h-[89px]` that had to be kept identical in two files
  to align the two footers' hairlines goes with them.
- **Analyze** moved into the Analysis pane header as a filled icon-and-label button, level with
  Results' "Copy results", so the primary action is reachable without scrolling past the
  feature list. Its validation hint moved to the end of the scroll body instead: the hint is
  pane-level, and compare mode renders a character counter under each of two text boxes.
- **Clear all** became an icon-only control in the History pane header, beside the theme
  toggle. Its confirmation prompt and its disabled-at-zero-entries behaviour are unchanged.
- Two design-system exceptions, both scoped to the floating menu and nothing else:
  `rounded-full` against §12.4's 4px-everywhere radius, and `shadow-md`, which `globals.css`
  otherwise reserves for toasts and modals.

## [0.2.2] — 2026-09-04

Dark mode, and a system/light/dark preference to choose it. Frontend only: the backend is
unchanged from 0.2.1, no API contract moved, and no stored history entry is affected.

### Added

- Dark mode. `:root[data-theme="dark"]` re-points the nine design tokens at a warm charcoal
  palette; because no component names a colour, that one block is the whole theme and not a
  single component's classes changed. `color-scheme` is set alongside it, so native
  scrollbars, the textarea caret and its resize handle follow the page instead of staying
  light.
- A theme control cycling **system → light → dark**, in the History pane footer and mirrored
  on the collapsed rail — an action belongs on the rail only if it still means something with
  the list hidden, which the colour scheme does. Below 1024px it sits under the History tab.
- The choice persists as a `theme` key inside the existing **`textropy.preferences.v1`** blob,
  beside the History and divider preferences. It is additive: a browser arriving from 0.2.1
  keeps its layout, and an absent or malformed value falls back to `system`, so the page
  follows the OS until told otherwise.
- `frontend/lib/theme.ts` and `frontend/components/shared/InlineScript.tsx` — an inline
  `<head>` script that resolves the preference and sets `data-theme` while the browser is
  still parsing the document. Every React mechanism runs at or after hydration, which is
  itself after the first paint, so without this a dark-mode reader gets a white flash on
  every load.

### Changed

- Four values that silently assumed a light ground became tokens: `--on-accent` (text and
  icons on a filled accent, which cannot keep borrowing `--surface` once the accent is the
  lighter colour), `--positive-soft` and `--negative-soft` (the comparison diff's tints,
  previously a 10% alpha chosen against white), and `--shadow-color` (Tailwind's shadows
  hardcode black at 10%, invisible on a near-black ground). Light mode renders identically.

## [0.2.1] — 2026-08-24

UI refinement across all three panes. The backend is unchanged from 0.2.0: no API contract
moved, and no stored history entry is affected.

### Added

- Collapsible History pane. The pane header carries a hide control; collapsed, it leaves a
  rail holding the two actions that still mean something with the list hidden — re-open and
  "New analysis". The toggle and rail are 1024px-and-above only: below that History is one of
  the three tabs, where hiding it would strand every saved analysis behind a control that is
  itself hidden.
- Adjustable divider between the Analysis and Results panes
  (`frontend/components/shared/PaneDivider.tsx`), operable by pointer or arrow keys, with both
  panes floored so neither can be dragged shut.
- `frontend/lib/preferences.ts` — a second `localStorage` store alongside `lib/history.ts`,
  following the same `useSyncExternalStore` contract, persisting both of the above under the
  new **`textropy.preferences.v1`** key. It holds layout preferences only and stays out of the
  analysis state machine. An absent or malformed value falls back to the defaults — History
  expanded, Analysis pane at 40% — so a browser arriving from 0.2.0 opens exactly as it did
  before, and clearing the key restores that layout.

### Changed

- The approximate marker is a bordered monospace chip
  (`frontend/components/results/ApproximateBadge.tsx`) rather than a bare `≈` superscript. The
  marked metric rows and the footnote that explains them render the same component, so the key
  and the values it describes cannot drift apart visually.
- The mode toggle spans the width of its pane in two equal halves, and feature lists lay out
  in as many columns as the pane can hold. Column count follows the pane's width rather than
  the viewport's — below 1024px the Analysis tab is full-width, so a narrower window can give
  a wider pane, which no breakpoint can express.

### Fixed

- A feature checkbox now sits beside the first line of a label that wraps, instead of centring
  itself against both lines.
- The History and Analysis panes' footers no longer disagree in height between roughly 1024px
  and 1124px, where the validation hint wraps to two lines and knocked the two hairlines out
  of alignment.

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

[Unreleased]: https://github.com/cyruscsc/textropy/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/cyruscsc/textropy/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/cyruscsc/textropy/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/cyruscsc/textropy/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/cyruscsc/textropy/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cyruscsc/textropy/releases/tag/v0.1.0
