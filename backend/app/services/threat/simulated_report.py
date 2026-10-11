"""Reproducible SIMULATED field/sensor reports for the AEGIS-COP mission workflow.

There is no live sensor ingestion. A simulated report stands in for one: it creates
a canonical evidence record (provenance.is_simulation = true), a threat linked to
that evidence (source SIMULATED_REPORT), and then asks the route monitor to reassess
the mission route with the normal threat-zone rules. Whether the route is
compromised is decided by those rules, not by this module.

Values in PROFILES are fixed inputs of the simulation (they describe what the
simulated source reports), not computed assessments. The only derived value is the
threat confidence label, using the documented rule in threat_confidence().
"""
import datetime
from typing import Dict, Optional

from app.services.evidence.evidence_service import evidence_service
from app.services.evidence.models import EvidenceCreate
from app.services.route_monitor_service import route_monitor_service
from app.services.routing_service import routing_service
from app.services.threat.models import ThreatEventCreate
from app.services.threat.threat_service import threat_service

PROFILES: Dict[str, dict] = {
    "ROAD_FLOODING_SENSOR": {
        "label": "Simulated water-level sensor: carriageway flooded",
        "source_type": "SENSOR",
        "source_id": "SIM-WLS-07",
        "observation_type": "ROAD_FLOODING",
        "declared_confidence": 0.8,
        "description": "SIMULATED water-level sensor reading: carriageway flooded (> 30 cm).",
        "category": "Road Flooding",
        "severity": "CRITICAL",
        "radius_m": 75.0,
    },
    "FIELD_TEAM_BLOCKAGE": {
        "label": "Simulated field-team report: road blocked",
        "source_type": "HUMAN_REPORT",
        "source_id": "SIM-FIELD-TEAM-2",
        "observation_type": "ROAD_BLOCKAGE",
        "declared_confidence": 0.7,
        "description": "SIMULATED field-team report: road blocked by fallen tree.",
        "category": "Road Obstruction",
        "severity": "CRITICAL",
        "radius_m": 40.0,
    },
}

CONFIDENCE_RULE = ("Single unconfirmed source: threat confidence is MEDIUM when the source's "
                   "declared confidence is >= 0.5, otherwise LOW. Never HIGH from one source.")


def threat_confidence(declared: float) -> str:
    return "MEDIUM" if declared >= 0.5 else "LOW"


class SimulatedReportError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def route_midpoint(route_record: dict) -> Optional[tuple]:
    """(lat, lon) of the middle vertex of the route geometry, or None."""
    geometry = routing_service.nodes_to_geometry(route_record.get("route_nodes") or [])
    if not geometry:
        return None
    lon, lat = geometry["coordinates"][len(geometry["coordinates"]) // 2]
    return lat, lon


def submit_simulated_report(route_id: str, profile_name: str = "ROAD_FLOODING_SENSOR") -> dict:
    profile = PROFILES.get(profile_name)
    if profile is None:
        raise SimulatedReportError(f"Unknown profile '{profile_name}'. Available: {sorted(PROFILES)}")
    record = route_monitor_service.get_route_record(route_id)
    if record is None:
        raise SimulatedReportError("Mission route not found", status_code=404)
    location = route_midpoint(record)
    if location is None:
        raise SimulatedReportError("Mission route has no geometry (road graph unavailable)", status_code=409)
    lat, lon = location
    now = datetime.datetime.utcnow().isoformat() + "Z"

    evidence = evidence_service.create_evidence(EvidenceCreate(
        source_type=profile["source_type"],
        source_id=profile["source_id"],
        observation_type=profile["observation_type"],
        timestamp=now,
        latitude=lat,
        longitude=lon,
        confidence=profile["declared_confidence"],
        description=profile["description"],
        provenance={
            "origin": profile["source_id"],
            "source_system": "AEGIS-COP simulated report",
            "is_simulation": True,
            "profile": profile_name,
            "confidence_basis": "DECLARED_BY_SIMULATION_PROFILE",
            "placement": "midpoint of mission route geometry",
            "mission_route_id": route_id,
        },
    ))

    threat = threat_service.create_threat(ThreatEventCreate(
        title=f"SIMULATED: {profile['label']}",
        category=profile["category"],
        severity=profile["severity"],
        confidence=threat_confidence(profile["declared_confidence"]),
        latitude=lat,
        longitude=lon,
        radius_m=profile["radius_m"],
        description=(f"{profile['description']} Derived from evidence {evidence['evidence_id']}. "
                     f"Confidence rule: {CONFIDENCE_RULE}"),
        source="SIMULATED_REPORT",
        evidence_references=[evidence["evidence_id"]],
    ), reassess_routes=False)
    evidence = evidence_service.associate_evidence_with_threat(evidence["evidence_id"], threat["incident_id"])
    threat = threat_service.get_threat(threat["incident_id"])  # canonical shape (category, etc.)

    # Link first, then reassess every monitored route once (the mission route's
    # result is returned; other routes the zone touches are updated too).
    assessment = route_monitor_service.reassess_all(trigger="SIMULATED_REPORT").get(route_id) \
        or route_monitor_service.reassess_route(route_id, trigger="SIMULATED_REPORT")

    return {
        "status": "success",
        "simulated": True,
        "profile": profile_name,
        "evidence": evidence,
        "threat": {k: threat[k] for k in ("incident_id", "title", "category", "severity", "confidence",
                                          "latitude", "longitude", "radius_m", "source", "first_seen",
                                          "evidence_references")},
        "confidence_rule": CONFIDENCE_RULE,
        "route_assessment": assessment,
    }
