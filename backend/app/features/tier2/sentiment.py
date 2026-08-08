"""Tier 2 sentiment feature (spec §3.1).

Thin shaper over the `sentiment.document` signal — the model call happens in Pass 1.
"""

from __future__ import annotations

from typing import Any

from app.features.base import FeatureComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import SENTIMENT_DOCUMENT
from app.signals.sentiment_transformer import DocumentSentiment


class Sentiment(FeatureComputer):
    name = "sentiment"
    tier = 2
    requires = (SENTIMENT_DOCUMENT,)

    def compute(self, ctx: AnalysisContext) -> dict[str, Any]:
        sentiment: DocumentSentiment = ctx.get(SENTIMENT_DOCUMENT)
        return {"label": sentiment.label, "score": round(sentiment.score, 4)}
