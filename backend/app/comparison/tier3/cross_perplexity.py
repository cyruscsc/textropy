"""Tier 3 cross-perplexity (spec §3.2) — **asymmetric**.

Perplexity of one text when the other is supplied as conditioning context. This is a
genuinely joint quantity: it cannot be assembled from the two texts' unconditional
`lm.token_logprobs`, so it re-invokes the (already-loaded, singleton) LM. Both directions
are computed and returned as `a_given_b` / `b_given_a`.
"""

from __future__ import annotations

import math
from typing import Any

from app.comparison.base import ComparisonComputer
from app.pipeline.context import AnalysisContext
from app.signals.lm_extractor import score_continuation


def _perplexity(context_text: str, target_text: str) -> float | None:
    scores = score_continuation(context_text, target_text)
    mean = scores.mean_logprob()
    if mean is None:
        return None
    return round(math.exp(-mean), 4)


class CrossPerplexity(ComparisonComputer):
    name = "cross_perplexity"
    tier = 3
    symmetric = False
    requires = ()  # scored jointly; no reusable per-text signal exists

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> dict[str, Any]:
        return {
            # a_given_b: perplexity of A when B is the prefix.
            "a_given_b": _perplexity(b.text, a.text),
            "b_given_a": _perplexity(a.text, b.text),
        }
