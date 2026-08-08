"""Tier 1 lexical features (spec §3.1).

Every computer here declares only `spacy.doc`, so all five run off one parse regardless of
how many the caller selects.
"""

from __future__ import annotations

from app.features.base import FeatureComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC
from app.signals.spacy_extractor import CONTENT_POS, word_tokens


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


class TypeTokenRatio(FeatureComputer):
    name = "ttr"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        tokens = word_tokens(ctx.get(SPACY_DOC))
        if not tokens:
            return 0.0
        return round(len({t.lower_ for t in tokens}) / len(tokens), 4)
