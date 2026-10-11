from typing import List, Optional, Dict, Any
from datetime import datetime
from app.database.connection import get_db_context
from app.models.threat_event import IncidentModel

class ThreatRepository:
    """Repository for Incidents / Threat Events persistence using SQLAlchemy 2.x."""

    def get_all(self, state: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db_context() as db:
            query = db.query(IncidentModel)
            if state:
                query = query.filter(IncidentModel.state == state)
            if status:
                query = query.filter(IncidentModel.status == status)
            records = query.all()
            return [self._to_dict(inc) for inc in records]

    def list_threats(self, category: Optional[str] = None, status: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db_context() as db:
            query = db.query(IncidentModel)
            if category:
                query = query.filter(IncidentModel.hazard_type == category)
            if status:
                query = query.filter(IncidentModel.status == status)
            if severity:
                query = query.filter(IncidentModel.severity == severity)
            records = query.all()
            return [self._to_dict(inc) for inc in records]

    def get_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        with get_db_context() as db:
            inc = db.query(IncidentModel).filter(IncidentModel.incident_id == incident_id).first()
            if not inc:
                return None
            return self._to_dict(inc)

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db_context() as db:
            inc_id = data["incident_id"]
            existing = db.query(IncidentModel).filter(IncidentModel.incident_id == inc_id).first()
            if existing:
                for key, value in data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                new_inc = IncidentModel(**data)
                db.add(new_inc)
            return data

    def save_all(self, data_list: List[Dict[str, Any]]):
        with get_db_context() as db:
            for data in data_list:
                inc_id = data["incident_id"]
                existing = db.query(IncidentModel).filter(IncidentModel.incident_id == inc_id).first()
                if existing:
                    for key, value in data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    new_inc = IncidentModel(**data)
                    db.add(new_inc)

    def close_threat(self, threat_id: str, reason: str = None) -> Optional[Dict[str, Any]]:
        with get_db_context() as db:
            inc = db.query(IncidentModel).filter(IncidentModel.incident_id == threat_id).first()
            if not inc:
                return None
            inc.status = "CLOSED"
            inc.resolved_at = datetime.utcnow().isoformat() + "Z"
            inc.updated_at = datetime.utcnow().isoformat() + "Z"
            if reason:
                timeline = list(inc.timeline or [])
                timeline.append({
                    "incident_id": threat_id,
                    "event_type": "THREAT_CLOSED",
                    "description": f"Threat event closed. Reason: {reason}",
                    "source": "OPERATOR",
                    "actor": "EOC_OPERATOR",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "metadata": {}
                })
                inc.timeline = timeline
            return self._to_dict(inc)

    def count(self) -> int:
        with get_db_context() as db:
            return db.query(IncidentModel).count()

    def _to_dict(self, inc: IncidentModel) -> Dict[str, Any]:
        return {
            "incident_id": inc.incident_id,
            "threat_id": inc.incident_id, # Alias for threat domain
            "title": inc.title,
            "category": inc.hazard_type,
            "hazard_type": inc.hazard_type,
            "severity": inc.severity,
            "status": inc.status,
            "state": inc.state,
            "district": inc.district,
            "city": inc.city,
            "latitude": inc.latitude,
            "longitude": inc.longitude,
            "radius_m": getattr(inc, "radius_m", 500.0) or 500.0,
            "risk_score": inc.risk_score,
            "official_warning": inc.official_warning,
            "confidence": inc.confidence,
            "source": inc.source,
            "first_seen": getattr(inc, "first_seen", None) or inc.created_at,
            "last_seen": getattr(inc, "last_seen", None) or inc.updated_at,
            "created_at": inc.created_at,
            "updated_at": inc.updated_at,
            "started_at": inc.started_at,
            "resolved_at": inc.resolved_at,
            "description": inc.description,
            "evidence_references": getattr(inc, "evidence_references", []) or [],
            "alerts": inc.alerts or [],
            "escalations": inc.escalations or [],
            "resource_requirements": inc.resource_requirements or [],
            "response_plans": inc.response_plans or [],
            "timeline": inc.timeline or []
        }

threat_repository = ThreatRepository()
