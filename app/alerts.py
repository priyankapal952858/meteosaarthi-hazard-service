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
