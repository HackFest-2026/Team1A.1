import datetime
import logging
import uuid
from typing import Dict, Any, Iterable, List, Optional

from .road_hazard_service import road_hazard_service
from .routing_service import routing_service
from .weather_adapter import weather_adapter
from app.services.threat.zones import ThreatZoneIndex, active_threat_zones
from app.services.hazard_scoring import summarize_risks
from app.repositories.monitored_route_repository import monitored_route_repository
from app.repositories.route_recommendation_repository import route_recommendation_repository

_STATUS_RANK = {"ACTIVE": 0, "AT_RISK": 1, "INVALIDATED": 2}  # REPLACED/unknown rank as 0

logger = logging.getLogger(__name__)


class RouteMonitorService:
    def __init__(self):
        self._load_from_db()

    def _load_from_db(self):
        self._monitored_routes: Dict[str, dict] = monitored_route_repository.get_all()

    def _persist_route(self, route_record: dict):
        monitored_route_repository.save(route_record)

    def _calculate_monitor_status(self, segments: List[dict]) -> tuple[str, dict]:
        critical = 0
        high = 0
        max_score = 0.0
        max_level = "SAFE"
        
        for seg in segments:
            risk = seg.get("hazard", {}).get("risk", {})
            score = risk.get("score") or 0.0  # None = nothing known; reported via completeness
            level = risk.get("level", "UNKNOWN")
            
            if score > max_score:
                max_score = score
            
            if level == "CRITICAL":
                critical += 1
            elif level == "HIGH":
                high += 1

        if max_score < 25:
            max_level = "SAFE"
        elif max_score < 50:
            max_level = "LOW"
        elif max_score < 75:
            max_level = "HIGH"
        else:
            max_level = "CRITICAL"
                    
        if critical > 0:
            status = "INVALIDATED"
        elif high > 0:
            status = "AT_RISK"
        else:
            status = "ACTIVE"
            
        summary = {
            "overall_score": max_score,
            "overall_level": max_level,
            "high_risk_segments": high,
            "critical_segments": critical,
            "highest_segment_score": max_score,
            **summarize_risks([seg.get("hazard", {}).get("risk", {}) for seg in segments]),
        }
        if segments:
            summary["weather"] = segments[0].get("hazard", {}).get("weather")
        return status, summary

    def _threat_status(self, node_ids: List[int]) -> tuple[str, dict]:
        """Monitoring status implied by active threat zones along the route geometry.

        CRITICAL zone on the route -> INVALIDATED; HIGH -> AT_RISK; lower severities
        are reported only. Unlike route planning there is no endpoint exemption.
        """
        index = ThreatZoneIndex(active_threat_zones())
        summary = {"checked": True, "critical_threat_ids": [], "high_threat_ids": [], "other_threat_ids": []}
        if not index:
            return "ACTIVE", summary
        edges = routing_service.route_edge_coordinates(node_ids)
        if edges is None:
            summary["checked"] = False
            return "ACTIVE", summary
        critical, high, other = set(), set(), set()
        for coords in edges:
            for zone, _dist in index.intersecting(coords):
                if zone.is_blocking:
                    critical.add(zone.threat_id)
                elif zone.severity == "HIGH":
                    high.add(zone.threat_id)
                else:
                    other.add(zone.threat_id)
        summary.update(critical_threat_ids=sorted(critical), high_threat_ids=sorted(high),
                       other_threat_ids=sorted(other))
        return ("INVALIDATED" if critical else "AT_RISK" if high else "ACTIVE"), summary

    def _evaluate_route(self, node_ids: List[int]) -> tuple[str, dict]:
        """Combined status: the worse of segment hazard status and threat-zone status."""
        assessment = road_hazard_service.assess_route(node_ids)
        status, summary = self._calculate_monitor_status(assessment.get("segments", []))
        summary["segment_count"] = assessment.get("segment_count", 0)
        threat_status, threat_summary = self._threat_status(node_ids)
        summary["threat_exposure"] = threat_summary
        if _STATUS_RANK[threat_status] > _STATUS_RANK[status]:
            status = threat_status
        return status, summary

    def list_routes(self) -> List[dict]:
        """All monitored route records, freshly loaded from the database."""
        self._load_from_db()
        return list(self._monitored_routes.values())

    def get_route_record(self, route_id: str) -> Optional[dict]:
        """Full persisted record for one route, or None."""
        self._load_from_db()
        return self._monitored_routes.get(route_id)

    def invalidate_route(self, route_id: str, reason: str = "Manually invalidated by operator",
                         actor: str = "EOC_OPERATOR", obstruction: Optional[dict] = None) -> Optional[dict]:
        """Persist a manual invalidation as an audited transition.

        Hazard scores are left untouched: a manual report is not a hazard
        measurement. When the operator supplies an obstruction location it is
        recorded as a CRITICAL threat so threat-aware routing avoids it.
        """
        record = self.get_route_record(route_id)
        if record is None:
            return None

        threat_id = None
        if obstruction:
            from app.services.threat.threat_service import threat_service
            from app.services.threat.models import ThreatEventCreate
            threat = threat_service.create_threat(ThreatEventCreate(
                title=f"Route obstruction reported on monitored route {route_id[:8]}",
                category="Road Obstruction",
                severity="CRITICAL",
                confidence="MEDIUM",
                latitude=float(obstruction["lat"]),
                longitude=float(obstruction["lon"]),
                radius_m=float(obstruction.get("radius_m", 50.0)),
                description=reason,
                source="CONTROLLED_DEMO" if obstruction.get("simulated") else "OPERATOR_REPORT",
            ), reassess_routes=False)
            threat_id = threat["incident_id"]

        now = datetime.datetime.now().isoformat()
        record["transitions"].append({
            "timestamp": now,
            "previous_status": record["monitor_status"],
            "new_status": "INVALIDATED",
            "trigger": "MANUAL",
            "actor": actor,
            "reason": reason,
            "obstruction_threat_id": threat_id,
        })
        record["monitor_status"] = "INVALIDATED"
        record["last_checked_at"] = now
        self._persist_route(record)
        if threat_id:
            # The new obstruction zone may also affect other monitored routes.
            self.reassess_all(trigger="THREAT_CHANGE", exclude=[route_id])

        return {
            "status": "success",
            "route_id": route_id,
            "monitor_status": "INVALIDATED",
            "obstruction_threat_id": threat_id,
        }

    def is_manually_invalidated(self, record: dict) -> bool:
        transitions = record.get("transitions") or []
        return (record.get("monitor_status") == "INVALIDATED" and bool(transitions)
                and transitions[-1].get("trigger") == "MANUAL")

    def register_route(self, route_payload: Dict[str, Any]) -> dict:
        route_id = str(uuid.uuid4())
        node_ids = route_payload.get("route_nodes", [])
        
        status, summary = self._evaluate_route(node_ids)
        
        now = datetime.datetime.now().isoformat()
        
        route_record = {
            "route_id": route_id,
            "origin": route_payload.get("origin"),
            "destination": route_payload.get("destination"),
            "route_nodes": node_ids,
            "distance_m": route_payload.get("distance_m", 0),
            "estimated_time_s": route_payload.get("estimated_time_s", 0),
            "created_at": now,
            "last_checked_at": now,
            "initial_hazard_summary": summary,
            "current_hazard_summary": summary,
            "monitor_status": status,
            "transitions": []
        }
        
        self._monitored_routes[route_id] = route_record
        self._persist_route(route_record)
        
        return {
            "status": "success",
            "route_id": route_id,
            "monitor_status": status,
            "segment_count": summary.get("segment_count", 0),
            "hazard_summary": summary
        }
        
    def get_route(self, route_id: str) -> dict:
        self._load_from_db()
        if route_id not in self._monitored_routes:
            return {"status": "not_found"}
            
        record = self._monitored_routes[route_id]
        
        # Pull environmental mode to display Provenance
        weather = weather_adapter.get_weather_evidence()
        mode_label = weather_adapter.mode_label()
        warning = weather.get("warning")
            
        res = {
            "status": "success",
            "route_id": record["route_id"],
            "monitor_status": record["monitor_status"],
            "created_at": record["created_at"],
            "last_checked_at": record["last_checked_at"],
            "hazard_summary": record["current_hazard_summary"],
            "environmental_mode": mode_label,
            # Mission history (all persisted): status transitions and replacement
            # recommendations with their operator decisions.
            "origin": record.get("origin"),
            "destination": record.get("destination"),
            "distance_m": record.get("distance_m"),
            "estimated_time_s": record.get("estimated_time_s"),
            "transitions": record.get("transitions") or [],
            "recommendations": route_recommendation_repository.list_for_route(route_id),
            # Replacement searches that produced no recommendation (e.g. no safe route).
            "replacement_attempts": record.get("replacement_attempts") or [],
        }
        if warning:
            res["warning"] = warning

        return res
        
    def reassess_all(self, trigger: str = "THREAT_CHANGE", exclude: Optional[Iterable[str]] = None) -> Dict[str, dict]:
        """Reassess every monitored route after the threat picture changed.

        Called when a threat is created, updated or closed, so a new zone on a route
        invalidates it without waiting for a manual check. A failure on one route is
        logged and reported, never allowed to block recording the threat itself.
        """
        self._load_from_db()
        skip = set(exclude or [])
        results: Dict[str, dict] = {}
        for route_id in list(self._monitored_routes):
            if route_id in skip:
                continue
            try:
                results[route_id] = self.reassess_route(route_id, trigger=trigger)
            except Exception as exc:  # noqa: BLE001 - isolate per-route failures
                logger.warning("Automatic reassessment of route %s failed: %s", route_id, exc)
                results[route_id] = {"status": "error", "route_id": route_id, "message": str(exc)}
        return results

    def record_replacement_attempt(self, route_id: str, attempt: dict) -> None:
        """Persist a replacement search that produced no recommendation."""
        self._load_from_db()
        record = self._monitored_routes.get(route_id)
        if record is None:
            return
        record["replacement_attempts"] = list(record.get("replacement_attempts") or []) + [attempt]
        self._persist_route(record)

    def reassess_route(self, route_id: str, trigger: str = "CHECK") -> dict:
        self._load_from_db()
        if route_id not in self._monitored_routes:
            return {"status": "not_found"}
            
        record = self._monitored_routes[route_id]
        prev_status = record["monitor_status"]
        
        # Reassess with current environment and active threats
        curr_status, summary = self._evaluate_route(record["route_nodes"])
        # An approved replacement that is still clear stays REPLACED: "still clear" is
        # not a new event and must not be logged as hazards having dropped.
        if prev_status == "REPLACED" and curr_status == "ACTIVE":
            curr_status = "REPLACED"
        # A manual invalidation stays in force until a replacement is approved;
        # improving hazard readings alone do not clear an operator's report.
        manual_retained = self.is_manually_invalidated(record) and curr_status != "INVALIDATED"
        if manual_retained:
            curr_status = "INVALIDATED"
        # Incomplete data (e.g. weather unavailable or stale) cannot show that conditions
        # improved: keep a worse previous status rather than downgrading on a lower bound.
        incomplete_retained = (
            not manual_retained
            and summary.get("score_basis") != "COMPLETE"
            and _STATUS_RANK.get(prev_status, 0) > _STATUS_RANK.get(curr_status, 0)
        )
        if incomplete_retained:
            curr_status = prev_status

        now = datetime.datetime.now().isoformat()
        record["last_checked_at"] = now
        record["current_hazard_summary"] = summary
        record["monitor_status"] = curr_status
        
        weather = weather_adapter.get_weather_evidence()
        mode_label = weather_adapter.mode_label()
        
        changed = (prev_status != curr_status)
        reason = None
        
        if changed:
            critical_threats = summary.get("threat_exposure", {}).get("critical_threat_ids") or []
            high_threats = summary.get("threat_exposure", {}).get("high_threat_ids") or []
            if curr_status == "INVALIDATED" and critical_threats:
                reason = "Route intersects active CRITICAL threat zone(s): " + ", ".join(critical_threats)
            elif curr_status == "AT_RISK" and high_threats and summary.get("high_risk_segments", 0) == 0:
                reason = "Route intersects active HIGH threat zone(s): " + ", ".join(high_threats)
            elif curr_status == "INVALIDATED":
                reason = "A monitored route segment reached CRITICAL hazard level."
            elif curr_status == "AT_RISK":
                reason = "A monitored route segment reached HIGH risk level."
            elif curr_status == "ACTIVE":
                reason = "Route hazards dropped to acceptable levels."
                
            record["transitions"].append({
                "timestamp": now,
                "previous_status": prev_status,
                "new_status": curr_status,
                "highest_segment_score": summary["highest_segment_score"],
                "environmental_mode": mode_label,
                "reason": reason,
                "trigger": trigger,
            })
            
        self._persist_route(record)

        res = {
            "status": "success",
            "route_id": route_id,
            "previous_status": prev_status,
            "current_status": curr_status,
            "changed": changed,
            "environmental_mode": mode_label,
            "threat_exposure": summary.get("threat_exposure"),
        }
        if manual_retained:
            res["manual_invalidation_retained"] = True
        if incomplete_retained:
            res["status_retained_incomplete_data"] = True
        res["data_completeness"] = summary.get("data_completeness")
        res["confidence"] = summary.get("confidence")
        res["weather_state"] = (summary.get("weather") or {}).get("state")
        
        if reason:
            res["reason"] = reason
        elif curr_status in ("INVALIDATED", "AT_RISK"):
            # Unchanged but compromised (e.g. already invalidated automatically when the
            # threat was recorded): report the stored reason for the current status.
            last = next((t for t in reversed(record.get("transitions") or [])
                         if t.get("new_status") == curr_status), None)
            if last and last.get("reason"):
                res["reason"] = last["reason"]
                res["reason_recorded_at"] = last.get("timestamp")
            
        if curr_status == "INVALIDATED":
            res["route_replacement_required"] = True
            
        if weather.get("warning"):
            res["warning"] = weather["warning"]
            
        return res

    def apply_replacement(self, route_id: str, candidate_route: dict, recommendation_id: str, actor: str = "EOC Operator"):
        self._load_from_db()
        if route_id not in self._monitored_routes:
            return
            
        record = self._monitored_routes[route_id]
        prev_status = record["monitor_status"]
        now = datetime.datetime.now().isoformat()
        
        # We need the candidate's summary which was pre-calculated or stored in candidate_route
        new_summary = candidate_route.get("hazard_summary", {})
        
        record["transitions"].append({
            "timestamp": now,
            "previous_status": prev_status,
            "new_status": "REPLACED",
            "highest_segment_score": new_summary.get("highest_segment_score", 0.0),
            "environmental_mode": weather_adapter.mode_label(),
            "reason": f"Route replaced by {actor}. Recommendation ID: {recommendation_id}"
        })
        
        # Keep old route for history
        record["previous_route_nodes"] = record["route_nodes"]
        
        # Update current stats
        record["route_nodes"] = candidate_route.get("route_nodes", [])
        record["distance_m"] = candidate_route.get("distance_m", 0)
        record["estimated_time_s"] = candidate_route.get("estimated_time_s", 0)
        record["current_hazard_summary"] = new_summary
        record["monitor_status"] = "REPLACED"
        record["last_checked_at"] = now
        
        self._persist_route(record)

route_monitor_service = RouteMonitorService()
