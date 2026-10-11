from fastapi import APIRouter
from app.services.cop.cop_service import cop_service
from app.services.cop.models import COPSnapshotResponse, COPSummaryResponse

router = APIRouter(prefix="/api/cop", tags=["cop"])

@router.get("", response_model=COPSnapshotResponse)
def get_cop_snapshot():
    """Retrieve complete, unified Common Operating Picture (COP) snapshot."""
    return cop_service.get_cop_snapshot()

@router.get("/summary", response_model=COPSummaryResponse)
def get_cop_summary():
    """Retrieve operational summary statistics of the Common Operating Picture."""
    return cop_service.get_cop_summary()
