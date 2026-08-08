"""Liveness / readiness probe (spec §6).

Readiness reflects whether the `models_ml` singletons this deployment intends to preload
have actually finished loading — not merely that the process is up.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import SettingsDep
from app.models_ml.model_registry import get_model_registry
from app.schemas.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: SettingsDep) -> HealthResponse:
    registry = get_model_registry()
    statuses = registry.status()

    if settings.model_loading == "eager":
        expected = [
            name for tier in settings.eager_tiers for name in registry.models_for_tier(tier)
        ]
        # An optional model that failed to load must not hold readiness down forever.
        ready = all(statuses.get(name) in {"loaded", "error"} for name in expected)
    else:
        # Nothing is preloaded in lazy mode, so the process is ready as soon as it serves.
        ready = True

    return HealthResponse(
        status="ok",
        ready=ready,
        model_loading=settings.model_loading,
        models=statuses,
    )
