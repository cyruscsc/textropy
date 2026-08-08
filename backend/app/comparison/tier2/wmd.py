"""Tier 2 Word Mover's Distance (spec §3.2) — exact optimal transport via POT.

Spec §8 lists "gensim / POT". POT is used here: the word vectors come from MiniLM rather
than a gensim `KeyedVectors` model, and POT solves the transport problem directly without
pulling in gensim's stricter scipy pin.
"""

from __future__ import annotations

import numpy as np
import ot

from app.comparison.base import ComparisonComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import EMBEDDING_WORD_VECTORS
from app.signals.embedding_extractor import WordVectors


class WordMoversDistance(ComparisonComputer):
    name = "wmd"
    tier = 2
    symmetric = True
    requires = (EMBEDDING_WORD_VECTORS,)

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> float | None:
        words_a: WordVectors = a.get(EMBEDDING_WORD_VECTORS)
        words_b: WordVectors = b.get(EMBEDDING_WORD_VECTORS)

        # No content words on one side: there is no distribution to transport.
        if not words_a.types or not words_b.types:
            return None

        # Cosine distance on L2-normalised vectors, clipped to kill float noise at 0.
        cost = 1.0 - (words_a.vectors @ words_b.vectors.T)
        cost = np.clip(cost.astype(np.float64), 0.0, 2.0)

        distance = ot.emd2(words_a.weights, words_b.weights, cost)
        return round(float(distance), 4)
