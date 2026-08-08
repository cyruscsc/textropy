"""An unavailable *optional* model must degrade one feature, not fail the request.

fastcoref is the only optional model (spec §8 lists it, but it is the least maintained
dependency in the stack). Losing it must not take Tier 2 sentiment or cohesion with it.
"""

from __future__ import annotations

import pytest

from app.models_ml import model_registry
from app.models_ml.model_registry import ModelUnavailableError
from app.pipeline.context import AnalysisContext
from app.services.analysis_service import AnalysisService
from app.signals.base import COREF_CLUSTERS, SPACY_DOC


@pytest.fixture
def service() -> AnalysisService:
    return AnalysisService()


def test_optional_signal_failure_is_recorded_not_raised(service, monkeypatch):
    def explode(self, ctx):
        raise ModelUnavailableError("Failed to load model 'coref': not installed")

    monkeypatch.setattr("app.signals.coreference.CorefExtractor.extract", explode, raising=True)

    ctx = AnalysisContext(text="The cat sat. It purred.", text_index=0)
    service.run_signals(ctx, [SPACY_DOC, COREF_CLUSTERS])

    assert ctx.has(SPACY_DOC), "the healthy signal must still be extracted"
    assert ctx.is_unavailable(COREF_CLUSTERS)
    assert "not installed" in ctx.unavailable_reason(COREF_CLUSTERS)


def test_dependent_feature_reports_unavailable(service, monkeypatch):
    monkeypatch.setattr(
        "app.signals.coreference.CorefExtractor.extract",
        lambda self, ctx: (_ for _ in ()).throw(ModelUnavailableError("coref is gone")),
    )

    ctx = AnalysisContext(text="The cat sat. It purred.", text_index=0)
    computers = service.plan(tiers=[2], feature_names=None)
    service.run_signals(ctx, [s for c in computers for s in c.requires])
    features = service.run_features(ctx, computers)

    assert features["tier2"]["coreference"] == {
        "available": False,
        "reason": "coref is gone",
    }
    # The features that do not depend on coref are unaffected.
    assert "label" in features["tier2"]["sentiment"]
    assert "mean_adjacent_similarity" in features["tier2"]["cohesion"]


def test_required_model_failure_still_raises(service, monkeypatch):
    """spaCy is not optional: if it cannot load, the request must fail loudly."""
    monkeypatch.setattr(
        "app.signals.spacy_extractor.SpacyDocExtractor.extract",
        lambda self, ctx: (_ for _ in ()).throw(ModelUnavailableError("spacy is gone")),
    )

    ctx = AnalysisContext(text="hello world", text_index=0)
    with pytest.raises(ModelUnavailableError):
        service.run_signals(ctx, [SPACY_DOC])


def test_only_coref_is_optional():
    """Guards the invariant the degradation path relies on."""
    registry = model_registry.get_model_registry()

    assert registry.any_optional([model_registry.COREF]) is True
    for name in (
        model_registry.SPACY,
        model_registry.CAUSAL_LM,
        model_registry.SENTENCE_EMBEDDER,
        model_registry.SENTIMENT,
    ):
        assert registry.any_optional([name]) is False, name
