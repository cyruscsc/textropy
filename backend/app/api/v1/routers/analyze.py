"""The single analysis endpoint driving both modes (spec §6).

Synchronous end to end, Tier 3 included — the MVP has no job queue (spec §9).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import AnalysisServiceDep, ComparisonServiceDep, SettingsDep
from app.comparison import registry as comparison_registry
from app.features import registry as feature_registry
from app.models_ml.model_registry import ModelUnavailableError
from app.schemas.requests import AnalyzeRequest
from app.schemas.responses import AnalyzeResponse, Meta, TextResult
from app.services.analysis_service import Timings

router = APIRouter(tags=["analyze"])


def _validate(request: AnalyzeRequest, max_text_chars: int) -> None:
    if max_text_chars > 0:
        for index, text in enumerate(request.texts):
            if len(text) > max_text_chars:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=(
                        f"texts[{index}] is {len(text)} characters; "
                        f"the configured limit is {max_text_chars}"
                    ),
                )

    if request.feature_names is None:
        return

    known = set(feature_registry.FEATURE_REGISTRY) | comparison_registry.known_names()
    unknown = [name for name in request.feature_names if name not in known]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown feature_names: {unknown}. See GET /api/v1/features.",
        )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    settings: SettingsDep,
    analysis_service: AnalysisServiceDep,
    comparison_service: ComparisonServiceDep,
) -> AnalyzeResponse:
    _validate(request, settings.max_text_chars)

    timings: Timings = {}
    try:
        if request.mode == "single":
            outcome = analysis_service.analyze_text(
                text=request.texts[0],
                text_index=0,
                tiers=request.tiers,
                feature_names=request.feature_names,
                timings=timings,
            )
            results = [TextResult(text_index=0, features=outcome.features_by_tier)]
            comparison = None
            tiers_computed = outcome.tiers_computed
        else:
            outcome = comparison_service.compare(
                text_a=request.texts[0],
                text_b=request.texts[1],
                tiers=request.tiers,
                feature_names=request.feature_names,
                timings=timings,
            )
            results = [
                TextResult(text_index=index, features=single.features_by_tier)
                for index, single in enumerate(outcome.results)
            ]
            comparison = outcome.comparison_by_tier
            tiers_computed = outcome.tiers_computed
    except ModelUnavailableError as exc:
        # A required model could not be loaded (e.g. the optional coref extra is absent).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return AnalyzeResponse(
        mode=request.mode,
        results=results,
        comparison=comparison,
        meta=Meta(elapsed_ms=timings, tiers_computed=tiers_computed),
    )
