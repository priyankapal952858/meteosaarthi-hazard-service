"""
Backup flood signal based on recent river-discharge anomalies.

This is not interchangeable with the historical NRSC/ISRO atlas. It is a
coordinate-based, near-real-time signal used only when the atlas has no
state-level data.
"""

from statistics import mean

import requests


FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"
FLOOD_API_TIMEOUT_SECONDS = 2


def _classify_discharge_ratio(ratio: float):
    if ratio >= 3:
        return {"level": "VERY_HIGH", "score": 80}

    if ratio >= 2:
        return {"level": "HIGH", "score": 60}

    if ratio >= 1.5:
        return {"level": "MODERATE", "score": 40}

    if ratio >= 1.1:
        return {"level": "LOW", "score": 20}

    return {"level": "MINIMAL", "score": 10}


def get_backup_flood_baseline(state_name: str, lat: float, lon: float):
    """Return a river-discharge anomaly signal for an uncovered location."""

    try:
        response = requests.get(
            FLOOD_API_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "river_discharge",
                "past_days": 30,
                "forecast_days": 1,
            },
            timeout=FLOOD_API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        values = payload["daily"]["river_discharge"]

        if len(values) < 2 or any(value is None for value in values):
            return None

        current_discharge = values[-1]
        reference_mean = mean(values[:-1])

        if reference_mean <= 0:
            return None

        ratio = current_discharge / reference_mean

        return {
            "status": "available",
            "state": state_name,
            "severity": _classify_discharge_ratio(ratio),
            "river_discharge_m3_per_s": current_discharge,
            "reference_mean_m3_per_s": round(reference_mean, 3),
            "discharge_ratio": round(ratio, 3),
            "data_type": "river_discharge_anomaly",
            "data_period": "previous 30 days compared with latest day",
            "source": "Open-Meteo Flood API",
            "disclaimer": (
                "This is a coordinate-based river-discharge anomaly signal, "
                "not historical flood-affected area and not a flood forecast."
            ),
        }

    except (
        requests.exceptions.RequestException,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return None
