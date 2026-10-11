from fastapi import APIRouter, Query
from typing import Optional
from ..services.satellite_service import satellite_service

router = APIRouter(prefix="/api/national/satellite", tags=["satellite"])

@router.get("/status")
def get_status():
    return satellite_service.get_status()

@router.get("/latest")
def get_latest():
    return satellite_service.get_latest()

@router.get("/layers")
def get_layers():
    return satellite_service.get_layers()

@router.get("/fire")
def get_fire(state: Optional[str] = None, district: Optional[str] = None):
    return satellite_service.get_fire(state, district)
