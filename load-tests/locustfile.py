"""Locust load-testing suite for the Arequipa IoT Water Quality API.

Loads real cleaned records from data/processed/arequipa_iot_clean.csv and
simulates concurrent ESP32 sensor nodes posting to POST /api/v1/telemetry.

Firestore free-tier reminder (20,000 writes/day):
  Each POST /api/v1/telemetry performs 2 Firestore writes:
    1) Insert into `telemetry`
    2) Upsert into `stations`
  With wait_time = 2-5 s (~0.28 req/s per user):
    - Scenario 1 (5 users,   1m):  ~85 POSTs   (~170 Firestore writes)
    - Scenario 2 (50 users,  1m):  ~850 POSTs  (~1,700 Firestore writes)
    - Scenario 3 (200 users, 1m):  ~3,400 POSTs (~6,800 Firestore writes)
  Total across all 3 scenarios: ~8,670 writes (< 45% of daily free tier).

Usage examples (run from project root):
  # Set target API key first (NEVER hardcode in this file)
  $env:IOT_API_KEY = "your-api-key"

  # Scenario 1: 5 concurrent sensors (1 min)
  locust -f load-tests/locustfile.py --headless -u 5 -r 5 -t 1m `
    --host http://127.0.0.1:8080 --csv load-tests/results_5_users

  # Scenario 2: 50 concurrent sensors (1 min)
  locust -f load-tests/locustfile.py --headless -u 50 -r 10 -t 1m `
    --host http://127.0.0.1:8080 --csv load-tests/results_50_users

  # Scenario 3: 200 concurrent sensors (1 min - Cloud Run autoscaling test)
  locust -f load-tests/locustfile.py --headless -u 200 -r 25 -t 1m `
    --host https://YOUR-CLOUD-RUN-URL --csv load-tests/results_200_users
"""

from __future__ import annotations

import csv
import os
import random
from pathlib import Path
from typing import Any

from locust import HttpUser, between, events, task

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEAN_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "arequipa_iot_clean.csv"

MIN_WAIT_S = float(os.environ.get("LOCUST_MIN_WAIT", "2.0"))
MAX_WAIT_S = float(os.environ.get("LOCUST_MAX_WAIT", "5.0"))


def load_clean_dataset(csv_path: Path) -> list[dict[str, Any]]:
    """Load all cleaned Arequipa readings into TelemetryIn-compatible dicts."""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No se encontró el dataset limpio: {csv_path}. Ejecuta primero etl/clean_arequipa_data.py."
        )

    records: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            records.append(
                {
                    "watershed": row["watershed"].strip(),
                    "station_id": row["station_id"].strip(),
                    "location": (row.get("location") or "").strip(),
                    "latitude": float(row["latitude"]) if row.get("latitude") else None,
                    "longitude": float(row["longitude"]) if row.get("longitude") else None,
                    "sample_date": row["sample_date"].strip(),
                    "water_temp_c": float(row["water_temp_c"]),
                    "ph": float(row["ph"]),
                    "dissolved_oxygen_mg_l": float(row["dissolved_oxygen_mg_l"]),
                    "electrical_conductivity_us_cm": float(
                        row["electrical_conductivity_us_cm"]
                    ),
                }
            )
    return records


DATASET_RECORDS: list[dict[str, Any]] = load_clean_dataset(CLEAN_CSV_PATH)
API_KEY: str = os.environ.get("IOT_API_KEY", "").strip()


@events.test_start.add_listener
def _on_test_start(environment: Any, **kwargs: Any) -> None:  # noqa: ARG001
    if not API_KEY:
        print(
            "[ADVERTENCIA] IOT_API_KEY no está definida en el entorno. "
            "Las peticiones POST /api/v1/telemetry responderán HTTP 401."
        )
    else:
        print(
            f"[Locust] Dataset cargado: {len(DATASET_RECORDS)} lecturas reales de Arequipa "
            f"(wait_time={MIN_WAIT_S}s-{MAX_WAIT_S}s)."
        )


class ESP32SensorUser(HttpUser):
    """Simulates an ESP32 water-quality sensor node and light dashboard polling."""

    wait_time = between(MIN_WAIT_S, MAX_WAIT_S)

    @task(8)
    def send_telemetry(self) -> None:
        payload = random.choice(DATASET_RECORDS)
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": API_KEY,
        }
        with self.client.post(
            "/api/v1/telemetry",
            json=payload,
            headers=headers,
            name="POST /api/v1/telemetry",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(
                    f"HTTP {response.status_code}: {response.text[:120]}"
                )

    @task(1)
    def read_stations(self) -> None:
        self.client.get("/api/v1/stations", name="GET /api/v1/stations")

    @task(1)
    def health_check(self) -> None:
        self.client.get("/health", name="GET /health")
