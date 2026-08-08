"""`coref.clusters` — fastcoref chains (spec §4)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models_ml import model_registry
from app.pipeline.context import AnalysisContext
from app.signals.base import COREF_CLUSTERS, SPACY_DOC, SignalExtractor


@dataclass(frozen=True)
class CorefClusters:
    clusters: list[list[str]]

    @property
    def chain_count(self) -> int:
        return len(self.clusters)


class CorefExtractor(SignalExtractor):
    name = COREF_CLUSTERS
    depends_on = (SPACY_DOC,)
    models = (model_registry.COREF,)

    def extract(self, ctx: AnalysisContext) -> CorefClusters:
        if not ctx.text.strip():
            return CorefClusters(clusters=[])

        model = model_registry.get_model(model_registry.COREF)
        preds = model.predict(texts=[ctx.text])
        if not preds:
            return CorefClusters(clusters=[])

        clusters = [list(cluster) for cluster in preds[0].get_clusters()]
        return CorefClusters(clusters=clusters)
