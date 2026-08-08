"""Single-text orchestration: Pass 1 -> Pass 2 (spec §2).

The ordering here is the whole point of the architecture:

1. Select the feature computers for the requested tiers.
2. Union their *declared* signal requirements.
3. Resolve that union (plus transitive dependencies) into a topological run order.
4. Run each extractor **once**, storing results on the context.
5. Run the feature computers, which only read.

Because step 2 is a set union over declarations, five Tier 1 features requiring
`spacy.doc` produce exactly one parse — without any cache.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.features import registry as feature_registry
from app.features.base import FeatureComputer
from app.models_ml.model_registry import ModelUnavailableError, get_model_registry
from app.pipeline.context import AnalysisContext
from app.signals import registry as signal_registry

logger = get_logger(__name__)

Timings = dict[str, float]


@contextmanager
def timed(timings: Timings, key: str) -> Iterator[None]:
    """Accumulate elapsed milliseconds under `key` (spec §6 `meta.elapsed_ms`)."""
    started = time.perf_counter()
    try:
        yield
    finally:
        timings[key] = round(timings.get(key, 0.0) + (time.perf_counter() - started) * 1000, 2)


@dataclass
class SingleTextOutcome:
    context: AnalysisContext
    features_by_tier: dict[str, dict[str, Any]] = field(default_factory=dict)
    tiers_computed: list[int] = field(default_factory=list)


class AnalysisService:
    """Pass 1 + Pass 2 for one text. Stateless: holds no per-request data."""

    def plan(
        self,
        tiers: Iterable[int] | None,
        feature_names: Iterable[str] | None,
    ) -> list[FeatureComputer]:
        return feature_registry.select(tiers=tiers, feature_names=feature_names)

    def resolve_signals(self, required: Iterable[str]) -> list[str]:
        """Expand a signal requirement set into a deduplicated, dependency-ordered list."""
        return signal_registry.resolve_order(required)

    def run_signals(self, ctx: AnalysisContext, signal_names: Iterable[str]) -> None:
        """Pass 1. Extractors already present on the context are skipped.

        A signal backed by an *optional* model that fails to load is recorded as
        unavailable rather than aborting the request: one stale optional dependency must
        not take down the features that do work.
        """
        registry = get_model_registry()
        for name in self.resolve_signals(signal_names):
            if ctx.has(name):
                continue
            extractor = signal_registry.get_extractor(name)
            logger.debug("Extracting signal %s for text %d", name, ctx.text_index)
            try:
                ctx.set(name, extractor.extract(ctx))
            except ModelUnavailableError as exc:
                if not registry.any_optional(extractor.models):
                    raise
                logger.warning("Signal %s unavailable: %s", name, exc)
                ctx.mark_unavailable(name, str(exc))

    def run_features(
        self,
        ctx: AnalysisContext,
        computers: Iterable[FeatureComputer],
    ) -> dict[str, dict[str, Any]]:
        """Pass 2. Read-only with respect to signals.

        Features whose signals went unavailable report that inline, so the rest of the
        tier is still returned.
        """
        by_tier: dict[str, dict[str, Any]] = {}
        for computer in computers:
            key = f"tier{computer.tier}"
            missing = [s for s in computer.requires if ctx.is_unavailable(s)]
            if missing:
                by_tier.setdefault(key, {})[computer.name] = {
                    "available": False,
                    "reason": ctx.unavailable_reason(missing[0]),
                }
                continue
            by_tier.setdefault(key, {})[computer.name] = computer.compute(ctx)
        return by_tier

    def analyze_text(
        self,
        text: str,
        text_index: int,
        tiers: Iterable[int] | None = None,
        feature_names: Iterable[str] | None = None,
        extra_signals: Iterable[str] = (),
        timings: Timings | None = None,
    ) -> SingleTextOutcome:
        """Full single-text pipeline.

        `extra_signals` lets the comparison service fold Pass 3's per-text requirements
        into this text's single Pass 1, so a double-text request never extracts a signal
        twice for the same text.
        """
        timings = timings if timings is not None else {}
        computers = self.plan(tiers, feature_names)

        required = feature_registry.required_signals(computers) | set(extra_signals)
        ctx = AnalysisContext(text=text, text_index=text_index)

        with timed(timings, "signals"):
            self.run_signals(ctx, required)

        with timed(timings, "features"):
            features_by_tier = self.run_features(ctx, computers)

        return SingleTextOutcome(
            context=ctx,
            features_by_tier=features_by_tier,
            tiers_computed=sorted({c.tier for c in computers}),
        )
