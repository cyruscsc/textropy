"""Process-wide ML model singletons (spec §4).

Models are loaded **once per process**, never per request. Two loading strategies are
supported via `Settings.model_loading`:

* ``eager`` — every model belonging to a tier in `Settings.eager_tiers` is loaded during
  application startup, so ``/health`` reports ready only once they are resident.
* ``lazy``  — each model is loaded on first use, trading a slow first request for a much
  smaller startup footprint on memory-constrained hosts.

Note the RAM consequence recorded in spec §9: this registry is per *process*, so running
multiple worker processes multiplies resident memory.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Registry keys.
SPACY = "spacy"
CAUSAL_LM = "causal_lm"
SENTENCE_EMBEDDER = "sentence_embedder"
SENTIMENT = "sentiment"
COREF = "coref"


class ModelUnavailableError(RuntimeError):
    """A model could not be loaded (missing weights, incompatible optional dependency, ...)."""


@dataclass
class _Entry:
    name: str
    loader: Callable[[], Any]
    tier: int
    optional: bool = False
    instance: Any = None
    error: str | None = None


class ModelRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        loader: Callable[[], Any],
        *,
        tier: int,
        optional: bool = False,
    ) -> None:
        self._entries[name] = _Entry(name=name, loader=loader, tier=tier, optional=optional)

    def get(self, name: str) -> Any:
        """Return the singleton, loading it on first use.

        A previous load failure is cached: a broken optional dependency must not cost a
        multi-second retry on every request.
        """
        entry = self._entries.get(name)
        if entry is None:
            raise KeyError(f"No model registered under {name!r}")

        if entry.instance is not None:
            return entry.instance

        with self._lock:
            # Re-check: another thread may have loaded it while we waited.
            if entry.instance is not None:
                return entry.instance
            if entry.error is not None:
                raise ModelUnavailableError(entry.error)

            started = time.perf_counter()
            try:
                entry.instance = entry.loader()
            except Exception as exc:  # noqa: BLE001 - recorded and re-raised as our type
                entry.error = f"Failed to load model {name!r}: {exc}"
                logger.error(entry.error)
                raise ModelUnavailableError(entry.error) from exc

            elapsed = (time.perf_counter() - started) * 1000
            logger.info("Loaded model %r in %.0f ms", name, elapsed)
            return entry.instance

    def warmup(self, tiers: list[int]) -> None:
        """Eagerly load every model whose tier is in `tiers`."""
        for entry in self._entries.values():
            if entry.tier not in tiers:
                continue
            try:
                self.get(entry.name)
            except ModelUnavailableError:
                if not entry.optional:
                    raise
                logger.warning(
                    "Optional model %r unavailable; dependent features will report "
                    "themselves unavailable and the rest of the API is unaffected.",
                    entry.name,
                )

    def is_loaded(self, name: str) -> bool:
        entry = self._entries.get(name)
        return entry is not None and entry.instance is not None

    def any_optional(self, names: Iterable[str]) -> bool:
        """True if any named model is optional — i.e. its absence should degrade, not fail."""
        return any(self._entries[name].optional for name in names if name in self._entries)

    def status(self) -> dict[str, str]:
        """Per-model load state, surfaced by the readiness probe."""
        out: dict[str, str] = {}
        for name, entry in self._entries.items():
            if entry.instance is not None:
                out[name] = "loaded"
            elif entry.error is not None:
                out[name] = "error"
            else:
                out[name] = "not_loaded"
        return out

    def models_for_tier(self, tier: int) -> list[str]:
        return [name for name, entry in self._entries.items() if entry.tier == tier]


_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    """Build (once) and return the process-wide registry."""
    global _registry
    if _registry is not None:
        return _registry

    # Imported here so that merely importing this module does not drag in torch/spaCy.
    from app.models_ml import (
        causal_lm,
        coref_model,
        sentence_embedder,
        sentiment_model,
        spacy_model,
    )

    registry = ModelRegistry()
    registry.register(SPACY, spacy_model.load, tier=1)
    registry.register(SENTIMENT, sentiment_model.load, tier=2)
    registry.register(SENTENCE_EMBEDDER, sentence_embedder.load, tier=2)
    registry.register(COREF, coref_model.load, tier=2, optional=True)
    registry.register(CAUSAL_LM, causal_lm.load, tier=3)

    _registry = registry
    return _registry


def get_model(name: str) -> Any:
    return get_model_registry().get(name)
