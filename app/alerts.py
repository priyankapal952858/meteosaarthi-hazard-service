def generate_alerts(hazards):
    """
    Generate user-facing alerts from detected hazards.

    If a hazard dict already includes a "message" field (e.g. the detailed
    flood-hazard message built in app.risk with real hectare/district
    figures), that message is preserved as-is. Only hazards without an
    existing message fall back to the generic template below — this keeps
    the function safe to call with simple hazards (like the plain "Heavy
    Rainfall" entries that only have a type/severity) while not discarding
    richer detail when it's already available.
    """

    if hazards is None:
        return []

    alerts = []

    for hazard in hazards:
        if not isinstance(hazard, dict):
            continue

        hazard_type = hazard.get("type", "Unknown hazard")
        severity = hazard.get("severity", "unknown")

        message = hazard.get("message")

        if not message:
            message = f"{hazard_type} detected with {severity} severity."

        alerts.append({
            "type": hazard_type,
            "severity": severity,
            "message": message
        })

    return alerts


def build_farmer_sms_message(alerts, state_name=None):
    """
    Create a compact, farmer-friendly SMS message from the generated alerts.
    Picks the most severe alert and keeps the content concise enough for a
    mobile SMS.
    """
    if not alerts:
        return "No active hazard alert in your area."

    severity_order = ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME"]
    highest_severity = "UNKNOWN"
    selected_message = None

    for alert in alerts:
        if not isinstance(alert, dict):
            continue

        severity = str(alert.get("severity", "UNKNOWN")).upper()
        if severity in severity_order:
            current_index = severity_order.index(severity)
            highest_index = severity_order.index(highest_severity) if highest_severity in severity_order else -1
            if current_index > highest_index:
                highest_severity = severity
                selected_message = alert.get("message") or alert.get("type") or "Alert"

    if selected_message is None:
        selected_message = alerts[0].get("message") or alerts[0].get("type") or "Alert"

    location_prefix = f"{state_name}: " if state_name else ""
    return (
        f"{location_prefix}Alert level {highest_severity}. "
        f"{selected_message} Please stay safe and follow local advisories."
    )
