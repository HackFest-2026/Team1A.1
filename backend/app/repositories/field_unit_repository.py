from typing import List, Optional, Dict, Any
from app.database.connection import get_db_context
from app.models.field_unit import FieldUnitModel

class FieldUnitRepository:
    """Repository for Field Units persistence using SQLAlchemy 2.x."""

    def get_all(self, incident_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db_context() as db:
            query = db.query(FieldUnitModel)
            if incident_id:
                query = query.filter(FieldUnitModel.incident_id == incident_id)
            records = query.all()
            return [self._to_dict(unit) for unit in records]

    def get_by_id(self, field_unit_id: str) -> Optional[Dict[str, Any]]:
        with get_db_context() as db:
            unit = db.query(FieldUnitModel).filter(FieldUnitModel.field_unit_id == field_unit_id).first()
            if not unit:
                return None
            return self._to_dict(unit)

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db_context() as db:
            unit_id = data["field_unit_id"]
            existing = db.query(FieldUnitModel).filter(FieldUnitModel.field_unit_id == unit_id).first()
            if existing:
                for key, value in data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                new_unit = FieldUnitModel(**data)
                db.add(new_unit)
            return data

    def save_all(self, data_list: List[Dict[str, Any]]):
        with get_db_context() as db:
            for data in data_list:
                unit_id = data["field_unit_id"]
                existing = db.query(FieldUnitModel).filter(FieldUnitModel.field_unit_id == unit_id).first()
                if existing:
                    for key, value in data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    new_unit = FieldUnitModel(**data)
                    db.add(new_unit)

    def count(self) -> int:
        with get_db_context() as db:
            return db.query(FieldUnitModel).count()

    def _to_dict(self, unit: FieldUnitModel) -> Dict[str, Any]:
        return {
            "field_unit_id": unit.field_unit_id,
            "name": unit.name,
            "unit_type": unit.unit_type,
            "status": unit.status,
            "resource_id": unit.resource_id,
            "incident_id": unit.incident_id,
            "latitude": unit.latitude,
            "longitude": unit.longitude,
            "location_accuracy_m": unit.location_accuracy_m,
            "last_seen": unit.last_seen,
            "state": unit.state,
            "district": unit.district,
            "city": unit.city,
            "operator": unit.operator,
            "contact": unit.contact,
            "source": unit.source,
            "demo": unit.demo
        }

field_unit_repository = FieldUnitRepository()
