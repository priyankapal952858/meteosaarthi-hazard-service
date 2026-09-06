from app.flood_hazard import combine_rainfall_and_flood_risk


def validate_coordinates(lat: float, lon: float):
    """
    Validate latitude and longitude values.
    """

    if not -90 <= lat <= 90:
        return False, "Invalid latitude. Latitude must be between -90 and 90."

    if not -180 <= lon <= 180:
        return False, "Invalid longitude. Longitude must be between -180 and 180."

    return True, None


def calculate_rainfall_risk(rainfall_mm_per_hour: float):
    """
    Calculate risk level from rainfall intensity.
    """

    if rainfall_mm_per_hour < 0:
        return {
            "level": "UNKNOWN",
            "score": None
        }

    if rainfall_mm_per_hour == 0:
        return {
            "level": "LOW",
            "score": 0
        }

    if rainfall_mm_per_hour < 2.5:
        return {
            "level": "LOW",
            "score": 20
        }

    if rainfall_mm_per_hour < 7.6:
        return {
            "level": "MODERATE",
            "score": 40
        }

    if rainfall_mm_per_hour < 15.6:
        return {
            "level": "HIGH",
            "score": 60
        }

    if rainfall_mm_per_hour < 64.5:
        return {
            "level": "VERY_HIGH",
            "score": 80
        }

    return {
        "level": "EXTREME",
        "score": 100
    }


def calculate_risk(
    lat: float,
    lon: float,
    rainfall_mm_per_hour: float = None,
    flood_baseline: dict = None
):
    """
    Calculate location-based weather hazard risk.

    flood_baseline is optional and is expected to be the dict returned by
    app.flood_hazard.get_flood_baseline(state_name). When provided and
    available, it is combined with the rainfall-based risk into a single
    combined risk level/score. When absent, unavailable, or errored, this
    function behaves exactly as before (rainfall-only), so existing
    callers and response shapes are unaffected.
    """

    valid, error = validate_coordinates(lat, lon)

    if not valid:
        return {
            "status": "error",
            "message": error
        }

    if rainfall_mm_per_hour is None:
        return {
            "status": "success",
            "location": {
                "latitude": lat,
                "longitude": lon
            },
            "risk": {
                "level": "UNKNOWN",
                "score": None
            },
            "hazards": [],
            "data_status": "awaiting_rainfall_data"
        }

    rainfall_risk = calculate_rainfall_risk(rainfall_mm_per_hour)

    combined_risk = combine_rainfall_and_flood_risk(
        rainfall_risk,
        flood_baseline
    )

    hazards = []

    if rainfall_mm_per_hour >= 7.6:
        hazards.append({
            "type": "Heavy Rainfall",
            "severity": rainfall_risk["level"]
        })

    if (
        flood_baseline is not None
        and flood_baseline.get("status") == "available"
        and flood_baseline["severity"]["level"] in
            ("MODERATE", "HIGH", "VERY_HIGH")
    ):
        if flood_baseline.get("data_type") == "historical_cumulative":
            flood_message = (
                f"{flood_baseline['state']} has a history of flood-affected "
                f"area of approximately {flood_baseline['flood_affected_area_ha']:,} "
                f"hectares across {flood_baseline['districts_affected']} districts "
                f"({flood_baseline.get('data_period', 'historical period')}). "
                "This reflects historical satellite-derived data, not a "
                "real-time flood condition."
            )
        else:
            flood_message = (
                f"{flood_baseline['state']} has a river-discharge anomaly of "
                f"{flood_baseline['discharge_ratio']} times its recent reference "
                f"mean ({flood_baseline.get('data_period', 'recent period')}). "
                "This is a backup river signal, not historical flood-area data."
            )

        flood_hazard_type = (
            "Flood Hazard (Historical)"
            if flood_baseline.get("data_type") == "historical_cumulative"
            else "Flood Hazard (Backup River Signal)"
        )

        hazards.append({
            "type": flood_hazard_type,
            "severity": flood_baseline["severity"]["level"],
            "message": flood_message
        })

    return {
        "status": "success",
        "location": {
            "latitude": lat,
            "longitude": lon
        },
        "rainfall": {
            "value_mm_per_hour": rainfall_mm_per_hour
        },
        "risk": combined_risk,
        "risk_components": {
            "rainfall_risk": rainfall_risk,
            "flood_baseline": flood_baseline
        },
        "hazards": hazards,
        "data_status": "rainfall_data_available"
    }
