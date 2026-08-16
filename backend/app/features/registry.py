"""Single-text feature registry (Pass 2).

Selection is by tier, or by an explicit `feature_names` override. `required_signals` is
what the orchestrator unions before running Pass 1.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.features.base import FeatureComputer
from app.features.tier1.clause import (
    AdjectiveClauseCount,
    AdverbialClauseCount,
    InfinitiveClauseCount,
    NounClauseCount,
)
from app.features.tier1.lexical import (
    ContentWordCount,
    ContentWordDensity,
    FunctionWordCount,
    FunctionWordDensity,
    LemmaCount,
    TypeTokenRatio,
    UniqueLemmaCount,
    UniqueWordCount,
    WordCount,
)
from app.features.tier1.sentence import (
    ComplexSentenceCount,
    ComplexSentenceDensity,
    CompoundComplexSentenceCount,
    CompoundComplexSentenceDensity,
    CompoundSentenceCount,
    CompoundSentenceDensity,
    SentenceCount,
    SentenceLengthMean,
    SentenceLengthStdev,
    SimpleSentenceCount,
    SimpleSentenceDensity,
)
from app.features.tier2.cohesion import Cohesion
from app.features.tier2.coreference import Coreference
from app.features.tier2.sentiment import Sentiment
from app.features.tier3.perplexity import Perplexity
from app.features.tier3.surprisal import MeanSurprisal

_COMPUTERS: tuple[FeatureComputer, ...] = (
    # Tier 1 — spaCy doc only
    WordCount(),
    UniqueWordCount(),
    LemmaCount(),
    UniqueLemmaCount(),
    ContentWordCount(),
    FunctionWordCount(),
    ContentWordDensity(),
    FunctionWordDensity(),
    TypeTokenRatio(),
    # Tier 1 — clause (specs_features.md §3)
    InfinitiveClauseCount(),
    NounClauseCount(),
    AdjectiveClauseCount(),
    AdverbialClauseCount(),
    # Tier 1 — sentence (specs_features.md §4)
    SentenceCount(),
    SimpleSentenceCount(),
    SimpleSentenceDensity(),
    CompoundSentenceCount(),
    CompoundSentenceDensity(),
    ComplexSentenceCount(),
    ComplexSentenceDensity(),
    CompoundComplexSentenceCount(),
    CompoundComplexSentenceDensity(),
    SentenceLengthMean(),
    SentenceLengthStdev(),
    # Tier 2
    Sentiment(),
    Coreference(),
    Cohesion(),
    # Tier 3
    Perplexity(),
    MeanSurprisal(),
)

FEATURE_REGISTRY: dict[str, FeatureComputer] = {c.name: c for c in _COMPUTERS}


class UnknownFeatureError(KeyError):
    """`feature_names` referenced a feature that is not registered."""


def select(
    tiers: Iterable[int] | None = None,
    feature_names: Iterable[str] | None = None,
) -> list[FeatureComputer]:
    """Choose the computers to run.

    `feature_names` is an override, not a filter within `tiers`: when supplied it selects
    exactly those features (spec §6 calls it an "explicit subset override"). Names that
    belong to the comparison registry are ignored here so a single `feature_names` list
    can address both registries.
    """
    if feature_names is not None:
        names = list(feature_names)
        unknown = [n for n in names if n not in FEATURE_REGISTRY]
        return [FEATURE_REGISTRY[n] for n in names if n not in unknown]

    wanted = set(tiers or ())
    return [c for c in _COMPUTERS if c.tier in wanted]


def required_signals(computers: Iterable[FeatureComputer]) -> set[str]:
    return {signal for computer in computers for signal in computer.requires}


def catalog() -> list[dict[str, Any]]:
    """Machine-readable entries for `GET /api/v1/features` (spec §6)."""
    return [
        {
            "name": c.name,
            "tier": c.tier,
            "scope": "single",
            "symmetric": None,
            "requires": list(c.requires),
        }
        for c in _COMPUTERS
    ]
