"""
Tests for the Open-Meteo rainfall client.
"""

from unittest.mock import Mock, patch

import requests

from app.rainfall_data import (
    UPSTREAM_TIMEOUT_SECONDS,
    get_rainfall_from_open_meteo,
)


class TestRainfallClient:

    @patch("app.rainfall_data.requests.get")
    def test_uses_two_second_upstream_timeout(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "latitude": 19.076,
            "longitude": 72.8777,
            "timezone": "Asia/Kolkata",
            "hourly": {
                "time": ["2026-01-01T00:00"],
                "rain": [10.0],
            },
        }
        mock_get.return_value = response

        result = get_rainfall_from_open_meteo(19.076, 72.8777)

        assert result["status"] == "success"
        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs["timeout"] == UPSTREAM_TIMEOUT_SECONDS
        assert UPSTREAM_TIMEOUT_SECONDS == 2

    @patch("app.rainfall_data.requests.get")
    def test_timeout_returns_clean_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        result = get_rainfall_from_open_meteo(19.076, 72.8777)

        assert result["status"] == "error"
        assert "Unable to fetch rainfall data" in result["message"]
