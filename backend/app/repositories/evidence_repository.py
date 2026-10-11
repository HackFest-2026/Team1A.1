from typing import List, Optional, Dict, Any
from app.database.connection import get_db_context
from app.models.evidence import EvidenceModel

class EvidenceRepository:
    """Repository for Evidence persistence using SQLAlchemy 2.x."""

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        with get_db_context() as db:
            records = db.query(EvidenceModel).all()
            return {r.evidence_id: self._to_dict(r) for r in records}

    def get_by_id(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        with get_db_context() as db:
            rec = db.query(EvidenceModel).filter(EvidenceModel.evidence_id == evidence_id).first()
            if not rec:
                return None
            return self._to_dict(rec)

    def list_evidence(
        self,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        threat_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with get_db_context() as db:
            query = db.query(EvidenceModel)
            if source_type:
                query = query.filter(EvidenceModel.source_type == source_type)
            if status:
                query = query.filter(EvidenceModel.status == status)
            if threat_id:
                query = query.filter(EvidenceModel.threat_id == threat_id)
            
            records = query.all()
            return [self._to_dict(r) for r in records]

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db_context() as db:
            ev_id = data["evidence_id"]
            existing = db.query(EvidenceModel).filter(EvidenceModel.evidence_id == ev_id).first()
            if existing:
                for key, value in data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                new_rec = EvidenceModel(**data)
                db.add(new_rec)
            return data

    def delete(self, evidence_id: str) -> bool:
        with get_db_context() as db:
            rec = db.query(EvidenceModel).filter(EvidenceModel.evidence_id == evidence_id).first()
            if rec:
                db.delete(rec)
                return True
            return False

    def count(self) -> int:
        with get_db_context() as db:
            return db.query(EvidenceModel).count()

    def _to_dict(self, rec: EvidenceModel) -> Dict[str, Any]:
        return {
            "evidence_id": rec.evidence_id,
            "source_type": rec.source_type,
            "source_id": rec.source_id,
            "observation_type": rec.observation_type,
            "timestamp": rec.timestamp,
            "latitude": rec.latitude,
            "longitude": rec.longitude,
            "confidence": rec.confidence,
            "provenance": rec.provenance or {},
            "media_reference": rec.media_reference,
            "description": rec.description or "",
            "status": rec.status,
            "threat_id": rec.threat_id,
            "created_at": rec.created_at,
            "updated_at": rec.updated_at,
        }

evidence_repository = EvidenceRepository()
