"""Response models (spec §6).

Tier payloads are typed as open dicts on purpose: the set of keys is driven by the feature
registry, so adding a feature must not require editing a response schema.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TextResult(BaseModel):
    text_index: int
    features: dict[str, dict[str, Any]] = Field(default_factory=dict)


class Meta(BaseModel):
    elapsed_ms: dict[str, float] = Field(default_factory=dict)
    tiers_computed: list[int] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    mode: Literal["single", "compare"]
    results: list[TextResult]
    comparison: dict[str, dict[str, Any]] | None = None
    meta: Meta


class FeatureCatalogEntry(BaseModel):
    name: str
    tier: int
    scope: Literal["single", "comparison"]
    symmetric: bool | None = None
    requires: list[str] = Field(default_factory=list)


class FeatureCatalogResponse(BaseModel):
    features: list[FeatureCatalogEntry]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    ready: bool
    model_loading: str
    models: dict[str, str]
