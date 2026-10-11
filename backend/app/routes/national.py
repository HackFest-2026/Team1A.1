from fastapi import APIRouter, Query
from typing import Optional
from ..services.national_weather_service import national_weather_service

router = APIRouter(prefix="/api/national", tags=["national"])

@router.get("/status")
def get_status():
    return national_weather_service.get_status()

@router.get("/weather")
def get_weather(state: Optional[str] = None, district: Optional[str] = None):
    return national_weather_service.get_weather(state, district)

@router.get("/warnings")
def get_warnings(state: Optional[str] = None):
    return national_weather_service.get_warnings(state)

@router.get("/nowcast")
def get_nowcast(district: Optional[str] = None):
    return national_weather_service.get_nowcast(district)
