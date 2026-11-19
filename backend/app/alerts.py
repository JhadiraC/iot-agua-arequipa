"""Alert evaluation rules for incoming water quality telemetry."""

from __future__ import annotations

from app.config import (
    DO_MIN_THRESHOLD,
    EC_MAX_THRESHOLD,
    PH_MAX_THRESHOLD,
    PH_MIN_THRESHOLD,
)


def evaluate_alerts(
    ph: float,
    dissolved_oxygen_mg_l: float,
    electrical_conductivity_us_cm: float,
) -> tuple[bool, list[str]]:
    """Evaluate referential water-quality thresholds and return (is_alert, reasons)."""
    reasons: list[str] = []

    if ph < PH_MIN_THRESHOLD:
        reasons.append(f"pH bajo ({ph:.2f} < {PH_MIN_THRESHOLD})")
    elif ph > PH_MAX_THRESHOLD:
        reasons.append(f"pH alto ({ph:.2f} > {PH_MAX_THRESHOLD})")

    if dissolved_oxygen_mg_l < DO_MIN_THRESHOLD:
        reasons.append(
            f"Oxígeno disuelto bajo ({dissolved_oxygen_mg_l:.2f} < {DO_MIN_THRESHOLD} mg/L)"
        )

    if electrical_conductivity_us_cm > EC_MAX_THRESHOLD:
        reasons.append(
            f"Conductividad alta ({electrical_conductivity_us_cm:.2f} > {EC_MAX_THRESHOLD} µS/cm)"
        )

    return (len(reasons) > 0, reasons)
