import math
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.repositories.threat_repository import threat_repository
from app.services.threat.models import ThreatEventCreate, ThreatEventUpdate, RouteExposureRequest
from app.services.threat.zones import distance_point_to_line_m

def reassess_monitored_routes() -> None:
    """A threat change can compromise (or stop compromising) monitored routes:
    reassess them now rather than waiting for a manual check."""
    from app.services.route_monitor_service import route_monitor_service  # avoid import cycle
    route_monitor_service.reassess_all(trigger="THREAT_CHANGE")


class ThreatService:
    """Business logic service for AEGIS-COP Threat Domain."""

    def create_threat(self, payload: ThreatEventCreate, reassess_routes: bool = True) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat() + "Z"
        threat_id = f"THREAT-{datetime.utcnow().year}-{str(uuid.uuid4())[:8].upper()}"
        
        data = {
            "incident_id": threat_id,
            "title": payload.title,
            "hazard_type": payload.category,
            "severity": payload.severity,
            "status": "DETECTED",
            "state": payload.state,
            "district": payload.district,
            "city": payload.city,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "radius_m": payload.radius_m,
            "risk_score": 80 if payload.severity == "CRITICAL" else (60 if payload.severity == "HIGH" else 40),  # severity-derived placeholder, not a calibrated risk
            "official_warning": "NONE",  # operator/simulated threats carry no official (IMD) warning
            "confidence": payload.confidence,
            "source": payload.source,
            "first_seen": now,
            "last_seen": now,
            "created_at": now,
            "updated_at": now,
            "description": payload.description,
            "evidence_references": payload.evidence_references,
            "alerts": [],
            "escalations": [],
            "resource_requirements": [],
            "response_plans": [],
            "timeline": [{
                "incident_id": threat_id,
                "event_type": "THREAT_CREATED",
                "description": f"Threat event created: {payload.title}",
                "source": payload.source,
                "actor": "OPERATOR",
                "timestamp": now,
                "metadata": {}
            }]
        }
        
        saved = threat_repository.save(data)
        if reassess_routes:
            reassess_monitored_routes()
        return saved

    def get_threat(self, threat_id: str) -> Optional[Dict[str, Any]]:
        return threat_repository.get_by_id(threat_id)

    def list_threats(self, category: Optional[str] = None, status: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        return threat_repository.list_threats(category=category, status=status, severity=severity)

    def update_threat(self, threat_id: str, update: ThreatEventUpdate, reassess_routes: bool = True) -> Optional[Dict[str, Any]]:
        existing = threat_repository.get_by_id(threat_id)
        if not existing:
            return None

        now = datetime.utcnow().isoformat() + "Z"
        update_dict = update.dict(exclude_unset=True)
        
        # Map schema fields to storage fields
        if "category" in update_dict:
            update_dict["hazard_type"] = update_dict.pop("category")

        for k, v in update_dict.items():
            if v is not None:
                existing[k] = v

        existing["updated_at"] = now
        existing["last_seen"] = now

        # Add timeline record
        timeline = existing.get("timeline") or []
        timeline.append({
            "incident_id": threat_id,
            "event_type": "THREAT_UPDATED",
            "description": "Threat event attributes updated",
            "source": "OPERATOR",
            "actor": "EOC_OPERATOR",
            "timestamp": now,
            "metadata": update_dict
        })
        existing["timeline"] = timeline

        saved = threat_repository.save(existing)
        if reassess_routes:
            reassess_monitored_routes()
        return saved

    def close_threat(self, threat_id: str, reason: str = None, reassess_routes: bool = True) -> Optional[Dict[str, Any]]:
        closed = threat_repository.close_threat(threat_id=threat_id, reason=reason)
        if closed is not None and reassess_routes:
            reassess_monitored_routes()
        return closed

    def get_threat_zone(self, threat_id: str) -> Optional[Dict[str, Any]]:
        threat = threat_repository.get_by_id(threat_id)
        if not threat or threat.get("status") == "CLOSED":
            return None

        lat = threat.get("latitude")
        lon = threat.get("longitude")
        radius_m = float(threat.get("radius_m") or 500.0)

        if lat is None or lon is None:
            return None

        # Approximate bounding box
        delta_lat = radius_m / 111320.0
        delta_lon = radius_m / (111320.0 * math.cos(math.radians(lat)))

        return {
            "zone_id": f"zone-{threat_id}",
            "threat_id": threat_id,
            "category": threat.get("hazard_type", "UNKNOWN"),
            "severity": threat.get("severity", "HIGH"),
            "status": threat.get("status", "ACTIVE"),
            "center": {"lat": lat, "lon": lon},
            "radius_m": radius_m,
            "bounding_box": {
                "min_lat": round(lat - delta_lat, 6),
                "max_lat": round(lat + delta_lat, 6),
                "min_lon": round(lon - delta_lon, 6),
                "max_lon": round(lon + delta_lon, 6)
            }
        }

    def assess_route_exposure(self, route_coords: List[List[float]], threat_ids: Optional[List[str]] = None, safety_buffer_m: float = 50.0) -> Dict[str, Any]:
        """Contract for evaluating route geometry against threat zones."""
        all_threats = threat_repository.get_all()
        from app.config.routing_policy import INACTIVE_THREAT_STATUSES
        active_threats = [t for t in all_threats if (t.get("status") or "").upper() not in INACTIVE_THREAT_STATUSES]
        
        if threat_ids:
            active_threats = [t for t in active_threats if t.get("incident_id") in threat_ids or t.get("threat_id") in threat_ids]

        affected_threats = []
        intersected_zones = []
        details = []
        max_exposure_score = 0.0
        highest_severity = "SAFE"
        severity_rank = {"SAFE": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}

        for threat in active_threats:
            t_id = threat.get("incident_id") or threat.get("threat_id")
            t_lat = threat.get("latitude")
            t_lon = threat.get("longitude")
            t_radius = float(threat.get("radius_m") or 500.0)
            t_sev = threat.get("severity", "HIGH")

            if t_lat is None or t_lon is None:
                continue

            # Distance to the full route geometry (segments, not only vertices).
            min_dist = distance_point_to_line_m(t_lat, t_lon, route_coords)

            effective_threshold = t_radius + safety_buffer_m
            if min_dist <= effective_threshold:
                affected_threats.append(t_id)
                zone_info = self.get_threat_zone(t_id)
                if zone_info:
                    intersected_zones.append(zone_info)

                # Compute risk score for exposure
                overlap_penetration = max(0.0, effective_threshold - min_dist) / effective_threshold
                sev_multiplier = 1.0 if t_sev == "CRITICAL" else (0.8 if t_sev == "HIGH" else 0.5)
                score = round(min(100.0, overlap_penetration * 100.0 * sev_multiplier), 2)
                
                if score > max_exposure_score:
                    max_exposure_score = score

                if severity_rank.get(t_sev, 0) > severity_rank.get(highest_severity, 0):
                    highest_severity = t_sev

                details.append({
                    "threat_id": t_id,
                    "title": threat.get("title"),
                    "category": threat.get("hazard_type"),
                    "severity": t_sev,
                    "distance_to_center_m": round(min_dist, 2),
                    "effective_radius_m": effective_threshold,
                    "exposure_score": score
                })

        return {
            "exposed": len(affected_threats) > 0,
            "exposure_score": max_exposure_score,
            "highest_severity": highest_severity,
            "affected_threat_ids": affected_threats,
            "threat_zones_intersected": intersected_zones,
            "details": details
        }

    def get_threat_geo_context(self, threat_id: str) -> Optional[Any]:
        from app.services.threat.models import ThreatGeoContext, ThreatTerrainContext, ThreatNearestRoadContext
        
        threat = threat_repository.get_by_id(threat_id)
        if not threat:
            return None

        lat = threat.get("latitude")
        lon = threat.get("longitude")

        if lat is None or lon is None:
            return ThreatGeoContext(
                threat_id=threat_id,
                location={"latitude": 0.0, "longitude": 0.0},
                terrain=ThreatTerrainContext(status="unavailable"),
                nearest_road=ThreatNearestRoadContext(),
                route_context={"related_monitored_routes": []}
            )

        from app.services.geo import geo_context_service
        point_ctx = geo_context_service.get_point_context(lat=lat, lon=lon)

        # Monitored routes whose geometry passes within the threat radius + safety buffer.
        from app.config import routing_policy
        from app.repositories.monitored_route_repository import monitored_route_repository
        from app.services.routing_service import routing_service
        reach_m = float(threat.get("radius_m") or 500.0) + routing_policy.THREAT_SAFETY_BUFFER_M
        related_routes = []
        unchecked_routes = []
        for r_id, r_data in monitored_route_repository.get_all().items():
            geometry = routing_service.nodes_to_geometry(r_data.get("route_nodes") or [])
            if geometry is None:
                unchecked_routes.append(r_id)
                continue
            dist = distance_point_to_line_m(lat, lon, geometry["coordinates"])
            if dist <= reach_m:
                related_routes.append({
                    "route_id": r_id,
                    "monitor_status": r_data.get("monitor_status", "ACTIVE"),
                    "distance_m": round(dist, 1),
                })

        terrain_ctx = ThreatTerrainContext(
            elevation_m=point_ctx.elevation_m,
            susceptibility_score=point_ctx.susceptibility_score,
            local_relative_elevation_m=point_ctx.local_relative_elevation_m,
            status=point_ctx.terrain_status,
            reason=point_ctx.terrain_reason,
            source=point_ctx.source
        )

        road_ctx = ThreatNearestRoadContext(
            node_id=point_ctx.nearest_node_id,
            latitude=point_ctx.nearest_node_lat,
            longitude=point_ctx.nearest_node_lon,
            distance_m=point_ctx.distance_to_nearest_node_m,
            coverage_status=point_ctx.road_coverage_status,
        )

        return ThreatGeoContext(
            threat_id=threat_id,
            location={"latitude": lat, "longitude": lon},
            terrain=terrain_ctx,
            nearest_road=road_ctx,
            route_context={
                "related_monitored_routes": related_routes,
                "search_radius_m": reach_m,
                "routes_without_geometry": unchecked_routes,
            }
        )

threat_service = ThreatService()

