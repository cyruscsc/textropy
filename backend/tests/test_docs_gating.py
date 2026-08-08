"""`TEXTROPY_ENVIRONMENT=production` must unmount the interactive docs.

The API endpoints themselves are never gated — only the docs surface.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import create_app

DOC_ROUTES = ("/docs", "/redoc", "/openapi.json")


@pytest.fixture
def app_client(monkeypatch):
    """Build an app under a given TEXTROPY_ENVIRONMENT.

    `get_settings()` caches a process-wide singleton, so it has to be cleared for the
    new environment to take effect. monkeypatch restores it after the test. The client
    is deliberately *not* used as a context manager: lifespan would trigger the model
    warmup, which none of these assertions need.
    """

    def build(environment: str) -> TestClient:
        monkeypatch.setenv("TEXTROPY_ENVIRONMENT", environment)
        monkeypatch.setattr(config, "_settings", None)
        return TestClient(create_app())

    return build


def test_docs_served_in_development(app_client):
    client = app_client("development")

    for route in DOC_ROUTES:
        assert client.get(route).status_code == 200, route


def test_docs_absent_in_production(app_client):
    client = app_client("production")

    for route in DOC_ROUTES:
        assert client.get(route).status_code == 404, route


def test_api_still_works_in_production(app_client):
    """Gating the docs must not touch the actual endpoints."""
    client = app_client("production")

    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/features").status_code == 200

    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": ["The cat sat on the mat."], "tiers": [1]},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["features"]["tier1"]["word_count"] == 6


def test_development_is_the_default(monkeypatch):
    monkeypatch.delenv("TEXTROPY_ENVIRONMENT", raising=False)

    settings = config.Settings()

    assert settings.environment == "development"
    assert settings.docs_enabled is True


def test_unknown_environment_is_rejected(monkeypatch):
    """A typo'd value must fail at startup, not silently leave docs exposed."""
    monkeypatch.setenv("TEXTROPY_ENVIRONMENT", "prod")

    with pytest.raises(ValueError):
        config.Settings()
