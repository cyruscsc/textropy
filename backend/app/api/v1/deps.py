"""Shared FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.analysis_service import AnalysisService
from app.services.comparison_service import ComparisonService


@lru_cache(maxsize=1)
def get_analysis_service() -> AnalysisService:
    # Services are stateless, so one instance per process is enough.
    return AnalysisService()


@lru_cache(maxsize=1)
def get_comparison_service() -> ComparisonService:
    return ComparisonService(get_analysis_service())


SettingsDep = Annotated[Settings, Depends(get_settings)]
AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
ComparisonServiceDep = Annotated[ComparisonService, Depends(get_comparison_service)]
