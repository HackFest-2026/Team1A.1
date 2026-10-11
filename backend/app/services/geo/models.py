from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class GeoGISStatus(BaseModel):
    status: str
    graph_available: bool
    dem_available: bool
    dem_source: str
    region: str
    nodes_count: int
    edges_count: int

class GeoPointContext(BaseModel):
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    susceptibility_score: Optional[int] = None
    local_relative_elevation_m: Optional[float] = None
    nearest_node_id: Optional[int] = None
    nearest_node_lat: Optional[float] = None
    nearest_node_lon: Optional[float] = None
    distance_to_nearest_node_m: Optional[float] = None
    road_coverage_status: str = Field(
        "GRAPH_UNAVAILABLE",
        description="WITHIN_COVERAGE, OUTSIDE_COVERAGE (nearest road beyond MAX_SNAP_DISTANCE_M; node fields null) or GRAPH_UNAVAILABLE")
    terrain_status: str = "unavailable"
    terrain_reason: Optional[str] = Field(
        None, description="When terrain is unavailable: DEM_UNAVAILABLE, OUTSIDE_DEM_COVERAGE, NODATA, DEM_CRS_INCOMPATIBLE or DEM_READ_ERROR")
    source: str = "ISRO/NRSC CartoDEM V3 R1 - D43D"

class GeoSnapResult(BaseModel):
    input_lat: float
    input_lon: float
    snapped_node_id: int
    snapped_lat: float
    snapped_lon: float
    distance_m: float

class GeoRouteContext(BaseModel):
    origin: Dict[str, float]
    destination: Dict[str, float]
    distance_m: float
    estimated_time_s: float
    route_mode: str = "STANDARD"
    route_nodes: List[int] = Field(default_factory=list)
    route_geometry: Dict[str, Any]
    elevation_profile: Optional[List[Dict[str, Any]]] = None
    min_elevation_m: Optional[float] = None
    max_elevation_m: Optional[float] = None
    hazard_summary: Optional[Dict[str, Any]] = None
    threat_exposure: Optional[Dict[str, Any]] = None
    coverage: Optional[Dict[str, Any]] = None
    source: str = "cached_openstreetmap"
