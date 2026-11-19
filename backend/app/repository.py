"""Repository pattern with dual storage backends: local SQLite and GCP Cloud Firestore."""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.alerts import evaluate_alerts
from app.config import get_firestore_project_id, get_local_db_path, get_storage_mode
from app.schemas import (
    LastReading,
    StationStatus,
    SummaryResponse,
    TelemetryIn,
    TelemetryRecord,
    WatershedSummary,
)


def build_station_doc_id(watershed: str, station_id: str) -> str:
    """Deterministic document ID for stations collection: '{watershed}_{station_id}'."""
    safe_w = watershed.replace("/", "_")
    safe_s = station_id.replace("/", "_")
    return f"{safe_w}_{safe_s}"


class TelemetryRepository(ABC):
    """Abstract repository interface for telemetry persistence and queries."""

    @abstractmethod
    def save_telemetry(self, payload: TelemetryIn) -> TelemetryRecord:
        """Persist telemetry reading and upsert station's latest snapshot."""

    @abstractmethod
    def list_telemetry(
        self,
        watershed: str | None = None,
        station_id: str | None = None,
        only_alerts: bool = False,
        limit: int = 100,
    ) -> list[TelemetryRecord]:
        """Query recent telemetry records with optional filters."""

    @abstractmethod
    def list_stations(self, watershed: str | None = None) -> list[StationStatus]:
        """List stations with their latest reading and alert state."""

    @abstractmethod
    def get_summary(self) -> SummaryResponse:
        """Compute aggregated metrics across all watersheds."""


class SQLiteLocalRepository(TelemetryRepository):
    """Local SQLite repository for zero-quota development and unit testing."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                    id TEXT PRIMARY KEY,
                    watershed TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    location TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    sample_date TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    water_temp_c REAL NOT NULL,
                    ph REAL NOT NULL,
                    dissolved_oxygen_mg_l REAL NOT NULL,
                    electrical_conductivity_us_cm REAL NOT NULL,
                    is_alert INTEGER NOT NULL,
                    alert_reasons TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_telemetry_filters
                ON telemetry (watershed, station_id, is_alert, ingested_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stations (
                    document_id TEXT PRIMARY KEY,
                    watershed TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    location TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    last_reading TEXT NOT NULL,
                    is_alert INTEGER NOT NULL,
                    alert_reasons TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_telemetry(self, payload: TelemetryIn) -> TelemetryRecord:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        record_id = str(uuid.uuid4())
        is_alert, alert_reasons = evaluate_alerts(
            ph=payload.ph,
            dissolved_oxygen_mg_l=payload.dissolved_oxygen_mg_l,
            electrical_conductivity_us_cm=payload.electrical_conductivity_us_cm,
        )

        record = TelemetryRecord(
            id=record_id,
            ingested_at=now_iso,
            is_alert=is_alert,
            alert_reasons=alert_reasons,
            **payload.model_dump(),
        )

        doc_id = build_station_doc_id(payload.watershed, payload.station_id)
        last_reading = LastReading(
            sample_date=payload.sample_date,
            ingested_at=now_iso,
            water_temp_c=payload.water_temp_c,
            ph=payload.ph,
            dissolved_oxygen_mg_l=payload.dissolved_oxygen_mg_l,
            electrical_conductivity_us_cm=payload.electrical_conductivity_us_cm,
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telemetry (
                    id, watershed, station_id, location, latitude, longitude,
                    sample_date, ingested_at, water_temp_c, ph,
                    dissolved_oxygen_mg_l, electrical_conductivity_us_cm,
                    is_alert, alert_reasons
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.watershed,
                    record.station_id,
                    record.location,
                    record.latitude,
                    record.longitude,
                    record.sample_date,
                    record.ingested_at,
                    record.water_temp_c,
                    record.ph,
                    record.dissolved_oxygen_mg_l,
                    record.electrical_conductivity_us_cm,
                    int(record.is_alert),
                    json.dumps(record.alert_reasons, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                INSERT INTO stations (
                    document_id, watershed, station_id, location, latitude, longitude,
                    last_reading, is_alert, alert_reasons, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    location = excluded.location,
                    latitude = COALESCE(excluded.latitude, stations.latitude),
                    longitude = COALESCE(excluded.longitude, stations.longitude),
                    last_reading = excluded.last_reading,
                    is_alert = excluded.is_alert,
                    alert_reasons = excluded.alert_reasons,
                    updated_at = excluded.updated_at
                """,
                (
                    doc_id,
                    record.watershed,
                    record.station_id,
                    record.location,
                    record.latitude,
                    record.longitude,
                    last_reading.model_dump_json(),
                    int(record.is_alert),
                    json.dumps(record.alert_reasons, ensure_ascii=False),
                    now_iso,
                ),
            )
            conn.commit()

        return record

    def list_telemetry(
        self,
        watershed: str | None = None,
        station_id: str | None = None,
        only_alerts: bool = False,
        limit: int = 100,
    ) -> list[TelemetryRecord]:
        clauses: list[str] = []
        params: list[Any] = []

        if watershed:
            clauses.append("watershed = ?")
            params.append(watershed)
        if station_id:
            clauses.append("station_id = ?")
            params.append(station_id)
        if only_alerts:
            clauses.append("is_alert = 1")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = (
            f"SELECT * FROM telemetry {where_sql} "
            "ORDER BY ingested_at DESC, rowid DESC LIMIT ?"
        )
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            TelemetryRecord(
                id=row["id"],
                watershed=row["watershed"],
                station_id=row["station_id"],
                location=row["location"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                sample_date=row["sample_date"],
                ingested_at=row["ingested_at"],
                water_temp_c=row["water_temp_c"],
                ph=row["ph"],
                dissolved_oxygen_mg_l=row["dissolved_oxygen_mg_l"],
                electrical_conductivity_us_cm=row["electrical_conductivity_us_cm"],
                is_alert=bool(row["is_alert"]),
                alert_reasons=json.loads(row["alert_reasons"]),
            )
            for row in rows
        ]

    def list_stations(self, watershed: str | None = None) -> list[StationStatus]:
        if watershed:
            query = (
                "SELECT * FROM stations WHERE watershed = ? "
                "ORDER BY watershed ASC, station_id ASC"
            )
            params: tuple[Any, ...] = (watershed,)
        else:
            query = "SELECT * FROM stations ORDER BY watershed ASC, station_id ASC"
            params = ()

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            StationStatus(
                document_id=row["document_id"],
                watershed=row["watershed"],
                station_id=row["station_id"],
                location=row["location"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                last_reading=LastReading.model_validate_json(row["last_reading"]),
                is_alert=bool(row["is_alert"]),
                alert_reasons=json.loads(row["alert_reasons"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def get_summary(self) -> SummaryResponse:
        with self._connect() as conn:
            station_count_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM stations"
            ).fetchone()
            total_stations = int(station_count_row["cnt"]) if station_count_row else 0

            rows = conn.execute(
                """
                SELECT
                    watershed,
                    COUNT(*) AS total_readings,
                    SUM(is_alert) AS total_alerts,
                    AVG(water_temp_c) AS avg_temp,
                    AVG(ph) AS avg_ph,
                    AVG(dissolved_oxygen_mg_l) AS avg_do,
                    AVG(electrical_conductivity_us_cm) AS avg_ec
                FROM telemetry
                GROUP BY watershed
                ORDER BY watershed ASC
                """
            ).fetchall()

        by_watershed: list[WatershedSummary] = []
        total_readings = 0
        total_alerts = 0

        for row in rows:
            cnt = int(row["total_readings"])
            alerts = int(row["total_alerts"] or 0)
            total_readings += cnt
            total_alerts += alerts
            by_watershed.append(
                WatershedSummary(
                    watershed=row["watershed"],
                    total_readings=cnt,
                    total_alerts=alerts,
                    alert_percentage=round((alerts / cnt) * 100.0, 2) if cnt else 0.0,
                    avg_water_temp_c=round(float(row["avg_temp"]), 2),
                    avg_ph=round(float(row["avg_ph"]), 2),
                    avg_dissolved_oxygen_mg_l=round(float(row["avg_do"]), 2),
                    avg_electrical_conductivity_us_cm=round(float(row["avg_ec"]), 2),
                )
            )

        alert_pct = (
            round((total_alerts / total_readings) * 100.0, 2) if total_readings else 0.0
        )
        return SummaryResponse(
            total_readings=total_readings,
            total_stations=total_stations,
            total_alerts=total_alerts,
            alert_percentage=alert_pct,
            by_watershed=by_watershed,
        )


class FirestoreRepository(TelemetryRepository):
    """Google Cloud Firestore repository optimized for free-tier read quotas."""

    TELEMETRY_COLLECTION = "telemetry"
    STATIONS_COLLECTION = "stations"

    def __init__(self, project_id: str | None = None) -> None:
        from google.cloud import firestore  # lazy import for local-mode portability

        self._firestore = firestore
        self.client = (
            firestore.Client(project=project_id) if project_id else firestore.Client()
        )

    def save_telemetry(self, payload: TelemetryIn) -> TelemetryRecord:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        is_alert, alert_reasons = evaluate_alerts(
            ph=payload.ph,
            dissolved_oxygen_mg_l=payload.dissolved_oxygen_mg_l,
            electrical_conductivity_us_cm=payload.electrical_conductivity_us_cm,
        )

        doc_ref = self.client.collection(self.TELEMETRY_COLLECTION).document()
        record = TelemetryRecord(
            id=doc_ref.id,
            ingested_at=now_iso,
            is_alert=is_alert,
            alert_reasons=alert_reasons,
            **payload.model_dump(),
        )

        telemetry_data = record.model_dump(exclude={"id"})
        doc_ref.set(telemetry_data)

        station_doc_id = build_station_doc_id(payload.watershed, payload.station_id)
        station_ref = self.client.collection(self.STATIONS_COLLECTION).document(
            station_doc_id
        )
        station_payload: dict[str, Any] = {
            "watershed": payload.watershed,
            "station_id": payload.station_id,
            "location": payload.location,
            "last_reading": {
                "sample_date": payload.sample_date,
                "ingested_at": now_iso,
                "water_temp_c": payload.water_temp_c,
                "ph": payload.ph,
                "dissolved_oxygen_mg_l": payload.dissolved_oxygen_mg_l,
                "electrical_conductivity_us_cm": payload.electrical_conductivity_us_cm,
            },
            "is_alert": is_alert,
            "alert_reasons": alert_reasons,
            "updated_at": now_iso,
        }
        if payload.latitude is not None:
            station_payload["latitude"] = payload.latitude
        if payload.longitude is not None:
            station_payload["longitude"] = payload.longitude

        station_ref.set(station_payload, merge=True)
        return record

    def list_telemetry(
        self,
        watershed: str | None = None,
        station_id: str | None = None,
        only_alerts: bool = False,
        limit: int = 100,
    ) -> list[TelemetryRecord]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self.client.collection(self.TELEMETRY_COLLECTION)
        if watershed:
            query = query.where(filter=FieldFilter("watershed", "==", watershed))
        if station_id:
            query = query.where(filter=FieldFilter("station_id", "==", station_id))
        if only_alerts:
            query = query.where(filter=FieldFilter("is_alert", "==", True))

        query = query.order_by(
            "ingested_at", direction=self._firestore.Query.DESCENDING
        ).limit(limit)

        results: list[TelemetryRecord] = []
        for snap in query.stream():
            data = snap.to_dict() or {}
            results.append(TelemetryRecord(id=snap.id, **data))
        return results

    def list_stations(self, watershed: str | None = None) -> list[StationStatus]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self.client.collection(self.STATIONS_COLLECTION)
        if watershed:
            query = query.where(filter=FieldFilter("watershed", "==", watershed))

        stations: list[StationStatus] = []
        for snap in query.stream():
            data = snap.to_dict() or {}
            stations.append(
                StationStatus(
                    document_id=snap.id,
                    watershed=data["watershed"],
                    station_id=data["station_id"],
                    location=data.get("location", ""),
                    latitude=data.get("latitude"),
                    longitude=data.get("longitude"),
                    last_reading=LastReading(**data["last_reading"]),
                    is_alert=bool(data.get("is_alert", False)),
                    alert_reasons=list(data.get("alert_reasons", [])),
                    updated_at=data["updated_at"],
                )
            )
        stations.sort(key=lambda s: (s.watershed, s.station_id))
        return stations

    def get_summary(self) -> SummaryResponse:
        # Count stations from lightweight stations collection
        station_snaps = list(
            self.client.collection(self.STATIONS_COLLECTION).select(["watershed"]).stream()
        )
        total_stations = len(station_snaps)

        # Projection query on telemetry to minimize payload size
        agg: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "count": 0.0,
                "alerts": 0.0,
                "sum_temp": 0.0,
                "sum_ph": 0.0,
                "sum_do": 0.0,
                "sum_ec": 0.0,
            }
        )
        projection = self.client.collection(self.TELEMETRY_COLLECTION).select(
            [
                "watershed",
                "is_alert",
                "water_temp_c",
                "ph",
                "dissolved_oxygen_mg_l",
                "electrical_conductivity_us_cm",
            ]
        )
        for snap in projection.stream():
            data = snap.to_dict() or {}
            w = data.get("watershed")
            if not w:
                continue
            bucket = agg[w]
            bucket["count"] += 1
            if data.get("is_alert"):
                bucket["alerts"] += 1
            bucket["sum_temp"] += float(data.get("water_temp_c", 0.0))
            bucket["sum_ph"] += float(data.get("ph", 0.0))
            bucket["sum_do"] += float(data.get("dissolved_oxygen_mg_l", 0.0))
            bucket["sum_ec"] += float(data.get("electrical_conductivity_us_cm", 0.0))

        by_watershed: list[WatershedSummary] = []
        total_readings = 0
        total_alerts = 0
        for watershed in sorted(agg.keys()):
            b = agg[watershed]
            cnt = int(b["count"])
            alerts = int(b["alerts"])
            total_readings += cnt
            total_alerts += alerts
            by_watershed.append(
                WatershedSummary(
                    watershed=watershed,
                    total_readings=cnt,
                    total_alerts=alerts,
                    alert_percentage=round((alerts / cnt) * 100.0, 2) if cnt else 0.0,
                    avg_water_temp_c=round(b["sum_temp"] / cnt, 2) if cnt else 0.0,
                    avg_ph=round(b["sum_ph"] / cnt, 2) if cnt else 0.0,
                    avg_dissolved_oxygen_mg_l=round(b["sum_do"] / cnt, 2) if cnt else 0.0,
                    avg_electrical_conductivity_us_cm=round(b["sum_ec"] / cnt, 2)
                    if cnt
                    else 0.0,
                )
            )

        alert_pct = (
            round((total_alerts / total_readings) * 100.0, 2) if total_readings else 0.0
        )
        return SummaryResponse(
            total_readings=total_readings,
            total_stations=total_stations,
            total_alerts=total_alerts,
            alert_percentage=alert_pct,
            by_watershed=by_watershed,
        )


def create_repository() -> TelemetryRepository:
    """Instantiate the configured repository based on STORAGE_MODE."""
    mode = get_storage_mode()
    if mode == "firestore":
        return FirestoreRepository(project_id=get_firestore_project_id())
    return SQLiteLocalRepository(db_path=get_local_db_path())
