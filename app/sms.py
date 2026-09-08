import os
from typing import Any, Dict, List, Optional


def normalize_phone_number(phone_number: str) -> str:
    """
    Normalize a farmer phone number to the expected Indian format.
    Accepts 10-digit local format or +91-prefixed format and returns a
    canonical international format: +91xxxxxxxxxx.
    """
    if not phone_number:
        return ""

    digits = "".join(ch for ch in str(phone_number) if ch.isdigit())

    if len(digits) == 10:
        return "+91" + digits

    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits

    if len(digits) > 10 and digits.startswith("0"):
        return "+91" + digits[1:]

    return "+" + digits if digits else ""


def send_sms(
    phone_number: str,
    message: str,
    provider: str = "fast2sms",
    api_key: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Send an SMS via an external provider if credentials are configured.

    This project intentionally does not hardcode or require a live SMS API
    key. If no key is available, it returns a structured disabled result so
    the app can remain safe and testable in local/offline environments.
    """
    if not phone_number or not message:
        return {
            "status": "error",
            "message": "Phone number and message are required."
        }

    normalized = normalize_phone_number(phone_number)
    if not normalized:
        return {
            "status": "error",
            "message": "Invalid phone number."
        }

    configured_key = api_key or os.getenv("SMS_API_KEY") or os.getenv("FAST2SMS_API_KEY")
    if not configured_key:
        return {
            "status": "disabled",
            "message": "SMS sending is disabled because no provider API key is configured.",
            "phone_number": normalized,
            "sms_text": message,
            "provider": provider,
        }

    try:
        import requests

        if provider.lower() == "fast2sms":
            url = "https://www.fast2sms.com/dev/bulkV2"
            payload = {
                "authorization": configured_key,
                "message": message,
                "language": "english",
                "route": "qt",
                "numbers": normalized.replace("+", ""),
            }
            response = requests.post(url, data=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return {
                "status": "success" if data.get("return") == True or data.get("messageId") else "error",
                "provider": provider,
                "phone_number": normalized,
                "response": data,
            }

        return {
            "status": "error",
            "message": f"Unsupported SMS provider: {provider}",
            "provider": provider,
            "phone_number": normalized,
        }

    except Exception as exc:  # pragma: no cover - network failure fallback
        return {
            "status": "error",
            "message": f"SMS sending failed: {str(exc)}",
            "provider": provider,
            "phone_number": normalized,
        }


def send_test_sms(phone_number: str, message: str = "Prototype SMS test from MeteoSaarthi") -> Dict[str, Any]:
    """
    Prototype-mode testing helper for sending to a trusted team member number.
    This is intended only for validation and should not be used for real
    production broadcasts.
    """
    normalized = normalize_phone_number(phone_number)
    if not normalized:
        return {
            "status": "error",
            "message": "Invalid phone number.",
            "mode": "prototype",
        }

    result = send_sms(normalized, message)
    result.setdefault("mode", "prototype")
    result.setdefault("phone_number", normalized)
    return result


def build_farmer_sms_message(alerts: List[Dict[str, Any]], state_name: Optional[str] = None) -> str:
    """
    Build a farmer-friendly SMS message from hazard alerts.
    """
    if not alerts:
        return "No active hazard alert in your area."

    highest_severity = "UNKNOWN"
    selected_message = None

    severity_order = ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME"]

    for alert in alerts:
        if not isinstance(alert, dict):
            continue

        severity = str(alert.get("severity", "UNKNOWN")).upper()
        if severity in severity_order:
            if severity_order.index(severity) > severity_order.index(highest_severity):
                highest_severity = severity
                selected_message = alert.get("message") or alert.get("type") or "Alert"

    if not selected_message:
        selected_message = alerts[0].get("message") or alerts[0].get("type") or "Alert"

    location_prefix = f"{state_name}: " if state_name else ""
    return f"{location_prefix}Alert level {highest_severity}. {selected_message} Please stay safe and monitor local advisories."
