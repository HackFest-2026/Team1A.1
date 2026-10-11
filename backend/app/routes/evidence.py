from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status

from app.services.evidence import (
    evidence_service,
    EvidenceCreate,
    EvidenceUpdate,
    EvidenceResponse,
    EvidenceThreatAssociateRequest,
)

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

@router.get("", response_model=List[EvidenceResponse])
def list_evidence(
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. NEW, REVIEWED, ASSOCIATED, ARCHIVED)"),
    threat_id: Optional[str] = Query(None, description="Filter by associated threat event ID")
):
    """Retrieve all evidence records matching filter criteria."""
    return evidence_service.list_evidence(
        source_type=source_type,
        status=status,
        threat_id=threat_id
    )

@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(evidence_id: str):
    """Retrieve a single evidence record by ID."""
    ev = evidence_service.get_evidence(evidence_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    return ev

@router.post("", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def create_evidence(payload: EvidenceCreate):
    """Create a new evidence observation record."""
    try:
        return evidence_service.create_evidence(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{evidence_id}", response_model=EvidenceResponse)
def update_evidence(evidence_id: str, payload: EvidenceUpdate):
    """Update attributes of an existing evidence record."""
    try:
        updated = evidence_service.update_evidence(evidence_id, payload)
        if not updated:
            raise HTTPException(status_code=404, detail="Evidence record not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{evidence_id}/associate-threat", response_model=EvidenceResponse)
def associate_evidence_with_threat(evidence_id: str, payload: EvidenceThreatAssociateRequest):
    """Associate an evidence observation with an existing Threat Event."""
    try:
        return evidence_service.associate_evidence_with_threat(
            evidence_id=evidence_id,
            threat_id=payload.threat_id
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'"))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{evidence_id}/archive", response_model=EvidenceResponse)
def archive_evidence(evidence_id: str):
    """Archive an evidence record."""
    archived = evidence_service.archive_evidence(evidence_id)
    if not archived:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    return archived
