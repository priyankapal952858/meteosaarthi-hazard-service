import base64
import os

import requests

from app.rainfall_data import (
    get_rainfall_from_open_meteo,
    get_current_rainfall
)


MOSDAC_RADAR_URL = os.getenv("MOSDAC_RADAR_URL")
MOSDAC_RADAR_TOKEN = os.getenv("MOSDAC_RADAR_TOKEN")
MOSDAC_RADAR_TIMEOUT_SECONDS = 2


def validate_coordinates(lat: float, lon: float):
    """
    Validate latitude and longitude.
    """

    if not -90 <= lat <= 90:
        return False, "Invalid latitude."

    if not -180 <= lon <= 180:
        return False, "Invalid longitude."

    return True, None


def classify_rainfall(rainfall_mm_per_hour: float):
    """
    Classify rainfall intensity.
    """

    if rainfall_mm_per_hour < 0:
        return "INVALID"

    if rainfall_mm_per_hour == 0:
        return "NO_RAIN"

    if rainfall_mm_per_hour < 2.5:
        return "LIGHT"

    if rainfall_mm_per_hour < 7.6:
        return "MODERATE"

    if rainfall_mm_per_hour < 15.6:
        return "HEAVY"

    if rainfall_mm_per_hour < 64.5:
        return "VERY_HEAVY"

    return "EXTREMELY_HEAVY"


def process_rainfall(
    lat: float,
    lon: float,
    rainfall_mm_per_hour: float
):
    """
    Process rainfall information for a location.
    """

    valid, error = validate_coordinates(lat, lon)

    if not valid:
        return {
            "status": "error",
            "message": error
        }

    intensity = classify_rainfall(rainfall_mm_per_hour)

    return {
        "status": "success",
        "location": {
            "latitude": lat,
            "longitude": lon
        },
        "rainfall": {
            "value_mm_per_hour": rainfall_mm_per_hour,
            "intensity": intensity,
            "source": "Open-Meteo"
        }
    }


# Radar imagery integration status. Kept as a single named constant so
# this can be flipped to "integrated" in one place once a real radar
# data source (e.g. IMD's Radar Image API) is wired in, rather than
# hunting through response-building code for prose strings to update.
RADAR_INTEGRATION_STATUS = (
    "configured"
    if MOSDAC_RADAR_URL
    else "not_integrated"
)
RADAR_INTEGRATION_NOTE = (
    "MOSDAC radar imagery is configured through MOSDAC_RADAR_URL. "
    "The endpoint must return an image and accept the documented "
    "latitude/longitude parameters. If it is unset or unavailable, "
    "Open-Meteo rainfall is used as a clearly labeled fallback."
)


def _get_mosdac_radar_image(lat: float, lon: float):
    if not MOSDAC_RADAR_URL:
        return None

    headers = {}
    if MOSDAC_RADAR_TOKEN:
        headers["Authorization"] = f"Bearer {MOSDAC_RADAR_TOKEN}"

    try:
        response = requests.get(
            MOSDAC_RADAR_URL,
            params={"lat": lat, "lon": lon},
            headers=headers,
            timeout=MOSDAC_RADAR_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return None

        return {
            "content_type": content_type.split(";", 1)[0],
            "data_base64": base64.b64encode(response.content).decode("ascii"),
            "source": "MOSDAC",
        }
    except requests.exceptions.RequestException:
        return None


def process_radar_data(
    lat: float = None,
    lon: float = None
):
    """
    Generate rainfall map data for a location, standing in for radar
    imagery until real radar integration is available (see
    RADAR_INTEGRATION_STATUS / RADAR_INTEGRATION_NOTE above).
    """

    if lat is None or lon is None:
        return {
            "status": "success",
            "radar": {
                "integration_status": RADAR_INTEGRATION_STATUS,
                "available": False,
                "source": "Open-Meteo",
                "data_type": "rainfall",
                "note": RADAR_INTEGRATION_NOTE,
                "message": "Location coordinates required for rainfall map data."
            }
        }

    valid, error = validate_coordinates(lat, lon)

    if not valid:
        return {
            "status": "error",
            "message": error
        }

    mosdac_image = _get_mosdac_radar_image(lat, lon)

    if mosdac_image is not None:
        return {
            "status": "success",
            "radar": {
                "integration_status": "integrated",
                "available": True,
                "source": mosdac_image["source"],
                "data_type": "radar_imagery",
                "content_type": mosdac_image["content_type"],
                "image_base64": mosdac_image["data_base64"],
                "note": "Genuine radar imagery fetched from the configured MOSDAC endpoint."
            },
            "location": {
                "latitude": lat,
                "longitude": lon
            }
        }

    rainfall_data = get_rainfall_from_open_meteo(lat, lon)

    if rainfall_data["status"] == "error":
        return rainfall_data

    rainfall = get_current_rainfall(
        rainfall_data["hourly"]
    )

    intensity = classify_rainfall(rainfall)

    return {
        "status": "success",
        "radar": {
            "integration_status": RADAR_INTEGRATION_STATUS,
            "available": False,
            "source": "Open-Meteo",
            "data_type": "rainfall",
            "note": RADAR_INTEGRATION_NOTE
        },
        "location": {
            "latitude": lat,
            "longitude": lon
        },
        "rainfall": {
            "value_mm_per_hour": rainfall,
            "intensity": intensity
        }
    }
