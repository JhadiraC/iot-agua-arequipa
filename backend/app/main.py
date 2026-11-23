"""FastAPI serverless backend for Arequipa IoT water-quality telemetry."""

from __future__ import annotations

import secrets
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_allowed_origins, get_iot_api_key, get_storage_mode
from app.repository import TelemetryRepository, create_repository
from app.schemas import (
    HealthResponse,
    StationStatus,
    SummaryResponse,
    TelemetryIn,
    TelemetryRecord,
)


@lru_cache(maxsize=1)
def get_repository() -> TelemetryRepository:
    """Singleton repository dependency (can be cleared in tests)."""
    return create_repository()


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
) -> None:
    """Validate X-API-KEY header against IOT_API_KEY environment variable."""
    expected_key = get_iot_api_key()
    if not expected_key or not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-KEY header.",
        )
    if not secrets.compare_digest(x_api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-KEY header.",
        )


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title="Arequipa IoT Water Quality API",
        description=(
            "Serverless backend for simulated ESP32 water-quality telemetry across "
            "the 5 watersheds of Arequipa, Peru (Cloud Run + Cloud Firestore / SQLite)."
        ),
        version="1.0.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        if exc.__class__.__name__ == "ResourceExhausted":
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": (
                        "Cuota diaria gratuita de Cloud Firestore alcanzada (429). "
                        "Cambia STORAGE_MODE=local en backend/.env o espera al reinicio diario."
                    )
                },
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Error interno del servidor: {exc.__class__.__name__}"},
        )

    @application.get("/health", response_model=HealthResponse, tags=["Health"])
    def health_check() -> HealthResponse:
        return HealthResponse(status="ok", storage_mode=get_storage_mode())

    @application.post(
        "/api/v1/telemetry",
        response_model=TelemetryRecord,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(verify_api_key)],
        tags=["Telemetry"],
    )
    def ingest_telemetry(
        payload: TelemetryIn,
        repo: TelemetryRepository = Depends(get_repository),
    ) -> TelemetryRecord:
        return repo.save_telemetry(payload)

    @application.get(
        "/api/v1/telemetry",
        response_model=list[TelemetryRecord],
        tags=["Telemetry"],
    )
    def list_telemetry(
        watershed: str | None = Query(default=None),
        station_id: str | None = Query(default=None),
        only_alerts: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=500),
        repo: TelemetryRepository = Depends(get_repository),
    ) -> list[TelemetryRecord]:
        return repo.list_telemetry(
            watershed=watershed,
            station_id=station_id,
            only_alerts=only_alerts,
            limit=limit,
        )

    @application.get(
        "/api/v1/stations",
        response_model=list[StationStatus],
        tags=["Stations"],
    )
    def list_stations(
        watershed: str | None = Query(default=None),
        repo: TelemetryRepository = Depends(get_repository),
    ) -> list[StationStatus]:
        return repo.list_stations(watershed=watershed)

    @application.get(
        "/api/v1/summary",
        response_model=SummaryResponse,
        tags=["Summary"],
    )
    def get_summary(
        repo: TelemetryRepository = Depends(get_repository),
    ) -> SummaryResponse:
        return repo.get_summary()

    return application


app = create_app()
