"""Tier 1 lexical features (spec §3.1).

Every computer here declares only `spacy.doc`, so all nine run off one parse regardless of
how many the caller selects.
"""

from __future__ import annotations

from typing import Any

from app.features.base import FeatureComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC
from app.signals.spacy_extractor import CONTENT_POS, word_tokens


def lemma_forms(doc: Any) -> list[str]:
    """Lowercased lemmas of the word tokens, in document order.

    Blank lemmas are dropped: spaCy leaves `lemma_` empty for tokens the lemmatizer cannot
    analyse, and counting an empty string as vocabulary would inflate both lemma metrics.
    Filtering here rather than in each computer is what keeps
    `unique_lemma_count <= lemma_count` true by construction.

    Lowercasing matches `unique_word_count`, so the two "unique" metrics differ only in
    lemmatisation and not in case handling.
    """
    lemmas = (token.lemma_.lower() for token in word_tokens(doc))
    return [lemma for lemma in lemmas if lemma]


def _density(matching: int, total: int) -> float:
    """Share of word tokens in a class, rounded like `ttr`.

    A text with no word tokens gives `0.0`, not null. The API rejects blank text, so this
    is only reachable via punctuation-only input ("..."), and `ttr` already answers the
    identical 0/0 with `0.0` — returning null from one Tier 1 ratio and zero from another
    for the same input would be the worse inconsistency. The consequence to know: the two
    densities sum to 1 for any text containing words, and to 0 for one that does not.
    """
    if not total:
        return 0.0
    return round(matching / total, 4)


class WordCount(FeatureComputer):
    name = "word_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return len(word_tokens(ctx.get(SPACY_DOC)))


class UniqueWordCount(FeatureComputer):
    name = "unique_word_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return len({t.lower_ for t in word_tokens(ctx.get(SPACY_DOC))})


class LemmaCount(FeatureComputer):
    """Word tokens carrying a lemma.

    spaCy assigns exactly one lemma per token, so on ordinary prose this equals
    `word_count`; it diverges only where the lemmatizer returns a blank. It is reported
    separately because it is the denominator `unique_lemma_count` is a ratio against —
    reading the pair off `word_count` would be wrong on exactly the inputs where blanks
    appear.
    """

    name = "lemma_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return len(lemma_forms(ctx.get(SPACY_DOC)))


class UniqueLemmaCount(FeatureComputer):
    """Distinct lemmas — vocabulary size after inflection is collapsed.

    Always `<= unique_word_count`: "run"/"runs"/"ran" are three surface types but one
    lemma. The gap between the two is what makes this worth reporting.
    """

    name = "unique_lemma_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return len(set(lemma_forms(ctx.get(SPACY_DOC))))


class ContentWordCount(FeatureComputer):
    name = "content_word_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return sum(1 for t in word_tokens(ctx.get(SPACY_DOC)) if t.pos_ in CONTENT_POS)


class FunctionWordCount(FeatureComputer):
    name = "function_word_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return sum(1 for t in word_tokens(ctx.get(SPACY_DOC)) if t.pos_ not in CONTENT_POS)


class ContentWordDensity(FeatureComputer):
    """`content_word_count / word_count` — lexical density."""

    name = "content_word_density"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        tokens = word_tokens(ctx.get(SPACY_DOC))
        content = sum(1 for t in tokens if t.pos_ in CONTENT_POS)
        return _density(content, len(tokens))


class FunctionWordDensity(FeatureComputer):
    """`function_word_count / word_count` — the complement of `content_word_density`.

    Computed from its own count rather than as `1 - content_word_density`, so the two are
    derived the same way and neither inherits the other's rounding error.
    """

    name = "function_word_density"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        tokens = word_tokens(ctx.get(SPACY_DOC))
        function = sum(1 for t in tokens if t.pos_ not in CONTENT_POS)
        return _density(function, len(tokens))


class TypeTokenRatio(FeatureComputer):
    name = "ttr"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        tokens = word_tokens(ctx.get(SPACY_DOC))
        if not tokens:
            return 0.0
        return round(len({t.lower_ for t in tokens}) / len(tokens), 4)
