# Textropy — MVP Technical Specification

## 1. Overview

Textropy is a web app for linguistic text analysis, supporting **single-text** analysis and **double-text** comparison across three feature tiers (increasing computational cost). This document specifies the **MVP scope**: a stateless, no-database, no-cache implementation that still follows a multi-pass architecture to avoid redundant computation *within a single request*.

**Explicitly out of scope for MVP:** persistence/database, server-side caching (Redis), background job queue (Celery/RQ), authentication, rate limiting. History is stored client-side only (browser `localStorage`).

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

## 9. Known MVP Limitations (Accepted Trade-offs)

| Limitation | Consequence | Deferred Fix |
|---|---|---|
| No cross-request caching | Identical texts reprocessed every request | Redis + content-hash `document_id` |
| Tier 3 runs synchronously | Slower response for perplexity/surprisal/cross-perplexity | Celery/RQ async job + polling endpoint |
| No auth/rate limiting | Vulnerable to abuse on public VPS | API key + `slowapi` rate limiting |
| History is client-only | Lost if browser storage is cleared; not shareable across devices | Optional server-side persistence |
| No input length cap enforced yet | Large inputs risk high latency/memory spikes | Tier-dependent max-length validation |
| Models loaded per Gunicorn worker process | Multiple workers multiply RAM usage | Consider single-worker + async concurrency, or shared model server |

These are intentionally deferred — not oversights — to keep the MVP's operational footprint minimal (single Docker service, no external dependencies) while preserving the multi-pass architecture so the upgrade path to the full design (Section referenced in prior discussion) is additive rather than a rewrite.
