"""Pass 2 base class — single-text feature computers (spec §2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.pipeline.context import AnalysisContext


class FeatureComputer(ABC):
    """Computes one single-text feature by *reading* an already-populated context.

    A computer must declare every signal it reads in `requires`. It must never invoke an
    extractor or a model itself: doing so would reintroduce the redundant computation the
    multi-pass design exists to prevent, and would bypass the orchestrator's guarantee
    that a shared signal is extracted once.
    """

    name: ClassVar[str]
    tier: ClassVar[int]
    requires: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def compute(self, ctx: AnalysisContext) -> Any:
        """Return this feature's JSON-serialisable value."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.name} tier={self.tier}>"
