# Pipeline internals

A code-level walkthrough of the analysis pipeline: `pipeline/`, `models_ml/`, `signals/`,
`features/` and `comparison/` — what each class does, how data flows between them, and which
invariants hold the design together.

[`README.md`](README.md) is the orientation document — what the service is, how to run it, what
each feature computes. This one assumes you have read it and are about to change something.

---

## Contents

1. [The problem the architecture solves](#1-the-problem-the-architecture-solves)
2. [Layering and dependency direction](#2-layering-and-dependency-direction)
3. [`pipeline/` — the passive container](#3-pipeline--the-passive-container)
4. [`models_ml/` — process-wide singletons](#4-models_ml--process-wide-singletons)
5. [`signals/` — Pass 1](#5-signals--pass-1)
6. [`features/` — Pass 2](#6-features--pass-2)
7. [`comparison/` — Pass 3](#7-comparison--pass-3)
8. [The one deliberate exception: Tier 3 comparison](#8-the-one-deliberate-exception-tier-3-comparison)
9. [Data flow: a single-text request, traced](#9-data-flow-a-single-text-request-traced)
10. [Data flow: a compare request](#10-data-flow-a-compare-request)
11. [Degradation: containing a broken optional dependency](#11-degradation-containing-a-broken-optional-dependency)
12. [The invariants, and what breaks if you violate them](#12-the-invariants-and-what-breaks-if-you-violate-them)
13. [Adding a feature: the two paths](#13-adding-a-feature-the-two-paths)

---

## 1. The problem the architecture solves

Twenty-eight features share a small number of expensive underlying computations:

- All thirteen Tier 1 features need a spaCy parse.
- `perplexity` and `mean_surprisal` both need DistilGPT2 log-probs.
- `cohesion` (single) and `semantic_similarity` (comparison) both need MiniLM sentence vectors.
- `ngram_overlap`, `pos_divergence` and `dep_divergence` need the same spaCy parse the Tier 1
  features already produced.

The conventional fix is a cache keyed on text content. The MVP deliberately has none — no
Redis, no memoization, nothing surviving the response. So redundancy has to be eliminated
**structurally**: by separating *extraction* from *consumption*, and making the extraction step
the only place a model is ever invoked.

That is the whole design. Three passes, one context per text:

```
                    ┌─────────────────────── one HTTP request ───────────────────────┐

  text A ──▶ Pass 1: signals ──▶ AnalysisContext(A) ──▶ Pass 2: features ──▶ results[0]
                                        │
  text B ──▶ Pass 1: signals ──▶ AnalysisContext(B) ──▶ Pass 2: features ──▶ results[1]
                                        │
                                        └──────────▶ Pass 3: comparison ──▶ comparison
                                                     (reads both contexts)
                    └──────────────── contexts discarded on response ────────────────┘
```

---

## 2. Layering and dependency direction

Five packages, and the import arrows only ever point one way:

```
  api/v1/routers/analyze.py          entry point, HTTP shape
        │
  services/{analysis,comparison}_service.py     orchestration — the only place that
        │                                        decides WHAT runs and in WHAT ORDER
        ├──────────────┬──────────────┬─────────────────┐
        ▼              ▼              ▼                 ▼
   signals/       features/     comparison/       pipeline/context.py
   (Pass 1)       (Pass 2)       (Pass 3)          (the shared bag)
        │              │              │
        └──────────────┴──────────────┴──▶ pipeline/context.py
        │
        ▼
   models_ml/         process-wide model singletons
```

Two rules give the architecture its teeth:

1. **`features/` and `comparison/` never import `models_ml/` or call an extractor.** They read
   from a context that is already populated. (One deliberate exception — see §8.)
2. **`pipeline/context.py` imports nothing from the app at all.** It is a passive container; it
   never computes.

Everything else follows from those.

---

## 3. `pipeline/` — the passive container

One file, 62 lines, and its passivity is the point (`pipeline/context.py:1-10` says so
explicitly).

```python
@dataclass
class AnalysisContext:
    text: str
    text_index: int = 0
    _signals: dict[str, Any]      = field(default_factory=dict, repr=False)
    _unavailable: dict[str, str]  = field(default_factory=dict, repr=False)
```

`AnalysisContext` holds **one text** and the signals extracted from it. Its API is deliberately
tiny:

| Method | Role |
|---|---|
| `has(name)` | Already extracted? Used by `run_signals` to skip work |
| `set(name, value)` | Pass 1 writes here — the *only* writer |
| `get(name)` | Passes 2/3 read here; raises `SignalNotAvailableError` on a miss |
| `mark_unavailable(name, reason)` | Optional-model degradation path |
| `is_unavailable(name)` / `unavailable_reason(name)` | Read back by Pass 2 |

Why this makes the once-per-text guarantee *structural*: since the context has no way to compute
anything, a feature computer that wants a signal it did not declare cannot lazily trigger
extraction. It gets an exception instead. `SignalNotAvailableError`'s message says so directly
(`context.py:47-55`):

```
Signal 'spacy.doc' was not extracted for text 0. Available: [...].
A feature computer must declare every signal it reads in its `requires` tuple.
```

That is a wiring bug surfaced loudly at the moment of violation, rather than a silent second
parse. The class docstring states the intent: *"That is what makes 'each signal computed at most
once per text' a structural property rather than a convention a feature could violate."*

Note `_unavailable` is a **separate dict** from `_signals`. An unavailable signal is not "present
with a null value" — it is absent, plus a recorded reason. That distinction is what lets
`run_features` emit a per-feature `{"available": false, "reason": ...}` instead of crashing.

---

## 4. `models_ml/` — process-wide singletons

Five thin loader modules plus a registry. Each loader is a single `load()` function returning the
model, or a small frozen dataclass bundling tokenizer + model + metadata:

| Module | Returns | Notes |
|---|---|---|
| `spacy_model.py` | spaCy `Language` | Re-raises `OSError` as a `RuntimeError` naming the fix (`uv sync`) |
| `causal_lm.py` | `CausalLM(tokenizer, model, max_length)` | Reads `n_positions` (1024 for DistilGPT2); applies `torch.set_num_threads` |
| `sentence_embedder.py` | `SentenceTransformer` | 13 lines, no wrapper needed |
| `sentiment_model.py` | `SentimentModel(tokenizer, model, id2label)` | Lowercases `id2label` so the API emits `"positive"`, not `"POSITIVE"` |
| `coref_model.py` | `FCoref` | Converts `ImportError` into a message naming `--extra coref` |

Every loader imports its heavy library **inside the function body**, not at module top. Same for
`get_model_registry()` (`model_registry.py:145-152`), which imports the five loader modules
lazily with the comment *"Imported here so that merely importing this module does not drag in
torch/spaCy."* This is what lets a Tier 1-only request never touch torch, and what keeps the test
suite's `-m "not heavy"` path fast.

### `ModelRegistry` (`model_registry.py:49`)

State per model is a `_Entry`: `name`, `loader`, `tier`, `optional`, plus mutable `instance` and
`error`.

`get()` (`model_registry.py:64`) is a double-checked lock:

```python
if entry.instance is not None:      # fast path, no lock
    return entry.instance
with self._lock:
    if entry.instance is not None:  # another thread may have won the race
        return entry.instance
    if entry.error is not None:     # cached failure
        raise ModelUnavailableError(entry.error)
    ...
```

Two things worth noticing:

- **The lock is an `RLock`, and it is registry-wide, not per-entry.** Two requests needing two
  *different* unloaded models serialize on the first load. That is an acceptable trade at MVP
  scale (loads happen once), but it is the reason a cold Tier 3 request can block a concurrent
  cold Tier 2 request.
- **Failures are cached, not retried.** A broken optional dependency would otherwise cost a
  multi-second import failure on *every* request. The tradeoff: a transient failure (network blip
  while fetching weights) is permanent for the life of the process.

`warmup(tiers)` (`model_registry.py:96`) drives eager loading at app startup. Its exception
handling is where required/optional first diverges: `ModelUnavailableError` re-raises for a
required model (startup fails loudly), and only logs a warning for an optional one.

Registration wires tier and optionality (`model_registry.py:155-159`):

```python
registry.register(SPACY,             spacy_model.load,       tier=1)
registry.register(SENTIMENT,         sentiment_model.load,   tier=2)
registry.register(SENTENCE_EMBEDDER, sentence_embedder.load, tier=2)
registry.register(COREF,             coref_model.load,       tier=2, optional=True)
registry.register(CAUSAL_LM,         causal_lm.load,         tier=3)
```

`COREF` is the only `optional=True` entry — the single hinge the whole degradation path turns on.
`any_optional(names)` (`model_registry.py:116`) is what `run_signals` calls to decide between
degrade and 503.

---

## 5. `signals/` — Pass 1

### The contract (`signals/base.py`)

```python
class SignalExtractor(ABC):
    name:       ClassVar[str]
    depends_on: ClassVar[tuple[str, ...]] = ()   # other signals
    models:     ClassVar[tuple[str, ...]] = ()   # model registry keys

    @abstractmethod
    def extract(self, ctx: AnalysisContext) -> Any: ...
```

`extract` returns a value; **the orchestrator stores it**, not the extractor. So an extractor
cannot accidentally write under the wrong key, or write two signals.

Signal names are module constants (`base.py:13-19`), so a typo is an `ImportError` at import time
rather than a missing signal at runtime.

### The seven extractors

| Signal | Class | `depends_on` | `models` |
|---|---|---|---|
| `spacy.doc` | `SpacyDocExtractor` | — | `spacy` |
| `lm.token_logprobs` | `LmTokenLogProbsExtractor` | — | `causal_lm` |
| `embedding.sentence_vectors` | `SentenceVectorsExtractor` | `spacy.doc` | `sentence_embedder` |
| `embedding.word_vectors` | `WordVectorsExtractor` | `spacy.doc` | `sentence_embedder` |
| `alignment.lm_to_spacy` | `LmToSpacyAlignmentExtractor` | `spacy.doc`, `lm.token_logprobs` | **none** |
| `sentiment.document` | `SentimentExtractor` | `spacy.doc` | `sentiment` |
| `coref.clusters` | `CorefExtractor` | `spacy.doc` | `coref` |

The dependency graph is shallow — one root (`spacy.doc`), one two-parent node
(`alignment.lm_to_spacy`) — but the resolver is fully general.

### `spacy_extractor.py` — the shared vocabulary

Besides the extractor, this module exports two items that keep terminology consistent across the
whole API:

```python
def word_tokens(doc):                     # punctuation and whitespace excluded
    return [t for t in doc if not t.is_punct and not t.is_space]

CONTENT_POS = frozenset({"NOUN", "PROPN", "VERB", "ADJ", "ADV"})
```

`features/tier1/lexical.py`, `comparison/tier1/ngram_overlap.py` and
`comparison/tier2/distribution_divergence.py` all import `word_tokens`. That is why "word count"
means the same thing in the Tier 1 metric and in the n-gram denominator.

### `lm_extractor.py` — token log-probabilities

```python
@dataclass(frozen=True)
class TokenLogProbs:
    token_ids: list[int]
    offsets:   list[tuple[int, int]]     # char spans into the original text
    logprobs:  list[float | None]        # logprobs[0] is always None
    truncated: bool
```

`logprobs[0] is None` encodes a real fact: the first token has no conditioning context, so it has
no log-probability. Representing that as `None` rather than `0.0` prevents a fabricated surprisal
of 0 nats (i.e. "perfectly predictable") from polluting the mean. `scored` filters it out;
`mean_logprob()` and `perplexity()` build on `scored`.

The `offsets` field is the load-bearing one for Tier 3: it is what makes the alignment signal
possible without a model.

`_token_logprobs` (`lm_extractor.py:65`) is the standard causal-LM shift:

```python
logits    = lm.model(input_ids=input_ids).logits
log_probs = torch.log_softmax(logits[0, :-1, :].float(), dim=-1)   # drop last position
targets   = input_ids[0, 1:]                                        # drop first token
picked    = log_probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
```

Position *i* of the logits predicts token *i+1*, so `picked[i] = log P(ids[i+1] | ids[≤i])`,
length `len(ids) - 1`. The extractor then prepends `None` to realign indices with `token_ids`.

### `alignment.py` — the only model-free extractor

The most interesting piece of pure logic in the codebase, and fully deterministic — unit-testable
without loading DistilGPT2.

The problem: DistilGPT2 emits BPE subwords whose offsets *include the leading space* (`" cat"` →
chars 3–7), while spaCy emits words (`"cat"` → chars 4–7). `align_offsets` (`alignment.py:32`)
reconciles them by interval overlap:

```python
starts = [s for s, _ in spacy_spans]
for lm_idx, (lm_start, lm_end) in enumerate(lm_offsets):
    if lm_end <= lm_start:                       # empty/whitespace-only BPE token
        continue
    pos = max(bisect_left(starts, lm_start + 1) - 1, 0)   # last spaCy token starting ≤ lm_start
    for cand in range(pos, len(spacy_spans)):
        s_start, s_end = spacy_spans[cand]
        if s_start >= lm_end:
            break
        if s_start < lm_end and lm_start < s_end:          # half-open overlap test
            spacy_to_lm[cand].append(lm_idx)
            if lm_to_spacy[lm_idx] is None:
                lm_to_spacy[lm_idx] = cand
```

The `bisect` gives an O(log n) entry point; the forward walk handles a subword spanning multiple
spaCy tokens. The half-open test is what correctly *rejects* the leading-space case: for `"the"`
(0–3) against `" cat"` (3–7), `lm_start < s_end` is `3 < 3` → false, so no spurious overlap. The
result is bidirectional:

```python
spacy_to_lm: list[list[int]]     # word index -> the subwords composing it
lm_to_spacy: list[int | None]    # subword index -> first word it touches
```

### `sentiment_transformer.py`

Resolves a spec tension noted in its docstring: §4 lists sentiment as a Pass 1 extractor, §5 puts
it in `features/tier2/`. Both are true here — the *model call* is the signal (once per text
regardless of readers), the Tier 2 feature is a three-line shaper. It scores **per sentence** in
batches of 16, then aggregates:

```python
totals[label] += score for each sentence         # confidence mass per label
label = max(totals, key=totals.get)
score = mean(scores of sentences carrying that label)
```

Equal weighting per sentence, not length-weighting — the comment explains that length-weighting
would let one long sentence dominate.

### `embedding_extractor.py`

Two signals sharing one model, both depending on `spacy.doc` so segmentation comes from the same
parse Tier 1 uses:

- **`SentenceVectors`** — per-sentence vectors, L2-normalised, plus a `document_vector` computed
  as the renormalised *mean of sentence vectors*. Cheaper than a second `encode()` of the full
  text, and consistent with the per-sentence view.
- **`WordVectors`** — **type-level**, not token-level. It counts content-word lemmas (excluding
  punct/space/stopwords, filtered to `CONTENT_POS`), embeds each distinct type once, and returns
  frequency weights normalised to sum to 1. This is truer to WMD's classical definition over
  static word2vec/GloVe vectors than embedding every occurrence in context would be.

Normalisation matters downstream: because vectors are L2-normalised at extraction, `cohesion` and
`semantic_similarity` compute cosine with a plain dot product, and `wmd` gets cosine distance as
`1 - V_a @ V_b.T`.

### The resolver (`signals/registry.py:50`)

```python
def resolve_order(required: Iterable[str]) -> list[str]:
```

A depth-first topological sort with cycle detection. `visiting` doubles as the cycle path for the
error message:

```python
cycle = " -> ".join([*visiting[visiting.index(name):], name])
raise ValueError(f"Cyclic signal dependency: {cycle}")
```

It returns each signal exactly once, dependencies first. `required_models()` (`registry.py:81`)
layers on top — it resolves the full order and unions the `models` of every extractor in it,
which is how a caller can know the model set for a request without running anything.

---

## 6. `features/` — Pass 2

The contract (`features/base.py:11`) is deliberately narrower than the extractor's:

```python
class FeatureComputer(ABC):
    name:     ClassVar[str]
    tier:     ClassVar[int]
    requires: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def compute(self, ctx: AnalysisContext) -> Any: ...
```

No `models` field — a feature computer has no business touching a model. The docstring states the
rule: *"It must never invoke an extractor or a model itself: doing so would reintroduce the
redundant computation the multi-pass design exists to prevent."*

| Feature | Tier | `requires` | Returns |
|---|---|---|---|
| `word_count` | 1 | `spacy.doc` | `int` |
| `unique_word_count` | 1 | `spacy.doc` | `int` (over `t.lower_`) |
| `lemma_count` | 1 | `spacy.doc` | `int` (over `lemma_forms`) |
| `unique_lemma_count` | 1 | `spacy.doc` | `int` (distinct lemmas) |
| `content_word_count` | 1 | `spacy.doc` | `int` (POS ∈ `CONTENT_POS`) |
| `function_word_count` | 1 | `spacy.doc` | `int` (POS ∉ `CONTENT_POS`) |
| `content_word_density` | 1 | `spacy.doc` | `float`, `0.0` on empty |
| `function_word_density` | 1 | `spacy.doc` | `float`, `0.0` on empty |
| `ttr` | 1 | `spacy.doc` | `float`, `0.0` on empty |
| `infinitive_clause_count` | 1 | `spacy.doc` | `int` (`TO`+`VB` shape) |
| `noun_clause_count` | 1 | `spacy.doc` | `int` (`NOUN_CLAUSE_DEPS`) |
| `adjective_clause_count` | 1 | `spacy.doc` | `int` (`ADJECTIVE_CLAUSE_DEPS`) |
| `adverbial_clause_count` | 1 | `spacy.doc` | `int` (`ADVERBIAL_CLAUSE_DEPS`) |
| `sentiment` | 2 | `sentiment.document` | `{label, score}` |
| `coreference` | 2 | `coref.clusters` | `{chain_count}` |
| `cohesion` | 2 | `embedding.sentence_vectors` | `{mean_adjacent_similarity, sentence_count}` |
| `perplexity` | 3 | `lm.token_logprobs` | `float \| None` |
| `mean_surprisal` | 3 | `lm.token_logprobs`, `spacy.doc`, `alignment.lm_to_spacy` | `float \| None` |

Notice how thin most of them are. `Sentiment.compute` is one `ctx.get` and a dict literal. That
thinness is the evidence the split worked: the expensive part moved to Pass 1, so Pass 2 is pure
shaping.

Tier 1 spans two modules: `tier1/lexical.py` (nine token-level features) and `tier1/clause.py`
(four dependency-label counts). The split follows `specs_features.md`'s feature groups, and the
clause module keeps its label sets as named `frozenset` constants — `NOUN_CLAUSE_DEPS` and
friends — rather than inline strings, so a mistyped label reads as a wrong-looking constant
instead of a count that silently returns zero.

The two lemma computers share a `lemma_forms(doc)` helper local to `tier1/lexical.py`, which
lowercases the lemma of each word token and drops blanks. The filtering lives in the helper
rather than in each computer so that `unique_lemma_count <= lemma_count` holds by
construction — split the filter across two computers and a blank lemma would break the
relationship on exactly the inputs nobody tests. It stays module-local rather than joining
`word_tokens` in `spacy_extractor.py` because nothing outside this module needs it yet;
promote it if a comparison computer ever does.

Two computers encode a `None`-vs-`0.0` judgment worth understanding:

- **`cohesion`** returns `mean_adjacent_similarity: None` for a single sentence. Adjacent
  similarity is *undefined* with one sentence; `0.0` would read as "maximally incohesive".
- **`perplexity`** returns `None` when fewer than two subword tokens exist — nothing was ever
  conditioned.

The Tier 1 ratios go the *other* way for the same kind of undefined case: `ttr`,
`content_word_density` and `function_word_density` all answer `0.0` when there are no word
tokens, via `_density`. That is not an oversight to reconcile — `ttr` set the precedent, the
three share a denominator, and returning null from one Tier 1 ratio while another returns
zero for identical input would be worse than either choice made consistently. Punctuation-only
text ("...") is the only way to reach it, since blank text is rejected at 422.

`cohesion`'s actual math exploits the pre-normalisation:

```python
similarities = np.sum(vectors[:-1] * vectors[1:], axis=1)   # row-wise dot = cosine
```

### `word_surprisals` — the shared Tier 3 primitive

`features/tier3/surprisal.py` exports a **module-level function**, not just a class:

```python
def word_surprisals(doc, logprobs, alignment) -> list[tuple[str, float]]:
    for token_idx, lm_indices in enumerate(alignment.spacy_to_lm):
        token = doc[token_idx]
        if token.is_punct or token.is_space:
            continue
        total, scored = 0.0, False
        for lm_idx in lm_indices:
            value = logprobs.logprobs[lm_idx]
            if value is None:
                continue
            total += -value          # negate: logprob -> surprisal
            scored = True
        if scored:
            out.append((token.text, total))
```

Surprisal per **word** = sum of the surprisals of its subwords (correct: probabilities multiply,
so log-probs add). Words with no scored subword are skipped rather than assigned 0 — the
docstring: *"attributing a surprisal to it would be fabricating one."*

This function being importable is what lets `comparison/tier3/conditional_surprisal.py` reuse it,
so "per word" means exactly the same thing in single-text and comparison mode. That is a
deliberate seam.

**A subtlety worth internalising:** `mean_surprisal` and `ln(perplexity)` are *not* the same
number, despite both being in nats. `perplexity` is `exp(-mean over scored **subwords**)`,
including subwords of punctuation. `mean_surprisal` averages over **words**, excluding
punctuation, with each word's subwords summed. They agree only when every word is a single
subword and there is no punctuation. The nats convention keeps them *comparable* — the docstring
carefully says `exp(mean_subword_surprisal)` — not identical.

### `features/registry.py`

```python
def select(tiers=None, feature_names=None) -> list[FeatureComputer]:
    if feature_names is not None:
        names   = list(feature_names)
        unknown = [n for n in names if n not in FEATURE_REGISTRY]
        return [FEATURE_REGISTRY[n] for n in names if n not in unknown]
    wanted = set(tiers or ())
    return [c for c in _COMPUTERS if c.tier in wanted]
```

Two behaviours that look odd until you see the whole system:

1. **`feature_names` is an override, not a filter within `tiers`.** When present, `tiers` is
   ignored entirely and `meta.tiers_computed` is *derived* from the chosen features. A
   half-selected tier never silently expands.
2. **Unknown names are silently dropped, not raised.** This is what lets one flat `feature_names`
   list address *both* registries — the single-text registry ignores `semantic_similarity`, the
   comparison registry ignores `word_count`. Genuinely bogus names are caught earlier, at the
   router (`analyze.py:36-42`), which validates against the **union** of both registries and
   returns 422.

`required_signals(computers)` (`registry.py:69`) is the two-line function everything hinges on:

```python
return {signal for computer in computers for signal in computer.requires}
```

A **set union over declarations**. Five Tier 1 features each declaring `spacy.doc` collapse to one
entry. No cache, no memoisation — just a set.

`catalog()` (`registry.py:73`) emits the `GET /api/v1/features` entries (`name`, `tier`,
`scope: "single"`, `symmetric: None`, `requires`) that the frontend's picker builds itself from.

---

## 7. `comparison/` — Pass 3

```python
class ComparisonComputer(ABC):
    name:      ClassVar[str]
    tier:      ClassVar[int]
    symmetric: ClassVar[bool] = True
    requires:  ClassVar[tuple[str, ...]] = ()      # per text

    @abstractmethod
    def compute(self, a: AnalysisContext, b: AnalysisContext) -> Any: ...
```

Two differences from `FeatureComputer`: it takes **two** contexts, and it carries a `symmetric`
flag. `requires` means "per text" — the orchestrator ensures *both* contexts have every listed
signal.

| Computer | Tier | Sym | `requires` | Backing |
|---|---|---|---|---|
| `levenshtein` | 1 | ✓ | — | rapidfuzz, raw chars |
| `lcs_length` | 1 | ✓ | — | rapidfuzz `LCSseq`, raw chars |
| `ngram_overlap` | 1 | ✓ | `spacy.doc` | Jaccard over word trigrams |
| `tfidf_cosine` | 1 | ✓ | — | scikit-learn |
| `semantic_similarity` | 2 | ✓ | `embedding.sentence_vectors` | dot of document vectors |
| `wmd` | 2 | ✓ | `embedding.word_vectors` | POT `ot.emd2` |
| `pos_divergence` | 2 | ✓ | `spacy.doc` | scipy JS divergence |
| `dep_divergence` | 2 | ✓ | `spacy.doc` | scipy JS divergence |
| `cross_perplexity` | 3 | ✗ | — | LM, joint scoring |
| `conditional_surprisal` | 3 | ✗ | `spacy.doc` | LM + alignment |

Notes on the ones with real content:

**`tfidf_cosine`** fits a fresh `TfidfVectorizer` on exactly the two texts — *"there is no corpus
to inherit IDF from in a stateless MVP, so the pair is the corpus."* It catches `ValueError`
(empty vocabulary, e.g. both texts pure punctuation) → `0.0`. Rows are L2-normalised by default,
so `matrix[0] @ matrix[1].T` is the cosine.

**`ngram_overlap`** is Jaccard (`|A∩B| / |A∪B|`) over lowercased word trigrams built from
`word_tokens` — the *same* token definition Tier 1 counts with. Empty union → `0.0`, with a
comment noting overlap is really undefined there.

**`wmd`** is the clearest payoff of type-level `WordVectors`:

```python
cost     = 1.0 - (words_a.vectors @ words_b.vectors.T)   # cosine distance
cost     = np.clip(cost.astype(np.float64), 0.0, 2.0)     # kill float noise at 0
distance = ot.emd2(words_a.weights, words_b.weights, cost)
```

Exact optimal transport, not an approximation. Returns `None` (not `0.0`) when either side has no
content words — there is no distribution to transport.

**`distribution_divergence.py`** holds *two* classes over one shared `_js_divergence`. The split
exists so `feature_names` can address `pos_divergence` and `dep_divergence` independently,
matching the two keys in the spec §6 response example. The math aligns both `Counter`s onto a
shared support before normalising, and returns `distance ** 2` — scipy's `jensenshannon` returns
the *distance* (a metric), and squaring recovers the *divergence*, base 2, so the range is a clean
0–1.

---

## 8. The one deliberate exception: Tier 3 comparison

`cross_perplexity` declares `requires = ()` and calls the LM directly. That looks like a violation
of the "never invoke a model in Pass 3" rule. It is not, and `comparison/base.py:20-23` states the
refined rule:

> *"Genuinely joint quantities (Tier 3 cross-perplexity conditions text B on text A) have no
> per-text signal to reuse, so those computers may call a model directly. What stays forbidden is
> recomputing something a per-text signal already holds."*

`P(A | B)` cannot be assembled from `P(A)` and `P(B)`. No per-text signal can hold it, because it
is not a property of one text. The cross-text primitive lives in `signals/lm_extractor.py:98`:

```python
def score_continuation(context_text: str, continuation_text: str) -> TokenLogProbs:
```

It is placed in `signals/` (not `comparison/`) because it is LM plumbing, but it is **not
registered as a signal** — the docstring explains: *"That is not a registered signal because it is
not a property of a single text."*

The mechanics are the trickiest index arithmetic in the codebase:

```python
budget   = max(lm.max_length - len(cont_ids), 0)   # reserve room for the continuation
kept_ctx = ctx_ids[-budget:] if budget else []      # keep the NEWEST context
joint    = [*kept_ctx, *cont_ids]
scores   = _token_logprobs(lm, joint)               # scores[i] -> joint[i+1]
start    = len(kept_ctx) - 1                        # first continuation token
```

The `-1` is because `scores` is already shifted by one. Two consequences:

- **The continuation's first token *is* scored**, unlike the unconditional signal — the context
  supplies its history. That is precisely the conditioning being measured.
- When `budget == 0` (the continuation alone fills the window), `start < 0`, and it falls back to
  the unconditional `[None, *scores]`. The `truncated` flag then reports
  `truncated or len(kept_ctx) < len(ctx_ids)`, so a caller can tell the score covers only part of
  the intended context.

Both Tier 3 comparison computers return `{"a_given_b": ..., "b_given_a": ...}` — the asymmetric
shape. `conditional_surprisal` is the more interesting of the two because it demonstrates
**partial** reuse: it declares `requires = (SPACY_DOC,)` and reuses each text's existing parse,
calling the LM only for the genuinely joint part, then re-running `align_offsets` (cheap,
model-free) against the new conditional offsets and feeding `word_surprisals` — the same function
`mean_surprisal` uses.

---

## 9. Data flow: a single-text request, traced

Request: `{mode: "single", texts: ["..."], tiers: [1, 3]}`

```
POST /api/v1/analyze
  │
  ├─ _validate()                          413 if over max_text_chars; 422 on unknown names
  │
  └─ AnalysisService.analyze_text(text, 0, tiers=[1,3])
       │
       ├─ 1. plan() → feature_registry.select(tiers=[1,3])
       │       → the 13 Tier 1 computers (lexical ×9, clause ×4)
       │         + Perplexity, MeanSurprisal
       │
       ├─ 2. required_signals(computers)  ← SET UNION over `requires`
       │       all 13 Tier 1 features → {spacy.doc}   ── 13 declarations, ONE entry
       │       perplexity             → {lm.token_logprobs}
       │       mean_surprisal         → {lm.token_logprobs, spacy.doc, alignment.lm_to_spacy}
       │       ────────────────────────────────────────────────────────────────
       │       union = {spacy.doc, lm.token_logprobs, alignment.lm_to_spacy}
       │
       ├─ 3. AnalysisContext(text=..., text_index=0)
       │
       ├─ 4. run_signals()  ─ timed as "signals"
       │       resolve_order(union) → topological:
       │         1. spacy.doc             ← no dependencies
       │         2. lm.token_logprobs     ← no dependencies
       │         3. alignment.lm_to_spacy ← depends on both, so it must come last
       │       each extractor runs ONCE; ctx.set(name, value)
       │
       ├─ 5. run_features()  ─ timed as "features"
       │       every computer only calls ctx.get(...)
       │
       └─ SingleTextOutcome(context, features_by_tier, tiers_computed=[1, 3])
              → TextResult(text_index=0, features={"tier1": {...}, "tier3": {...}})
```

The topological order deserves a close look, because the naive reading is wrong. `resolve_order`
iterates `sorted(set(required))`, which is
`['alignment.lm_to_spacy', 'lm.token_logprobs', 'spacy.doc']` — alphabetically, alignment comes
*first*. But `visit('alignment.lm_to_spacy')` immediately recurses into its
`depends_on = (SPACY_DOC, LM_TOKEN_LOGPROBS)` **in declaration order**, appending `spacy.doc` then
`lm.token_logprobs` to the output before appending itself. The sort determines which root is
*visited* first; the `depends_on` tuple order determines the actual emitted order.

Then Pass 2 runs, and `spacy.doc` was parsed exactly once for fifteen features — with no cache
anywhere in the system.

---

## 10. Data flow: a compare request

`ComparisonService.compare` (`comparison_service.py:30`) is only 45 lines because it delegates
rather than reimplements:

```python
computers     = comparison_registry.select(tiers=tiers, feature_names=feature_names)
extra_signals = comparison_registry.required_signals(computers)   # per-text needs of Pass 3

outcomes = [
    self.analysis.analyze_text(text=text, text_index=index,
                               tiers=tiers, feature_names=feature_names,
                               extra_signals=extra_signals,   # ◀── the key move
                               timings=timings)
    for index, text in enumerate((text_a, text_b))
]
```

**`extra_signals` is the mechanism that keeps Pass 3 from double-extracting.** Inside
`analyze_text` (`analysis_service.py:128`):

```python
required = feature_registry.required_signals(computers) | set(extra_signals)
```

So Pass 3's per-text requirements are folded into each text's *single* Pass 1. Concretely, for
`tiers=[1,2]` compare mode:

- Pass 2 needs `{spacy.doc, sentiment.document, coref.clusters, embedding.sentence_vectors}`
- Pass 3 needs `{spacy.doc, embedding.sentence_vectors, embedding.word_vectors}`
- Union per text: `{spacy.doc, sentiment.document, coref.clusters, embedding.sentence_vectors,
  embedding.word_vectors}`

`spacy.doc` and `embedding.sentence_vectors` are each extracted **once per text**, serving both
passes. `ngram_overlap`, `pos_divergence` and `dep_divergence` all read the parse that Tier 1's
word counts already produced.

Then:

```python
ctx_a, ctx_b = outcomes[0].context, outcomes[1].context
for computer in computers:
    comparison_by_tier[f"tier{computer.tier}"][computer.name] = computer.compute(ctx_a, ctx_b)
```

Pass 3 reads two finished contexts. It never re-parses, re-embeds, or reaches for a model except
in the Tier 3 joint case.

`tiers_computed` unions the single-text tiers with the comparison tiers, so a `feature_names`-only
request reports exactly the tiers its chosen features live in.

One detail on `meta.elapsed_ms`: the `timed` context manager (`analysis_service.py:35`)
**accumulates** into a shared dict:

```python
timings[key] = round(timings.get(key, 0.0) + elapsed_ms, 2)
```

The same `timings` dict is threaded through both texts, so in compare mode `"signals"` is the
*combined* Pass 1 time across A and B, `"features"` the combined Pass 2, and `"comparison"` Pass 3
alone. Three keys, not six.

---

## 11. Degradation: containing a broken optional dependency

This is the other cross-cutting mechanism, and it spans all five packages. Trace a missing
`fastcoref`:

```
models_ml/coref_model.load()
    ImportError → RuntimeError("fastcoref is not installed...")
         │
ModelRegistry.get(COREF)
    caches entry.error, raises ModelUnavailableError
         │
signals/coreference.py CorefExtractor.extract() propagates it
         │
services/analysis_service.run_signals()  ◀── the decision point
    except ModelUnavailableError:
        if not registry.any_optional(extractor.models):   # COREF is optional=True
            raise                                          # → 503 for a REQUIRED model
        ctx.mark_unavailable(name, str(exc))               # → degrade
         │
services/analysis_service.run_features()
    missing = [s for s in computer.requires if ctx.is_unavailable(s)]
    if missing:
        {"available": False, "reason": ctx.unavailable_reason(missing[0])}
         │
api/.../analyze.py
    ModelUnavailableError → HTTP 503        (only reached for required models)
```

The result: `coreference` renders one "Unavailable" row, `word_count` / `sentiment` / `cohesion` /
`perplexity` all return normally, and the request is a 200. Whereas a missing spaCy model —
`optional=False` — takes the whole request to 503, which is correct, since nothing would work.

`{"available": false, "reason": ...}` is currently the *only* per-feature failure shape. A feature
computer that raises an exception still fails the entire request; there is no general per-feature
`status`. That is the known gap recorded in the MVP trade-offs.

**A latent edge worth knowing about:** `run_signals` marks a failed signal unavailable but keeps
iterating the resolved order. No extractor currently *depends on* `coref.clusters`, so this never
bites. But if one were added, its `extract()` would call `ctx.get(COREF_CLUSTERS)` →
`SignalNotAvailableError`, which `run_signals` does **not** catch (it catches only
`ModelUnavailableError`) → the whole request 500s instead of degrading. If you ever add an
extractor downstream of an optional-model signal, `run_signals` needs to learn to transitively
propagate unavailability.

---

## 12. The invariants, and what breaks if you violate them

| Invariant | Enforced by | Failure if violated |
|---|---|---|
| A signal is extracted ≤ once per text | Set union + `resolve_order` + `ctx.has()` skip | Silent duplicate model calls; latency doubles with no error |
| A feature reads only declared signals | `ctx.get()` raising `SignalNotAvailableError` | Loud exception naming the undeclared signal |
| Pass 2/3 never invoke models | Convention + `FeatureComputer` having no `models` field | The redundancy the architecture exists to prevent |
| Signal names are typo-proof | Constants in `signals/base.py` | `ImportError` at import, not a runtime miss |
| Optional-model failure degrades; required fails | `any_optional()` at `run_signals` | Either a 503 for a cosmetic feature, or a silent broken metric |
| Asymmetric metrics declare it | `symmetric = False` + `{a_given_b, b_given_a}` | Frontend renders a direction-dependent number as if it were symmetric |

The one to guard hardest is the second. It is the guardrail that makes the first
*self-correcting*: if you write a feature that reaches for an undeclared signal, you get an
exception during development, not a quietly slower endpoint in production. That asymmetry — noisy
on violation, invisible when correct — is what lets the pattern survive contributors who have not
read this document.

`tests/test_signal_resolution.py` asserts deduplication, topological order and cycle detection
directly; `tests/test_optional_model_degradation.py` covers both branches of the degradation
decision. Those invariants are checked, not merely documented.

---

## 13. Adding a feature: the two paths

**Fits an existing signal** — two steps: write the `FeatureComputer` subclass with the right
`requires`, add it to `_COMPUTERS` in `features/registry.py`. The catalog endpoint, tier
selection, `feature_names` override and signal scheduling all pick it up automatically.

**Needs a new signal** — three steps: add the name constant to `signals/base.py`, write the
`SignalExtractor` (declaring `depends_on` and `models`) and register it in `signals/registry.py`,
then write the feature. If it needs a new *model*, add a loader in `models_ml/` and a
`register(...)` line with the right `tier` and `optional`.

In both cases nothing in `services/` changes. The orchestrator knows about registries, not about
individual features — which is the property that makes the pipeline extensible without touching
the code that schedules it.
