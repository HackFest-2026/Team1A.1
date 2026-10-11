from typing import List, Optional, Dict, Any
from app.database.connection import get_db_context
from app.models.monitored_route import MonitoredRouteModel

class MonitoredRouteRepository:
    """Repository for Monitored Routes persistence using SQLAlchemy 2.x."""

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        with get_db_context() as db:
            records = db.query(MonitoredRouteModel).all()
            return {r.route_id: self._to_dict(r) for r in records}

    def get_by_id(self, route_id: str) -> Optional[Dict[str, Any]]:
        with get_db_context() as db:
            rec = db.query(MonitoredRouteModel).filter(MonitoredRouteModel.route_id == route_id).first()
            if not rec:
                return None
            return self._to_dict(rec)

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db_context() as db:
            r_id = data["route_id"]
            existing = db.query(MonitoredRouteModel).filter(MonitoredRouteModel.route_id == r_id).first()
            if existing:
                for key, value in data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                new_rec = MonitoredRouteModel(**data)
                db.add(new_rec)
            return data

    def count(self) -> int:
        with get_db_context() as db:
            return db.query(MonitoredRouteModel).count()

    def _to_dict(self, rec: MonitoredRouteModel) -> Dict[str, Any]:
        return {
            "route_id": rec.route_id,
            "origin": rec.origin or {},
            "destination": rec.destination or {},
            "route_nodes": rec.route_nodes or [],
            "distance_m": rec.distance_m,
            "estimated_time_s": rec.estimated_time_s,
            "created_at": rec.created_at,
            "last_checked_at": rec.last_checked_at,
            "initial_hazard_summary": rec.initial_hazard_summary or {},
            "current_hazard_summary": rec.current_hazard_summary or {},
            "monitor_status": rec.monitor_status,
            "transitions": rec.transitions or [],
            "previous_route_nodes": rec.previous_route_nodes,
            "replacement_attempts": rec.replacement_attempts or [],
        }

monitored_route_repository = MonitoredRouteRepository()
