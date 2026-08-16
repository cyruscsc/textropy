"""Tests for the dependency resolution that underpins the multi-pass design (spec §2).

These load no models: the guarantee is a property of the declarations and the topological
sort, so it is testable in isolation.
"""

from __future__ import annotations

import pytest

from app.comparison import registry as comparison_registry
from app.features import registry as feature_registry
from app.signals import registry as signal_registry
from app.signals.base import (
    ALIGNMENT_LM_TO_SPACY,
    LM_TOKEN_LOGPROBS,
    SPACY_DOC,
    SignalExtractor,
)


def test_all_tier1_features_need_only_one_signal():
    """The headline claim of spec §3.1: every Tier 1 feature, one parse.

    Deliberately not pinned to a feature count — adding a Tier 1 feature must not fail
    this test, but adding one that drags in a second signal must.
    """
    computers = feature_registry.select(tiers=[1])
    assert len(computers) > 1, "guard against the selection silently returning nothing"
    assert {c.tier for c in computers} == {1}

    required = feature_registry.required_signals(computers)
    assert required == {SPACY_DOC}
    assert signal_registry.resolve_order(required) == [SPACY_DOC]


def test_resolve_order_includes_transitive_dependencies_once():
    order = signal_registry.resolve_order([ALIGNMENT_LM_TO_SPACY, SPACY_DOC])

    assert len(order) == len(set(order)), "each signal must appear exactly once"
    assert set(order) == {SPACY_DOC, LM_TOKEN_LOGPROBS, ALIGNMENT_LM_TO_SPACY}
    # Dependencies must precede dependents.
    assert order.index(SPACY_DOC) < order.index(ALIGNMENT_LM_TO_SPACY)
    assert order.index(LM_TOKEN_LOGPROBS) < order.index(ALIGNMENT_LM_TO_SPACY)


def test_duplicate_requests_collapse():
    assert signal_registry.resolve_order([SPACY_DOC, SPACY_DOC, SPACY_DOC]) == [SPACY_DOC]


def test_every_declared_signal_is_registered():
    """A feature declaring an unregistered signal is a wiring bug; catch it at test time."""
    declared = feature_registry.required_signals(feature_registry.select(tiers=[1, 2, 3]))
    declared |= comparison_registry.required_signals(comparison_registry.select(tiers=[1, 2, 3]))
    for extractor in signal_registry.SIGNAL_REGISTRY.values():
        declared |= set(extractor.depends_on)

    unknown = declared - set(signal_registry.SIGNAL_REGISTRY)
    assert not unknown, f"unregistered signals declared: {unknown}"


def test_unknown_signal_raises():
    with pytest.raises(signal_registry.UnknownSignalError):
        signal_registry.resolve_order(["nope.not_a_signal"])


def test_cycles_are_detected(monkeypatch):
    class Left(SignalExtractor):
        name = "cycle.left"
        depends_on = ("cycle.right",)

        def extract(self, ctx):  # pragma: no cover - never runs
            raise AssertionError

    class Right(SignalExtractor):
        name = "cycle.right"
        depends_on = ("cycle.left",)

        def extract(self, ctx):  # pragma: no cover - never runs
            raise AssertionError

    patched = dict(signal_registry.SIGNAL_REGISTRY)
    patched.update({"cycle.left": Left(), "cycle.right": Right()})
    monkeypatch.setattr(signal_registry, "SIGNAL_REGISTRY", patched)

    with pytest.raises(ValueError, match="Cyclic signal dependency"):
        signal_registry.resolve_order(["cycle.left"])


def test_required_models_follows_dependencies():
    """Alignment needs no model itself, but its dependencies need spaCy and the LM."""
    models = signal_registry.required_models([ALIGNMENT_LM_TO_SPACY])
    assert models == {"spacy", "causal_lm"}


def test_comparison_tier3_features_are_asymmetric():
    """Spec §3.2 marks exactly the Tier 3 comparisons as direction-dependent."""
    for computer in comparison_registry.select(tiers=[1, 2]):
        assert computer.symmetric is True, computer.name
    for computer in comparison_registry.select(tiers=[3]):
        assert computer.symmetric is False, computer.name


def test_feature_names_override_selects_across_both_registries():
    single = feature_registry.select(feature_names=["word_count", "levenshtein"])
    comparison = comparison_registry.select(feature_names=["word_count", "levenshtein"])

    assert [c.name for c in single] == ["word_count"]
    assert [c.name for c in comparison] == ["levenshtein"]
