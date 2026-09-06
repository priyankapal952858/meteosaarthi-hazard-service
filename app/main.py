
from fastapi import FastAPI, Query, Request
from uuid import uuid4

from app.risk import calculate_risk

from app.gis import (
    get_location_info,
    get_state_boundary,
    create_risk_geojson,
    create_risk_zone_geojson,
    create_risk_feature_collection,
    create_rainfall_intensity_geojson,
    create_combined_feature_collection
)

from app.radar import (
    process_radar_data,
    process_rainfall
)

from app.rainfall_data import (
    get_rainfall_from_open_meteo,
    get_current_rainfall
)

from app.alerts import generate_alerts

from app.flood_hazard import get_flood_baseline


app = FastAPI(
    title="MeteoSaarthi GIS Radar Hazard Service",
    description="GIS, radar processing, hazard detection and risk mapping service",
    version="1.0.0"
)


@app.middleware("http")
async def add_request_trace_ids(request: Request, call_next):
    request_id = request.headers.get(
        "X-Request-ID",
        str(uuid4())
    )

    trace_id = request.headers.get(
        "X-Trace-ID",
        str(uuid4())
    )

    # Stored on request.state so route handlers can attach the same IDs
    # into error response bodies, not just response headers.
    request.state.request_id = request_id
    request.state.trace_id = trace_id

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Trace-ID"] = trace_id

    return response


def _with_trace(result: dict, request: Request):
    """
    If result is an error response, attach request_id/trace_id to the
    body as well as the headers, so consumers of the JSON body alone
    (not just headers) can still correlate/debug failed requests.
    """

    if isinstance(result, dict) and result.get("status") == "error":
        result.setdefault("request_id", getattr(request.state, "request_id", None))
        result.setdefault("trace_id", getattr(request.state, "trace_id", None))

    return result


def _get_state_name(state_boundary: dict):
    """
    Safely extract a state name from a get_state_boundary() result,
    regardless of whether the location was found, out of coverage, or
    the lookup itself errored. Returns None if no state name is available
    for any reason — callers must treat that as "no flood baseline
    lookup possible" rather than assuming a default state.
    """

    if not isinstance(state_boundary, dict):
        return None

    if state_boundary.get("status") != "success":
        return None

    if not state_boundary.get("found"):
        return None

    return state_boundary.get("state")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "gis-radar-hazard-service",
        "version": "1.0.0"
    }


@app.get("/capabilities")
def capabilities():
    return {
        "service": "gis-radar-hazard-service",
        "version": "1.0.0",
        "coverage": "India",

        "capabilities": [
            "radar_processing",
            "gis_processing",
            "risk_mapping",
            "hazard_detection",
            "alert_generation",
            "state_boundary_mapping",
            "historical_flood_hazard_baseline"
        ],

        "endpoints": {
            "/maps/risk": {
                "method": "GET",
                "inputs": {
                    "lat": "float",
                    "lon": "float",
                    "rainfall": "float (optional, mm/hour)"
                },
                "output": [
                    "risk",
                    "risk_components",
                    "hazards",
                    "gis",
                    "state_boundary",
                    "flood_hazard",
                    "geojson",
                    "risk_zone",
                    "feature_collection",
                    "rainfall_intensity",
                    "combined_feature_collection"
                ]
            },

            "/maps/radar": {
                "method": "GET",
                "inputs": {
                    "lat": "float",
                    "lon": "float"
                },
                "output": [
                    "rainfall",
                    "intensity"
                ],
                "integration_status": "not_integrated",
                "data_source": "Open-Meteo rainfall data used as a substitute signal; "
                                "real radar imagery integration is pending access to "
                                "IMD's registered Radar Image API"
            },

            "/maps/rainfall": {
                "method": "GET",
                "inputs": {
                    "lat": "float",
                    "lon": "float"
                },
                "output": [
                    "rainfall",
                    "intensity"
                ]
            },

            "/alerts/current": {
                "method": "GET",
                "inputs": {
                    "lat": "float",
                    "lon": "float",
                    "rainfall": "float (optional, mm/hour)"
                },
                "output": [
                    "risk",
                    "alerts",
                    "flood_hazard"
                ]
            },

            "/health": {
                "method": "GET",
                "output": [
                    "status",
                    "service",
                    "version"
                ]
            }
        },

        "data_sources": {
            "rainfall": "Open-Meteo (live)",
            "flood_hazard_baseline": {
                "source": "NRSC/ISRO Flood Affected Area Atlas of India (1998-2022)",
                "type": "historical_cumulative",
                "coverage": "24 Indian states with published data; other states/UTs "
                            "use a separate Open-Meteo river-discharge anomaly "
                            "signal when coordinates are available; locations "
                            "where that backup also fails return 'unavailable'."
            },
            "flood_hazard_backup": {
                "source": "Open-Meteo Flood API",
                "type": "river_discharge_anomaly",
                "coverage": "Coordinate-based backup signal; not historical "
                            "flood-affected-area data."
            }
        }
    }


@app.get("/maps/risk")
def risk_map(
    request: Request,
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    rainfall: float = Query(
        None,
        description="Rainfall in mm/hour"
    )
):
    rainfall_source = "manual"

    if rainfall is None:

        rainfall_data = get_rainfall_from_open_meteo(
            lat,
            lon
        )

        if rainfall_data["status"] == "error":
            return _with_trace(rainfall_data, request)

        rainfall = get_current_rainfall(
            rainfall_data["hourly"]
        )

        rainfall_source = "Open-Meteo"

    # Find the Indian state/UT containing the location. Computed before
    # calculate_risk() so its result can inform the flood hazard baseline.
    state_boundary = get_state_boundary(
        lat,
        lon
    )

    state_name = _get_state_name(state_boundary)

    # Historical flood hazard baseline for the detected state. Returns an
    # explicit "unavailable"/"error" status rather than fabricated data
    # when no state was detected or no data source covers that state.
    flood_baseline = get_flood_baseline(state_name, lat, lon)

    risk_result = calculate_risk(
        lat,
        lon,
        rainfall,
        flood_baseline
    )

    if risk_result["status"] == "error":
        return _with_trace(risk_result, request)

    # Basic GIS location information.
    gis_result = get_location_info(
        lat,
        lon
    )

    # Risk point GeoJSON.
    geojson = create_risk_geojson(
        lat,
        lon,
        risk_result["risk"]["level"],
        risk_result["risk"]["score"]
    )

    # Risk zone GeoJSON.
    risk_zone = create_risk_zone_geojson(
        lat,
        lon,
        risk_result["risk"]["level"],
        risk_result["risk"]["score"]
    )

    # Risk FeatureCollection.
    feature_collection = create_risk_feature_collection(
        lat,
        lon,
        risk_result["risk"]["level"],
        risk_result["risk"]["score"]
    )

    # Rainfall processing.
    rainfall_result = process_rainfall(
        lat,
        lon,
        rainfall
    )

    # Rainfall intensity GeoJSON.
    rainfall_intensity = create_rainfall_intensity_geojson(
        lat,
        lon,
        rainfall,
        rainfall_result["rainfall"]["intensity"]
    )

    # Combined GIS FeatureCollection.
    combined_feature_collection = create_combined_feature_collection(
        lat,
        lon,
        risk_result["risk"]["level"],
        risk_result["risk"]["score"],
        rainfall,
        rainfall_result["rainfall"]["intensity"]
    )

    # Add all GIS information to the response.
    risk_result["rainfall"]["source"] = rainfall_source
    risk_result["gis"] = gis_result
    risk_result["state_boundary"] = state_boundary
    risk_result["flood_hazard"] = flood_baseline
    risk_result["geojson"] = geojson
    risk_result["risk_zone"] = risk_zone
    risk_result["feature_collection"] = feature_collection
    risk_result["rainfall_intensity"] = rainfall_intensity
    risk_result["combined_feature_collection"] = combined_feature_collection

    return risk_result


@app.get("/maps/radar")
def radar_map(
    request: Request,
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude")
):
    return _with_trace(process_radar_data(
        lat,
        lon
    ), request)


@app.get("/maps/rainfall")
def rainfall_map(
    request: Request,
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude")
):
    rainfall_data = get_rainfall_from_open_meteo(
        lat,
        lon
    )

    if rainfall_data["status"] == "error":
        return _with_trace(rainfall_data, request)

    rainfall = get_current_rainfall(
        rainfall_data["hourly"]
    )

    return _with_trace(
        process_rainfall(lat, lon, rainfall),
        request
    )


@app.get("/alerts")
@app.get("/alerts/current")
def current_alerts(
    request: Request,
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    rainfall: float = Query(
        None,
        description="Rainfall in mm/hour"
    )
):
    rainfall_source = "manual"

    if rainfall is None:

        rainfall_data = get_rainfall_from_open_meteo(
            lat,
            lon
        )

        if rainfall_data["status"] == "error":
            return _with_trace(rainfall_data, request)

        rainfall = get_current_rainfall(
            rainfall_data["hourly"]
        )

        rainfall_source = "Open-Meteo"

    state_boundary = get_state_boundary(
        lat,
        lon
    )

    state_name = _get_state_name(state_boundary)

    flood_baseline = get_flood_baseline(state_name, lat, lon)

    risk_result = calculate_risk(
        lat,
        lon,
        rainfall,
        flood_baseline
    )

    if risk_result["status"] == "error":
        return _with_trace(risk_result, request)

    alerts = generate_alerts(
        risk_result["hazards"]
    )

    return {
        "status": "success",

        "location": {
            "latitude": lat,
            "longitude": lon
        },

        "rainfall": {
            "value_mm_per_hour": rainfall,
            "source": rainfall_source
        },

        "risk": risk_result["risk"],

        "flood_hazard": flood_baseline,

        "alerts": alerts
    }
