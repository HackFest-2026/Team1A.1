from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query

from app.services.threat.threat_service import threat_service
from app.services.threat.models import (
    ThreatEventCreate,
    ThreatEventUpdate,
    RouteExposureRequest,
    ThreatGeoContext,
)

router = APIRouter(prefix="/api/threats", tags=["threats"])

@router.get("", response_model=List[Dict[str, Any]])
def list_threats(
    category: Optional[str] = Query(None, description="Filter by hazard category"),
    status: Optional[str] = Query(None, description="Filter by status (e.g., DETECTED, ACTIVE, CLOSED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (e.g., LOW, HIGH, CRITICAL)")
):
    """Retrieve all threat events matching criteria."""
    return threat_service.list_threats(category=category, status=status, severity=severity)

@router.get("/{threat_id}/geo-context", response_model=ThreatGeoContext)
def get_threat_geo_context(threat_id: str):
    """Retrieve geographic context (terrain, nearest road node, monitored route context) for a threat event."""
    geo_ctx = threat_service.get_threat_geo_context(threat_id)
    if not geo_ctx:
        raise HTTPException(status_code=404, detail="Threat event not found")
    return geo_ctx

@router.get("/{threat_id}", response_model=Dict[str, Any])
def get_threat(threat_id: str):
    """Retrieve a single threat event by ID."""
    threat = threat_service.get_threat(threat_id)
    if not threat:
        raise HTTPException(status_code=404, detail="Threat event not found")
    return threat

@router.post("", response_model=Dict[str, Any], status_code=201)
def create_threat(payload: ThreatEventCreate):
    """Create a new threat event."""
    return threat_service.create_threat(payload)

@router.patch("/{threat_id}", response_model=Dict[str, Any])
def update_threat(threat_id: str, payload: ThreatEventUpdate):
    """Update attributes of an existing threat event."""
    updated = threat_service.update_threat(threat_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Threat event not found")
    return updated

@router.post("/{threat_id}/close", response_model=Dict[str, Any])
def close_threat(threat_id: str, reason: Optional[str] = Query(None, description="Reason for closing threat")):
    """Close an active threat event."""
    closed = threat_service.close_threat(threat_id, reason=reason)
    if not closed:
        raise HTTPException(status_code=404, detail="Threat event not found")
    return closed

@router.get("/{threat_id}/zone", response_model=Dict[str, Any])
def get_threat_zone(threat_id: str):
    """Get spatial Threat Zone definition derived from a threat event."""
    zone = threat_service.get_threat_zone(threat_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Threat zone not found or threat is closed")
    return zone

@router.post("/assess-exposure", response_model=Dict[str, Any])
def assess_route_exposure(payload: RouteExposureRequest):
    """Assess route geometry against active Threat Zones."""
    return threat_service.assess_route_exposure(
        route_coords=payload.route_coordinates,
        threat_ids=payload.threat_ids,
        safety_buffer_m=payload.safety_buffer_m
    )

