
import os
from threading import Lock

from shapely.geometry import Point
import geopandas as gpd


_BOUNDARIES = None
_BOUNDARIES_LOCK = Lock()


def _get_boundaries():
    global _BOUNDARIES

    if _BOUNDARIES is None:
        with _BOUNDARIES_LOCK:
            if _BOUNDARIES is None:
                data_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data",
                    "gis",
                    "boundaries",
                    "state_NWIC.GeoJSON"
                )
                boundaries = gpd.read_file(data_path)
                _BOUNDARIES = boundaries.to_crs("EPSG:4326")

    return _BOUNDARIES


def create_location_point(lat: float, lon: float):
    """
    Create a geographic point from latitude and longitude.
    """

    if not -90 <= lat <= 90:
        raise ValueError("Latitude must be between -90 and 90.")

    if not -180 <= lon <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    return Point(lon, lat)


def get_location_info(lat: float, lon: float):
    """
    Return basic GIS information for a location.
    """

    point = create_location_point(lat, lon)

    return {
        "latitude": lat,
        "longitude": lon,
        "geometry": {
            "type": "Point",
            "coordinates": [point.x, point.y]
        },
        "coordinate_reference_system": "EPSG:4326"
    }


def get_state_boundary(lat: float, lon: float):
    """
    Find the Indian state/UT containing the given location
    and return its boundary as GeoJSON.
    """

    if not -90 <= lat <= 90:
        return {
            "status": "error",
            "message": "Latitude must be between -90 and 90."
        }

    if not -180 <= lon <= 180:
        return {
            "status": "error",
            "message": "Longitude must be between -180 and 180."
        }

    gdf = _get_boundaries()

    point = Point(lon, lat)

    matching_state = gdf[gdf.geometry.contains(point)]

    if matching_state.empty:
        return {
            "status": "success",
            "found": False,
            "message": "Location is outside the available state boundaries."
        }

    state = matching_state.iloc[0]

    state_name = state.get("state_name")

    if state_name is None:
        state_name = state.get("state")

    geometry = state.geometry.__geo_interface__

    return {
        "status": "success",
        "found": True,
        "state": state_name,
        "geometry": geometry,
        "coordinate_reference_system": "EPSG:4326"
    }


def create_risk_geojson(
    lat: float,
    lon: float,
    risk_level: str,
    risk_score: int
):
    """
    Create a GeoJSON Feature representing weather risk
    at a specific location.
    """

    point = create_location_point(lat, lon)

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [point.x, point.y]
        },
        "properties": {
            "layer_type": "risk_point",
            "risk_level": risk_level,
            "risk_score": risk_score
        }
    }


def create_risk_zone_geojson(
    lat: float,
    lon: float,
    risk_level: str,
    risk_score: int
):
    """
    Create a circular GeoJSON risk zone around a location.

    The radius depends on the risk severity.
    """

    point = create_location_point(lat, lon)

    risk_radii = {
        "LOW": 2,
        "MODERATE": 3,
        "HIGH": 5,
        "VERY_HIGH": 8,
        "EXTREME": 10
    }

    radius_km = risk_radii.get(
        risk_level.upper(),
        2
    )

    # Approximate conversion from kilometres to degrees.
    radius_degrees = radius_km / 111.0

    zone = point.buffer(radius_degrees)

    coordinates = [
        [list(coord) for coord in zone.exterior.coords]
    ]

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": coordinates
        },
        "properties": {
            "layer_type": "risk_zone",
            "risk_level": risk_level,
            "risk_score": risk_score,
            "radius_km": radius_km
        }
    }


def create_risk_feature_collection(
    lat: float,
    lon: float,
    risk_level: str,
    risk_score: int
):
    """
    Create a GeoJSON FeatureCollection containing
    the risk point and surrounding risk zone.
    """

    risk_point = create_risk_geojson(
        lat,
        lon,
        risk_level,
        risk_score
    )

    risk_zone = create_risk_zone_geojson(
        lat,
        lon,
        risk_level,
        risk_score
    )

    return {
        "type": "FeatureCollection",
        "features": [
            risk_point,
            risk_zone
        ]
    }


def create_rainfall_intensity_geojson(
    lat: float,
    lon: float,
    rainfall_mm_per_hour: float,
    intensity: str
):
    """
    Create a GeoJSON feature representing
    rainfall intensity at a location.
    """

    point = create_location_point(lat, lon)

    intensity_radii = {
        "NO_RAIN": 1,
        "LIGHT": 2,
        "MODERATE": 3,
        "HEAVY": 5,
        "VERY_HEAVY": 8,
        "EXTREMELY_HEAVY": 10
    }

    radius_km = intensity_radii.get(
        intensity.upper(),
        2
    )

    radius_degrees = radius_km / 111.0

    zone = point.buffer(radius_degrees)

    coordinates = [
        [list(coord) for coord in zone.exterior.coords]
    ]

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": coordinates
        },
        "properties": {
            "layer_type": "rainfall_intensity",
            "rainfall_mm_per_hour": rainfall_mm_per_hour,
            "intensity": intensity,
            "radius_km": radius_km
        }
    }


def create_combined_feature_collection(
    lat: float,
    lon: float,
    risk_level: str,
    risk_score: int,
    rainfall_mm_per_hour: float,
    rainfall_intensity: str
):
    """
    Create a GeoJSON FeatureCollection containing
    the risk point, risk zone and rainfall intensity zone.
    """

    risk_point = create_risk_geojson(
        lat,
        lon,
        risk_level,
        risk_score
    )

    risk_zone = create_risk_zone_geojson(
        lat,
        lon,
        risk_level,
        risk_score
    )

    rainfall_zone = create_rainfall_intensity_geojson(
        lat,
        lon,
        rainfall_mm_per_hour,
        rainfall_intensity
    )

    return {
        "type": "FeatureCollection",
        "features": [
            risk_point,
            risk_zone,
            rainfall_zone
        ]
    }
