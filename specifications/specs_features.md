# Linguistic Feature Specification

The reference for every linguistic feature Textropy exposes — implemented and planned.
Where [`specs_mvp.md`](specs_mvp.md) defines the *architecture* (passes, signals, API shape),
this file defines the *features*: what each one measures, how it is derived from the parse,
what it returns, and how it behaves at the edges.

Anything listed here as **Planned** is a commitment to the definition below, not just to the
name. Implement from this document; if a definition turns out to be wrong or unworkable,
change it here first.

**Status legend** — ✅ Implemented · 📋 Planned · 🔒 Settled by an accepted decision (§11) ·
⚠️ Standing caveat that survives the decision

Every decision this document once left open has been **accepted at its default** (§11). Nothing
here is waiting on an answer; the decisions remain recorded so the reasoning and the rejected
alternatives stay recoverable.

---

## 1. Conventions

These hold for every feature unless its entry says otherwise. They exist so that two
features counting "words" never disagree.

### 1.1 Naming

Feature names are `snake_case` and are the literal response keys under
`results[].features.tier{N}`, and the literal values accepted by `feature_names`. A name is
API surface: renaming one is a breaking change.

### 1.2 What counts as a word

A **word token** is a spaCy token with `is_punct == False` and `is_space == False`. This is
`app/signals/spacy_extractor.word_tokens()`, and it is the single definition of "word" across
the codebase — `word_count`, the n-gram denominator, and every density below all use it.

`word_count` is therefore the denominator for all lexical ratios, and excludes punctuation.

### 1.3 Content vs function words

A word token is **content** if `token.pos_ ∈ {NOUN, PROPN, VERB, ADJ, ADV}`
(`spacy_extractor.CONTENT_POS`), and **function** otherwise. The two sets partition the word
tokens exhaustively, so `content_word_count + function_word_count == word_count` always.

Note this treats `AUX` (is, was, have) as a function word, which is the standard lexical
density convention but differs from tagging schemes that fold AUX into VERB.

### 1.4 Ratios and zero denominators

Every ratio returns `0.0` when its denominator is zero, matching `ttr` and the two lexical
densities (`app/features/tier1/lexical._density`). It never returns `null`.

The reachable zero-denominator cases are: punctuation-only text (`"..."` — blank text is
rejected with 422, so this is the only route to `word_count == 0`), and text with no
punctuation at all (`punctuation_count == 0`).

Returning `null` here was considered and rejected: `ttr` set the precedent, ratios in the same
group share denominators, and one Tier 1 ratio answering `null` while its neighbour answers
`0.0` for identical input is worse than either choice applied consistently. Contrast Tier 2/3,
where `cohesion` and `perplexity` *do* return `null` — there the quantity is undefined rather
than empty, and `0.0` would read as a real measurement.

### 1.5 Means and standard deviations

Several features report a mean and standard deviation over a per-unit series (per sentence,
per noun). For a series of length *n*:

| n | mean | stdev |
|---|---|---|
| 0 | `0.0` | `0.0` |
| 1 | the value | `0.0` |
| ≥2 | arithmetic mean | population stdev |

**Standard deviation is the population form (`ddof=0`, `numpy.std` default).** The sentences
of a document *are* the population being described, not a sample drawn from a larger one, and
`ddof=0` gives a defined `0.0` for a single sentence where the sample form would be `nan`.
Any feature reporting a stdev must pair it with a mean over the identical series.

### 1.6 Numeric output

Floats are rounded to **4 decimal places** at the point of return; counts are plain `int`.
Rounding is presentational only — never round an intermediate that feeds another feature.

### 1.7 Signals

Every feature in Tier 1 requires exactly one signal, `spacy.doc`. This is load-bearing: it is
what keeps the whole tier on a single parse regardless of how many features are selected. A
proposed Tier 1 feature that needs a second signal is not a Tier 1 feature — raise it as a
design change rather than adding the dependency quietly.

---

## 2. Tier 1 — Lexical ✅

All nine are implemented in `app/features/tier1/lexical.py`.

| Feature | Definition | Type |
|---|---|---|
| `word_count` | Count of word tokens (§1.2) | `int` |
| `unique_word_count` | Distinct lowercased surface forms (`token.lower_`) | `int` |
| `lemma_count` | Word tokens carrying a non-blank lemma | `int` |
| `unique_lemma_count` | Distinct lowercased lemmas | `int` |
| `content_word_count` | Word tokens with `pos_ ∈ CONTENT_POS` | `int` |
| `function_word_count` | Word tokens with `pos_ ∉ CONTENT_POS` | `int` |
| `content_word_density` | `content_word_count / word_count` | `float` |
| `function_word_density` | `function_word_count / word_count` | `float` |
| `ttr` | `unique_word_count / word_count` | `float` |

**Guaranteed relationships.** `content_word_count + function_word_count == word_count`;
`content_word_density + function_word_density == 1.0` for any text containing words, `0.0`
otherwise; `unique_lemma_count <= unique_word_count`, since lemmatisation merges surface types
and never splits them.

**On `lemma_count`.** spaCy assigns exactly one lemma per token, so this equals `word_count` on
ordinary prose and diverges only where the lemmatizer returns a blank string. It is retained as
the explicit denominator for `unique_lemma_count` rather than as an independent measurement. If
a lemma-level TTR is wanted later, `unique_lemma_count / lemma_count` is the ratio to add — and
it is the reason `lemma_count` is worth keeping as a separate key.

---

## 3. Tier 1 — Clause ✅

Implemented in `app/features/tier1/clause.py`; tests in `tests/test_clause_features.py`.

All four count clause *instances across the whole text*, not per sentence. Each is the number
of tokens in the document matching a dependency-label predicate. The label sets are the module
constants `NOUN_CLAUSE_DEPS`, `ADJECTIVE_CLAUSE_DEPS` and `ADVERBIAL_CLAUSE_DEPS`; the
infinitive predicate is `is_infinitive_clause()`.

| Feature | Counts tokens where | Type |
|---|---|---|
| `infinitive_clause_count` | the token is a bare-infinitive verb (`tag_ == "VB"`) with an `aux` child tagged `TO` | `int` |
| `noun_clause_count` | `dep_ ∈ {ccomp, csubj, csubjpass, pcomp}` | `int` |
| `adjective_clause_count` | `dep_ ∈ {relcl, acl}` | `int` |
| `adverbial_clause_count` | `dep_ == advcl` | `int` |

### 3.1 Why these labels

Verified against `en_core_web_sm`; each was confirmed on a real parse rather than taken from
the label inventory:

- **Infinitive** — `He wants to leave early.` → `leave`/`VB` with `to`/`TO` as an `aux` child.
  Keying on the token's own dep label would not work, because an infinitive clause surfaces
  under several: `xcomp` here, but `csubj` in `To err is human.` The `TO`+`VB` shape is
  invariant across both.
- **Noun clause** — a clause filling a nominal slot. `ccomp` (`She said that he was tired.`),
  `csubj`/`csubjpass` (`To err is human.`), `pcomp` (`He insisted on leaving early.`).
- **Adjective clause** — `relcl` is the finite relative clause; `acl` is the non-finite
  participial modifier (`The book written by Tolkien…`), traditionally a reduced relative.
  Both modify a nominal, so both count.
- **Adverbial clause** — `advcl` (`She smiled when he arrived.`).

### 3.2 ⚠️ The categories overlap

**These four counts do not partition the clauses of a text, and must not be presented as if
they do.** `To err is human.` contains one clause that is both infinitive (`TO`+`VB`) and
nominal (`csubj`), and it increments both counters. `He wants to leave early.` increments
`infinitive_clause_count` while its `xcomp` label appears in none of the other three sets.

Two consequences for implementation and UI:

1. Do not add a "total clause count" derived by summing these four, and do not build densities
   over their sum.
2. 🔒 The `xcomp` label is deliberately absent from `noun_clause_count` (**Decision 1,
   accepted**). Non-finite complements (`wants to leave`, `saw him run`) are covered by
   `infinitive_clause_count` where infinitival, and are otherwise not counted. The rejected
   alternative was adding `xcomp` to the noun-clause set, which counts more clauses at the cost
   of heavier overlap with `infinitive_clause_count` — most infinitival `xcomp` tokens would
   then increment both.

### 3.3 ⚠️ Known parse hazard: semicolons

`The cat sat; the dog barked.` parses with `sat` as a **`ccomp`** of `barked`, so a
semicolon-joined compound sentence silently increments `noun_clause_count`. This is a parser
artifact, not a definitional problem, and it also affects sentence classification (§4.3).

🔒 **Decision 2, accepted: not special-cased.** The counts carry the parser's reading, noise
included. The rejected alternative was detecting the shape — a `ccomp` separated from its head
by a `;` token — and reclassifying it as coordination. That was declined because it puts a
hand-written syntactic rule in front of the parser for one punctuation mark, which invites the
same treatment for every other construction the model gets wrong, and because the corrected
number would no longer be reproducible from the parse the rest of the tier reports.

The caveat stands regardless of the decision: semicolon-heavy prose will read as more
subordinated than it is. It belongs in the §10 disclosure.

---

## 4. Tier 1 — Sentence ✅

Implemented in `app/features/tier1/sentence.py`; tests in `tests/test_sentence_features.py`.
Sentence segmentation is `doc.sents`, i.e. the same parse; no separate sentencizer.

The classifier is `classify_sentence()`, built from `count_independent_clauses()` and
`count_dependent_clauses()`; the label sets are the module constants `SUBJECT_DEPS`,
`DEPENDENT_CLAUSE_DEPS` and `FINITE_VERB_TAGS`. Ratios, means and stdevs come from
`app/features/tier1/stats.py`, which is the single implementation of §1.4–1.6.

| Feature | Definition | Type |
|---|---|---|
| `sentence_count` | `len(list(doc.sents))`, empty sentences excluded | `int` |
| `simple_sentence_count` | Sentences classified simple (§4.1) | `int` |
| `simple_sentence_density` | `simple_sentence_count / sentence_count` | `float` |
| `compound_sentence_count` | Sentences classified compound | `int` |
| `compound_sentence_density` | `compound_sentence_count / sentence_count` | `float` |
| `complex_sentence_count` | Sentences classified complex | `int` |
| `complex_sentence_density` | `complex_sentence_count / sentence_count` | `float` |
| `compound_complex_sentence_count` | Sentences classified compound-complex — **added, see §4.2** | `int` |
| `compound_complex_sentence_density` | `compound_complex_sentence_count / sentence_count` | `float` |
| `sentence_length_mean` | Mean word tokens (§1.2) per sentence | `float` |
| `sentence_length_stdev` | Population stdev of the same series (§1.5) | `float` |

An "empty sentence" is a `doc.sents` span with zero word tokens — a span of only punctuation or
whitespace. Excluding them keeps `sentence_count` from being inflated by `"..."` and keeps it
consistent with the sentence series used by every mean and stdev here.

### 4.1 Classification algorithm

For each sentence, compute two sets of tokens.

**Independent clauses.** The sentence ROOT, plus every token that is

- `dep_ == "conj"`, and
- `pos_ ∈ {VERB, AUX}`, and
- has a subject of its own — a child with `dep_ ∈ {nsubj, nsubjpass, csubj, csubjpass, expl}`.

The subject requirement is what separates a compound sentence from a compound predicate:
`The cat sat and the dog barked.` gives `barked` its own `nsubj` (two independent clauses),
whereas `He came and went.` leaves `went` subjectless (one). `She likes tea and coffee.` is
excluded by the POS test, since the `conj` there is a noun.

**Dependent clauses.** Tokens with `dep_ ∈ {advcl, relcl, acl, ccomp, csubj, csubjpass, pcomp}`
that are **finite**, where finite means `tag_ ∈ {VBD, VBP, VBZ, MD}` or the token has an
`aux`/`auxpass` child with such a tag.

Then classify:

| Independent | Dependent (finite) | Class |
|---|---|---|
| 1 | 0 | simple |
| ≥2 | 0 | compound |
| 1 | ≥1 | complex |
| ≥2 | ≥1 | compound-complex |

### 4.2 Why compound-complex was added

The draft listed simple, compound and complex only. Those three do not cover the sentence
space: `Because it rained, the game was cancelled and we went home.` has two independent
clauses *and* a dependent one, and it parses exactly that way (`advcl` + a subject-bearing
`conj`). Without a fourth class such a sentence must be either misfiled or dropped, and in
either case the three densities stop summing to 1.

With the fourth class, **the four counts partition `sentence_count` exactly, and the four
densities sum to 1.0** whenever `sentence_count > 0`. That invariant is worth an extra key, and
is the property to assert in tests.

### 4.3 🔒 Why finiteness gates the dependent set

Traditional grammar calls a sentence complex when it contains a subordinate *clause* — a
subject plus a finite verb. Non-finite complements are phrases: `He wants to leave early.` is a
simple sentence in every style guide, but its `xcomp` would make it "complex" under a naive
label test, and participial `acl` would do the same to `The book written by Tolkien sold well.`

Hence: the clause counts in §3 use the broad label set (they are counting clause-like
structures), and sentence classification uses the finite subset (it is applying a grammatical
category). The two answering differently about the same sentence is intended, and the
implementation should not "fix" it by unifying them.

Note the semicolon hazard from §3.3 lands here too: `The cat sat; the dog barked.` classifies
as **complex** rather than compound, because the parser makes the first clause a `ccomp`.

---

## 5. Tier 1 — Punctuation ✅

Implemented in `app/features/tier1/punctuation.py`; tests in
`tests/test_punctuation_features.py`. This is the one group whose denominator is *not*
`word_count`, and the one whose tokens every other Tier 1 group excludes (§1.2).

Unlike §3, §4 and §6 this group reads tags rather than parse structure, so it sits outside the
§11.1 disclosure scope — with the ellipsis caveat in §5.1.1 as its own local qualification.

| Feature | Definition | Type |
|---|---|---|
| `punctuation_count` | Tokens with `is_punct == True` | `int` |
| `internal_punctuation_count` | Punctuation tokens that are not terminal | `int` |
| `internal_punctuation_ratio` | `internal_punctuation_count / punctuation_count` | `float` |
| `terminal_punctuation_count` | Punctuation tokens with `tag_ == "."` | `int` |
| `terminal_punctuation_ratio` | `terminal_punctuation_count / punctuation_count` | `float` |

### 5.1 The terminal test

`tag_ == "."` is the discriminator. Verified against the model: `.`, `!` and `?` all receive
it, while `,` gets `,`, and `;`, `:` and `--` all get `:`. Brackets get `-LRB-` / `-RRB-`, and
opening and closing quotes get their own distinct tags.

Matching on the token's text instead would need an open-ended character list. Do not use
`is_sent_end`, which is true of the last token of a sentence whether or not it is punctuation.

Internal punctuation is defined as the complement (`is_punct and tag_ != "."`), so the two
counts partition `punctuation_count` and the two ratios sum to 1.0 whenever any punctuation is
present. This makes quotes, brackets and dashes internal, which is the intended reading.

### 5.1.1 ⚠️ Correction: ellipsis is not reliably terminal

An earlier draft of this section claimed `...` also receives `.`. **That is wrong**, and it was
wrong because it generalised from a single verified example. Re-checked across contexts:

| Text | tag on `...` |
|---|---|
| `Stop! Really? Yes... Maybe -- perhaps.` | `.` |
| `Yes...` | `:` |
| `Yes... Maybe.` | `:` |
| `Wait... what?` | `:` |
| `He paused... then left.` | `:` |
| `...` | `:` |

`...` is tagged `:` in most contexts and `.` in some — a statistical tagger's output on the same
three characters, not a rule. So **an ellipsis usually counts as internal punctuation, but not
always**, and the same text can classify differently depending on its neighbours.

The definition above is unchanged: `tag_ == "."` remains the test, and `is_terminal_punctuation`
in the module carries this caveat. Two alternatives were considered and not taken, because
either is a definitional change rather than a fix:

- **Treat `...` as terminal by text match.** Contradicts the reason the tag test was chosen, and
  would wrongly mark the mid-sentence `He paused... then left.` as terminal.
- **Treat `...` as internal by text match.** More predictable, but overrides the tagger in the
  cases where it is right, and still hard-codes one character sequence.

If the inconsistency proves to matter in practice, it belongs in §11 as a new decision with the
alternatives above — not as a quiet change to the predicate.

### 5.2 Correction to the draft

The draft defined `terminal_punctuation_ratio` as *"internal punctuation count / punctuation
count"* — a copy-paste of the line above it, which would have shipped two identically-valued
keys under different names. The numerator is the terminal count, as above.

---

## 6. Tier 1 — Complexity ✅

Implemented in `app/features/tier1/complexity.py`; tests in
`tests/test_complexity_features.py`. Three mean/stdev pairs, each over a different series.
Every stdev follows §1.5, via `tier1/stats.py`.

Per-unit values (`mean_dependency_distance`, `tree_depth`, `phrasal_elaboration`) are returned
unrounded; only the aggregating mean/stdev round, per §1.6.

| Feature | Series | Type |
|---|---|---|
| `mdd_mean` | Per-sentence mean dependency distance | `float` |
| `mdd_stdev` | Population stdev of that series | `float` |
| `dependency_depth_mean` | Per-sentence parse-tree depth | `float` |
| `dependency_depth_stdev` | Population stdev of that series | `float` |
| `phrasal_elaboration_mean` | Per-**noun** dependent count | `float` |
| `phrasal_elaboration_stdev` | Population stdev of that series | `float` |

Note the third pair's series is per noun, not per sentence — its `n` is the number of nouns in
the document, and a text with no nouns yields `0.0` for both.

### 6.1 Mean dependency distance

For one sentence, over every token that is not the sentence ROOT:

```
dependency_distance(token) = abs(token.i - token.head.i)
MDD(sentence)              = mean(dependency_distance(t) for t in sentence if t.dep_ != "ROOT")
```

Distances are measured in **token positions including punctuation**, because `token.i` is an
index into the doc. A sentence with one token (or only a root) has no arcs; its MDD is `0.0`.

🔒 **Decision 3, accepted: punctuation arcs are included.** Every non-ROOT token contributes an
arc, `punct` included. The rejected alternative was excluding them, on the grounds that
punctuation often attaches to a distant head and inflates the measure — a real effect, but
excluding it makes the denominator disagree with `token.i`-based distances and puts this metric
out of step with the published MDD literature, which measures over the full arc set. Revisiting
changes every published number.

### 6.2 Dependency tree depth

Depth of the sentence's dependency tree, measured in edges: the ROOT sits at depth 0, its
children at 1, and the feature takes the maximum over all tokens.

```
depth(token) = 0 if token.dep_ == "ROOT" else depth(token.head) + 1
tree_depth(sentence) = max(depth(t) for t in sentence)
```

Implement iteratively or with memoisation — a recursive walk per token is O(n·depth) and will
be visibly slow on long sentences. Punctuation tokens are included; they are leaves and cannot
increase the maximum unless the parse is degenerate.

### 6.3 Phrasal elaboration

For each token with `pos_ ∈ {NOUN, PROPN}`, the number of its **direct dependents**, excluding
punctuation children:

```
elaboration(noun) = len([c for c in noun.children if not c.is_punct])
```

Verified: in `The very tall man with a hat…`, `man` has three dependents — `The`/det,
`tall`/amod, `with`/prep. `very` is *not* counted, because it modifies `tall` and is therefore
a grandchild.

🔒 **Decision 4, accepted: direct children.** Direct children measure how many modifiers a noun
takes; subtree size (`len(list(noun.subtree))`) measures how much material hangs off it. They
answer different questions and give very different numbers on the same text. Direct children
was chosen because "phrasal elaboration" names the modification a head attracts, and because
subtree size double-counts — material under a noun's relative clause is already reflected in
that clause's own tokens. If subtree size is wanted later it is a **new feature under a new
name**, not a redefinition of this one.

---

## 7. Tier 2 ✅

| Feature | Definition | Signal | Type |
|---|---|---|---|
| `sentiment` | Document polarity from DistilBERT SST-2, aggregated from per-sentence scores by summed confidence mass | `sentiment.document` | `{label, score}` |
| `coreference` | Number of coreference chains found by fastcoref | `coref.clusters` | `{chain_count}` |
| `cohesion` | Mean cosine similarity between adjacent sentence embeddings | `embedding.sentence_vectors` | `{mean_adjacent_similarity, sentence_count}` |

`cohesion` returns `mean_adjacent_similarity: null` for a single sentence — the quantity is
undefined with nothing to compare against, and `0.0` would read as "maximally incohesive". This
is the §1.4 exception, and it is intentional.

`coreference` is the only feature backed by an optional dependency. Without the `coref` extra
installed it returns `{"available": false, "reason": ...}` and every other feature keeps
working.

---

## 8. Tier 3 ✅

| Feature | Definition | Signal | Type |
|---|---|---|---|
| `perplexity` | `exp(−mean log P)` over scored DistilGPT2 subword tokens | `lm.token_logprobs` | `float \| null` |
| `mean_surprisal` | Mean per-**word** surprisal in nats | `lm.token_logprobs`, `spacy.doc`, `alignment.lm_to_spacy` | `float \| null` |

`mean_surprisal` is reported per spaCy word, not per subword: the alignment signal maps BPE
subwords onto words by character offset and their surprisals are summed (log-probabilities add).
Words whose subwords are all unscored are skipped — the first token of a text has no
conditioning context, and giving it a surprisal would be inventing one.

**`mean_surprisal` is not `ln(perplexity)`.** Perplexity averages over subwords including
punctuation; surprisal averages over words excluding it. Both are in nats, which makes them
comparable, not identical. Do not "reconcile" them.

---

## 9. Implementation notes

### 9.1 Module layout

Tier 1 is split by feature group, one module per §-heading above:

```
app/features/tier1/
├── lexical.py       ✅ 9 features
├── clause.py        ✅ 4
├── stats.py         ✅ ratio / mean / stdev (§1.4-1.6)
├── sentence.py      ✅ 11
├── punctuation.py   ✅ 5
└── complexity.py    ✅ 6
```

All 35 are implemented. Each computer declares `requires = (SPACY_DOC,)` and is added to `_COMPUTERS` in
`app/features/registry.py`. Nothing in `services/` changes, and `/api/v1/features` advertises
new features automatically — the frontend picker builds itself from that endpoint, so no
frontend change is needed either.

A computer in the clause, sentence or complexity groups must also set `approximate = True`,
which is what carries the §11.1 disclosure into the UI. It is the one piece of metadata a new
Tier 1 feature has to get right by hand; the pinning test in §9.4 is what catches it.

### 9.2 Shared helpers

Sentence-level features need a shared "sentences with at least one word token" helper, and
several groups need per-sentence series. Put shared predicates where their consumers are: local
to a module while one module uses them, promoted to `signals/spacy_extractor.py` (alongside
`word_tokens` and `CONTENT_POS`) only once a second module needs them.

`content_sentences()` has now made that move: §6 became its second consumer, so it lives in
`signals/spacy_extractor.py` beside `word_tokens` and `CONTENT_POS`, and one definition of "a
sentence" serves both groups. The numeric conventions took the same path earlier:
`tier1/stats.py` exists because §4 needed both a ratio and mean/stdev, and `lexical.py` had a
private ratio of its own — two implementations of §1.4 is exactly the drift these conventions
exist to prevent, so the lexical copy was folded into the shared one.

Clause-label predicates in particular should be named constants, not inline label strings —
`ADJECTIVE_CLAUSE_DEPS = frozenset({"relcl", "acl"})` — so the §3 definitions are greppable and
a typo is a wrong-looking constant rather than a silently-zero count.

### 9.3 Cost

All 35 Tier 1 features read the same `spacy.doc`. Going from 5 features to 35 added **zero**
model invocations and still costs one parse per request, which is the property the multi-pass
architecture exists to preserve. See [`../backend/ARCHITECTURE.md`](../backend/ARCHITECTURE.md).

### 9.4 Testing

Parser-dependent features need fixtures that pin *both* the intended reading and the parse
producing it. Assert against sentences verified in the model, not sentences that ought to
parse a given way — see §10.

Invariants worth asserting directly, since they catch definitional drift that per-feature
tests miss:

- `content_word_count + function_word_count == word_count`
- the four sentence-class counts sum to `sentence_count`
- the four sentence-class densities sum to 1.0 (within rounding) when `sentence_count > 0`
- `internal_punctuation_count + terminal_punctuation_count == punctuation_count`
- every ratio is `0.0` when its denominator is 0
- every stdev is `0.0` for a single-element series
- MDD, tree depth and phrasal elaboration agree with hand-computed arcs on a known parse
- the catalog's `approximate` set is exactly §3 ∪ §4 ∪ §6 — pinned rather than spot-checked,
  since §11.1's disclosure is scoped by group and a new feature on the wrong side of the line
  would otherwise reach the results pane with the wrong caveat

---

## 10. ⚠️ Parser reliability

`en_core_web_sm` is the smallest English pipeline, and the clause, sentence and complexity
groups depend on parse *structure* far more than the lexical group depends on POS tags. Two
short, unremarkable sentences were mis-parsed while verifying this document:

| Sentence | Expected | `en_core_web_sm` gives |
|---|---|---|
| `The man who arrived late apologised.` | ROOT `apologised`, `relcl` on `man` | ROOT is `man`; `apologised` tagged `JJ`, attached `advcl` |
| `The book written by Tolkien sold well.` | ROOT `sold`, `acl` on `book` | ROOT is `book`; `sold` attached as a second `acl` |

Both would be counted wrongly by §3 and §4 — the first inflates `adverbial_clause_count`, and
both distort sentence classification.

Three options were weighed:

1. **Accept and disclose** — keep `en_core_web_sm`, and surface parser-derived features in the
   UI with a note that they are approximate. Cheapest, and preserves the single-model footprint.
2. **Upgrade the model** — `en_core_web_md` or `en_core_web_trf` parses these correctly at real
   cost in image size and latency. `trf` in particular would move Tier 1 off "cheap and fast",
   which is the tier's defining property.
3. **Split the tier** — leave lexical features on `sm` and promote structural features to Tier 2
   with a larger parser as a second signal. Honest about cost, but breaks §1.7's one-signal
   guarantee and is the largest architectural change of the three.

🔒 **Decision 5, accepted: option 1 — accept and disclose.** Tier 1 stays on `en_core_web_sm`,
and the clause, sentence and complexity groups ship as approximate measures.

Accepting option 1 is what makes option 2 cheap to reach later: nothing in §3–6 depends on
*which* parser produced the parse, so upgrading the model is a config change plus a re-baseline
of the test fixtures, not a redesign. Option 3 is the one that gets more expensive with time,
since it breaks the one-signal guarantee.

The accepted option carries two obligations, tracked in §11.1. Neither is optional: the
standing rule is that structural metrics from a parser known to misread ordinary relative
clauses must not be presented as authoritative without the disclosure.

---

## 11. Decision record

**All five decisions are accepted, each at the default that was proposed.** None is open; there
is nothing here for an implementer to resolve. They are kept as a record rather than dissolved
into the definitions above so that a later reader can see what was chosen, what was turned down,
and what revisiting would cost — the definitions alone would show only the winner.

| # | Question | Accepted | Rejected alternative | Section |
|---|---|---|---|---|
| 1 | Should `xcomp` count toward `noun_clause_count`? | **No** — infinitives are counted by their own feature | Add `xcomp` to the noun-clause set, accepting heavier overlap | §3.2 |
| 2 | Special-case semicolon-joined clauses mis-parsed as `ccomp`? | **No** — carry the parser's reading, disclose the noise | Detect `ccomp`-across-`;` and reclassify as coordination | §3.3, §4.3 |
| 3 | Include punctuation arcs in MDD? | **Yes** — every non-ROOT token contributes an arc | Exclude `punct` arcs as distance-inflating | §6.1 |
| 4 | Phrasal elaboration: direct children or subtree size? | **Direct children**, punctuation excluded | Subtree size — now reserved for a separately-named feature | §6.3 |
| 5 | Which parser-accuracy option? | **Option 1** — keep `en_core_web_sm`, disclose in the UI | Option 2 (larger model) · Option 3 (promote to Tier 2) | §10 |

### 11.1 Follow-ups created by Decision 5

Accepting option 1 defers cost rather than removing it. Both items below are commitments, not
suggestions, and neither is satisfied by anything in the current codebase:

- **UI disclosure — ✅ satisfied.** Parser-derived features — every feature in §3, §4 and
  §6 — must be presented in the results pane with a visible note that they are approximate.
  The scope is exactly those three groups; the lexical group in §2 needs no caveat, since POS
  tagging on `en_core_web_sm` is materially more reliable than its parsing, and the
  punctuation group in §5 reads tags rather than parse structure (§5's preamble).

  **How it is implemented.** The obligation is scoped by *group*, but the results pane
  renders by value shape and knows nothing about groups — and a hand-maintained list of
  twenty-one names in the frontend would drift the first time a parser-derived feature was
  added. So the scope is published instead: `FeatureComputer.approximate` is a class
  attribute, set on the twenty-one computers in `clause.py`, `sentence.py` and
  `complexity.py`, and `GET /api/v1/features` carries it as a per-feature `approximate`
  boolean. The frontend builds a predicate from that catalog and marks each affected row
  with a `≈` footnote, with the matching note at the foot of any tier section containing
  one. A new parser-derived feature therefore ships with its caveat attached and needs no
  frontend change.

  This keeps §11.1 a genuinely shared obligation: the backend cannot *display* anything, but
  it is the only side that knows which features read the parse, so it declares the scope and
  the frontend discloses it. `tests/test_api_tier1.py::test_catalog_marks_exactly_the_parser_derived_features_approximate`
  pins the set, so a feature landing in the wrong half fails there rather than reaching a
  reader mislabelled.
- **Benchmark before any upgrade.** Compare `en_core_web_sm` against `en_core_web_md` on
  representative inputs, measuring both the accuracy gain on structural features and the cost in
  image size and per-request latency. Decision 5 should not be revisited on the strength of the
  two mis-parses in §10 alone — two sentences are an illustration, not a measurement.

### 11.2 Revisiting

Decisions 1–4 each change published numbers, and the response payload is unversioned, so a
change silently alters what returning clients receive. Any revision therefore lands here first —
amend the row, state what moved and why — before any code changes. Decision 5 is the cheap one
to reverse: §3–6 never name the model, so an upgrade is a config change plus re-baselined test
fixtures.
