"""Pydantic v2 schemas with physical range validation for IoT telemetry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TelemetryIn(BaseModel):
    """Incoming telemetry payload sent by an ESP32 sensor node."""

    model_config = ConfigDict(str_strip_whitespace=True)

    watershed: str = Field(..., min_length=1, max_length=64)
    station_id: str = Field(..., min_length=1, max_length=64)
    location: str = Field(default="", max_length=300)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    sample_date: str = Field(..., min_length=8, max_length=32)

    # Physical bounds matching ETL quality control
    water_temp_c: float = Field(..., ge=0.0, le=50.0)
    ph: float = Field(..., ge=0.0, le=14.0)
    dissolved_oxygen_mg_l: float = Field(..., ge=0.0, le=25.0)
    electrical_conductivity_us_cm: float = Field(..., gt=0.0)


class TelemetryRecord(TelemetryIn):
    """Persisted telemetry document with server timestamp and alert evaluation."""

    id: str
    ingested_at: str
    is_alert: bool
    alert_reasons: list[str]


class LastReading(BaseModel):
    """Compact snapshot of the latest telemetry reading for a station."""

    sample_date: str
    ingested_at: str
    water_temp_c: float
    ph: float
    dissolved_oxygen_mg_l: float
    electrical_conductivity_us_cm: float


class StationStatus(BaseModel):
    """Current state of a monitoring station (one document per station)."""

    document_id: str
    watershed: str
    station_id: str
    location: str
    latitude: float | None
    longitude: float | None
    last_reading: LastReading
    is_alert: bool
    alert_reasons: list[str]
    updated_at: str


class WatershedSummary(BaseModel):
    """Aggregated telemetry statistics for a single watershed."""

    watershed: str
    total_readings: int
    total_alerts: int
    alert_percentage: float
    avg_water_temp_c: float
    avg_ph: float
    avg_dissolved_oxygen_mg_l: float
    avg_electrical_conductivity_us_cm: float


class SummaryResponse(BaseModel):
    """Global and per-watershed summary metrics."""

    total_readings: int
    total_stations: int
    total_alerts: int
    alert_percentage: float
    by_watershed: list[WatershedSummary]


class HealthResponse(BaseModel):
    """Service health check payload."""

    status: str
    storage_mode: str
