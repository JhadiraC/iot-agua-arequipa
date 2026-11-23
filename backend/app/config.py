"""Application configuration and referential water-quality alert thresholds."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env for local execution without overriding explicit env vars
load_dotenv(BACKEND_DIR / ".env", override=False)

# Normalize relative GOOGLE_APPLICATION_CREDENTIALS against backend/
_creds_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
if _creds_env:
    _creds_path = Path(_creds_env)
    if not _creds_path.is_absolute():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
            (BACKEND_DIR / _creds_path).resolve()
        )

# ---------------------------------------------------------------------------
# Referential water-quality alert thresholds (configurable constants)
# ---------------------------------------------------------------------------
PH_MIN_THRESHOLD: float = 6.5
PH_MAX_THRESHOLD: float = 8.5
DO_MIN_THRESHOLD: float = 4.0
EC_MAX_THRESHOLD: float = 2500.0


def get_storage_mode() -> str:
    """Return active storage mode: 'local' (SQLite) or 'firestore' (GCP)."""
    mode = os.environ.get("STORAGE_MODE", "local").strip().lower()
    if mode not in {"local", "firestore"}:
        raise ValueError(
            f"Unsupported STORAGE_MODE='{mode}'. Expected 'local' or 'firestore'."
        )
    return mode


def get_local_db_path() -> Path:
    """Return SQLite file path for local development/testing."""
    env_path = os.environ.get("LOCAL_DB_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return BACKEND_DIR / "local_dev.db"


def get_iot_api_key() -> str | None:
    """Return expected API key from environment variable (never hardcoded)."""
    key = os.environ.get("IOT_API_KEY", "").strip()
    return key or None


def get_allowed_origins() -> list[str]:
    """Parse CORS allowed origins from ALLOWED_ORIGINS env var."""
    raw = os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:5173"]


def get_firestore_project_id() -> str | None:
    """Optional explicit GCP project ID for Firestore client."""
    project_id = os.environ.get("FIRESTORE_PROJECT_ID", "").strip()
    return project_id or None
