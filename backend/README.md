# Textropy backend

Stateless multi-pass linguistic text analysis API. Implements the MVP spec in
[`../specifications/specs_mvp.md`](../specifications/specs_mvp.md).

## Setup

Requires [uv](https://docs.astral.sh/uv/). All dependencies live in a project-local `.venv`.

```bash
uv sync                 # base install
uv sync --extra coref   # + fastcoref, enabling the Tier 2 coreference feature
```

`en_core_web_sm` is a declared dependency (pinned by URL in `pyproject.toml`), so no
separate `spacy download` step is needed. The Tier 2/3 transformer weights download from
Hugging Face on first use and are cached under `~/.cache/huggingface`.

## Running

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs`.

```bash
# Tier 1 single-text
curl -s localhost:8000/api/v1/analyze -H 'content-type: application/json' \
  -d '{"mode":"single","texts":["The cat sat on the mat."],"tiers":[1]}' | jq

# All tiers, comparison
curl -s localhost:8000/api/v1/analyze -H 'content-type: application/json' \
  -d '{"mode":"compare","texts":["The cat sat.","A feline rested."],"tiers":[1,2,3]}' | jq

curl -s localhost:8000/api/v1/features | jq   # feature catalog
curl -s localhost:8000/api/v1/health | jq     # liveness + model readiness
```

## Tests

```bash
uv run pytest                      # everything (downloads Tier 2/3 models on first run)
uv run pytest -m "not heavy"       # fast: Tier 1 + pure-logic tests, no model downloads
uv run pytest tests/test_alignment.py -v        # a single file
uv run pytest -k test_cycles_are_detected       # a single test
```

## Lint / format

```bash
uv run ruff check app tests
uv run ruff format app tests
```

## Configuration

Environment variables, all prefixed `TEXTROPY_` (see `app/core/config.py`):

| Variable | Default | Notes |
|---|---|---|
| `TEXTROPY_MODEL_LOADING` | `eager` | `eager` preloads at startup; `lazy` loads on first use |
| `TEXTROPY_EAGER_TIERS` | `[1]` | Tiers preloaded when eager. `[1,2,3]` costs ~1.5–2GB RSS |
| `TEXTROPY_MAX_TEXT_CHARS` | `0` | `0` disables the cap (spec §9 records this as deferred) |
| `TEXTROPY_CORS_ORIGINS` | `["http://localhost:3000"]` | Frontend origin |
| `TEXTROPY_LOG_LEVEL` | `INFO` | |

## Architecture

Three passes over an in-memory `AnalysisContext` per text, discarded when the response is
sent (spec §2):

1. **Pass 1 — signals** (`app/signals/`): spaCy doc, LM token logprobs, embeddings,
   subword alignment, sentiment, coref.
2. **Pass 2 — features** (`app/features/`): single-text features that only *read* the context.
3. **Pass 3 — comparison** (`app/comparison/`): cross-text metrics over both finished contexts.

Each computer declares the signals it needs; `services/analysis_service.py` unions those
declarations, topologically sorts them with their transitive dependencies, and runs each
extractor exactly once. That is what makes "five Tier 1 features, one parse" structural
rather than a convention — there is no cache involved.
`services/comparison_service.py` folds Pass 3's per-text signal needs into each text's
single Pass 1, so a double-text request never extracts the same signal twice.

### Notes on specific choices

- **Sentiment and coreference are signals, not just features.** Spec §4 lists them as Pass 1
  extractors while §5 puts them in `features/tier2/`. Both are implemented: the model call is
  a signal (so it runs once per text regardless of how many features read it) and the Tier 2
  feature is the thin computer that shapes it for the response.
- **Surprisal is per word, in nats.** The alignment signal maps DistilGPT2 subwords onto
  spaCy tokens and sums them, so `mean_surprisal` is per word while staying consistent with
  `perplexity` (`perplexity == exp(mean_subword_surprisal)`).
- **WMD uses POT, not gensim.** Spec §8 allows either. The word vectors come from MiniLM
  rather than gensim `KeyedVectors`, and POT avoids gensim's stricter scipy pin.
- **fastcoref is an optional extra** pinned to `transformers<5`; it reads transformers
  internals that v5 removed. Without the extra, the `coreference` feature returns
  `{"available": false, "reason": ...}` and every other feature is unaffected.

## MVP limitations

Intentional, per spec §9: no cross-request cache, Tier 3 runs synchronously in-request, no
auth or rate limiting, no input length cap enforced by default.
