"""ETL script to clean and unify Arequipa surface water quality data (5 watersheds).

Source: Rymes et al., Data in Brief, 2024 (data/raw/*.xlsx)
Outputs in data/processed/:
  - arequipa_iot_clean.csv
  - arequipa_sample_15_stations.csv
  - etl_report.json
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import openpyxl

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

WATERSHED_FILES: list[tuple[str, str, str]] = [
    ("Camaná", "Camana_Water_Quality_Data_Final_2024_7_13.xlsx", "Camaná WQ Aqueous"),
    ("Chili", "Chili_Water_Quality_Data_Final_2024_7_13.xlsx", "Chili WQ Aqueous"),
    ("Ocoña", "Ocona_Water_Quality_Data_Final_2024_7_13.xlsx", "Ocoña WQ Aqueous"),
    ("Tambo", "Tambo_Water_Quality_Data_Final_2024_7_13.xlsx", "Tambo WQ Aqueous"),
    ("Yauca", "Yauca_Water_Quality_Data_Final_2024_7_13.xlsx", "Yauca WQ Aqueous"),
]

OUTPUT_COLUMNS = [
    "watershed",
    "station_id",
    "location",
    "latitude",
    "longitude",
    "sample_date",
    "water_temp_c",
    "ph",
    "dissolved_oxygen_mg_l",
    "electrical_conductivity_us_cm",
]

NULL_STRINGS = {"", "na", "n/a", "nan", "null", "none", "nd", "n.d.", "-", "--"}


def normalize_column_name(name: Any) -> str:
    """Remove newlines and collapse duplicate whitespace."""
    if name is None:
        return ""
    text = str(name).replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_string(value: Any) -> str:
    """Normalize string fields; return empty string for null-like values."""
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value).replace("\r", " ").replace("\n", " ")).strip()
    if text.lower() in NULL_STRINGS:
        return ""
    return text


def parse_float(value: Any) -> float | None:
    """Parse numeric value to float, returning None for missing or non-numeric entries."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else f
    text = str(value).strip().replace(",", ".")
    if text.lower() in NULL_STRINGS:
        return None
    try:
        f = float(text)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except ValueError:
        return None


def parse_sample_date(value: Any) -> str | None:
    """Parse Excel datetime/date/serial or string dates (e.g. '22-Oct-2013') to YYYY-MM-DD."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)) and not math.isnan(value):
        # Excel 1900 date system serial number
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=float(value))).date().isoformat()

    text = str(value).strip()
    if not text or text.lower() in NULL_STRINGS:
        return None

    # Normalize Spanish/English month abbreviations (e.g. 'Sept' -> 'Sep')
    month_aliases = {
        "ene": "Jan",
        "abr": "Apr",
        "ago": "Aug",
        "sept": "Sep",
        "set": "Sep",
        "dic": "Dec",
    }
    normalized = text
    for alias, en in month_aliases.items():
        normalized = re.sub(rf"\b{alias}\b", en, normalized, flags=re.IGNORECASE)

    formats = (
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d-%b-%y",
        "%d/%b/%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def find_column_index(headers: list[str], target: str) -> int:
    """Find exact column index (case-insensitive) after normalization."""
    target_lower = target.lower()
    for idx, col in enumerate(headers):
        if col.lower() == target_lower:
            return idx
    raise KeyError(f"Column '{target}' not found in headers.")


def find_conductivity_column(headers: list[str]) -> tuple[int, str]:
    """Dynamically detect the column containing 'Electrical Conductivity'."""
    for idx, col in enumerate(headers):
        if "electrical conductivity" in col.lower():
            return idx, col
    raise KeyError("No column containing 'Electrical Conductivity' found.")


def check_physical_anomalies(
    water_temp_c: float,
    ph: float,
    dissolved_oxygen_mg_l: float,
    electrical_conductivity_us_cm: float,
) -> list[str]:
    """Return list of physical transcription anomaly reasons (empty if valid)."""
    reasons: list[str] = []
    if not (0.0 <= ph <= 14.0):
        reasons.append(f"ph={ph} fuera de [0, 14]")
    if not (0.0 <= water_temp_c <= 50.0):
        reasons.append(f"water_temp_c={water_temp_c} fuera de [0, 50]")
    if not (0.0 <= dissolved_oxygen_mg_l <= 25.0):
        reasons.append(f"dissolved_oxygen_mg_l={dissolved_oxygen_mg_l} fuera de [0, 25]")
    if electrical_conductivity_us_cm <= 0.0:
        reasons.append(
            f"electrical_conductivity_us_cm={electrical_conductivity_us_cm} <= 0"
        )
    return reasons


def process_watershed(
    watershed_name: str,
    filename: str,
    sheet_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Process one watershed Excel file and return clean rows, stats, and anomalies."""
    filepath = RAW_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Missing raw file: {filepath}")

    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    if sheet_name not in wb.sheetnames:
        wb.close()
        raise ValueError(f"Sheet '{sheet_name}' not found in {filename}")

    ws = wb[sheet_name]
    rows_iter = ws.iter_rows(values_only=True)
    raw_header = next(rows_iter)
    headers = [normalize_column_name(c) for c in raw_header]

    col_station = find_column_index(headers, "Station ID Code")
    col_location = find_column_index(headers, "Body of Water/Description of Location")
    col_lat = find_column_index(headers, "Latitude (WGS84)")
    col_lon = find_column_index(headers, "Longitude (WGS84)")
    col_date = find_column_index(headers, "Date Sample Collected (DD-MO-YYYY)")
    col_temp = find_column_index(headers, "Water Temp. C")
    col_ph = find_column_index(headers, "pH")
    col_do = find_column_index(headers, "DO (mg/L)")
    col_ec, ec_col_name = find_conductivity_column(headers)

    raw_rows = 0
    dropped_nulls = 0
    dropped_anomalies = 0
    clean_rows: list[dict[str, Any]] = []
    anomalies_detail: list[dict[str, Any]] = []

    def safe_get(row: tuple[Any, ...], idx: int) -> Any:
        return row[idx] if idx < len(row) else None

    for excel_row_num, row in enumerate(rows_iter, start=2):
        # Skip completely empty trailing rows
        if row is None or all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        raw_rows += 1

        station_id = clean_string(safe_get(row, col_station))
        location = clean_string(safe_get(row, col_location))
        latitude = parse_float(safe_get(row, col_lat))
        longitude = parse_float(safe_get(row, col_lon))
        sample_date = parse_sample_date(safe_get(row, col_date))

        water_temp_c = parse_float(safe_get(row, col_temp))
        ph = parse_float(safe_get(row, col_ph))
        dissolved_oxygen_mg_l = parse_float(safe_get(row, col_do))
        electrical_conductivity_us_cm = parse_float(safe_get(row, col_ec))

        # Drop rows with nulls in any of the 4 IoT parameters
        if (
            water_temp_c is None
            or ph is None
            or dissolved_oxygen_mg_l is None
            or electrical_conductivity_us_cm is None
        ):
            dropped_nulls += 1
            continue

        reasons = check_physical_anomalies(
            water_temp_c=water_temp_c,
            ph=ph,
            dissolved_oxygen_mg_l=dissolved_oxygen_mg_l,
            electrical_conductivity_us_cm=electrical_conductivity_us_cm,
        )
        if reasons:
            dropped_anomalies += 1
            anomalies_detail.append(
                {
                    "watershed": watershed_name,
                    "source_file": filename,
                    "excel_row": excel_row_num,
                    "station_id": station_id,
                    "sample_date": sample_date,
                    "water_temp_c": water_temp_c,
                    "ph": ph,
                    "dissolved_oxygen_mg_l": dissolved_oxygen_mg_l,
                    "electrical_conductivity_us_cm": electrical_conductivity_us_cm,
                    "reasons": reasons,
                }
            )
            continue

        clean_rows.append(
            {
                "watershed": watershed_name,
                "station_id": station_id,
                "location": location,
                "latitude": "" if latitude is None else round(latitude, 6),
                "longitude": "" if longitude is None else round(longitude, 6),
                "sample_date": sample_date or "",
                "water_temp_c": round(water_temp_c, 4),
                "ph": round(ph, 4),
                "dissolved_oxygen_mg_l": round(dissolved_oxygen_mg_l, 4),
                "electrical_conductivity_us_cm": round(electrical_conductivity_us_cm, 4),
            }
        )

    wb.close()

    valid_stations = sorted({r["station_id"] for r in clean_rows if r["station_id"]})
    stats = {
        "source_file": filename,
        "sheet_name": sheet_name,
        "detected_conductivity_column": ec_col_name,
        "raw_rows": raw_rows,
        "dropped_null_iot_params": dropped_nulls,
        "dropped_physical_anomalies": dropped_anomalies,
        "clean_rows": len(clean_rows),
        "valid_stations_count": len(valid_stations),
    }
    return clean_rows, stats, anomalies_detail


def write_csv(filepath: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows to UTF-8 CSV using OUTPUT_COLUMNS."""
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run_etl() -> dict[str, Any]:
    """Execute full ETL pipeline across all 5 watersheds."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    all_clean_rows: list[dict[str, Any]] = []
    watershed_stats: dict[str, Any] = {}
    all_anomalies: list[dict[str, Any]] = []

    for watershed_name, filename, sheet_name in WATERSHED_FILES:
        clean_rows, stats, anomalies = process_watershed(
            watershed_name=watershed_name,
            filename=filename,
            sheet_name=sheet_name,
        )
        all_clean_rows.extend(clean_rows)
        watershed_stats[watershed_name] = stats
        all_anomalies.extend(anomalies)

    # Sort clean dataset deterministically by watershed, station_id, sample_date
    all_clean_rows.sort(
        key=lambda r: (r["watershed"], r["station_id"], r["sample_date"])
    )

    # Select top 3 stations with most records per watershed (15 simulated ESP32 nodes)
    by_watershed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_clean_rows:
        by_watershed[row["watershed"]].append(row)

    selected_stations_summary: dict[str, list[dict[str, Any]]] = {}
    sample_15_rows: list[dict[str, Any]] = []

    for watershed_name, _, _ in WATERSHED_FILES:
        w_rows = by_watershed[watershed_name]
        counts = Counter(r["station_id"] for r in w_rows if r["station_id"])
        # Sort by (-count, station_id) for deterministic tie-breaking
        top_3 = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:3]
        top_3_ids = {station_id for station_id, _ in top_3}
        selected_stations_summary[watershed_name] = [
            {"station_id": sid, "records": cnt} for sid, cnt in top_3
        ]
        sample_15_rows.extend(
            r for r in w_rows if r["station_id"] in top_3_ids
        )

    sample_15_rows.sort(
        key=lambda r: (r["watershed"], r["station_id"], r["sample_date"])
    )

    clean_csv_path = PROCESSED_DIR / "arequipa_iot_clean.csv"
    sample_csv_path = PROCESSED_DIR / "arequipa_sample_15_stations.csv"
    report_json_path = PROCESSED_DIR / "etl_report.json"

    write_csv(clean_csv_path, all_clean_rows)
    write_csv(sample_csv_path, sample_15_rows)

    unique_stations_total = len(
        {(r["watershed"], r["station_id"]) for r in all_clean_rows if r["station_id"]}
    )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totals": {
            "raw_rows": sum(s["raw_rows"] for s in watershed_stats.values()),
            "dropped_null_iot_params": sum(
                s["dropped_null_iot_params"] for s in watershed_stats.values()
            ),
            "dropped_physical_anomalies": sum(
                s["dropped_physical_anomalies"] for s in watershed_stats.values()
            ),
            "clean_rows": len(all_clean_rows),
            "valid_stations_count": unique_stations_total,
            "sample_15_stations_rows": len(sample_15_rows),
        },
        "by_watershed": watershed_stats,
        "physical_anomalies_discarded": all_anomalies,
        "sample_15_stations_selected": selected_stations_summary,
        "outputs": {
            "clean_csv": str(clean_csv_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "sample_15_stations_csv": str(sample_csv_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "etl_report_json": str(report_json_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        },
    }

    with report_json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


if __name__ == "__main__":
    result = run_etl()
    print(json.dumps(result, indent=2, ensure_ascii=False))
