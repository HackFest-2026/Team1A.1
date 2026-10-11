from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SystemStatusModel(BaseModel):
    status: str = Field("ONLINE", description="Overall backend system status")
    mode: str = Field("LOCAL", description="Operational execution mode (LOCAL / EDGE)")
    backend_health: str = Field("HEALTHY", description="FastAPI health check status")
    gis_status: str = Field("READY", description="OSM / NetworkX GIS graph availability")
    weather_mode: str = Field("UNAVAILABLE", description="AVAILABLE, STALE, UNAVAILABLE or CONTROLLED_SCENARIO")

class MapContextModel(BaseModel):
    center: Dict[str, float] = Field(default_factory=lambda: {"lat": 15.3647, "lon": 75.1240})
    default_zoom: int = 13
    region: str = "Hubballi-Dharwad"

class COPThreatModel(BaseModel):
    id: str
    category: str
    severity: str
    confidence: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_m: float = 500.0
    status: str
    title: str
    description: str = ""
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    source: Optional[str] = Field(None, description="Origin of the record, e.g. AEGIS_OBSERVATION or CONTROLLED_DEMO")
    is_demo: bool = Field(False, description="True for seeded/controlled demonstration records")

class COPFieldUnitModel(BaseModel):
    id: str
    name: str
    type: str
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    incident_id: Optional[str] = None
    last_seen: Optional[str] = None
    is_demo: bool = False

class COPMonitoredRouteModel(BaseModel):
    id: str
    status: str
    origin: Optional[Dict[str, float]] = None
    destination: Optional[Dict[str, float]] = None
    distance_m: float = 0.0
    estimated_time_s: float = 0.0
    hazard_summary: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = Field(
        None, description="GeoJSON LineString from the road graph; null when the graph or a node is unavailable"
    )

class COPEvidenceModel(BaseModel):
    """Canonical evidence record (Phase 4A `evidence` table)."""
    id: str
    threat_id: Optional[str] = None
    source_type: str
    source_id: Optional[str] = None
    observation_type: str
    timestamp: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence: float = Field(..., description="Source confidence, 0.0-1.0")
    status: str
    is_simulation: bool = False
    provenance: Dict[str, Any] = Field(default_factory=dict)
    media_reference: Optional[str] = None
    description: str = ""

class COPSummaryResponse(BaseModel):
    """Counts derived from the same snapshot; filtering rules are part of the contract."""
    generated_at: str
    system_status: str
    active_threat_count: int = Field(..., description="Threats whose status is not CLOSED or RESOLVED")
    active_unit_count: int = Field(..., description="Field units whose status is not COMPLETED or UNAVAILABLE")
    monitored_route_count: int = Field(..., description="All monitored routes in the snapshot")
    invalidated_route_count: int = Field(..., description="Monitored routes with status INVALIDATED")
    active_evidence_count: int = Field(..., description="Canonical evidence in the snapshot (ARCHIVED excluded)")

class COPSnapshotResponse(BaseModel):
    generated_at: str
    system: SystemStatusModel
    map: MapContextModel
    threats: List[COPThreatModel]
    field_units: List[COPFieldUnitModel]
    monitored_routes: List[COPMonitoredRouteModel]
    evidence: List[COPEvidenceModel]
    summary: Optional[COPSummaryResponse] = Field(None, description="Counts computed from this snapshot")

