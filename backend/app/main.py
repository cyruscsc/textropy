"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import analyze, catalog, health
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.models_ml.model_registry import get_model_registry

logger = get_logger(__name__)


def _app_version() -> str:
    """Read the version from installed package metadata.

    pyproject's `[project] version` is the single source of truth for the backend, so
    OpenAPI cannot drift from the released version the way a second literal here would.
    """
    try:
        return package_version("textropy-backend")
    except PackageNotFoundError:
        # Source tree with the project not installed (e.g. bare `PYTHONPATH=. uvicorn`).
        # Both `uv sync` and the Dockerfile install it, so this is a dev-only fallback.
        return "0.0.0+unknown"


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

    docs_enabled = settings.docs_enabled
    logger.info(
        "Starting in %s mode (interactive docs %s)",
        settings.environment,
        "enabled" if docs_enabled else "disabled",
    )

    app = FastAPI(
        title=settings.app_name,
        version=_app_version(),
        summary="Stateless multi-pass linguistic text analysis",
        lifespan=lifespan,
        # Passing None unmounts the route entirely — a 404, not an empty page.
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
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
