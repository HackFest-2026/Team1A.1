from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.threat.simulated_report import (
    CONFIDENCE_RULE,
    PROFILES,
    SimulatedReportError,
    submit_simulated_report,
)

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class SimulatedReportRequest(BaseModel):
    route_id: str
    profile: str = "ROAD_FLOODING_SENSOR"


@router.get("/profiles")
def list_profiles():
    """Fixed simulation profiles (inputs, not assessments) and the confidence rule."""
    return {"profiles": PROFILES, "confidence_rule": CONFIDENCE_RULE}


@router.post("/field-report")
def create_simulated_report(payload: SimulatedReportRequest):
    """Create a SIMULATED report on a mission route: evidence + linked threat, then reassess the route."""
    try:
        return submit_simulated_report(payload.route_id, payload.profile)
    except SimulatedReportError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
