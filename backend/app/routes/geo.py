from fastapi import APIRouter, HTTPException, Query
from app.services.routing_service import NoSafeRouteError, OutsideCoverageError
from app.services.geo import (
    geo_context_service,
    GeoGISStatus,
    GeoPointContext,
    GeoSnapResult,
    GeoRouteContext
)

router = APIRouter(prefix="/api/geo", tags=["Geo Context"])

@router.get("/status", response_model=GeoGISStatus)
def get_geo_status():
    """Get status of underlying GIS infrastructure (OSM road graph and CartoDEM terrain)."""
    return geo_context_service.get_gis_status()

@router.get("/coverage")
def get_coverage():
    """Geographic coverage manifest derived from the loaded datasets (ADR-008)."""
    return geo_context_service.get_coverage_manifest()

@router.get("/point", response_model=GeoPointContext)
def get_point_context(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude")
):
    """Retrieve geospatial point context including elevation, terrain susceptibility, and nearest road node."""
    try:
        return geo_context_service.get_point_context(lat=lat, lon=lon)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/snap", response_model=GeoSnapResult)
def snap_coordinate(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude")
):
    """Snap a coordinate to the nearest OSM road graph node and calculate distance in meters."""
    try:
        return geo_context_service.snap_coordinate(lat=lat, lon=lon)
    except OutsideCoverageError as e:
        raise HTTPException(status_code=422, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/route-context", response_model=GeoRouteContext)
def get_route_context(
    origin_lat: float = Query(..., description="Origin latitude"),
    origin_lon: float = Query(..., description="Origin longitude"),
    destination_lat: float = Query(..., description="Destination latitude"),
    destination_lon: float = Query(..., description="Destination longitude"),
    hazard_aware: bool = Query(False, description="Enable hazard-aware routing"),
    include_elevation: bool = Query(True, description="Include elevation profile along route"),
    avoid_threats: bool = Query(True, description="Apply the threat-zone routing policy")
):
    """Calculate route geospatial context including geometry, distance, travel time, elevation profile, and hazard summary."""
    try:
        return geo_context_service.get_route_context(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            hazard_aware=hazard_aware,
            include_elevation_profile=include_elevation,
            avoid_threats=avoid_threats,
        )
    except NoSafeRouteError as e:
        raise HTTPException(status_code=409, detail=e.to_dict())
    except OutsideCoverageError as e:
        raise HTTPException(status_code=422, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
