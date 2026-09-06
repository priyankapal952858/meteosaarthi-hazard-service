"""
Tests for the FastAPI application (app.main).

External dependencies (Open-Meteo rainfall fetch, GIS state boundary
lookup) are mocked throughout so these tests run fast, offline, and
without needing the real state_NWIC.GeoJSON file. This also lets us
directly exercise DEGRADED MODE scenarios: what happens when the
rainfall source fails, when no state can be determined, and when the
flood hazard data file itself is missing or corrupted.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


SUCCESSFUL_STATE_BOUNDARY_MAHARASHTRA = {
    "status": "success",
    "found": True,
    "state": "Maharashtra",
    "geometry": {"type": "Point", "coordinates": [72.8777, 19.076]},
    "coordinate_reference_system": "EPSG:4326"
}

NOT_FOUND_STATE_BOUNDARY = {
    "status": "success",
    "found": False,
    "message": "Location is outside the available state boundaries."
}

SUCCESSFUL_RAINFALL = {
    "status": "success",
    "source": "Open-Meteo",
    "location": {"latitude": 19.076, "longitude": 72.8777},
    "timezone": "Asia/Kolkata",
    "hourly": {
        "time": ["2026-01-01T00:00"],
        "rainfall_mm": [10.0]
    }
}

FAILED_RAINFALL = {
    "status": "error",
    "message": "Unable to fetch rainfall data: connection timed out"
}


class TestHealthAndCapabilities:

    def test_health_returns_200_and_healthy_status(self):
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"

    def test_capabilities_returns_expected_endpoints(self):
        response = client.get("/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert "/maps/risk" in body["endpoints"]
        assert "/alerts/current" in body["endpoints"]
        assert body["endpoints"]["/maps/radar"]["integration_status"] == "not_integrated"

    def test_responses_include_trace_headers(self):
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        assert "X-Trace-ID" in response.headers


class TestMapsRiskHappyPath:

    @patch("app.main.get_state_boundary")
    def test_manual_rainfall_maharashtra(self, mock_state_boundary):
        mock_state_boundary.return_value = SUCCESSFUL_STATE_BOUNDARY_MAHARASHTRA

        response = client.get("/maps/risk?lat=19.0760&lon=72.8777&rainfall=10")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["state_boundary"]["state"] == "Maharashtra"
        assert body["flood_hazard"]["status"] == "available"
        assert body["risk"]["level"] == "HIGH"
        assert body["risk"]["flood_baseline_included"] is True

    @patch("app.main.get_state_boundary")
    def test_state_not_found_still_returns_rainfall_only_risk(self, mock_state_boundary):
        mock_state_boundary.return_value = NOT_FOUND_STATE_BOUNDARY

        response = client.get("/maps/risk?lat=0&lon=0&rainfall=10")

        assert response.status_code == 200
        body = response.json()
        assert body["flood_hazard"]["status"] == "unavailable"
        assert body["risk"]["flood_baseline_included"] is False
        # Rainfall-only risk should still be computed correctly.
        assert body["risk"]["level"] == "HIGH"

    @patch("app.main.get_state_boundary")
    @patch("app.main.get_rainfall_from_open_meteo")
    @patch("app.main.get_current_rainfall")
    def test_auto_rainfall_fetch_when_not_provided(
        self, mock_get_current, mock_get_rainfall, mock_state_boundary
    ):
        mock_state_boundary.return_value = SUCCESSFUL_STATE_BOUNDARY_MAHARASHTRA
        mock_get_rainfall.return_value = SUCCESSFUL_RAINFALL
        mock_get_current.return_value = 10.0

        response = client.get("/maps/risk?lat=19.0760&lon=72.8777")

        assert response.status_code == 200
        body = response.json()
        assert body["rainfall"]["source"] == "Open-Meteo"


class TestMapsRiskInvalidInput:

    def test_invalid_latitude_returns_error(self):
        response = client.get("/maps/risk?lat=999&lon=72.8777&rainfall=10")
        assert response.status_code == 200  # app returns error dict, not HTTP error
        body = response.json()
        assert body["status"] == "error"

    def test_missing_required_params_returns_422(self):
        response = client.get("/maps/risk")
        assert response.status_code == 422


class TestTraceableMapErrors:

    @patch("app.main.process_radar_data")
    def test_radar_error_body_includes_trace_ids(self, mock_process_radar):
        mock_process_radar.return_value = {
            "status": "error",
            "message": "Radar source unavailable"
        }

        response = client.get("/maps/radar?lat=19.0760&lon=72.8777")

        assert response.json()["status"] == "error"
        assert response.json()["request_id"] is not None
        assert response.json()["trace_id"] is not None

    @patch("app.main.get_rainfall_from_open_meteo")
    def test_rainfall_error_body_includes_trace_ids(self, mock_get_rainfall):
        mock_get_rainfall.return_value = FAILED_RAINFALL

        response = client.get("/maps/rainfall?lat=19.0760&lon=72.8777")

        assert response.json()["status"] == "error"
        assert response.json()["request_id"] is not None
        assert response.json()["trace_id"] is not None


class TestDegradedMode:
    """
    Explicit tests for the 'test degraded mode' requirement: the service
    should stay usable (or fail cleanly with request/trace IDs attached)
    when upstream dependencies are unavailable, rather than crashing.
    """

    @patch("app.main.get_rainfall_from_open_meteo")
    def test_rainfall_source_down_returns_clean_error_with_trace_ids(
        self, mock_get_rainfall
    ):
        mock_get_rainfall.return_value = FAILED_RAINFALL

        response = client.get("/maps/risk?lat=19.0760&lon=72.8777")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert "request_id" in body
        assert "trace_id" in body
        assert body["request_id"] is not None

    @patch("app.main.get_state_boundary")
    def test_state_boundary_lookup_failure_does_not_crash_risk_endpoint(
        self, mock_state_boundary
    ):
        """
        If the GIS boundary lookup itself errors out (e.g. the GeoJSON
        file is missing or corrupted on disk), /maps/risk must still
        respond rather than raising an unhandled exception — it should
        fall back to rainfall-only risk.
        """
        mock_state_boundary.return_value = {
            "status": "error",
            "message": "Unable to read state boundary file."
        }

        response = client.get("/maps/risk?lat=19.0760&lon=72.8777&rainfall=10")

        assert response.status_code == 200
        body = response.json()
        # _get_state_name() treats a non-"success" boundary status as
        # "no state determined", so the flood baseline correctly falls
        # back to unavailable instead of crashing.
        assert body["flood_hazard"]["status"] == "unavailable"
        assert body["risk"]["level"] == "HIGH"  # rainfall-only still works

    def test_flood_hazard_data_file_missing_degrades_gracefully(self, tmp_path, monkeypatch):
        """
        Simulates the flood_hazard_state_stats.json file being deleted
        or corrupted on disk. get_flood_baseline() must return a clean
        'error' status rather than raising, and the risk pipeline must
        still complete using rainfall alone.
        """
        import app.flood_hazard as flood_hazard_module

        # Point the module at a path that does not exist, and clear its
        # cache so the next call is forced to re-read from disk.
        monkeypatch.setattr(
            flood_hazard_module, "_DATA_PATH", str(tmp_path / "does_not_exist.json")
        )
        monkeypatch.setattr(flood_hazard_module, "_CACHE", None)

        result = flood_hazard_module.get_flood_baseline("Maharashtra")

        assert result["status"] == "error"

    def test_flood_hazard_corrupted_file_degrades_gracefully(self, tmp_path, monkeypatch):
        """
        Simulates a corrupted (invalid JSON) data file — must not crash.
        """
        import app.flood_hazard as flood_hazard_module

        bad_file = tmp_path / "corrupted.json"
        bad_file.write_text("{ this is not valid json ")

        monkeypatch.setattr(flood_hazard_module, "_DATA_PATH", str(bad_file))
        monkeypatch.setattr(flood_hazard_module, "_CACHE", None)

        result = flood_hazard_module.get_flood_baseline("Maharashtra")

        assert result["status"] == "error"

    def test_flood_hazard_wrong_json_structure_degrades_gracefully(
        self, tmp_path, monkeypatch
    ):
        """A valid JSON document with no state data must also fail cleanly."""
        import app.flood_hazard as flood_hazard_module

        malformed_file = tmp_path / "wrong_structure.json"
        malformed_file.write_text("{\"unexpected\": []}")

        monkeypatch.setattr(
            flood_hazard_module, "_DATA_PATH", str(malformed_file)
        )
        monkeypatch.setattr(flood_hazard_module, "_CACHE", None)

        result = flood_hazard_module.get_flood_baseline("Maharashtra")

        assert result["status"] == "error"


class TestAlertsCurrent:

    @patch("app.main.get_state_boundary")
    def test_planned_alerts_path_is_supported(self, mock_state_boundary):
        mock_state_boundary.return_value = SUCCESSFUL_STATE_BOUNDARY_MAHARASHTRA

        response = client.get("/alerts?lat=19.0760&lon=72.8777&rainfall=10")

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @patch("app.main.get_state_boundary")
    def test_alerts_current_includes_flood_hazard_field(self, mock_state_boundary):
        mock_state_boundary.return_value = SUCCESSFUL_STATE_BOUNDARY_MAHARASHTRA

        response = client.get("/alerts/current?lat=19.0760&lon=72.8777&rainfall=10")

        assert response.status_code == 200
        body = response.json()
        assert "flood_hazard" in body
        assert body["flood_hazard"]["status"] == "available"
        assert any(a["type"] == "Flood Hazard (Historical)" for a in body["alerts"])
