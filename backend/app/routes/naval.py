from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.ais_service import ais_service

router = APIRouter(prefix="/api/naval", tags=["naval"])

class IngestVesselContactRequest(BaseModel):
    mmsi: Optional[str] = None
    name: Optional[str] = "RADAR CONTACT"
    vessel_type: Optional[str] = "SURFACE_VESSEL"
    latitude: float
    longitude: float
    sog: Optional[float] = 0.0
    cog: Optional[float] = 0.0
    ais_status: Optional[str] = "matched"
    is_dark_vessel: Optional[bool] = False
    notes: Optional[str] = None

@router.get("/status")
def get_naval_status():
    """Status of live AIS stream ingestion and radar correlation."""
    return ais_service.get_status()

@router.get("/vessels")
def list_vessels(filter: Optional[str] = Query("ALL", description="Filter: ALL, DARK, MISMATCH, matched, missing")):
    """List current tactical vessels tracked in real time."""
    return {
        "status": "success",
        "count": len(ais_service.list_vessels(filter)),
        "vessels": ais_service.list_vessels(filter)
    }

@router.post("/vessels")
def ingest_vessel(contact: IngestVesselContactRequest):
    """Ingest a live vessel contact or radar track into AEGIS-COP."""
    try:
        res = ais_service.ingest_contact(contact.model_dump())
        return {"status": "success", "contact": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
