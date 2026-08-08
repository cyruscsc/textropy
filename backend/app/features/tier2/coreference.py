"""Tier 2 coreference feature (spec §3.1)."""

from __future__ import annotations

from typing import Any

from app.features.base import FeatureComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import COREF_CLUSTERS
from app.signals.coreference import CorefClusters


class Coreference(FeatureComputer):
    name = "coreference"
    tier = 2
    requires = (COREF_CLUSTERS,)

    def compute(self, ctx: AnalysisContext) -> dict[str, Any]:
        clusters: CorefClusters = ctx.get(COREF_CLUSTERS)
        return {"chain_count": clusters.chain_count}
