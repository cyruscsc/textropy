"""Tier 2 cohesion — sentence-to-sentence similarity (spec §3.1)."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.features.base import FeatureComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import EMBEDDING_SENTENCE_VECTORS
from app.signals.embedding_extractor import SentenceVectors


class Cohesion(FeatureComputer):
    name = "cohesion"
    tier = 2
    requires = (EMBEDDING_SENTENCE_VECTORS,)

    def compute(self, ctx: AnalysisContext) -> dict[str, Any]:
        sentence_vectors: SentenceVectors = ctx.get(EMBEDDING_SENTENCE_VECTORS)
        vectors = sentence_vectors.vectors

        # Adjacent similarity is undefined for a single sentence; report null rather than
        # a misleading 0.0 (which would read as "maximally incohesive").
        if vectors.shape[0] < 2:
            return {"mean_adjacent_similarity": None, "sentence_count": int(vectors.shape[0])}

        # Vectors are already L2-normalised, so the dot product is the cosine.
        similarities = np.sum(vectors[:-1] * vectors[1:], axis=1)
        return {
            "mean_adjacent_similarity": round(float(similarities.mean()), 4),
            "sentence_count": int(vectors.shape[0]),
        }
