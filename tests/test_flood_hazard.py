"""
Tests for app.flood_hazard.

Covers: known-state lookups, unknown-state honesty, case-insensitivity,
severity classification boundaries, and the rainfall/flood combination
logic including its degraded-mode fallback.
"""

import pytest

from app.flood_hazard import (
    get_flood_baseline,
    classify_flood_severity,
    combine_rainfall_and_flood_risk,
)


class TestGetFloodBaseline:

    def test_known_state_returns_available(self):
        result = get_flood_baseline("Maharashtra")
        assert result["status"] == "available"
        assert result["state"] == "Maharashtra"
        assert result["flood_affected_area_ha"] == 233590
        assert result["districts_affected"] == 20

    def test_case_insensitive_match(self):
        result = get_flood_baseline("maharashtra")
        assert result["status"] == "available"
        assert result["state"] == "Maharashtra"

    def test_whitespace_tolerant_match(self):
        result = get_flood_baseline("  Maharashtra  ")
        assert result["status"] == "available"

    def test_unknown_state_returns_unavailable_not_error(self):
        """
        A state genuinely outside the atlas's coverage (e.g. Goa) must
        return 'unavailable', never fabricated data, and never a crash.
        """
        result = get_flood_baseline("Goa")
        assert result["status"] == "unavailable"
        assert "Goa" in result["message"]

    def test_none_state_returns_unavailable(self):
        result = get_flood_baseline(None)
        assert result["status"] == "unavailable"

    def test_empty_string_state_returns_unavailable(self):
        result = get_flood_baseline("")
        assert result["status"] == "unavailable"

    def test_tripura_chapter_level_data_present(self):
        """
        Tripura was added from its own atlas chapter (not the national
        summary table) — regression test to make sure it stays available.
        """
        result = get_flood_baseline("Tripura")
        assert result["status"] == "available"
        assert result["flood_affected_area_ha"] == 3928

    def test_himachal_pradesh_honestly_unavailable(self):
        """
        Himachal Pradesh has a narrative-only chapter in the source atlas
        with no district table — must NOT be fabricated as available.
        """
        result = get_flood_baseline("Himachal Pradesh")
        assert result["status"] == "unavailable"


class TestClassifyFloodSeverity:

    def test_none_is_unknown(self):
        assert classify_flood_severity(None)["level"] == "UNKNOWN"

    def test_very_high_boundary(self):
        assert classify_flood_severity(500000)["level"] == "VERY_HIGH"
        assert classify_flood_severity(999999)["level"] == "VERY_HIGH"

    def test_high_band(self):
        assert classify_flood_severity(200000)["level"] == "HIGH"
        assert classify_flood_severity(499999)["level"] == "HIGH"

    def test_moderate_band(self):
        assert classify_flood_severity(50000)["level"] == "MODERATE"

    def test_low_band(self):
        assert classify_flood_severity(10000)["level"] == "LOW"

    def test_minimal_band(self):
        assert classify_flood_severity(0)["level"] == "MINIMAL"
        assert classify_flood_severity(9999)["level"] == "MINIMAL"


class TestCombineRainfallAndFloodRisk:

    def test_combines_when_both_available(self):
        rainfall_risk = {"level": "LOW", "score": 0}
        flood_baseline = get_flood_baseline("Assam")  # VERY_HIGH / 80

        combined = combine_rainfall_and_flood_risk(rainfall_risk, flood_baseline)

        assert combined["flood_baseline_included"] is True
        # 0.6 * 0 + 0.4 * 80 = 32
        assert combined["score"] == 32
        assert combined["level"] == "MODERATE"

    def test_falls_back_to_rainfall_only_when_flood_unavailable(self):
        rainfall_risk = {"level": "LOW", "score": 20}
        flood_baseline = get_flood_baseline("Goa")  # unavailable

        combined = combine_rainfall_and_flood_risk(rainfall_risk, flood_baseline)

        assert combined["flood_baseline_included"] is False
        assert combined["score"] == 20
        assert combined["level"] == "LOW"

    def test_falls_back_when_flood_baseline_is_none(self):
        rainfall_risk = {"level": "HIGH", "score": 60}

        combined = combine_rainfall_and_flood_risk(rainfall_risk, None)

        assert combined["flood_baseline_included"] is False
        assert combined["score"] == 60

    def test_falls_back_when_rainfall_score_is_none(self):
        rainfall_risk = {"level": "UNKNOWN", "score": None}
        flood_baseline = get_flood_baseline("Maharashtra")

        combined = combine_rainfall_and_flood_risk(rainfall_risk, flood_baseline)

        assert combined["flood_baseline_included"] is False
