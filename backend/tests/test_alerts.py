"""Unit tests for water-quality alert threshold evaluation and config helpers."""

from __future__ import annotations

import pytest

from app.alerts import evaluate_alerts
from app.config import (
    DO_MIN_THRESHOLD,
    EC_MAX_THRESHOLD,
    PH_MAX_THRESHOLD,
    PH_MIN_THRESHOLD,
    get_storage_mode,
)
from app.repository import build_station_doc_id


def test_normal_reading_produces_no_alerts() -> None:
    is_alert, reasons = evaluate_alerts(
        ph=7.5,
        dissolved_oxygen_mg_l=7.2,
        electrical_conductivity_us_cm=450.0,
    )
    assert is_alert is False
    assert reasons == []


def test_exact_boundary_values_are_not_alerts() -> None:
    is_alert_low, reasons_low = evaluate_alerts(
        ph=PH_MIN_THRESHOLD,
        dissolved_oxygen_mg_l=DO_MIN_THRESHOLD,
        electrical_conductivity_us_cm=EC_MAX_THRESHOLD,
    )
    assert is_alert_low is False
    assert reasons_low == []

    is_alert_high, reasons_high = evaluate_alerts(
        ph=PH_MAX_THRESHOLD,
        dissolved_oxygen_mg_l=DO_MIN_THRESHOLD,
        electrical_conductivity_us_cm=EC_MAX_THRESHOLD,
    )
    assert is_alert_high is False
    assert reasons_high == []


def test_low_ph_alert() -> None:
    is_alert, reasons = evaluate_alerts(
        ph=5.8,
        dissolved_oxygen_mg_l=6.5,
        electrical_conductivity_us_cm=500.0,
    )
    assert is_alert is True
    assert len(reasons) == 1
    assert "pH bajo" in reasons[0]


def test_high_ph_alert() -> None:
    is_alert, reasons = evaluate_alerts(
        ph=9.02,
        dissolved_oxygen_mg_l=6.72,
        electrical_conductivity_us_cm=84.75,
    )
    assert is_alert is True
    assert len(reasons) == 1
    assert "pH alto" in reasons[0]


def test_low_dissolved_oxygen_alert() -> None:
    is_alert, reasons = evaluate_alerts(
        ph=7.4,
        dissolved_oxygen_mg_l=3.1,
        electrical_conductivity_us_cm=600.0,
    )
    assert is_alert is True
    assert len(reasons) == 1
    assert "Oxígeno disuelto bajo" in reasons[0]


def test_high_conductivity_alert() -> None:
    is_alert, reasons = evaluate_alerts(
        ph=7.8,
        dissolved_oxygen_mg_l=6.0,
        electrical_conductivity_us_cm=3150.0,
    )
    assert is_alert is True
    assert len(reasons) == 1
    assert "Conductividad alta" in reasons[0]


def test_multiple_simultaneous_alerts() -> None:
    is_alert, reasons = evaluate_alerts(
        ph=4.2,
        dissolved_oxygen_mg_l=2.5,
        electrical_conductivity_us_cm=4200.0,
    )
    assert is_alert is True
    assert len(reasons) == 3
    joined = " | ".join(reasons)
    assert "pH bajo" in joined
    assert "Oxígeno disuelto bajo" in joined
    assert "Conductividad alta" in joined


def test_build_station_doc_id_sanitizes_slashes() -> None:
    assert build_station_doc_id("Camaná", "QAroc1") == "Camaná_QAroc1"
    assert build_station_doc_id("Chili/Alto", "S/1") == "Chili_Alto_S_1"


def test_invalid_storage_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_MODE", "postgres")
    with pytest.raises(ValueError, match="Unsupported STORAGE_MODE"):
        get_storage_mode()
