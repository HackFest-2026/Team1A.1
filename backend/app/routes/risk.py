from fastapi import APIRouter, Query
from typing import Optional
from ..services.national_risk_service import national_risk_service

router = APIRouter(prefix="/api/national/risk", tags=["national-risk"])

@router.get("")
def get_national_risk(state: Optional[str] = None, district: Optional[str] = None):
    return national_risk_service.get_national_risk(state, district)

@router.get("/forecast")
def get_national_forecast():
    return national_risk_service.get_forecast()

@router.get("/{region_id}")
def get_region_risk(region_id: str):
    return national_risk_service.get_region_risk(region_id)
