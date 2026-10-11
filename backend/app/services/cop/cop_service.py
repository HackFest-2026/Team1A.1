from datetime import datetime
from typing import List, Dict, Any

from app.services.threat.threat_service import threat_service
from app.services.field_operations.field_service import field_service
from app.services.route_monitor_service import route_monitor_service
from app.services.evidence.evidence_service import evidence_service
from app.services.routing_service import routing_service
from app.services.weather_adapter import weather_adapter

from app.services.cop.models import (
    SystemStatusModel,
    MapContextModel,
    COPThreatModel,
    COPFieldUnitModel,
    COPMonitoredRouteModel,
    COPEvidenceModel,
    COPSnapshotResponse,
    COPSummaryResponse,
)

class CopService:
    """Orchestration/read-model service that composes domain state into a COP snapshot."""

    def get_cop_snapshot(self) -> COPSnapshotResponse:
        now = datetime.utcnow().isoformat() + "Z"

        # 1. System & GIS Status Context
        gis_info = routing_service.get_status()
        gis_status_str = "READY" if gis_info.get("graph_available") else "UNAVAILABLE"
        weather = weather_adapter.assess_weather()
        weather_mode_str = "CONTROLLED_SCENARIO" if weather["controlled_scenario"] else weather["state"]

        system_status = SystemStatusModel(
            status="ONLINE",
            mode="LOCAL",
            backend_health="HEALTHY",
            gis_status=gis_status_str,
            weather_mode=weather_mode_str,
        )

        map_context = MapContextModel(
            center={"lat": 15.3647, "lon": 75.1240},
            default_zoom=13,
            region="Hubballi-Dharwad",
        )

        # 2. Normalize Threats
        raw_threats = threat_service.list_threats()
        normalized_threats: List[COPThreatModel] = []
        for t in raw_threats:
            t_id = t.get("incident_id") or t.get("threat_id") or "UNKNOWN"
            normalized_threats.append(
                COPThreatModel(
                    id=t_id,
                    category=t.get("category") or t.get("hazard_type") or "General Threat",
                    severity=t.get("severity") or "HIGH",
                    confidence=t.get("confidence") or "MEDIUM",
                    latitude=t.get("latitude"),
                    longitude=t.get("longitude"),
                    radius_m=float(t.get("radius_m") or 500.0),
                    status=t.get("status") or "DETECTED",
                    title=t.get("title") or "Threat Event",
                    description=t.get("description") or "",
                    first_seen=t.get("first_seen") or t.get("created_at"),
                    last_seen=t.get("last_seen") or t.get("updated_at"),
                    source=t.get("source"),
                    is_demo=t.get("source") in ("CONTROLLED_DEMO", "SIMULATED_REPORT"),
                )
            )

        # 3. Normalize Field Units
        raw_units = field_service.get_all()
        normalized_units: List[COPFieldUnitModel] = []
        for u in raw_units:
            u_id = u.get("field_unit_id") or "UNKNOWN"
            normalized_units.append(
                COPFieldUnitModel(
                    id=u_id,
                    name=u.get("name") or "Field Unit",
                    type=u.get("unit_type") or "RESCUE_TEAM",
                    status=u.get("status") or "ASSIGNED",
                    latitude=u.get("latitude"),
                    longitude=u.get("longitude"),
                    incident_id=u.get("incident_id"),
                    last_seen=u.get("last_seen"),
                    is_demo=bool(u.get("demo")),
                )
            )

        # 4. Normalize Monitored Routes
        normalized_routes: List[COPMonitoredRouteModel] = []
        for r in route_monitor_service.list_routes():
            r_id = r.get("route_id") or "UNKNOWN"
            normalized_routes.append(
                COPMonitoredRouteModel(
                    id=r_id,
                    status=r.get("monitor_status") or "ACTIVE",
                    origin=r.get("origin"),
                    destination=r.get("destination"),
                    distance_m=float(r.get("distance_m") or 0.0),
                    estimated_time_s=float(r.get("estimated_time_s") or 0.0),
                    hazard_summary=r.get("current_hazard_summary") or r.get("initial_hazard_summary") or {},
                    created_at=r.get("created_at"),
                    last_checked_at=r.get("last_checked_at"),
                    geometry=routing_service.nodes_to_geometry(r.get("route_nodes") or []),
                )
            )

        # 5. Canonical evidence (Phase 4A store); ARCHIVED records are excluded.
        normalized_evidence: List[COPEvidenceModel] = []
        for e in evidence_service.list_active_evidence():
            provenance = e.get("provenance") or {}
            normalized_evidence.append(
                COPEvidenceModel(
                    id=e["evidence_id"],
                    threat_id=e.get("threat_id"),
                    source_type=e["source_type"],
                    source_id=e.get("source_id"),
                    observation_type=e["observation_type"],
                    timestamp=e.get("timestamp") or e.get("created_at"),
                    latitude=e.get("latitude"),
                    longitude=e.get("longitude"),
                    confidence=float(e.get("confidence", 0.0)),
                    status=e.get("status") or "NEW",
                    is_simulation=bool(provenance.get("is_simulation")) or e["source_type"] == "SIMULATION",
                    provenance=provenance,
                    media_reference=e.get("media_reference"),
                    description=e.get("description") or "",
                )
            )

        snapshot = COPSnapshotResponse(
            generated_at=now,
            system=system_status,
            map=map_context,
            threats=normalized_threats,
            field_units=normalized_units,
            monitored_routes=normalized_routes,
            evidence=normalized_evidence,
        )
        snapshot.summary = self._summarize(snapshot, now)
        return snapshot

    def get_cop_summary(self) -> COPSummaryResponse:
        return self.get_cop_snapshot().summary

    def _summarize(self, snapshot: COPSnapshotResponse, now: str) -> COPSummaryResponse:

        active_threats = [t for t in snapshot.threats if t.status not in ("CLOSED", "RESOLVED")]
        active_units = [u for u in snapshot.field_units if u.status not in ("COMPLETED", "UNAVAILABLE")]
        invalidated_routes = [r for r in snapshot.monitored_routes if r.status == "INVALIDATED"]

        return COPSummaryResponse(
            generated_at=now,
            system_status=snapshot.system.status,
            active_threat_count=len(active_threats),
            active_unit_count=len(active_units),
            monitored_route_count=len(snapshot.monitored_routes),
            invalidated_route_count=len(invalidated_routes),
            active_evidence_count=len(snapshot.evidence),
        )

cop_service = CopService()
