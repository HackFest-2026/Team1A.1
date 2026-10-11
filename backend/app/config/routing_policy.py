"""Threat-zone routing policy (ADR-007).

All multipliers are UNCALIBRATED prototype defaults chosen for interpretability:
they scale an edge's travel time when the edge passes within a threat zone.
Change them here; do not hard-code penalties elsewhere.
"""

# Extra distance added to every threat radius when testing edge intersection.
THREAT_SAFETY_BUFFER_M = 25.0

# Severities whose zones are hard blocks. A route never uses an edge inside them;
# if no alternative exists the API reports no-safe-route.
BLOCKING_SEVERITIES = frozenset({"CRITICAL"})

# Travel-time multipliers for non-blocking zones. Overlapping zones on one edge do
# not compound: the strongest single multiplier applies.
SEVERITY_MULTIPLIERS = {
    "HIGH": 3.0,
    "MODERATE": 1.75,
    "LOW": 1.25,
}

# Severity assumed for unrecognised values (conservative).
UNKNOWN_SEVERITY = "HIGH"

# A blocking zone that contains the route origin or destination cannot be avoided.
# Its edges stay usable (to leave/enter) but carry this multiplier, and the
# response reports the zone under `endpoint_zones`.
ENDPOINT_ZONE_MULTIPLIER = 10.0

# Threat statuses that do not produce zones.
INACTIVE_THREAT_STATUSES = frozenset({"CLOSED", "RESOLVED", "ARCHIVED"})
