"""
flood_hazard.py

Provides a state-level HISTORICAL flood-hazard baseline, derived from the
NRSC/ISRO "Flood Affected Area Atlas of India (1998-2022)" (Table 5.1).

IMPORTANT — WHAT THIS IS AND IS NOT:
- This is historical, satellite-derived cumulative flood-affected-area data.
- It is NOT real-time flooding and NOT a flood forecast.
- Coverage is limited to the states published in the source atlas. For any
  state/UT not present in the data file, this module returns an explicit
  "unavailable" status. It NEVER fabricates a hazard level for locations
  where no authoritative source exists.

This module works for ANY Indian state that appears in the data file — it
does not hard-code Maharashtra, Assam, or any specific state as special
cases. States/UTs outside the source atlas's coverage are handled
identically and generically via the "unavailable" path.
"""

import json
import os

from app.flood_backup import get_backup_flood_baseline

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "flood_hazard_state_stats.json"
)

_CACHE = None


def _load_data():
    """
    Load and cache the flood hazard state statistics file.

    Returns None (rather than raising) if the file is missing or invalid,
    so that callers can degrade gracefully instead of crashing the whole
    risk pipeline if this optional data source is unavailable.
    """

    global _CACHE

    if _CACHE is not None:
        return _CACHE

    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        if (
            not isinstance(loaded_data, dict)
            or not isinstance(loaded_data.get("state_stats"), dict)
        ):
            return None

        _CACHE = loaded_data
        return _CACHE

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def classify_flood_severity(flood_affected_area_ha: float):
    """
    Classify a state's cumulative historical flood-affected area (in
    hectares) into a severity level and numeric score, using bucket
    boundaries derived from Table 5.2 of the source atlas.

    This is a simplification introduced by this service for the purpose
    of combining flood history with rainfall risk — it is NOT an official
    NRSC/ISRO classification scale.
    """

    if flood_affected_area_ha is None:
        return {"level": "UNKNOWN", "score": None}

    if flood_affected_area_ha >= 500000:
        return {"level": "VERY_HIGH", "score": 80}

    if flood_affected_area_ha >= 200000:
        return {"level": "HIGH", "score": 60}

    if flood_affected_area_ha >= 50000:
        return {"level": "MODERATE", "score": 40}

    if flood_affected_area_ha >= 10000:
        return {"level": "LOW", "score": 20}

    return {"level": "MINIMAL", "score": 10}


def get_flood_baseline(state_name: str, lat: float = None, lon: float = None):
    """
    Return the historical flood-hazard baseline for a given Indian state
    or union territory name.

    Returns a dict always containing a "status" key:
      - "available":   state found in the atlas data; includes severity
                        classification and source stats.
      - "unavailable":  state name was empty/None, or not present in the
                        atlas data. This is an expected, honest outcome
                        for states outside the source atlas's coverage —
                        NOT an error.
      - "error":        the underlying data file could not be loaded.
    """

    data = _load_data()

    if data is None:
        return {
            "status": "error",
            "message": "Flood hazard reference data is currently unavailable."
        }

    if not state_name:
        return {
            "status": "unavailable",
            "message": "No state could be determined for this location; "
                       "flood hazard baseline cannot be looked up.",
            "data_type": "historical_cumulative",
            "data_period": data.get("_metadata", {}).get("data_period")
        }

    state_stats = data.get("state_stats", {})

    # Case-insensitive, whitespace-tolerant match so minor formatting
    # differences between the boundary dataset's state names and this
    # atlas's state names don't cause false "unavailable" results.
    normalized_lookup = {
        key.strip().lower(): key for key in state_stats.keys()
    }

    match_key = normalized_lookup.get(state_name.strip().lower())

    if match_key is None:
        if state_name and lat is not None and lon is not None:
            backup_baseline = get_backup_flood_baseline(state_name, lat, lon)

            if backup_baseline is not None:
                return backup_baseline

        return {
            "status": "unavailable",
            "state": state_name,
            "message": f"No authoritative historical flood-hazard data is "
                       f"available for '{state_name}' in this service's "
                       f"current data source.",
            "data_type": "historical_cumulative",
            "data_period": data.get("_metadata", {}).get("data_period")
        }

    stats = state_stats[match_key]
    severity = classify_flood_severity(stats["flood_affected_area_ha"])

    return {
        "status": "available",
        "state": match_key,
        "severity": severity,
        "districts_affected": stats["districts_affected"],
        "flood_affected_area_ha": stats["flood_affected_area_ha"],
        "data_type": "historical_cumulative",
        "data_period": data.get("_metadata", {}).get("data_period"),
        "source": data.get("_metadata", {}).get("source"),
        "disclaimer": data.get("_metadata", {}).get("important_disclaimer")
    }


def combine_rainfall_and_flood_risk(
    rainfall_risk: dict,
    flood_baseline: dict,
    flood_weight: float = 0.4
):
    """
    Combine a rainfall-based risk assessment with a historical flood
    baseline into a single combined risk level/score.

    If the flood baseline is unavailable or errored, the combined result
    falls back to the rainfall-only risk unchanged — this keeps the
    service fully functional (degraded but honest) for locations where
    no flood data source exists, rather than failing the whole request.

    flood_weight is the fraction of the combined score attributed to the
    flood baseline (default 0.4); the remainder (0.6) comes from rainfall.
    This weighting reflects that rainfall is the more immediate/dynamic
    signal, while the flood baseline is historical context.
    """

    rainfall_score = rainfall_risk.get("score")

    if (
        flood_baseline is None
        or flood_baseline.get("status") != "available"
        or rainfall_score is None
    ):
        combined = dict(rainfall_risk)
        combined["flood_baseline_included"] = False
        return combined

    flood_score = flood_baseline["severity"].get("score")

    if flood_score is None:
        combined = dict(rainfall_risk)
        combined["flood_baseline_included"] = False
        return combined

    combined_score = round(
        (1 - flood_weight) * rainfall_score + flood_weight * flood_score
    )

    combined_level = _score_to_level(combined_score)

    return {
        "level": combined_level,
        "score": combined_score,
        "flood_baseline_included": True,
        "flood_weight": flood_weight
    }


def _score_to_level(score: float):
    """
    Map a combined numeric risk score back to a risk level label, using
    the same score bands as app/risk.py's rainfall-only classification,
    so combined and rainfall-only results stay on a consistent scale.
    """

    if score <= 0:
        return "LOW"

    if score < 30:
        return "LOW"

    if score < 50:
        return "MODERATE"

    if score < 70:
        return "HIGH"

    if score < 90:
        return "VERY_HIGH"

    return "EXTREME"
