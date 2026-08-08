"""Tier 1 longest common subsequence (spec §3.2) — raw text, rapidfuzz."""

from __future__ import annotations

from rapidfuzz.distance import LCSseq

from app.comparison.base import ComparisonComputer
from app.pipeline.context import AnalysisContext


class LongestCommonSubsequence(ComparisonComputer):
    name = "lcs_length"
    tier = 1
    symmetric = True
    requires = ()

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> int:
        # LCSseq.similarity is the length of the longest common subsequence (characters).
        return int(LCSseq.similarity(a.text, b.text))
