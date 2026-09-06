"""
Tests for app.radar.

Covers rainfall classification bands, coordinate validation, and —
importantly — that process_radar_data() always honestly labels itself
as a non-integrated rainfall substitute rather than claiming to be
real radar imagery.
"""

from unittest.mock import patch

from app.radar import (
    classify_rainfall,
    validate_coordinates,
    process_rainfall,
    process_radar_data,
    RADAR_INTEGRATION_STATUS,
)


class TestClassifyRainfall:

    def test_negative_is_invalid(self):
        assert classify_rainfall(-1) == "INVALID"

    def test_zero_is_no_rain(self):
        assert classify_rainfall(0) == "NO_RAIN"

    def test_light(self):
        assert classify_rainfall(1.0) == "LIGHT"

    def test_moderate(self):
        assert classify_rainfall(5.0) == "MODERATE"

    def test_heavy(self):
        assert classify_rainfall(10.0) == "HEAVY"

    def test_very_heavy(self):
        assert classify_rainfall(30.0) == "VERY_HEAVY"

    def test_extremely_heavy(self):
        assert classify_rainfall(100.0) == "EXTREMELY_HEAVY"


class TestValidateCoordinates:

    def test_valid(self):
        assert validate_coordinates(19.0, 72.0) == (True, None)

    def test_invalid_lat(self):
        valid, _ = validate_coordinates(91, 72.0)
        assert valid is False

    def test_invalid_lon(self):
        valid, _ = validate_coordinates(19.0, 181)
        assert valid is False


class TestProcessRainfall:

    def test_invalid_coordinates_returns_error(self):
        result = process_rainfall(999, 72.0, 5.0)
        assert result["status"] == "error"

    def test_valid_returns_success_with_intensity(self):
        result = process_rainfall(19.0, 72.0, 10.0)
        assert result["status"] == "success"
        assert result["rainfall"]["intensity"] == "HEAVY"
        assert result["rainfall"]["source"] == "Open-Meteo"


class TestProcessRadarData:

    def test_no_coordinates_returns_not_integrated_status(self):
        result = process_radar_data()
        assert result["status"] == "success"
        assert result["radar"]["integration_status"] == RADAR_INTEGRATION_STATUS
        assert result["radar"]["available"] is False

    def test_never_claims_to_be_real_radar(self):
        """
        Regression guard: this endpoint must never report itself as
        genuinely integrated radar imagery until that integration
        actually exists.
        """
        result = process_radar_data()
        assert result["radar"]["integration_status"] == "not_integrated"
        assert "radar imagery" in result["radar"]["note"].lower()

    def test_invalid_coordinates_returns_error(self):
        result = process_radar_data(999, 72.0)
        assert result["status"] == "error"

    @patch("app.radar.get_rainfall_from_open_meteo")
    @patch("app.radar.get_current_rainfall")
    def test_valid_coordinates_uses_rainfall_as_substitute(
        self, mock_get_current, mock_get_rainfall
    ):
        mock_get_rainfall.return_value = {
            "status": "success",
            "hourly": {"time": [], "rainfall_mm": []}
        }
        mock_get_current.return_value = 12.0

        result = process_radar_data(19.0, 72.0)

        assert result["status"] == "success"
        assert result["radar"]["available"] is False
        assert result["radar"]["integration_status"] == "not_integrated"
        assert result["rainfall"]["intensity"] == "HEAVY"

    @patch("app.radar.get_rainfall_from_open_meteo")
    def test_degrades_gracefully_when_rainfall_source_fails(self, mock_get_rainfall):
        """
        If the upstream Open-Meteo rainfall source fails, this must
        return a clean error rather than crashing.
        """
        mock_get_rainfall.return_value = {
            "status": "error",
            "message": "Unable to fetch rainfall data: connection timed out"
        }

        result = process_radar_data(19.0, 72.0)

        assert result["status"] == "error"
