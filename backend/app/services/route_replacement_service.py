import re
import uuid
import datetime
from typing import Optional

from .route_monitor_service import route_monitor_service
from .routing_service import routing_service, NoSafeRouteError
from app.repositories.route_recommendation_repository import route_recommendation_repository
from .weather_adapter import weather_adapter

DEFAULT_ACTOR = "EOC operator"
# Operator names are SELF-DECLARED: there is no authentication in this prototype.
ACTOR_BASIS = "SELF_DECLARED_NOT_AUTHENTICATED"
_MAX_ACTOR = 80
_MAX_REASON = 500


def _clean_text(value, limit: int) -> Optional[str]:
    """Single-line, control-character-free, length-limited text, or None if empty."""
    if value is None:
        return None
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] or None


def clean_actor(value) -> str:
    return _clean_text(value, _MAX_ACTOR) or DEFAULT_ACTOR


def clean_reason(value) -> Optional[str]:
    return _clean_text(value, _MAX_REASON)


class RouteReplacementService:
    def __init__(self):
        # Proposal-time audit events are process-local; recommendations and
        # operator decisions are persisted in route_recommendations.
        self._audit_log: list = []

    def recommend_replacement(self, route_id: str) -> dict:
        route_record = route_monitor_service.get_route_record(route_id)
        if not route_record:
            return {"status": "error", "message": "Route not found"}

        if route_record["monitor_status"] != "INVALIDATED":
            return {
                "status": "success",
                "route_id": route_id,
                "replacement_status": "NOT_REQUIRED",
                "message": "Replacement not required."
            }

        origin = route_record.get("origin") or {}
        destination = route_record.get("destination") or {}
        if not all(k in origin for k in ("lat", "lon")) or not all(k in destination for k in ("lat", "lon")):
            return {
                "status": "error",
                "message": "Monitored route has no origin/destination with 'lat' and 'lon'; cannot compute a replacement."
            }
        manual_invalidation = route_monitor_service.is_manually_invalidated(route_record)
        threat_invalidation = bool(
            (route_record.get("current_hazard_summary") or {}).get("threat_exposure", {}).get("critical_threat_ids"))
        # Score comparison only makes sense when the invalidation came from hazard scores.
        # A route closed by an operator or a CRITICAL threat zone is replaced by any
        # different route the threat policy allows (which never enters blocking zones).
        policy_invalidation = manual_invalidation or threat_invalidation

        try:
            candidate = routing_service.calculate_route(
                origin["lat"], origin["lon"],
                destination["lat"], destination["lon"],
                hazard_aware=True
            )
        except NoSafeRouteError as e:
            self._record_attempt(route_id, "NO_SAFE_AVAILABLE_ROUTE", str(e),
                                 blocking_threat_ids=list(e.blocking_threat_ids or []))
            return {
                "status": "success",
                "route_id": route_id,
                "replacement_status": "NO_SAFE_AVAILABLE_ROUTE",
                "message": str(e),
                "blocking_threat_ids": e.blocking_threat_ids,
                "blocked_hazard_edges": e.blocked_hazard_edges,
                "attempt_recorded": True,
            }
        except Exception as e:
            if "No route exists" in str(e):
                self._record_attempt(route_id, "NO_ROUTE", "No alternative path exists.")
                return {
                    "status": "success",
                    "route_id": route_id,
                    "replacement_status": "NO_ROUTE",
                    "message": "No alternative path exists.",
                    "attempt_recorded": True,
                }
            return {
                "status": "error",
                "message": str(e)
            }

        if not candidate.get("route_nodes"):
            self._record_attempt(route_id, "NO_ROUTE", "No alternative path exists.")
            return {
                "status": "success",
                "route_id": route_id,
                "replacement_status": "NO_ROUTE",
                "message": "No alternative path exists.",
                "attempt_recorded": True,
            }

        old_summary = route_record["current_hazard_summary"]
        new_summary = candidate["hazard_summary"]
        
        old_score = old_summary.get("overall_score", 0.0)
        new_score = new_summary.get("overall_score", 0.0)
        # With incomplete data the candidate's score is only a lower bound; compare its
        # upper bound so an unknown component never makes a candidate look safer.
        candidate_partial = new_summary.get("score_basis") != "COMPLETE"
        comparison_score = new_summary.get("score_upper_bound", new_score) if candidate_partial else new_score
        new_critical = new_summary.get("critical_segments", 0)

        is_identical = (candidate["route_nodes"] == route_record["route_nodes"])

        if is_identical:
            replacement_status = "NO_BETTER_ROUTE"
            reason = "Current hazard-aware routing did not identify a lower-risk alternative."
        elif new_critical > 0:
            replacement_status = "NO_SAFE_AVAILABLE_ROUTE"
            reason = "Candidate route has CRITICAL segments."
        elif comparison_score >= old_score and not policy_invalidation:
            replacement_status = "NO_BETTER_ROUTE"
            reason = ("Candidate route is not lower risk than the current route"
                      + (" (candidate assessed on incomplete data; compared on its upper bound)." if candidate_partial else "."))
        elif policy_invalidation:
            replacement_status = "RECOMMENDATION_READY"
            reason = ("Current route was invalidated by an operator or a CRITICAL threat zone; "
                      "candidate is a different route that avoids blocking zones and has no CRITICAL segments.")
        else:
            replacement_status = "RECOMMENDATION_READY"
            reason = "Candidate route has lower hazard exposure and no CRITICAL segments."

        rec_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()
        
        mode_label = weather_adapter.mode_label()

        if replacement_status == "RECOMMENDATION_READY":
            route_recommendation_repository.save({
                "recommendation_id": rec_id,
                "route_id": route_id,
                "status": "PENDING",
                "candidate_route": candidate,
                "reason": reason,
                "created_at": now
            })
        else:
            self._record_attempt(route_id, replacement_status, reason, timestamp=now)

        audit_event = {
            "recommendation_id": rec_id if replacement_status == "RECOMMENDATION_READY" else None,
            "route_id": route_id,
            "timestamp": now,
            "old_hazard_score": old_score,
            "candidate_hazard_score": new_score,
            "old_critical_segments": old_summary.get("critical_segments", 0),
            "candidate_critical_segments": new_critical,
            "environmental_mode": mode_label,
            "reason": reason,
            "replacement_status": replacement_status
        }
        self._audit_log.append(audit_event)

        res = {
            "status": "success",
            "route_id": route_id,
            "replacement_status": replacement_status,
            "current_route": {
                "distance_m": route_record.get("distance_m", 0),
                "travel_time_s": route_record.get("estimated_time_s", 0),
                "hazard_score": old_score,
                "hazard_level": old_summary.get("overall_level", "SAFE"),
                "critical_segments": old_summary.get("critical_segments", 0),
                "high_risk_segments": old_summary.get("high_risk_segments", 0)
            },
            "candidate_route": {
                "distance_m": candidate.get("distance_m", 0),
                "travel_time_s": candidate.get("estimated_time_s", 0),
                "hazard_score": new_score,
                "hazard_score_upper_bound": new_summary.get("score_upper_bound"),
                "score_basis": new_summary.get("score_basis"),
                "hazard_level": new_summary.get("overall_level", "SAFE"),
                "critical_segments": new_critical,
                "high_risk_segments": new_summary.get("high_risk_segments", 0),
                "route_nodes": candidate.get("route_nodes"),
                "coordinates": (candidate.get("route") or {}).get("coordinates"),
                "threat_exposure": candidate.get("threat_exposure"),
            },
            "decision": {
                "recommended": replacement_status == "RECOMMENDATION_READY",
                "reason": reason
            },
            "data_completeness": {
                "current_route": old_summary.get("data_completeness"),
                "candidate_route": new_summary.get("data_completeness"),
                "candidate_confidence": new_summary.get("confidence"),
                "weather": new_summary.get("weather"),
            },
            "environmental_mode": mode_label,
            "provenance": {
                "weather": mode_label,
                "terrain": "ISRO/NRSC CartoDEM V3 R1 \u2014 D43D (LOCAL/CACHED DATA)",
                "road": "OpenStreetMap (LOCAL/CACHED GRAPH)"
            }
        }
        
        if replacement_status == "RECOMMENDATION_READY":
            res["recommendation_id"] = rec_id
            
        return res

    def _record_attempt(self, route_id: str, outcome: str, message: str, timestamp: Optional[str] = None, **extra) -> None:
        route_monitor_service.record_replacement_attempt(route_id, {
            "timestamp": timestamp or datetime.datetime.now().isoformat(),
            "outcome": outcome,
            "message": message,
            **extra,
        })

    def approve_replacement(self, route_id: str, recommendation_id: str, actor: str = DEFAULT_ACTOR,
                            reason: Optional[str] = None) -> dict:
        actor, reason = clean_actor(actor), clean_reason(reason)
        rec = route_recommendation_repository.get_by_id(recommendation_id)
        if not rec or rec["route_id"] != route_id:
            return {"status": "error", "message": "Recommendation not found or mismatch"}

        if rec["status"] != "PENDING":
            return {"status": "error", "message": f"Recommendation is already {rec['status']}"}

        now = datetime.datetime.now().isoformat()
        rec.update({"status": "APPROVED", "decided_at": now, "decided_by": actor, "decision_reason": reason})
        route_recommendation_repository.save(rec)

        # Apply the replacement
        route_monitor_service.apply_replacement(route_id, rec["candidate_route"], recommendation_id, actor=actor)
        
        audit_event = {
            "recommendation_id": recommendation_id,
            "route_id": route_id,
            "timestamp": now,
            "action": "APPROVED",
            "actor": actor,
            "actor_basis": ACTOR_BASIS,
            "reason": reason,
        }
        self._audit_log.append(audit_event)
        
        return {
            "status": "success",
            "approval_status": "APPROVED",
            "route_id": route_id,
            "replacement_status": "APPROVED",
            "audit_event": audit_event
        }

    def reject_replacement(self, route_id: str, recommendation_id: str, reason: str, actor: str = DEFAULT_ACTOR) -> dict:
        actor, reason = clean_actor(actor), clean_reason(reason) or "Operator rejected recommendation"
        rec = route_recommendation_repository.get_by_id(recommendation_id)
        if not rec or rec["route_id"] != route_id:
            return {"status": "error", "message": "Recommendation not found or mismatch"}

        if rec["status"] != "PENDING":
            return {"status": "error", "message": f"Recommendation is already {rec['status']}"}

        now = datetime.datetime.now().isoformat()
        rec.update({"status": "REJECTED", "decided_at": now, "decided_by": actor, "decision_reason": reason})
        route_recommendation_repository.save(rec)

        audit_event = {
            "recommendation_id": recommendation_id,
            "route_id": route_id,
            "timestamp": now,
            "action": "REJECTED",
            "actor": actor,
            "actor_basis": ACTOR_BASIS,
            "reason": reason
        }
        self._audit_log.append(audit_event)
        
        return {
            "status": "success",
            "approval_status": "REJECTED",
            "route_id": route_id,
            "replacement_status": "REJECTED",
            "audit_event": audit_event
        }

route_replacement_service = RouteReplacementService()
