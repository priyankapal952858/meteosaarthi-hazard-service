"""
Local application performance smoke tests.

Upstream network calls are mocked so this measures service processing and
serialization overhead, not internet-provider latency.
"""

from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

STATE_BOUNDARY = {
    "status": "success",
    "found": True,
    "state": "Maharashtra",
    "geometry": {"type": "Point", "coordinates": [72.8777, 19.076]},
    "coordinate_reference_system": "EPSG:4326",
}


@patch("app.main.get_state_boundary", return_value=STATE_BOUNDARY)
def test_risk_endpoint_local_processing_stays_under_two_seconds(
    mock_state_boundary,
):
    durations = []

    for _ in range(10):
        started = perf_counter()
        response = client.get(
            "/maps/risk?lat=19.0760&lon=72.8777&rainfall=10"
        )
        durations.append(perf_counter() - started)

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    assert max(durations) < 2
    assert mock_state_boundary.call_count == 10


@patch("app.main.get_state_boundary", return_value=STATE_BOUNDARY)
def test_risk_endpoint_handles_concurrent_local_requests(mock_state_boundary):
    def request_risk_map(_):
        return client.get(
            "/maps/risk?lat=19.0760&lon=72.8777&rainfall=10"
        )

    started = perf_counter()

    with ThreadPoolExecutor(max_workers=10) as executor:
        responses = list(executor.map(request_risk_map, range(20)))

    elapsed = perf_counter() - started

    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["status"] == "success" for response in responses)
    assert elapsed < 2
    assert mock_state_boundary.call_count == 20
