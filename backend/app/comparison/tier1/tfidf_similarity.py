"""Tier 1 TF-IDF cosine similarity (spec §3.2) — joint vectorizer over both texts."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer

from app.comparison.base import ComparisonComputer
from app.pipeline.context import AnalysisContext


class TfidfCosine(ComparisonComputer):
    name = "tfidf_cosine"
    tier = 1
    symmetric = True
    requires = ()  # raw text, per spec §3.2

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> float:
        # A joint vectorizer fit on exactly these two texts, per spec: there is no corpus
        # to inherit IDF from in a stateless MVP, so the pair *is* the corpus.
        vectorizer = TfidfVectorizer()
        try:
            matrix = vectorizer.fit_transform([a.text, b.text])
        except ValueError:
            # Raised when the vocabulary is empty (e.g. both texts are pure punctuation).
            return 0.0

        normalised = matrix  # TfidfVectorizer L2-normalises rows by default
        similarity = float((normalised[0] @ normalised[1].T).toarray()[0, 0])
        return round(similarity, 4)
