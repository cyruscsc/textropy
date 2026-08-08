"""Comparison computer registry (Pass 3)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.comparison.base import ComparisonComputer
from app.comparison.tier1.edit_distance import LevenshteinDistance
from app.comparison.tier1.lcs import LongestCommonSubsequence
from app.comparison.tier1.ngram_overlap import NgramOverlap
from app.comparison.tier1.tfidf_similarity import TfidfCosine
from app.comparison.tier2.distribution_divergence import DepDivergence, PosDivergence
from app.comparison.tier2.semantic_similarity import SemanticSimilarity
from app.comparison.tier2.wmd import WordMoversDistance
from app.comparison.tier3.conditional_surprisal import ConditionalSurprisal
from app.comparison.tier3.cross_perplexity import CrossPerplexity

_COMPUTERS: tuple[ComparisonComputer, ...] = (
    # Tier 1
    LevenshteinDistance(),
    LongestCommonSubsequence(),
    NgramOverlap(),
    TfidfCosine(),
    # Tier 2
    SemanticSimilarity(),
    WordMoversDistance(),
    PosDivergence(),
    DepDivergence(),
    # Tier 3 — asymmetric
    CrossPerplexity(),
    ConditionalSurprisal(),
)

COMPARISON_REGISTRY: dict[str, ComparisonComputer] = {c.name: c for c in _COMPUTERS}


def select(
    tiers: Iterable[int] | None = None,
    feature_names: Iterable[str] | None = None,
) -> list[ComparisonComputer]:
    """Mirror of `features.registry.select` for the comparison registry."""
    if feature_names is not None:
        names = list(feature_names)
        return [COMPARISON_REGISTRY[n] for n in names if n in COMPARISON_REGISTRY]

    wanted = set(tiers or ())
    return [c for c in _COMPUTERS if c.tier in wanted]


def required_signals(computers: Iterable[ComparisonComputer]) -> set[str]:
    """Signals each text needs before Pass 3 can run."""
    return {signal for computer in computers for signal in computer.requires}


def known_names() -> set[str]:
    return set(COMPARISON_REGISTRY)


def catalog() -> list[dict[str, Any]]:
    """Machine-readable entries for `GET /api/v1/features` (spec §6)."""
    return [
        {
            "name": c.name,
            "tier": c.tier,
            "scope": "comparison",
            "symmetric": c.symmetric,
            "requires": list(c.requires),
        }
        for c in _COMPUTERS
    ]
