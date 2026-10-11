import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.repositories.evidence_repository import evidence_repository
from app.repositories.threat_repository import threat_repository
from app.services.evidence.models import EvidenceCreate, EvidenceUpdate

class EvidenceService:
    """Business logic service for AEGIS-COP Evidence Domain."""

    def create_evidence(self, payload: EvidenceCreate) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat() + "Z"
        evidence_id = f"EVD-{datetime.utcnow().year}-{str(uuid.uuid4())[:8].upper()}"
        
        # Verify threat exists if threat_id is provided
        initial_status = "NEW"
        if payload.threat_id:
            threat = threat_repository.get_by_id(payload.threat_id)
            if not threat:
                raise ValueError(f"Threat event '{payload.threat_id}' does not exist")
            initial_status = "ASSOCIATED"

        # Build provenance
        prov = payload.provenance or {}
        if "origin" not in prov:
            prov["origin"] = payload.source_id or payload.source_type
        if "source_system" not in prov:
            prov["source_system"] = "AEGIS-COP"
        if "is_simulation" not in prov:
            prov["is_simulation"] = (payload.source_type == "SIMULATION")

        data = {
            "evidence_id": evidence_id,
            "source_type": payload.source_type,
            "source_id": payload.source_id,
            "observation_type": payload.observation_type,
            "timestamp": payload.timestamp or now,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "confidence": payload.confidence,
            "provenance": prov,
            "media_reference": payload.media_reference,
            "description": payload.description,
            "status": initial_status,
            "threat_id": payload.threat_id,
            "created_at": now,
            "updated_at": now,
        }

        return evidence_repository.save(data)

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        return evidence_repository.get_by_id(evidence_id)

    def list_evidence(
        self,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        threat_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return evidence_repository.list_evidence(
            source_type=source_type,
            status=status,
            threat_id=threat_id
        )

    def list_active_evidence(self) -> List[Dict[str, Any]]:
        """Evidence shown in the active COP: everything except ARCHIVED records."""
        return [e for e in evidence_repository.list_evidence() if e.get("status") != "ARCHIVED"]

    def update_evidence(self, evidence_id: str, update: EvidenceUpdate) -> Optional[Dict[str, Any]]:
        existing = evidence_repository.get_by_id(evidence_id)
        if not existing:
            return None

        now = datetime.utcnow().isoformat() + "Z"
        update_dict = update.dict(exclude_unset=True)

        if "threat_id" in update_dict and update_dict["threat_id"]:
            threat = threat_repository.get_by_id(update_dict["threat_id"])
            if not threat:
                raise ValueError(f"Threat event '{update_dict['threat_id']}' does not exist")
            if existing.get("status") in ["NEW", "REVIEWED"]:
                update_dict["status"] = "ASSOCIATED"

        for k, v in update_dict.items():
            if v is not None:
                existing[k] = v

        existing["updated_at"] = now
        return evidence_repository.save(existing)

    def associate_evidence_with_threat(self, evidence_id: str, threat_id: str) -> Dict[str, Any]:
        existing = evidence_repository.get_by_id(evidence_id)
        if not existing:
            raise KeyError(f"Evidence '{evidence_id}' not found")

        threat = threat_repository.get_by_id(threat_id)
        if not threat:
            raise ValueError(f"Threat event '{threat_id}' not found")

        now = datetime.utcnow().isoformat() + "Z"
        existing["threat_id"] = threat_id
        existing["status"] = "ASSOCIATED"
        existing["updated_at"] = now

        return evidence_repository.save(existing)

    def archive_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        existing = evidence_repository.get_by_id(evidence_id)
        if not existing:
            return None

        now = datetime.utcnow().isoformat() + "Z"
        existing["status"] = "ARCHIVED"
        existing["updated_at"] = now

        return evidence_repository.save(existing)

evidence_service = EvidenceService()
