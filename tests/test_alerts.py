"""
Tests for app.alerts.
"""

from app.alerts import generate_alerts, build_farmer_sms_message
from app.sms import normalize_phone_number, send_sms, send_test_sms


class TestGenerateAlerts:

    def test_none_input_returns_empty_list(self):
        assert generate_alerts(None) == []

    def test_empty_list_returns_empty_list(self):
        assert generate_alerts([]) == []

    def test_non_dict_items_are_skipped(self):
        result = generate_alerts(["not a dict", 123, None])
        assert result == []

    def test_preserves_existing_rich_message(self):
        hazards = [{
            "type": "Flood Hazard (Historical)",
            "severity": "HIGH",
            "message": "Maharashtra has a history of flood-affected area of 233,590 hectares."
        }]

        result = generate_alerts(hazards)

        assert len(result) == 1
        assert result[0]["message"] == (
            "Maharashtra has a history of flood-affected area of 233,590 hectares."
        )

    def test_falls_back_to_generic_message_when_absent(self):
        hazards = [{"type": "Heavy Rainfall", "severity": "HIGH"}]

        result = generate_alerts(hazards)

        assert result[0]["message"] == "Heavy Rainfall detected with HIGH severity."

    def test_missing_type_and_severity_use_defaults(self):
        result = generate_alerts([{}])
        assert result[0]["type"] == "Unknown hazard"
        assert result[0]["severity"] == "unknown"

    def test_multiple_hazards_handled_independently(self):
        hazards = [
            {"type": "Heavy Rainfall", "severity": "HIGH"},
            {"type": "Flood Hazard (Historical)", "severity": "VERY_HIGH", "message": "Custom message."}
        ]

        result = generate_alerts(hazards)

        assert len(result) == 2
        assert result[0]["message"] == "Heavy Rainfall detected with HIGH severity."
        assert result[1]["message"] == "Custom message."


class TestFarmerSmsMessages:

    def test_build_farmer_sms_message_uses_highest_severity(self):
        alerts = [
            {"type": "Heavy Rainfall", "severity": "MODERATE", "message": "Alert 1"},
            {"type": "Flood Hazard", "severity": "VERY_HIGH", "message": "Alert 2"},
        ]

        result = build_farmer_sms_message(alerts, state_name="Maharashtra")

        assert "Maharashtra" in result
        assert "VERY_HIGH" in result
        assert "Alert 2" in result

    def test_normalize_phone_number_formats_indian_mobile(self):
        assert normalize_phone_number("9876543210") == "+919876543210"
        assert normalize_phone_number("+919876543210") == "+919876543210"

    def test_send_sms_returns_disabled_when_no_provider_configured(self):
        result = send_sms("9876543210", "Test alert", provider="fast2sms", api_key=None)
        assert result["status"] == "disabled"

    def test_send_test_sms_returns_prototype_status(self):
        result = send_test_sms("9876543210", "Prototype test message")
        assert result["mode"] == "prototype"
        assert result["phone_number"] == "+919876543210"
