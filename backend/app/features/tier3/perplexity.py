"""Tier 3 perplexity (spec §3.1)."""

from __future__ import annotations

from app.features.base import FeatureComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import LM_TOKEN_LOGPROBS
from app.signals.lm_extractor import TokenLogProbs


class Perplexity(FeatureComputer):
    name = "perplexity"
    tier = 3
    requires = (LM_TOKEN_LOGPROBS,)

    def compute(self, ctx: AnalysisContext) -> float | None:
        logprobs: TokenLogProbs = ctx.get(LM_TOKEN_LOGPROBS)
        value = logprobs.perplexity()
        # None when the text has fewer than two subword tokens — nothing was conditioned.
        return None if value is None else round(value, 4)
