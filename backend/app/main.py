"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import analyze, catalog, health
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.models_ml.model_registry import get_model_registry

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    if settings.model_loading == "eager":
        logger.info("Preloading models for tiers %s", settings.eager_tiers)
        get_model_registry().warmup(settings.eager_tiers)
    else:
        logger.info("Lazy model loading: models load on first use")

    yield
    # Nothing to tear down: the MVP holds no connections, files, or background workers.


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        summary="Stateless multi-pass linguistic text analysis",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    for router in (analyze.router, catalog.router, health.router):
        app.include_router(router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
