"""Tier 2 semantic similarity (spec §3.2) — MiniLM document vectors."""

from __future__ import annotations

import numpy as np

from app.comparison.base import ComparisonComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import EMBEDDING_SENTENCE_VECTORS
from app.signals.embedding_extractor import SentenceVectors


class SemanticSimilarity(ComparisonComputer):
    name = "semantic_similarity"
    tier = 2
    symmetric = True
    requires = (EMBEDDING_SENTENCE_VECTORS,)

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> float:
        vectors_a: SentenceVectors = a.get(EMBEDDING_SENTENCE_VECTORS)
        vectors_b: SentenceVectors = b.get(EMBEDDING_SENTENCE_VECTORS)

        if vectors_a.count == 0 or vectors_b.count == 0:
            return 0.0

        # Document vectors are L2-normalised, so this dot product is the cosine.
        similarity = float(np.dot(vectors_a.document_vector, vectors_b.document_vector))
        return round(similarity, 4)
