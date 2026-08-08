"""Pass 3 base class — double-text comparison computers (spec §2, §3.2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.pipeline.context import AnalysisContext


class ComparisonComputer(ABC):
    """Computes one cross-text metric from two already-populated contexts.

    `requires` lists signals needed **per text**; the orchestrator unions them with the
    single-text feature requirements so each text is still processed by exactly one Pass 1.
    A comparison computer must never re-parse or re-embed either text.

    Genuinely joint quantities (Tier 3 cross-perplexity conditions text B on text A) have
    no per-text signal to reuse, so those computers may call a model directly. What stays
    forbidden is recomputing something a per-text signal already holds.

    `symmetric = False` means the metric is direction-dependent; those computers return
    `{"a_given_b": ..., "b_given_a": ...}` (spec §3.2).
    """

    name: ClassVar[str]
    tier: ClassVar[int]
    symmetric: ClassVar[bool] = True
    requires: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def compute(self, a: AnalysisContext, b: AnalysisContext) -> Any:
        """Return this metric's JSON-serialisable value."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.name} tier={self.tier}>"
