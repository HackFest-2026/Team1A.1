"""
Maritime Intelligence & AIS Tracking Router for AEGIS-COP.
Provides endpoints for importing historical AIS CSV datasets, querying vessel telemetry,
playing back historical movement tracks, and planning sea routes using verified topological graphs.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field

from app.services.maritime_ais import maritime_ais_service

router = APIRouter(prefix="/api/maritime", tags=["maritime intelligence"])

class SeaRouteRequest(BaseModel):
    origin: str = Field(..., description="Origin port or waypoint ID (e.g. 'mumbai')")
    destination: str = Field(..., description="Destination port or waypoint ID (e.g. 'colombo')")
    speed_knots: Optional[float] = Field(14.0, ge=1.0, le=50.0, description="Vessel cruising speed in knots")

class DirectCSVImportRequest(BaseModel):
    csv_content: str = Field(..., description="Raw CSV string content")
    source_name: Optional[str] = Field("Direct Input CSV", description="Label for imported dataset")

@router.post("/ais/import")
async def import_ais_csv(
    file: Optional[UploadFile] = File(None)
):
    """
    Import historical AIS observations from a user-uploaded CSV file.
    Validates coordinates, timestamps, and column aliases, reporting any rejected rows.
    """
    if file is None:
        raise HTTPException(
            status_code=400,
            detail="No file uploaded. Please supply a CSV file in multipart/form-data field 'file'."
        )

    # 50MB file size limit
    MAX_BYTES = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="AIS CSV exceeds maximum allowed upload size of 50 MB.")

    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            csv_text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Could not decode CSV text as UTF-8 or Latin-1.")

    try:
        summary = maritime_ais_service.import_csv_content(csv_text, source_name=file.filename or "Uploaded AIS CSV")
        return {
            "status": "success",
            "message": f"Imported {summary['valid_rows']} valid AIS records across {summary['vessel_count']} vessels.",
            "summary": summary
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error importing AIS CSV: {str(e)}")

@router.post("/ais/import-raw")
def import_raw_csv_text(payload: DirectCSVImportRequest):
    """Import historical AIS observations from direct CSV string payload."""
    try:
        summary = maritime_ais_service.import_csv_content(payload.csv_content, source_name=payload.source_name)
        return {
            "status": "success",
            "message": f"Imported {summary['valid_rows']} valid AIS records across {summary['vessel_count']} vessels.",
            "summary": summary
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error importing AIS CSV: {str(e)}")

@router.post("/ais/demo-load")
def load_demo_dataset():
    """Reloads the bundled demonstration historical AIS dataset (Arabian Sea / Indian Ocean)."""
    try:
        maritime_ais_service.preload_sample_dataset()
        summary = maritime_ais_service.get_summary()
        return {
            "status": "success",
            "message": "Bundled demonstration historical AIS dataset loaded successfully.",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load demonstration dataset: {str(e)}")

@router.get("/ais/summary")
def get_ais_summary():
    """Retrieve import statistics, bounding box, and temporal freshness of current AIS data."""
    return {
        "status": "success",
        "dataset": maritime_ais_service.get_summary()
    }

@router.get("/ais/vessels")
def list_ais_vessels(
    search: Optional[str] = Query(None, description="Search by vessel name or MMSI"),
    ship_type: Optional[str] = Query(None, description="Filter by ship type (e.g. Tanker, Cargo, Fishing)"),
    min_lat: Optional[float] = Query(None, description="Minimum latitude bounding filter"),
    max_lat: Optional[float] = Query(None, description="Maximum latitude bounding filter"),
    min_lon: Optional[float] = Query(None, description="Minimum longitude bounding filter"),
    max_lon: Optional[float] = Query(None, description="Maximum longitude bounding filter"),
    limit: int = Query(200, ge=1, le=1000, description="Max vessels to return")
):
    """List tracked vessels matching filter criteria."""
    vessels = maritime_ais_service.list_vessels(
        search=search,
        ship_type=ship_type,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit
    )
    return {
        "status": "success",
        "count": len(vessels),
        "vessels": vessels
    }

@router.get("/ais/positions")
def get_ais_positions(
    mmsi: Optional[str] = Query(None, description="Filter by vessel MMSI"),
    ship_type: Optional[str] = Query(None, description="Filter by ship type"),
    start_time: Optional[str] = Query(None, description="Start timestamp (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="End timestamp (ISO 8601)"),
    min_lat: Optional[float] = Query(None, description="Bounding box min latitude"),
    max_lat: Optional[float] = Query(None, description="Bounding box max latitude"),
    min_lon: Optional[float] = Query(None, description="Bounding box min longitude"),
    max_lon: Optional[float] = Query(None, description="Bounding box max longitude"),
    limit: int = Query(1000, ge=1, le=5000, description="Max positions to return"),
    sample_step: int = Query(1, ge=1, le=20, description="Downsample step to keep map performant")
):
    """Retrieve observation positions matching temporal and geographic bounds."""
    res = maritime_ais_service.get_positions(
        mmsi=mmsi,
        ship_type=ship_type,
        start_time=start_time,
        end_time=end_time,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
        sample_step=sample_step
    )
    return {
        "status": "success",
        **res
    }

@router.get("/ais/tracks/{mmsi}")
def get_vessel_track(
    mmsi: str,
    max_gap_hours: float = Query(6.0, ge=0.5, le=72.0, description="Maximum hours before splitting track into separate segment")
):
    """
    Retrieve chronological track observations for a specific vessel.
    Detects large time gaps to prevent misleading straight-line interpolation across gaps.
    """
    track = maritime_ais_service.get_vessel_track(mmsi=mmsi, max_gap_hours=max_gap_hours)
    if not track.get("found"):
        raise HTTPException(status_code=404, detail=track.get("error", f"Vessel MMSI {mmsi} not found"))
    return {
        "status": "success",
        "track": track
    }

@router.get("/ports")
def list_navigable_ports():
    """Retrieve available ports and navigable sea waypoints in the topological graph."""
    return {
        "status": "success",
        "ports": maritime_ais_service.list_ports()
    }

@router.post("/route")
def calculate_sea_route(req: SeaRouteRequest):
    """
    Calculate a prototype maritime sea route between verified ports/waypoints
    using Dijkstra's algorithm across validated navigable deepwater corridors.
    """
    try:
        route_result = maritime_ais_service.plan_sea_route(
            origin_id=req.origin,
            destination_id=req.destination,
            speed_knots=req.speed_knots
        )
        return {
            "status": "success",
            "route": route_result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")
