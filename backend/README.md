# Textropy backend

Stateless linguistic text-analysis API. One endpoint analyses a single text or compares two,
across three tiers of increasing computational cost. Implements the MVP spec in
[`../specifications/specs_mvp.md`](../specifications/specs_mvp.md).

There is no database, no cache, no job queue, and no auth. A request arrives, is analysed
entirely in memory, and everything computed for it is discarded when the response is sent.

This README is the orientation document. For a code-level walkthrough of the pipeline — every
class in `pipeline/`, `models_ml/`, `signals/`, `features/` and `comparison/`, the data flow
through them, and the invariants that hold the design together — see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Quick start

Requires [uv](https://docs.astral.sh/uv/). All dependencies live in a project-local `.venv`.

```bash
uv sync                 # base install
uv sync --extra coref   # + fastcoref, enabling the Tier 2 coreference feature

uv run fastapi dev app/main.py     # http://127.0.0.1:8000 — docs at /docs
```

`en_core_web_sm` is a declared dependency (pinned by URL in `pyproject.toml`), so no separate
`spacy download` step is needed. The Tier 2/3 transformer weights download from Hugging Face
on first use and are cached under `~/.cache/huggingface`.

```bash
curl -s localhost:8000/api/v1/analyze -H 'content-type: application/json' \
  -d '{"mode":"single","texts":["The cat sat on the mat."],"tiers":[1]}' | jq
```

---

## The problem this architecture solves

Most of the 28 features share underlying work. All thirteen Tier 1 features want a spaCy parse.
Perplexity and mean surprisal both want DistilGPT2 token log-probabilities. Cohesion and
comparison-mode semantic similarity both want sentence embeddings. A naive implementation
where each feature extracts what it needs would parse the same text thirteen times and run
DistilGPT2 twice per request.

The usual fix is a cache. The MVP deliberately has none — no Redis, and no in-process memo
that would leak across requests. So redundant work is eliminated *structurally* instead,
by separating extraction from consumption and letting an orchestrator schedule the former.

That is the whole idea behind the three passes. Everything below follows from it.

---

## Three passes over one context

```
POST /api/v1/analyze
        │
        ├─ Pass 1  SIGNALS      app/signals/       writes → AnalysisContext
        │          spaCy parse, LM log-probs, embeddings, alignment,
        │          sentiment, coref — each computed at most ONCE per text
        │
        ├─ Pass 2  FEATURES     app/features/      reads ← AnalysisContext
        │          single-text values: word_count, ttr, perplexity, …
        │
        └─ Pass 3  COMPARISON   app/comparison/    reads ← context A + context B
                   cross-text metrics: levenshtein, wmd, cross_perplexity, …

response sent → contexts dropped → nothing persisted
```

**`AnalysisContext`** (`app/pipeline/context.py`) is a plain in-memory bag of signals for
**one** text, created per request. It is deliberately *passive*: it never computes anything.
Pass 1 writes to it; Passes 2 and 3 only read. A feature cannot reach around it to extract
its own signal, because it has no way to — it holds no models and no text-processing code.

That passivity is what makes "each signal computed at most once per text" a property of the
structure rather than a convention a future feature could quietly violate.

### Pass 1 — signals

A `SignalExtractor` (`app/signals/base.py`) declares two things: the other signals it needs
(`depends_on`) and the models it loads (`models`).

| Signal | Extractor | Depends on | Model |
|---|---|---|---|
| `spacy.doc` | `spacy_extractor.py` | — | `en_core_web_sm` |
| `lm.token_logprobs` | `lm_extractor.py` | — | `distilgpt2` |
| `embedding.sentence_vectors` | `embedding_extractor.py` | `spacy.doc` | `all-MiniLM-L6-v2` |
| `embedding.word_vectors` | `embedding_extractor.py` | `spacy.doc` | `all-MiniLM-L6-v2` |
| `alignment.lm_to_spacy` | `alignment.py` | `spacy.doc`, `lm.token_logprobs` | none — pure arithmetic |
| `sentiment.document` | `sentiment_transformer.py` | `spacy.doc` | DistilBERT SST-2 |
| `coref.clusters` | `coreference.py` | `spacy.doc` | fastcoref (optional) |

Signal names are constants in `app/signals/base.py`. Import them rather than writing string
literals, so a typo is an `ImportError` instead of a signal that silently goes missing at
runtime.

### Pass 2 — features

A `FeatureComputer` declares its `tier` and a `requires` tuple of signal names, then reads
only those from the context. It never triggers extraction.

### Pass 3 — comparison

A `ComparisonComputer` receives *both* finished contexts. Its `requires` lists signals needed
**per text**; the orchestrator folds those into each text's own Pass 1, so comparison mode
still parses each text exactly once. Comparison computers never re-parse or re-embed.

Asymmetric metrics set `symmetric = False` and return both directions as
`{"a_given_b": …, "b_given_a": …}`.

---

## How dependencies are resolved

Dependency is **declared, not hardcoded**. No feature knows what any other feature needs, and
the orchestrator knows nothing about individual features. The union is computed at request
time from whatever was selected.

`AnalysisService.analyze_text` (`app/services/analysis_service.py`):

1. **Select** the computers for the requested tiers (or the explicit `feature_names`).
2. **Union** their declared `requires` into a set — duplicates collapse here.
3. **Resolve** that set into a topological run order via `signals/registry.resolve_order`,
   which pulls in transitive dependencies and raises on cycles or unknown signals.
4. **Run** each extractor once, storing results on the context.
5. **Run** the feature computers, which only read.

Worked example — `{"tiers": [1, 3]}` selects fifteen computers:

```
all 13 Tier 1 features                        requires  {spacy.doc}
perplexity                                    requires  {lm.token_logprobs}
mean_surprisal                                requires  {lm.token_logprobs, spacy.doc,
                                                         alignment.lm_to_spacy}
                                                 │
union ───────────────────────────────────────────┘
  {spacy.doc, lm.token_logprobs, alignment.lm_to_spacy}
                                                 │
resolve_order (topological) ─────────────────────┘
  1. spacy.doc              ← no dependencies
  2. lm.token_logprobs      ← no dependencies
  3. alignment.lm_to_spacy  ← depends on both, so it must come last
```

One parse and one DistilGPT2 pass, for fifteen features. Eight Tier 1 features (the lemma
pair, the density pair, and the four clause counts) were added after this document was first
written, and the extractor count did not move — which is the property the design buys.

Step 3 also means a computer can depend on a *derived* signal without knowing what that
signal is built from: `mean_surprisal` asks for `alignment.lm_to_spacy` and the resolver works
out that a parse and an LM pass must happen first, in that order.

`tests/test_signal_resolution.py` asserts these properties directly — deduplication, correct
topological order, cycle detection — so they are checked, not just documented.

---

## What each feature actually computes

### Single-text (`app/features/`)

| Tier | Feature | Reads | Notes |
|---|---|---|---|
| 1 | `word_count` | `spacy.doc` | punctuation and whitespace excluded |
| 1 | `unique_word_count` | `spacy.doc` | distinct lowercased forms |
| 1 | `lemma_count` | `spacy.doc` | word tokens carrying a lemma — equals `word_count` on ordinary prose |
| 1 | `unique_lemma_count` | `spacy.doc` | distinct lemmas; `<= unique_word_count`, since inflection collapses |
| 1 | `content_word_count` | `spacy.doc` | POS in `{NOUN, PROPN, VERB, ADJ, ADV}` |
| 1 | `function_word_count` | `spacy.doc` | the complement of the above |
| 1 | `content_word_density` | `spacy.doc` | `content_word_count / word_count`; lexical density |
| 1 | `function_word_density` | `spacy.doc` | `function_word_count / word_count`; sums to 1 with the above |
| 1 | `ttr` | `spacy.doc` | type-token ratio = unique / total |
| 1 | `infinitive_clause_count` | `spacy.doc` | `VB` verb with a `TO` aux child |
| 1 | `noun_clause_count` | `spacy.doc` | dep ∈ `{ccomp, csubj, csubjpass, pcomp}` |
| 1 | `adjective_clause_count` | `spacy.doc` | dep ∈ `{relcl, acl}` |
| 1 | `adverbial_clause_count` | `spacy.doc` | dep `advcl` |
| 2 | `sentiment` | `sentiment.document` | `{label, score}` from DistilBERT SST-2 |
| 2 | `coreference` | `coref.clusters` | `{chain_count}` from fastcoref |
| 2 | `cohesion` | `embedding.sentence_vectors` | mean cosine similarity of adjacent sentences |
| 3 | `perplexity` | `lm.token_logprobs` | `exp(−mean log P)` over subwords |
| 3 | `mean_surprisal` | + `spacy.doc`, `alignment.lm_to_spacy` | per **word**, in nats |

### Comparison (`app/comparison/`)

| Tier | Feature | Sym. | Reads | Backed by |
|---|---|---|---|---|
| 1 | `levenshtein` | ✓ | raw text | rapidfuzz |
| 1 | `lcs_length` | ✓ | raw text | rapidfuzz |
| 1 | `ngram_overlap` | ✓ | `spacy.doc` | Jaccard over token n-grams |
| 1 | `tfidf_cosine` | ✓ | raw text | scikit-learn |
| 2 | `semantic_similarity` | ✓ | `embedding.sentence_vectors` | MiniLM cosine |
| 2 | `wmd` | ✓ | `embedding.word_vectors` | POT `ot.emd2` |
| 2 | `pos_divergence` | ✓ | `spacy.doc` | Jensen-Shannon, 0–1 |
| 2 | `dep_divergence` | ✓ | `spacy.doc` | Jensen-Shannon, 0–1 |
| 3 | `cross_perplexity` | ✗ | — | LM, scored jointly |
| 3 | `conditional_surprisal` | ✗ | `spacy.doc` | LM, scored jointly |

### Two computations worth explaining

**Subword-to-word alignment.** DistilGPT2 scores BPE subwords; users care about words.
`signals/alignment.py` maps the two tokenizations onto each other through character offsets —
each LM token is attributed to the first spaCy token whose character span it overlaps — and
`mean_surprisal` sums the subword surprisals composing each word. It is pure interval
arithmetic with no model involved, so it is unit-tested without loading DistilGPT2
(`tests/test_alignment.py`).

Values are in **nats**, which keeps `mean_surprisal` consistent with `perplexity`. Words whose
subwords are all unscored are skipped: the first token of a text has no conditioning context,
and attributing a surprisal to it would be inventing one.

**Why Tier 3 comparison may call the LM directly.** `cross_perplexity` scores text A *with
text B as the conditioning prefix*. That is a genuinely joint quantity — it cannot be
assembled from the two texts' unconditional log-probabilities, so no per-text signal could
hold it. `lm_extractor.score_continuation` is the cross-text primitive: it concatenates the
context and target token ids, trims the context to fit the model window (keeping the newest
part), and returns only the target's scores. The rule that still holds everywhere: never
recompute something a per-text signal already has.

---

## Comparison mode

`ComparisonService.compare` does **not** reimplement extraction. It asks the comparison
registry which per-text signals Pass 3 will need, passes them to `AnalysisService` as
`extra_signals`, and lets each text run through the ordinary single-text pipeline once:

```
compare(A, B, tiers=[1,2])
   │
   ├── extra_signals = {spacy.doc, embedding.sentence_vectors, embedding.word_vectors}
   │
   ├── analyze_text(A, extra_signals=…)  → context A   (one Pass 1, one Pass 2)
   ├── analyze_text(B, extra_signals=…)  → context B   (one Pass 1, one Pass 2)
   │
   └── Pass 3 computers read (context A, context B)
```

So a comparison response contains full single-text results for both texts *and* the cross-text
metrics, having parsed and embedded each text exactly once.

---

## Models

All ML models are process-wide singletons in `app/models_ml/model_registry.py`, never
instantiated per request. Loading is configurable rather than hardcoded:

- `TEXTROPY_MODEL_LOADING=eager` (default) preloads every model whose tier is in
  `TEXTROPY_EAGER_TIERS` (default `[1]`, i.e. spaCy only) during startup. `/api/v1/health`
  reports `ready` only once they are resident.
- `TEXTROPY_MODEL_LOADING=lazy` loads each model on first use — smaller startup footprint,
  slower first request per tier.

`registry.get()` uses double-checked locking and **caches load failures**, so a broken
optional dependency does not cost a multi-second retry on every request. Everything loaded is
roughly 1.5–2GB resident.

### Graceful degradation

fastcoref is the only model marked `optional`. When an optional model fails to load, the
signal is recorded as unavailable rather than raising, and only the features that declared it
report the fact:

```json
"tier2": {
  "sentiment": { "label": "positive", "score": 0.9999 },
  "cohesion":  { "mean_adjacent_similarity": 0.1666, "sentence_count": 2 },
  "coreference": { "available": false, "reason": "Failed to load model 'coref': …" }
}
```

A **required** model that fails still raises and surfaces as HTTP 503 — degrading silently
there would return numbers the deployment cannot actually compute. Both paths are covered by
`tests/test_optional_model_degradation.py`.

---

## API

### `POST /api/v1/analyze`

```jsonc
{
  "mode": "single",        // or "compare"
  "texts": ["…"],          // exactly 1 for single, exactly 2 for compare
  "tiers": [1, 2, 3],
  "feature_names": null    // optional override — see below
}
```

`feature_names` is an **override, not a filter within `tiers`**: when supplied it selects
exactly those features and `meta.tiers_computed` is derived from them. It addresses both
registries, and each registry ignores names belonging to the other, so one list can mix
single-text and comparison features.

Single-text response (`tiers: [1,2,3]`, real output):

```json
{
  "mode": "single",
  "results": [{
    "text_index": 0,
    "features": {
      "tier1": { "word_count": 9, "unique_word_count": 8, "content_word_count": 4,
                 "function_word_count": 5, "ttr": 0.8889 },
      "tier2": { "sentiment": { "label": "positive", "score": 0.9999 },
                 "coreference": { "chain_count": 1 },
                 "cohesion": { "mean_adjacent_similarity": 0.1666, "sentence_count": 2 } },
      "tier3": { "perplexity": 100.6948, "mean_surprisal": 5.2519 }
    }
  }],
  "comparison": null,
  "meta": { "elapsed_ms": { "signals": 812.4, "features": 0.8 }, "tiers_computed": [1,2,3] }
}
```

In `compare` mode `results` holds both texts and `comparison` is populated:

```json
"comparison": {
  "tier1": { "levenshtein": 17, "lcs_length": 13, "ngram_overlap": 0.0, "tfidf_cosine": 0.1943 },
  "tier2": { "semantic_similarity": 0.5508, "wmd": 0.4652,
             "pos_divergence": 0.1667, "dep_divergence": 0.0 },
  "tier3": { "cross_perplexity":      { "a_given_b": 41.2769, "b_given_a": 117.6457 },
             "conditional_surprisal": { "a_given_b": 3.9932,  "b_given_a": 6.1619 } }
}
```

Errors: `422` for an unknown `feature_names` entry or a mode/texts-length mismatch, `413`
when `TEXTROPY_MAX_TEXT_CHARS` is exceeded, `503` when a required model cannot load.

### `GET /api/v1/features`

Machine-readable catalog — `{name, tier, scope, symmetric, requires}` per feature, generated
from the two registries. This drives the frontend's tier/feature picker, so adding a feature
makes it appear in the UI with no frontend change.

### `GET /api/v1/health`

`{status, ready, model_loading, models}`, where `models` maps each registry key to
`loaded` / `not_loaded` / `error`. Readiness reflects actual model state, not just
process-up. An optional model stuck in `error` does not hold readiness down forever.

---

## Layout

```
app/
├── main.py                  # app factory; lifespan runs the eager warmup
├── core/                    # config.py (pydantic-settings), logging.py
├── api/v1/
│   ├── deps.py              # DI: settings + service singletons
│   └── routers/             # analyze.py, catalog.py, health.py
├── schemas/                 # requests.py, responses.py (Pydantic v2)
├── pipeline/context.py      # AnalysisContext — per-request, in-memory
├── signals/                 # PASS 1 — base.py, *_extractor.py, alignment.py, registry.py
├── features/                # PASS 2 — tier1/, tier2/, tier3/, registry.py
├── comparison/              # PASS 3 — tier1/, tier2/, tier3/, registry.py
├── services/                # analysis_service.py, comparison_service.py — orchestration
└── models_ml/               # per-process model singletons + model_registry.py
```

Tier payloads are typed as open dicts in `schemas/responses.py` on purpose: the key set is
driven by the registries, so adding a feature must not require editing a response schema.

### Adding a feature

1. Write the computer in `features/tierN/` (or `comparison/tierN/`), declaring `name`,
   `tier`, and `requires`.
2. Register it in the corresponding `registry.py`.

That is all. The orchestrator picks up the new requirement, `/api/v1/features` advertises it,
and the response gains a key. If it needs a signal that does not exist yet, add the extractor
in `signals/`, give it a constant in `signals/base.py`, and register it — dependents are found
through `depends_on`, not through edits to the service.

[`ARCHITECTURE.md`](ARCHITECTURE.md) walks through both paths in detail, along with the
invariants a new computer has to respect.

---

## Running

Development — `fastapi dev` serves on `127.0.0.1:8000` with auto-reload:

```bash
uv run fastapi dev app/main.py
```

Production — `fastapi run` binds `0.0.0.0:8000`, disables reload, and enables
`--proxy-headers` for the reverse proxy:

```bash
docker build -t textropy-api . && docker run -p 8000:8000 textropy-api

# or, without Docker:
TEXTROPY_ENVIRONMENT=production uv run fastapi run app/main.py
```

Leave `--workers` unset (the default is one). Models are per-process singletons, so each
extra worker adds another ~1.5–2GB of resident memory (spec §9); scale with async concurrency
instead. Running a single uvicorn process rather than gunicorn also means no worker-kill
timeout, which matters because Tier 3 runs synchronously in-request.

Set `TEXTROPY_EAGER_TIERS='[1,2,3]'` in production so the first Tier 2/3 request does not pay
the model load.

`TEXTROPY_ENVIRONMENT=production` unmounts `/docs`, `/redoc` and `/openapi.json` — the API has
no auth or rate limiting yet, so the interactive docs would otherwise let anyone aim
synchronous Tier 3 requests at the host. The Dockerfile sets it by default.

## Configuration

Environment variables, all prefixed `TEXTROPY_` (see `app/core/config.py`):

| Variable | Default | Notes |
|---|---|---|
| `TEXTROPY_ENVIRONMENT` | `development` | `production` unmounts `/docs`, `/redoc`, `/openapi.json` |
| `TEXTROPY_MODEL_LOADING` | `eager` | `eager` preloads at startup; `lazy` loads on first use |
| `TEXTROPY_EAGER_TIERS` | `[1]` | Tiers preloaded when eager. `[1,2,3]` costs ~1.5–2GB RSS |
| `TEXTROPY_MAX_TEXT_CHARS` | `0` | `0` disables the cap (spec §9 records this as deferred) |
| `TEXTROPY_CORS_ORIGINS` | `["http://localhost:3000"]` | Frontend origin |
| `TEXTROPY_LOG_LEVEL` | `INFO` | |

## Tests

```bash
uv run pytest                      # everything (downloads Tier 2/3 models on first run)
uv run pytest -m "not heavy"       # fast: Tier 1 + pure-logic tests, no model downloads
uv run pytest tests/test_alignment.py -v        # a single file
uv run pytest -k test_cycles_are_detected       # a single test
```

Tests that load transformer weights are marked `heavy`. Prefer `-m "not heavy"` while
iterating on architecture or Tier 1 — the interesting invariants (signal resolution,
alignment, degradation) are all in the fast set.

```bash
uv run ruff check app tests
uv run ruff format app tests
```

## Design decisions

Resolutions of spec ambiguities, kept here so they are not silently "fixed" later:

- **Sentiment and coreference are signals *and* features.** Spec §4 lists them as Pass 1
  extractors; §5 puts them in `features/tier2/`. Both exist: the model call is a signal, so it
  runs once per text no matter how many features read it, and the Tier 2 feature is the thin
  computer that shapes it for the response.
- **Surprisal is per spaCy token, in nats** — consistent with perplexity, and matching the
  spec §6 example values (`ln(24.7) ≈ 3.2` against a shown `mean_surprisal` of 3.1).
- **`pos_divergence` and `dep_divergence` are two computers**, not one, matching the two keys
  in the spec §6 response and letting `feature_names` address them separately.
- **WMD uses POT (`ot.emd2`) over type-level MiniLM vectors**, not gensim. Spec §8 allows
  either; POT avoids gensim's stricter scipy pin, and type-level vectors are truer to WMD's
  classical definition than contextual ones.
- **fastcoref is an optional extra pinned to `transformers<5`.** It reads transformers
  internals removed in v5 (`all_tied_weights_keys`). sentence-transformers accepts
  `transformers>=4.41,<6`, so 4.x satisfies the whole stack.
- **`fastapi[standard-no-fastapi-cloud-cli]`** rather than `fastapi[standard]`: same `fastapi`
  CLI and uvicorn, minus the FastAPI Cloud deploy client (and the sentry-sdk it brings) that a
  self-hosted deployment has no use for.

## MVP limitations

Intentional, per spec §9 — deferred to keep this a single service with no external
dependencies, while keeping the multi-pass structure so each fix is additive:

| Limitation | Deferred fix |
|---|---|
| No cross-request caching — identical texts are reprocessed every request | Redis + content-hash `document_id` |
| Tier 3 runs synchronously in-request | Celery/RQ job + polling endpoint |
| No auth or rate limiting | API key + `slowapi` |
| No input length cap enforced by default | tier-dependent max-length validation |
| Multiple workers multiply model RAM | single worker, or a shared model server |
