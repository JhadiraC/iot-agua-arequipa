"""Pytest fixtures for isolated backend API testing with local SQLite."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_repository

TEST_API_KEY = "test-secret-iot-key"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Provide a FastAPI TestClient backed by a fresh temporary SQLite DB."""
    db_file = tmp_path / "test_telemetry.db"
    monkeypatch.setenv("STORAGE_MODE", "local")
    monkeypatch.setenv("LOCAL_DB_PATH", str(db_file))
    monkeypatch.setenv("IOT_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")

    get_repository.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_repository.cache_clear()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Valid X-API-KEY headers for telemetry ingestion."""
    return {"X-API-KEY": TEST_API_KEY}
