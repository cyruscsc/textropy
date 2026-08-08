from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="session")
def client() -> TestClient:
    # `with` triggers the lifespan handler, so the eager warmup runs exactly as in prod.
    with TestClient(create_app()) as test_client:
        yield test_client
