"""The per-request, per-text analysis context (spec §2).

`AnalysisContext` is a plain in-memory bag of extracted signals for **one** text. It is
created when a request arrives and dropped when the response is sent — nothing here is
persisted, and there is no cross-request reuse in the MVP.

The context is deliberately *passive*: it never computes anything. Pass 1 populates it,
Passes 2 and 3 only read from it. That is what makes "each signal computed at most once
per text" a structural property rather than a convention a feature could violate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SignalNotAvailableError(RuntimeError):
    """A feature asked for a signal the orchestrator did not populate.

    This is always a wiring bug: the feature failed to declare the signal in its
    `requires`, so the orchestrator never scheduled its extractor.
    """


@dataclass
class AnalysisContext:
    text: str
    text_index: int = 0
    _signals: dict[str, Any] = field(default_factory=dict, repr=False)
    # Signals whose extractor could not run because an *optional* model is missing.
    # Dependent features report this instead of failing the whole request.
    _unavailable: dict[str, str] = field(default_factory=dict, repr=False)

    def has(self, name: str) -> bool:
        return name in self._signals

    def mark_unavailable(self, name: str, reason: str = "") -> None:
        self._unavailable[name] = reason or f"Signal {name!r} is unavailable in this deployment"

    def is_unavailable(self, name: str) -> bool:
        return name in self._unavailable

    def unavailable_reason(self, name: str) -> str:
        return self._unavailable.get(name, "")

    def get(self, name: str) -> Any:
        try:
            return self._signals[name]
        except KeyError:
            raise SignalNotAvailableError(
                f"Signal {name!r} was not extracted for text {self.text_index}. "
                f"Available: {sorted(self._signals)}. A feature computer must declare "
                f"every signal it reads in its `requires` tuple."
            ) from None

    def set(self, name: str, value: Any) -> None:
        self._signals[name] = value

    @property
    def signal_names(self) -> list[str]:
        return sorted(self._signals)
