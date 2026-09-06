import requests
from datetime import datetime


UPSTREAM_TIMEOUT_SECONDS = 2


def validate_coordinates(lat: float, lon: float):
    """
    Validate latitude and longitude.
    """

    if not -90 <= lat <= 90:
        return False, "Invalid latitude."

    if not -180 <= lon <= 180:
        return False, "Invalid longitude."

    return True, None


def get_current_rainfall(hourly_data):
    """
    Get rainfall for the current local hour.

    Open-Meteo provides hourly timestamps in the requested
    timezone. This function uses the current system time to
    match the corresponding hour.
    """

    current_hour = datetime.now().strftime("%Y-%m-%dT%H:00")

    times = hourly_data["time"]
    rainfall_values = hourly_data["rainfall_mm"]

    if current_hour in times:
        index = times.index(current_hour)
        return rainfall_values[index]

    return rainfall_values[0]


def get_rainfall_from_open_meteo(lat: float, lon: float):
    """
    Fetch hourly rainfall data from Open-Meteo
    for any latitude and longitude in India.
    """

    valid, error = validate_coordinates(lat, lon)

    if not valid:
        return {
            "status": "error",
            "message": error
        }

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "rain",
        "forecast_days": 1,
        "timezone": "Asia/Kolkata"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=UPSTREAM_TIMEOUT_SECONDS
        )

        response.raise_for_status()

        data = response.json()

        return {
            "status": "success",
            "source": "Open-Meteo",
            "location": {
                "latitude": data["latitude"],
                "longitude": data["longitude"]
            },
            "timezone": data.get(
                "timezone",
                "Asia/Kolkata"
            ),
            "hourly": {
                "time": data["hourly"]["time"],
                "rainfall_mm": data["hourly"]["rain"]
            }
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Unable to fetch rainfall data: {str(e)}"
        }

    except KeyError as e:
        return {
            "status": "error",
            "message": f"Unexpected API response. Missing field: {str(e)}"
        }