"""Tier 1 n-gram overlap (spec §3.2) — word-level Jaccard over the shared spaCy parse."""

from __future__ import annotations

from app.comparison.base import ComparisonComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC
from app.signals.spacy_extractor import word_tokens

# Trigrams: long enough to capture phrasing, short enough to still overlap on short texts.
NGRAM_SIZE = 3


def _ngrams(doc, n: int) -> set[tuple[str, ...]]:
    tokens = [t.lower_ for t in word_tokens(doc)]
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


class NgramOverlap(ComparisonComputer):
    name = "ngram_overlap"
    tier = 1
    symmetric = True
    requires = (SPACY_DOC,)

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> float:
        ngrams_a = _ngrams(a.get(SPACY_DOC), NGRAM_SIZE)
        ngrams_b = _ngrams(b.get(SPACY_DOC), NGRAM_SIZE)

        union = ngrams_a | ngrams_b
        if not union:
            # Both texts are shorter than one n-gram: overlap is undefined, not zero.
            return 0.0
        return round(len(ngrams_a & ngrams_b) / len(union), 4)
