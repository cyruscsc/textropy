"""Double-text orchestration: Pass 1 (x2) -> Pass 2 (x2) -> Pass 3 (spec §2).

This service does **not** reimplement single-text extraction. It asks the comparison
registry which per-text signals Pass 3 will need, hands them to `AnalysisService` as
`extra_signals`, and lets each text go through the ordinary single-text pipeline exactly
once. Pass 3 then reads both finished contexts.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.comparison import registry as comparison_registry
from app.services.analysis_service import AnalysisService, SingleTextOutcome, Timings, timed


@dataclass
class ComparisonOutcome:
    results: list[SingleTextOutcome]
    comparison_by_tier: dict[str, dict[str, Any]] = field(default_factory=dict)
    tiers_computed: list[int] = field(default_factory=list)


class ComparisonService:
    def __init__(self, analysis_service: AnalysisService | None = None) -> None:
        self.analysis = analysis_service or AnalysisService()

    def compare(
        self,
        text_a: str,
        text_b: str,
        tiers: Iterable[int] | None = None,
        feature_names: Iterable[str] | None = None,
        timings: Timings | None = None,
    ) -> ComparisonOutcome:
        timings = timings if timings is not None else {}

        computers = comparison_registry.select(tiers=tiers, feature_names=feature_names)
        # Per-text signals Pass 3 needs, merged into each text's own Pass 1.
        extra_signals = comparison_registry.required_signals(computers)

        outcomes = [
            self.analysis.analyze_text(
                text=text,
                text_index=index,
                tiers=tiers,
                feature_names=feature_names,
                extra_signals=extra_signals,
                timings=timings,
            )
            for index, text in enumerate((text_a, text_b))
        ]

        ctx_a, ctx_b = outcomes[0].context, outcomes[1].context

        comparison_by_tier: dict[str, dict[str, Any]] = {}
        with timed(timings, "comparison"):
            for computer in computers:
                key = f"tier{computer.tier}"
                comparison_by_tier.setdefault(key, {})[computer.name] = computer.compute(
                    ctx_a, ctx_b
                )

        tiers_computed = sorted(
            {tier for outcome in outcomes for tier in outcome.tiers_computed}
            | {c.tier for c in computers}
        )
        return ComparisonOutcome(
            results=outcomes,
            comparison_by_tier=comparison_by_tier,
            tiers_computed=tiers_computed,
        )
