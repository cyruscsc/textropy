"""Feature catalog (spec §6) — drives the frontend's tier/feature picker."""

from __future__ import annotations

from fastapi import APIRouter

from app.comparison import registry as comparison_registry
from app.features import registry as feature_registry
from app.schemas.responses import FeatureCatalogEntry, FeatureCatalogResponse

router = APIRouter(tags=["catalog"])


@router.get("/features", response_model=FeatureCatalogResponse)
def features() -> FeatureCatalogResponse:
    entries = [
        FeatureCatalogEntry(**entry)
        for entry in (*feature_registry.catalog(), *comparison_registry.catalog())
    ]
    return FeatureCatalogResponse(features=entries)
