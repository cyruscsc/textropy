"""Signal registry and dependency resolution (spec §2).

The registry turns a *set of requested signals* into a *topologically ordered run list*
that includes transitive dependencies exactly once. This is where "each signal is computed
at most once per text, and only if some selected feature needs it" is actually enforced —
no cache involved, just set union plus a topological sort.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.signals.alignment import LmToSpacyAlignmentExtractor
from app.signals.base import SignalExtractor
from app.signals.coreference import CorefExtractor
from app.signals.embedding_extractor import (
    SentenceVectorsExtractor,
    WordVectorsExtractor,
)
from app.signals.lm_extractor import LmTokenLogProbsExtractor
from app.signals.sentiment_transformer import SentimentExtractor
from app.signals.spacy_extractor import SpacyDocExtractor

_EXTRACTORS: tuple[SignalExtractor, ...] = (
    SpacyDocExtractor(),
    LmTokenLogProbsExtractor(),
    SentenceVectorsExtractor(),
    WordVectorsExtractor(),
    LmToSpacyAlignmentExtractor(),
    SentimentExtractor(),
    CorefExtractor(),
)

SIGNAL_REGISTRY: dict[str, SignalExtractor] = {e.name: e for e in _EXTRACTORS}


class UnknownSignalError(KeyError):
    """A feature declared a signal that no extractor provides."""


def get_extractor(name: str) -> SignalExtractor:
    try:
        return SIGNAL_REGISTRY[name]
    except KeyError:
        raise UnknownSignalError(
            f"No extractor registered for signal {name!r}. Known: {sorted(SIGNAL_REGISTRY)}"
        ) from None


def resolve_order(required: Iterable[str]) -> list[str]:
    """Expand `required` with transitive dependencies, in a runnable order.

    Returns each signal exactly once, with every dependency preceding its dependents.
    Raises on unknown signals and on dependency cycles.
    """
    order: list[str] = []
    done: set[str] = set()
    visiting: list[str] = []  # doubles as the cycle path for error messages

    def visit(name: str) -> None:
        if name in done:
            return
        if name in visiting:
            cycle = " -> ".join([*visiting[visiting.index(name) :], name])
            raise ValueError(f"Cyclic signal dependency: {cycle}")

        extractor = get_extractor(name)
        visiting.append(name)
        for dep in extractor.depends_on:
            visit(dep)
        visiting.pop()

        done.add(name)
        order.append(name)

    for name in sorted(set(required)):
        visit(name)
    return order


def required_models(signal_names: Iterable[str]) -> set[str]:
    """Model registry keys needed to extract the given signals (dependencies included)."""
    return {model for name in resolve_order(signal_names) for model in get_extractor(name).models}
