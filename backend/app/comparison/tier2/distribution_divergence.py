"""Tier 2 POS / dependency distribution divergence (spec §3.2).

Jensen-Shannon **divergence** (the square of scipy's Jensen-Shannon *distance*), base 2, so
values run 0 (identical distributions) to 1 (disjoint).

Split into two computers — `pos_divergence` and `dep_divergence` — matching the two keys in
the spec §6 response example and letting `feature_names` address them independently.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from scipy.spatial.distance import jensenshannon

from app.comparison.base import ComparisonComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC
from app.signals.spacy_extractor import word_tokens


def _distribution(doc, attribute: str) -> Counter:
    return Counter(getattr(token, attribute) for token in word_tokens(doc))


def _js_divergence(dist_a: Counter, dist_b: Counter) -> float | None:
    if not dist_a or not dist_b:
        return None

    # Align both distributions onto a shared support before comparing.
    labels = sorted(set(dist_a) | set(dist_b))
    vec_a = np.array([dist_a.get(label, 0) for label in labels], dtype=np.float64)
    vec_b = np.array([dist_b.get(label, 0) for label in labels], dtype=np.float64)
    vec_a /= vec_a.sum()
    vec_b /= vec_b.sum()

    distance = jensenshannon(vec_a, vec_b, base=2)
    if np.isnan(distance):
        return None
    return round(float(distance**2), 4)


class PosDivergence(ComparisonComputer):
    name = "pos_divergence"
    tier = 2
    symmetric = True
    requires = (SPACY_DOC,)

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> float | None:
        return _js_divergence(
            _distribution(a.get(SPACY_DOC), "pos_"),
            _distribution(b.get(SPACY_DOC), "pos_"),
        )


class DepDivergence(ComparisonComputer):
    name = "dep_divergence"
    tier = 2
    symmetric = True
    requires = (SPACY_DOC,)

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> float | None:
        return _js_divergence(
            _distribution(a.get(SPACY_DOC), "dep_"),
            _distribution(b.get(SPACY_DOC), "dep_"),
        )
