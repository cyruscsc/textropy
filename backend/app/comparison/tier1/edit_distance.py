"""Tier 1 Levenshtein distance (spec §3.2) — raw text, rapidfuzz."""

from __future__ import annotations

from rapidfuzz.distance import Levenshtein

from app.comparison.base import ComparisonComputer
from app.pipeline.context import AnalysisContext


class LevenshteinDistance(ComparisonComputer):
    name = "levenshtein"
    tier = 1
    symmetric = True
    requires = ()  # operates on raw text

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> int:
        return int(Levenshtein.distance(a.text, b.text))
