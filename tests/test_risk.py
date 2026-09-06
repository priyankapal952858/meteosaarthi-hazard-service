"""
Tests for app.risk.

Covers: coordinate validation, rainfall-only classification bands,
the full calculate_risk() flow with and without a flood baseline, and
the hazards list construction (including that hazards only fire above
their respective thresholds).
"""

from app.risk import (
    validate_coordinates,
    calculate_rainfall_risk,
    calculate_risk,
)
from app.flood_hazard import get_flood_baseline


class TestValidateCoordinates:

    def test_valid_coordinates(self):
        valid, error = validate_coordinates(19.076, 72.8777)
        assert valid is True
        assert error is None

    def test_invalid_latitude(self):
        valid, error = validate_coordinates(91, 72.8777)
        assert valid is False
        assert "latitude" in error.lower()

    def test_invalid_longitude(self):
        valid, error = validate_coordinates(19.076, 181)
        assert valid is False
        assert "longitude" in error.lower()

    def test_boundary_values_are_valid(self):
        assert validate_coordinates(90, 180)[0] is True
        assert validate_coordinates(-90, -180)[0] is True


class TestCalculateRainfallRisk:

    def test_negative_rainfall_is_unknown(self):
        assert calculate_rainfall_risk(-1)["level"] == "UNKNOWN"

    def test_zero_rainfall_is_low(self):
        result = calculate_rainfall_risk(0)
        assert result == {"level": "LOW", "score": 0}

    def test_light_rain(self):
        assert calculate_rainfall_risk(1.0)["level"] == "LOW"

    def test_moderate_rain(self):
        assert calculate_rainfall_risk(5.0)["level"] == "MODERATE"

    def test_heavy_rain(self):
        assert calculate_rainfall_risk(10.0)["level"] == "HIGH"

    def test_very_heavy_rain(self):
        assert calculate_rainfall_risk(30.0)["level"] == "VERY_HIGH"

    def test_extreme_rain(self):
        assert calculate_rainfall_risk(100.0)["level"] == "EXTREME"


class TestCalculateRisk:

    def test_invalid_coordinates_returns_error(self):
        result = calculate_risk(999, 72.8777, 10.0)
        assert result["status"] == "error"

    def test_no_rainfall_returns_unknown_awaiting_data(self):
        result = calculate_risk(19.076, 72.8777, None)
        assert result["status"] == "success"
        assert result["risk"]["level"] == "UNKNOWN"
        assert result["data_status"] == "awaiting_rainfall_data"
        assert result["hazards"] == []

    def test_rainfall_only_when_no_flood_baseline_given(self):
        result = calculate_risk(19.076, 72.8777, 10.0)
        assert result["status"] == "success"
        assert result["risk"]["level"] == "HIGH"
        assert result["risk"]["score"] == 60

    def test_combines_flood_baseline_when_provided(self):
        flood_baseline = get_flood_baseline("Maharashtra")
        result = calculate_risk(19.076, 72.8777, 10.0, flood_baseline)

        assert result["risk_components"]["flood_baseline"] == flood_baseline
        assert result["risk"]["flood_baseline_included"] is True

    def test_heavy_rainfall_hazard_appears_above_threshold(self):
        result = calculate_risk(19.076, 72.8777, 10.0)
        hazard_types = [h["type"] for h in result["hazards"]]
        assert "Heavy Rainfall" in hazard_types

    def test_no_heavy_rainfall_hazard_below_threshold(self):
        result = calculate_risk(19.076, 72.8777, 2.0)
        hazard_types = [h["type"] for h in result["hazards"]]
        assert "Heavy Rainfall" not in hazard_types

    def test_flood_hazard_appears_for_elevated_baseline(self):
        flood_baseline = get_flood_baseline("Assam")  # VERY_HIGH
        result = calculate_risk(26.2, 92.9, 0.0, flood_baseline)

        hazard_types = [h["type"] for h in result["hazards"]]
        assert "Flood Hazard (Historical)" in hazard_types

        flood_hazard = next(
            h for h in result["hazards"] if h["type"] == "Flood Hazard (Historical)"
        )
        assert "Assam" in flood_hazard["message"]
        assert "historical" in flood_hazard["message"].lower()

    def test_no_flood_hazard_for_unavailable_state(self):
        flood_baseline = get_flood_baseline("Goa")
        result = calculate_risk(15.3, 74.1, 1.0, flood_baseline)

        hazard_types = [h["type"] for h in result["hazards"]]
        assert "Flood Hazard (Historical)" not in hazard_types

    def test_no_flood_hazard_for_low_severity_baseline(self):
        """
        A state with a MINIMAL/LOW baseline should not generate a flood
        hazard entry — only MODERATE/HIGH/VERY_HIGH do.
        """
        flood_baseline = get_flood_baseline("Jharkhand")  # small area -> MINIMAL
        result = calculate_risk(23.6, 85.3, 1.0, flood_baseline)

        hazard_types = [h["type"] for h in result["hazards"]]
        assert "Flood Hazard (Historical)" not in hazard_types

    def test_backup_river_signal_uses_distinct_hazard_label(self):
        backup_baseline = {
            "status": "available",
            "state": "Goa",
            "severity": {"level": "HIGH", "score": 60},
            "discharge_ratio": 2.0,
            "data_type": "river_discharge_anomaly",
            "data_period": "previous 30 days compared with latest day",
        }

        result = calculate_risk(15.49, 73.83, 0.0, backup_baseline)

        backup_hazard = next(
            h for h in result["hazards"]
            if h["type"] == "Flood Hazard (Backup River Signal)"
        )
        assert "2.0 times" in backup_hazard["message"]
        assert "historical flood-area" in backup_hazard["message"]
