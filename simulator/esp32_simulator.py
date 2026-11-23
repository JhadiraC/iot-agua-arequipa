"""ESP32 telemetry simulator for Arequipa surface water quality monitoring.

Reads cleaned sample data from data/processed/arequipa_sample_15_stations.csv
and sends HTTP POST requests to the FastAPI /api/v1/telemetry endpoint either
sequentially or concurrently, recording latency metrics to CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "arequipa_sample_15_stations.csv"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "latency_results.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulador de nodos ESP32 enviando telemetría de calidad de agua (Arequipa)."
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("API_URL", "http://127.0.0.1:8080/api/v1/telemetry"),
        help="URL del endpoint POST /api/v1/telemetry (default: http://127.0.0.1:8080/api/v1/telemetry).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("IOT_API_KEY", ""),
        help="API Key para el header X-API-KEY (o variable de entorno IOT_API_KEY).",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Ruta al CSV de entrada (default: data/processed/arequipa_sample_15_stations.csv).",
    )
    parser.add_argument(
        "--mode",
        choices=("sequential", "concurrent"),
        default="sequential",
        help="Modo de envío: 'sequential' o 'concurrent' (default: sequential).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Número de hilos concurrentes (nodos ESP32) en modo concurrent (default: 5).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="Intervalo en segundos entre envíos (default: 0.1).",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="Máximo de registros a enviar (0 = todos los registros del CSV).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout HTTP en segundos por petición (default: 10.0).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Ruta del CSV de salida de latencias (default: simulator/latency_results.csv).",
    )
    return parser.parse_args()


def load_telemetry_rows(csv_path: Path, max_records: int = 0) -> list[dict[str, Any]]:
    """Load CSV rows and transform them into TelemetryIn JSON payloads."""
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo CSV: {csv_path}")

    payloads: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            payload: dict[str, Any] = {
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
            payloads.append(payload)
            if max_records > 0 and len(payloads) >= max_records:
                break
    return payloads


def send_reading(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """Send a single telemetry JSON payload via HTTP POST and measure latency."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        },
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    start = time.perf_counter()
    status_code = 0
    is_alert = False
    error_detail = ""

    parsed_url = urllib_parse.urlparse(url)
    is_loopback = parsed_url.hostname in {"127.0.0.1", "localhost", "::1"}
    opener = (
        urllib_request.build_opener(urllib_request.ProxyHandler({}))
        if is_loopback
        else urllib_request.build_opener()
    )

    try:
        with opener.open(req, timeout=timeout) as resp:
            status_code = resp.status
            raw_resp = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw_resp)
                is_alert = bool(parsed.get("is_alert", False))
            except json.JSONDecodeError:
                pass
    except urllib_error.HTTPError as exc:
        status_code = exc.code
        error_detail = exc.read().decode("utf-8", errors="replace")[:160]
    except Exception as exc:  # noqa: BLE001
        status_code = 0
        error_detail = str(exc)[:160]

    latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return {
        "timestamp": timestamp,
        "station_id": payload["station_id"],
        "watershed": payload["watershed"],
        "status_code": status_code,
        "latency_ms": latency_ms,
        "is_alert": is_alert,
        "error": error_detail,
    }


def run_sequential(
    payloads: list[dict[str, Any]],
    url: str,
    api_key: str,
    interval: float,
    timeout: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    total = len(payloads)
    for idx, payload in enumerate(payloads, start=1):
        res = send_reading(url=url, api_key=api_key, payload=payload, timeout=timeout)
        results.append(res)
        alert_tag = " [ALERTA]" if res["is_alert"] else ""
        print(
            f"[{idx:03d}/{total:03d}] {res['watershed']} / {res['station_id']} -> "
            f"HTTP {res['status_code']} ({res['latency_ms']:.2f} ms){alert_tag}"
        )
        if interval > 0 and idx < total:
            time.sleep(interval)
    return results


def run_concurrent(
    payloads: list[dict[str, Any]],
    url: str,
    api_key: str,
    workers: int,
    interval: float,
    timeout: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    total = len(payloads)

    def _worker_task(item: dict[str, Any]) -> dict[str, Any]:
        res = send_reading(url=url, api_key=api_key, payload=item, timeout=timeout)
        if interval > 0:
            time.sleep(interval)
        return res

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(_worker_task, p) for p in payloads]
        for idx, future in enumerate(as_completed(futures), start=1):
            res = future.result()
            results.append(res)
            alert_tag = " [ALERTA]" if res["is_alert"] else ""
            print(
                f"[{idx:03d}/{total:03d}] {res['watershed']} / {res['station_id']} -> "
                f"HTTP {res['status_code']} ({res['latency_ms']:.2f} ms){alert_tag}"
            )
    return results


def export_latency_csv(results: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["timestamp", "station_id", "status_code", "latency_ms"]
        )
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    "timestamp": row["timestamp"],
                    "station_id": row["station_id"],
                    "status_code": row["status_code"],
                    "latency_ms": row["latency_ms"],
                }
            )


def print_summary(results: list[dict[str, Any]], output_path: Path) -> None:
    if not results:
        print("No se enviaron registros.")
        return

    latencies = [r["latency_ms"] for r in results]
    ok_count = sum(1 for r in results if 200 <= r["status_code"] < 300)
    alert_count = sum(1 for r in results if r["is_alert"])
    err_count = len(results) - ok_count
    sorted_lat = sorted(latencies)
    p95_idx = max(0, min(len(sorted_lat) - 1, int(len(sorted_lat) * 0.95) - 1))

    print("\n=== Resumen de Simulación ESP32 ===")
    print(f"Total enviados : {len(results)}")
    print(f"Exitosos (2xx) : {ok_count}")
    print(f"Errores        : {err_count}")
    print(f"Alertas        : {alert_count}")
    print(f"Latencia prom. : {statistics.mean(latencies):.2f} ms")
    print(f"Latencia p50   : {statistics.median(latencies):.2f} ms")
    print(f"Latencia p95   : {sorted_lat[p95_idx]:.2f} ms")
    print(f"Latencia máx.  : {max(latencies):.2f} ms")
    print(f"CSV exportado  : {output_path}")


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print(
            "Error: Debes proporcionar --api-key o definir la variable de entorno IOT_API_KEY.",
            file=sys.stderr,
        )
        return 1

    payloads = load_telemetry_rows(args.csv, max_records=args.max_records)
    print(
        f"Iniciando simulación ({args.mode}) de {len(payloads)} lecturas hacia {args.url}..."
    )

    if args.mode == "concurrent":
        results = run_concurrent(
            payloads=payloads,
            url=args.url,
            api_key=args.api_key,
            workers=args.workers,
            interval=args.interval,
            timeout=args.timeout,
        )
    else:
        results = run_sequential(
            payloads=payloads,
            url=args.url,
            api_key=args.api_key,
            interval=args.interval,
            timeout=args.timeout,
        )

    export_latency_csv(results, args.output)
    print_summary(results, args.output)
    return 0 if all(200 <= r["status_code"] < 300 for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
