"""Integration tests for the FastAPI IoT telemetry endpoints."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


SAMPLE_CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "processed"
    / "arequipa_sample_15_stations.csv"
)


def _normal_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "watershed": "Camaná",
        "station_id": "QAroc1",
        "location": "Quebrada Arocpampa, upstream of the Laguna Huisca Huisca",
        "latitude": -14.993888,
        "longitude": -72.300726,
        "sample_date": "2014-09-02",
        "water_temp_c": 14.5,
        "ph": 7.6,
        "dissolved_oxygen_mg_l": 7.39,
        "electrical_conductivity_us_cm": 585.0,
    }
    base.update(overrides)
    return base


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "storage_mode": "local"}


def test_ingest_requires_valid_api_key(client: TestClient) -> None:
    payload = _normal_payload()

    missing = client.post("/api/v1/telemetry", json=payload)
    assert missing.status_code == 401

    wrong = client.post(
        "/api/v1/telemetry",
        json=payload,
        headers={"X-API-KEY": "wrong-key"},
    )
    assert wrong.status_code == 401


def test_ingest_normal_and_alert_telemetry(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    normal_resp = client.post(
        "/api/v1/telemetry",
        json=_normal_payload(),
        headers=auth_headers,
    )
    assert normal_resp.status_code == 201
    normal_data = normal_resp.json()
    assert normal_data["id"]
    assert normal_data["ingested_at"].endswith("Z")
    assert normal_data["is_alert"] is False
    assert normal_data["alert_reasons"] == []

    alert_resp = client.post(
        "/api/v1/telemetry",
        json=_normal_payload(
            watershed="Chili",
            station_id="QAñas1",
            location="Quebrada Añashuayco",
            latitude=-16.42553,
            longitude=-71.675134,
            sample_date="2018-04-04",
            water_temp_c=19.7,
            ph=9.3,
            dissolved_oxygen_mg_l=3.2,
            electrical_conductivity_us_cm=3100.0,
        ),
        headers=auth_headers,
    )
    assert alert_resp.status_code == 201
    alert_data = alert_resp.json()
    assert alert_data["is_alert"] is True
    assert len(alert_data["alert_reasons"]) == 3


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("water_temp_c", 449.1),
        ("water_temp_c", -1.0),
        ("ph", 32.56),
        ("ph", -0.5),
        ("dissolved_oxygen_mg_l", 717.0),
        ("electrical_conductivity_us_cm", 0.0),
        ("electrical_conductivity_us_cm", -10.0),
        ("latitude", -95.0),
        ("longitude", 190.0),
    ],
)
def test_ingest_rejects_physical_anomalies(
    client: TestClient,
    auth_headers: dict[str, str],
    field: str,
    bad_value: float,
) -> None:
    resp = client.post(
        "/api/v1/telemetry",
        json=_normal_payload(**{field: bad_value}),
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_list_telemetry_filters_and_ordering(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.post(
        "/api/v1/telemetry",
        json=_normal_payload(watershed="Camaná", station_id="QAroc1", ph=7.5),
        headers=auth_headers,
    )
    client.post(
        "/api/v1/telemetry",
        json=_normal_payload(watershed="Camaná", station_id="RAnda1", ph=9.02),
        headers=auth_headers,
    )
    client.post(
        "/api/v1/telemetry",
        json=_normal_payload(watershed="Chili", station_id="RChil4", ph=7.9),
        headers=auth_headers,
    )

    all_records = client.get("/api/v1/telemetry").json()
    assert len(all_records) == 3
    # Most recent reading first
    assert all_records[0]["station_id"] == "RChil4"

    camana_only = client.get("/api/v1/telemetry", params={"watershed": "Camaná"}).json()
    assert len(camana_only) == 2
    assert all(r["watershed"] == "Camaná" for r in camana_only)

    station_only = client.get(
        "/api/v1/telemetry", params={"station_id": "QAroc1"}
    ).json()
    assert len(station_only) == 1
    assert station_only[0]["station_id"] == "QAroc1"

    alerts_only = client.get("/api/v1/telemetry", params={"only_alerts": True}).json()
    assert len(alerts_only) == 1
    assert alerts_only[0]["station_id"] == "RAnda1"
    assert alerts_only[0]["is_alert"] is True

    limited = client.get("/api/v1/telemetry", params={"limit": 2}).json()
    assert len(limited) == 2


def test_stations_upsert_and_coordinate_preservation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # First reading with coordinates and normal state
    client.post(
        "/api/v1/telemetry",
        json=_normal_payload(
            watershed="Tambo",
            station_id="RTamb1",
            latitude=-17.0,
            longitude=-71.5,
            ph=7.5,
            sample_date="2015-08-01",
        ),
        headers=auth_headers,
    )
    # Second reading for same station without coordinates and with alert
    client.post(
        "/api/v1/telemetry",
        json=_normal_payload(
            watershed="Tambo",
            station_id="RTamb1",
            latitude=None,
            longitude=None,
            ph=9.1,
            sample_date="2015-09-01",
        ),
        headers=auth_headers,
    )

    stations = client.get("/api/v1/stations", params={"watershed": "Tambo"}).json()
    assert len(stations) == 1
    station = stations[0]
    assert station["document_id"] == "Tambo_RTamb1"
    assert station["latitude"] == -17.0
    assert station["longitude"] == -71.5
    assert station["last_reading"]["sample_date"] == "2015-09-01"
    assert station["last_reading"]["ph"] == 9.1
    assert station["is_alert"] is True


def test_summary_empty_and_populated(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    empty_resp = client.get("/api/v1/summary")
    assert empty_resp.status_code == 200
    assert empty_resp.json() == {
        "total_readings": 0,
        "total_stations": 0,
        "total_alerts": 0,
        "alert_percentage": 0.0,
        "by_watershed": [],
    }

    # Two readings on Camaná (1 station, 1 alert) + one normal reading on Chili
    client.post(
        "/api/v1/telemetry",
        json=_normal_payload(
            watershed="Camaná",
            station_id="QAroc1",
            water_temp_c=14.0,
            ph=7.5,
            dissolved_oxygen_mg_l=7.0,
            electrical_conductivity_us_cm=500.0,
        ),
        headers=auth_headers,
    )
    client.post(
        "/api/v1/telemetry",
        json=_normal_payload(
            watershed="Camaná",
            station_id="QAroc1",
            water_temp_c=16.0,
            ph=9.5,
            dissolved_oxygen_mg_l=5.0,
            electrical_conductivity_us_cm=700.0,
        ),
        headers=auth_headers,
    )
    client.post(
        "/api/v1/telemetry",
        json=_normal_payload(
            watershed="Chili",
            station_id="RChil4",
            water_temp_c=18.0,
            ph=8.0,
            dissolved_oxygen_mg_l=8.0,
            electrical_conductivity_us_cm=300.0,
        ),
        headers=auth_headers,
    )

    summary = client.get("/api/v1/summary").json()
    assert summary["total_readings"] == 3
    assert summary["total_stations"] == 2
    assert summary["total_alerts"] == 1
    assert summary["alert_percentage"] == 33.33
    assert len(summary["by_watershed"]) == 2

    camana = next(w for w in summary["by_watershed"] if w["watershed"] == "Camaná")
    assert camana["total_readings"] == 2
    assert camana["total_alerts"] == 1
    assert camana["alert_percentage"] == 50.0
    assert camana["avg_water_temp_c"] == 15.0
    assert camana["avg_ph"] == 8.5
    assert camana["avg_dissolved_oxygen_mg_l"] == 6.0
    assert camana["avg_electrical_conductivity_us_cm"] == 600.0


def test_etl_sample_csv_compatibility(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Verify rows from Fase 1 ETL sample CSV ingest cleanly into Fase 2 API."""
    assert SAMPLE_CSV_PATH.exists(), f"Missing ETL sample file: {SAMPLE_CSV_PATH}"

    with SAMPLE_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))[:10]

    assert len(rows) == 10
    for row in rows:
        payload = {
            "watershed": row["watershed"],
            "station_id": row["station_id"],
            "location": row["location"],
            "latitude": float(row["latitude"]) if row["latitude"] else None,
            "longitude": float(row["longitude"]) if row["longitude"] else None,
            "sample_date": row["sample_date"],
            "water_temp_c": float(row["water_temp_c"]),
            "ph": float(row["ph"]),
            "dissolved_oxygen_mg_l": float(row["dissolved_oxygen_mg_l"]),
            "electrical_conductivity_us_cm": float(
                row["electrical_conductivity_us_cm"]
            ),
        }
        resp = client.post("/api/v1/telemetry", json=payload, headers=auth_headers)
        assert resp.status_code == 201

    summary = client.get("/api/v1/summary").json()
    assert summary["total_readings"] == 10
    assert summary["total_stations"] >= 1
