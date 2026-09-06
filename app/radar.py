from app.rainfall_data import (
    get_rainfall_from_open_meteo,
    get_current_rainfall
)


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
RADAR_INTEGRATION_STATUS = "not_integrated"
RADAR_INTEGRATION_NOTE = (
    "Real weather radar imagery is not yet integrated into this service. "
    "IMD (India Meteorological Department) publishes an official Radar "
    "Image API, but per-station radar coverage (each station has a "
    "limited ~250-500km range) means there is no single unified 'India "
    "radar' layer the way there is for rainfall. Integration is pending "
    "access to IMD's registered Radar Image API endpoint. Until then, "
    "this endpoint returns Open-Meteo rainfall data as a substitute "
    "signal, clearly marked as such below — never presented as radar "
    "imagery."
)


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
