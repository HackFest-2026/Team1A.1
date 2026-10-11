import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from .models import Incident, TimelineEvent, IncidentAuditLog
from ..national_risk_service import national_risk_service
from app.repositories.threat_repository import threat_repository

class IncidentService:
    def __init__(self):
        self._load_from_db()

    def _load_from_db(self):
        self.incidents: Dict[str, Incident] = {}
        self.audit_logs: List[IncidentAuditLog] = []
        db_records = threat_repository.get_all()
        for rec in db_records:
            timeline_events = [TimelineEvent(**t) if isinstance(t, dict) else t for t in rec.get("timeline", [])]
            rec["timeline"] = timeline_events
            inc = Incident(**rec)
            self.incidents[inc.incident_id] = inc

    def _persist_incident(self, incident: Incident):
        # Convert Incident model to dict for persistence
        data = incident.dict()
        # Convert TimelineEvent objects to dicts for JSON column
        data["timeline"] = [t if isinstance(t, dict) else t.dict() for t in incident.timeline]
        threat_repository.save(data)

    def _log_audit(self, actor: str, role: str, action: str, incident_id: str, result: str, metadata: Dict[str, Any] = None):
        log = IncidentAuditLog(
            actor=actor,
            role=role,
            action=action,
            incident_id=incident_id,
            result=result,
            metadata=metadata or {}
        )
        self.audit_logs.append(log)

    def _add_timeline(self, incident: Incident, event_type: str, description: str, source: str, actor: str, metadata: Dict[str, Any] = None):
        event = TimelineEvent(
            incident_id=incident.incident_id,
            event_type=event_type,
            description=description,
            source=source,
            actor=actor,
            metadata=metadata or {}
        )
        incident.timeline.append(event)
        incident.updated_at = datetime.utcnow().isoformat() + "Z"
        self._persist_incident(incident)

    def scan_for_incidents(self) -> Dict[str, Any]:
        """Reads risk engine and recommends/updates incidents."""
        risk_data = national_risk_service.get_national_risk()
        regions = risk_data.get("regions", [])

        # No regions from the risk feed (e.g. IMD access not configured) -> fall back to a
        # built-in list of DEMO regions. Those are fixtures, not detections: they are
        # labelled DEMO, carry no official warning, and say so in their timeline.
        from_fallback = not regions
        if from_fallback:
            regions = [
                {
                    "state": "Karnataka", "district": "Gokul Road Corridor", "city": "Hubballi",
                    "latitude": 15.3647, "longitude": 75.1240,
                    "risk": {"level": "CRITICAL", "score": 88}, "official_warning": {"level": "RED"},
                    "hazard_type": "Road Waterlogging", "title": "Gokul Road Waterlogging",
                    "description": "Heavy rainfall has caused water accumulation along Gokul Road. Stormwater drainage is overflowing and vehicle access is restricted."
                },
                {
                    "state": "Karnataka", "district": "Dharwad Central", "city": "Dharwad",
                    "latitude": 15.4589, "longitude": 75.0078,
                    "risk": {"level": "HIGH", "score": 78}, "official_warning": {"level": "ORANGE"},
                    "hazard_type": "Drainage Overflow", "title": "Dharwad Central Drainage Overflow",
                    "description": "Stormwater drainage overflow is affecting road access near Dharwad Central following heavy rainfall."
                },
                {
                    "state": "Karnataka", "district": "Old Hubballi Sector", "city": "Hubballi",
                    "latitude": 15.3520, "longitude": 75.1380,
                    "risk": {"level": "CRITICAL", "score": 85}, "official_warning": {"level": "RED"},
                    "hazard_type": "Low-Lying Area Flooding", "title": "Hubballi Low-Lying Area Flooding",
                    "description": "Urban inundation in low-lying residential sectors of Old Hubballi. Retention ponds are at maximum capacity."
                },
                {
                    "state": "Karnataka", "district": "Keshwapur Corridor", "city": "Hubballi",
                    "latitude": 15.3600, "longitude": 75.1450,
                    "risk": {"level": "HIGH", "score": 72}, "official_warning": {"level": "ORANGE"},
                    "hazard_type": "Open Drain Blockage", "title": "Keshwapur Open Drain Blockage",
                    "description": "An open drainage channel is reported blocked near Keshwapur, resulting in overflow toward the main roadway."
                },
                {
                    "state": "Karnataka", "district": "Vidyanagar Junction", "city": "Hubballi",
                    "latitude": 15.3720, "longitude": 75.1180,
                    "risk": {"level": "HIGH", "score": 76}, "official_warning": {"level": "ORANGE"},
                    "hazard_type": "Flooded Junction", "title": "Vidyanagar Junction Inundation",
                    "description": "Traffic junction near KIMS Hospital is waterlogged. Traffic speed reduced; emergency vehicle routing required."
                },
                {
                    "state": "Karnataka", "district": "Unkal Lake Outlet", "city": "Hubballi",
                    "latitude": 15.3850, "longitude": 75.1050,
                    "risk": {"level": "CRITICAL", "score": 89}, "official_warning": {"level": "RED"},
                    "hazard_type": "Culvert Overflow", "title": "Unkal Lake Spillway Overflow",
                    "description": "Culvert overflow near Unkal Lake spillway is threatening nearby access arterial roads."
                },
                {
                    "state": "Karnataka", "district": "Hosur Circle Corridor", "city": "Hubballi",
                    "latitude": 15.3550, "longitude": 75.1320,
                    "risk": {"level": "MODERATE", "score": 68}, "official_warning": {"level": "YELLOW"},
                    "hazard_type": "Road Access Affected", "title": "Hosur Circle Waterlogging",
                    "description": "Runoff accumulation near Hosur Circle causing slow traffic and partial lane closure."
                },
                {
                    "state": "Karnataka", "district": "Navanagar Sector 4", "city": "Hubballi",
                    "latitude": 15.3900, "longitude": 75.0950,
                    "risk": {"level": "HIGH", "score": 75}, "official_warning": {"level": "ORANGE"},
                    "hazard_type": "Drainage Overflow", "title": "Navanagar Stormwater Overflow",
                    "description": "Stormwater channel overflow near Navanagar residential sector."
                },
                {
                    "state": "Karnataka", "district": "Jubilee Circle", "city": "Dharwad",
                    "latitude": 15.4520, "longitude": 75.0110,
                    "risk": {"level": "MODERATE", "score": 64}, "official_warning": {"level": "YELLOW"},
                    "hazard_type": "Flooded Access Road", "title": "Jubilee Circle Road Flooding",
                    "description": "Localized waterlogging near Jubilee Circle affecting arterial road access."
                }
            ]

        new_incidents = []
        updated_incidents = []

        for region in regions:
            rr_level = region.get("risk", {}).get("level", "NORMAL").upper()
            imd_level = "NONE" if from_fallback else region.get("official_warning", {}).get("level", "NORMAL").upper()
            
            if rr_level in ["CRITICAL", "HIGH"] or imd_level in ["CRITICAL", "HIGH"]:
                state = region["state"]
                district = region["district"]
                hazard_type = region.get("hazard_type", "Flood / Severe Weather")
                
                # Deduplication: Find active incident for state + district
                existing_inc = None
                for inc in self.incidents.values():
                    if inc.state == state and inc.district == district and inc.status not in ["RESOLVED", "CLOSED"]:
                        existing_inc = inc
                        break
                
                severity = "CRITICAL" if "CRITICAL" in [rr_level, imd_level] else "HIGH"
                confidence = "HIGH" if (rr_level in ["CRITICAL", "HIGH"] and imd_level in ["CRITICAL", "HIGH"]) else "MEDIUM"
                
                if existing_inc:
                    if existing_inc.severity != severity:
                        old_sev = existing_inc.severity
                        existing_inc.severity = severity
                        existing_inc.risk_score = region.get("risk", {}).get("score")
                        existing_inc.official_warning = imd_level
                        existing_inc.confidence = confidence
                        self._add_timeline(
                            existing_inc, "RISK_INCREASED" if severity == "CRITICAL" else "RISK_CHANGED",
                            f"Severity changed from {old_sev} to {severity}",
                            "RISK_ENGINE", "SYSTEM"
                        )
                        self._persist_incident(existing_inc)
                        updated_incidents.append(existing_inc.incident_id)
                else:
                    title = region.get("title") or f"DEMO INCIDENT: {hazard_type} in {district}"
                    if from_fallback and not title.upper().startswith("DEMO"):
                        title = f"DEMO: {title}"
                    description = region.get("description") or "Automated risk detection based on controlled flood scenario precipitation and drainage runoff."
                    if from_fallback:
                        description += " (Built-in demo region: the regional risk feed is not configured, so this is a fixture, not a detection.)"
                    inc = Incident(
                        title=title,
                        hazard_type=hazard_type,
                        severity=severity,
                        status="DETECTED",
                        state=state,
                        district=district,
                        city=region.get("city"),
                        latitude=region.get("latitude"),
                        longitude=region.get("longitude"),
                        risk_score=region.get("risk", {}).get("score"),
                        official_warning=imd_level,
                        confidence=confidence,
                        source="CONTROLLED_DEMO",
                        description=description
                    )
                    self.incidents[inc.incident_id] = inc
                    if from_fallback:
                        self._add_timeline(inc, "INCIDENT_CREATED",
                                           "DEMO incident created from the built-in region list (no regional risk feed configured; not a detection)",
                                           "DEMO_FIXTURE", "SYSTEM")
                    else:
                        self._add_timeline(inc, "INCIDENT_CREATED", "Incident created by the risk engine from the regional risk feed", "RISK_ENGINE", "SYSTEM")
                    self._log_audit("SYSTEM", "SYSTEM", "INCIDENT_CREATED", inc.incident_id, "SUCCESS")
                    self._persist_incident(inc)
                    new_incidents.append(inc.incident_id)

        if new_incidents or updated_incidents:
            # New or changed incidents are threat zones too.
            from app.services.threat.threat_service import reassess_monitored_routes
            reassess_monitored_routes()

        return {
            "status": "success",
            "new_incidents": new_incidents,
            "updated_incidents": updated_incidents,
            "source": "BUILT_IN_DEMO_REGIONS" if from_fallback else "REGIONAL_RISK_FEED",
        }

    def get_all(self, state: str = None, status: str = None) -> List[Dict[str, Any]]:
        self._load_from_db()
        res = []
        for inc in self.incidents.values():
            if state and inc.state != state: continue
            if status and inc.status != status: continue
            res.append(inc.dict())
        # Sort by updated_at descending
        res.sort(key=lambda x: x["updated_at"], reverse=True)
        return res

    def get_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        self._load_from_db()
        inc = self.incidents.get(incident_id)
        if not inc: return None
        return inc.dict()

    def update_status(self, incident_id: str, new_status: str, actor: str = "EOC_OPERATOR", role: str = "EOC_OPERATOR") -> Dict[str, Any]:
        self._load_from_db()
        inc = self.incidents.get(incident_id)
        if not inc:
            return {"error": "Incident not found"}
        
        old_status = inc.status
        inc.status = new_status
        if new_status == "RESOLVED":
            inc.resolved_at = datetime.utcnow().isoformat() + "Z"
            
        self._add_timeline(inc, "STATUS_UPDATED", f"Status changed from {old_status} to {new_status}", "OPERATOR", actor)
        self._log_audit(actor, role, "INCIDENT_UPDATED", incident_id, f"SUCCESS: Status={new_status}")
        self._persist_incident(inc)
        # A resolved incident stops being a threat zone; reassess monitored routes.
        from app.services.threat.threat_service import reassess_monitored_routes
        reassess_monitored_routes()
        return {"status": "success", "incident": inc.dict()}

    def link_alert(self, incident_id: str, alert_id: str, actor: str = "SYSTEM"):
        self._load_from_db()
        inc = self.incidents.get(incident_id)
        if inc and alert_id not in inc.alerts:
            inc.alerts.append(alert_id)
            self._add_timeline(inc, "ALERT_LINKED", f"Alert {alert_id} linked to incident", "ALERT_ENGINE", actor)
            self._persist_incident(inc)

    def link_escalation(self, incident_id: str, escalation_id: str, actor: str = "SYSTEM"):
        self._load_from_db()
        inc = self.incidents.get(incident_id)
        if inc and escalation_id not in inc.escalations:
            inc.escalations.append(escalation_id)
            self._add_timeline(inc, "AUTHORITY_ESCALATED", f"Authority Escalation {escalation_id} recommended", "OPERATOR", actor)
            self._persist_incident(inc)

incident_service = IncidentService()
