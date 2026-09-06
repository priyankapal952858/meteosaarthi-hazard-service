"""
Tests for the coordinate-based backup flood signal.
"""

from unittest.mock import Mock, patch

from app.flood_backup import get_backup_flood_baseline
from app.flood_hazard import get_flood_baseline


class TestFloodBackup:

    @patch("app.flood_backup.requests.get")
    def test_returns_river_discharge_anomaly(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "daily": {
                "river_discharge": [1.0, 1.0, 1.0, 2.0]
            }
        }
        mock_get.return_value = response

        result = get_backup_flood_baseline("Goa", 15.49, 73.83)

        assert result["status"] == "available"
        assert result["data_type"] == "river_discharge_anomaly"
        assert result["severity"]["level"] == "HIGH"
        assert result["discharge_ratio"] == 2.0
        assert "flood_affected_area_ha" not in result
        assert mock_get.call_args.kwargs["timeout"] == 2

    @patch("app.flood_backup.requests.get")
    def test_provider_failure_returns_no_backup_value(self, mock_get):
        mock_get.side_effect = OSError("provider unavailable")

        result = get_backup_flood_baseline("Goa", 15.49, 73.83)

        assert result is None

    @patch("app.flood_hazard.get_backup_flood_baseline")
    def test_uncovered_state_uses_backup_when_coordinates_exist(self, mock_backup):
        mock_backup.return_value = {
            "status": "available",
            "state": "Goa",
            "severity": {"level": "MODERATE", "score": 40},
            "discharge_ratio": 1.5,
            "data_type": "river_discharge_anomaly",
        }

        result = get_flood_baseline("Goa", 15.49, 73.83)

        assert result["status"] == "available"
        assert result["data_type"] == "river_discharge_anomaly"
        mock_backup.assert_called_once_with("Goa", 15.49, 73.83)
