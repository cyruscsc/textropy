"""Tier 1 sentence features (specs_features.md §4).

Segmentation is `doc.sents` — the same parse every other Tier 1 feature reads, with no
separate sentencizer.

Eight of the eleven computers here re-run `classify_sentences()` over the document. That is
deliberate: a feature computer may not cache across computers (Pass 2 only reads the context),
and classification is O(tokens), the same order as the `word_tokens` scan the lexical group
repeats. If it ever shows up in profiling, the fix is a derived signal in Pass 1 — a design
change under §1.7, not a cache bolted into a computer.
"""

from __future__ import annotations

from typing import Any

from app.features.base import FeatureComputer
from app.features.tier1.stats import mean, ratio, stdev
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC
from app.signals.spacy_extractor import word_tokens

# §4.1. Named rather than inlined so the spec's definitions stay greppable and a mistyped
# label reads as a wrong-looking constant instead of a silently-zero count.

# A coordinated verb needs a subject of its own to head an independent clause.
SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass", "csubj", "csubjpass", "expl"})

# Candidate subordinate clauses. Gated by finiteness below — see `is_finite` and §4.3.
DEPENDENT_CLAUSE_DEPS = frozenset({"advcl", "relcl", "acl", "ccomp", "csubj", "csubjpass", "pcomp"})

FINITE_VERB_TAGS = frozenset({"VBD", "VBP", "VBZ", "MD"})
AUX_DEPS = frozenset({"aux", "auxpass"})

# Class labels. Internal only — the API surface is the feature names, not these.
SIMPLE = "simple"
COMPOUND = "compound"
COMPLEX = "complex"
COMPOUND_COMPLEX = "compound_complex"


def content_sentences(doc: Any) -> list[Any]:
    """Sentence spans holding at least one word token.

    A span of only punctuation or whitespace is not a sentence for counting purposes — `"..."`
    parses as one such span, and letting it through would inflate `sentence_count` and skew
    every mean and stdev built on the same series.
    """
    return [sent for sent in doc.sents if word_tokens(sent)]


def is_finite(token: Any) -> bool:
    """Whether `token` is a finite verb — tensed itself, or carrying a tensed auxiliary."""
    if token.tag_ in FINITE_VERB_TAGS:
        return True
    return any(
        child.dep_ in AUX_DEPS and child.tag_ in FINITE_VERB_TAGS for child in token.children
    )


def count_independent_clauses(sent: Any) -> int:
    """The ROOT, plus each coordinated verb carrying its own subject.

    The subject test is what separates a compound sentence from a compound predicate:
    `The cat sat and the dog barked.` gives `barked` its own `nsubj`, while `He came and went.`
    leaves `went` subjectless. The POS test excludes coordinated nouns — `She likes tea and
    coffee.`
    """
    count = 1  # the sentence ROOT
    for token in sent:
        if token.dep_ != "conj" or token.pos_ not in {"VERB", "AUX"}:
            continue
        if any(child.dep_ in SUBJECT_DEPS for child in token.children):
            count += 1
    return count


def count_dependent_clauses(sent: Any) -> int:
    """Subordinate clauses, restricted to finite ones (§4.3).

    Finiteness is what keeps `He wants to leave early.` simple: its `xcomp` is a phrase, not a
    clause, and a bare label test would file the sentence as complex against every style guide.
    """
    return sum(1 for token in sent if token.dep_ in DEPENDENT_CLAUSE_DEPS and is_finite(token))


def classify_sentence(sent: Any) -> str:
    """One of the four classes in §4.1's table.

    `<= 1` rather than `== 1` on the independent count: the ROOT alone already guarantees one,
    so the comparison is about whether coordination added another.
    """
    independent = count_independent_clauses(sent)
    dependent = count_dependent_clauses(sent)

    if dependent == 0:
        return SIMPLE if independent <= 1 else COMPOUND
    return COMPLEX if independent <= 1 else COMPOUND_COMPLEX


def classify_sentences(doc: Any) -> list[str]:
    """Class of every content sentence, in document order."""
    return [classify_sentence(sent) for sent in content_sentences(doc)]


def sentence_lengths(doc: Any) -> list[int]:
    """Word tokens per content sentence — the series behind mean and stdev."""
    return [len(word_tokens(sent)) for sent in content_sentences(doc)]


class SentenceCount(FeatureComputer):
    name = "sentence_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return len(content_sentences(ctx.get(SPACY_DOC)))


class _SentenceClassCount(FeatureComputer):
    """Shared base: count the sentences of one class.

    The four classes partition `sentence_count` exactly (§4.2), which is why one base with a
    class label serves all four rather than four near-identical bodies.
    """

    tier = 1
    requires = (SPACY_DOC,)
    sentence_class: str

    def compute(self, ctx: AnalysisContext) -> int:
        return classify_sentences(ctx.get(SPACY_DOC)).count(self.sentence_class)


class _SentenceClassDensity(FeatureComputer):
    """Shared base: that class as a share of all sentences."""

    tier = 1
    requires = (SPACY_DOC,)
    sentence_class: str

    def compute(self, ctx: AnalysisContext) -> float:
        classes = classify_sentences(ctx.get(SPACY_DOC))
        return ratio(classes.count(self.sentence_class), len(classes))


class SimpleSentenceCount(_SentenceClassCount):
    name = "simple_sentence_count"
    sentence_class = SIMPLE


class SimpleSentenceDensity(_SentenceClassDensity):
    name = "simple_sentence_density"
    sentence_class = SIMPLE


class CompoundSentenceCount(_SentenceClassCount):
    name = "compound_sentence_count"
    sentence_class = COMPOUND


class CompoundSentenceDensity(_SentenceClassDensity):
    name = "compound_sentence_density"
    sentence_class = COMPOUND


class ComplexSentenceCount(_SentenceClassCount):
    name = "complex_sentence_count"
    sentence_class = COMPLEX


class ComplexSentenceDensity(_SentenceClassDensity):
    name = "complex_sentence_density"
    sentence_class = COMPLEX


class CompoundComplexSentenceCount(_SentenceClassCount):
    name = "compound_complex_sentence_count"
    sentence_class = COMPOUND_COMPLEX


class CompoundComplexSentenceDensity(_SentenceClassDensity):
    name = "compound_complex_sentence_density"
    sentence_class = COMPOUND_COMPLEX


class SentenceLengthMean(FeatureComputer):
    name = "sentence_length_mean"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        return mean(sentence_lengths(ctx.get(SPACY_DOC)))


class SentenceLengthStdev(FeatureComputer):
    name = "sentence_length_stdev"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        return stdev(sentence_lengths(ctx.get(SPACY_DOC)))
