from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class ThreatEventCreate(BaseModel):
    title: str
    category: str = Field(..., description="Hazard or threat category, e.g. Flood, Drainage Overflow, Waterlogging")
    severity: str = Field("HIGH", description="Severity level: LOW, MODERATE, HIGH, CRITICAL")
    confidence: str = Field("MEDIUM", description="Confidence level: LOW, MEDIUM, HIGH")
    latitude: float
    longitude: float
    radius_m: float = Field(500.0, description="Threat radius in meters")
    state: str = "Karnataka"
    district: str = "Dharwad"
    city: Optional[str] = "Hubballi"
    description: str = ""
    source: str = "AEGIS_OBSERVATION"
    evidence_references: List[str] = Field(default_factory=list)

class ThreatEventUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    confidence: Optional[str] = None
    status: Optional[str] = None
    radius_m: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    evidence_references: Optional[List[str]] = None

class ThreatZoneModel(BaseModel):
    zone_id: str
    threat_id: str
    category: str
    severity: str
    status: str
    center: Dict[str, float]
    radius_m: float
    bounding_box: Dict[str, float]

class RouteExposureRequest(BaseModel):
    route_coordinates: List[List[float]] = Field(..., description="GeoJSON coordinates array [[lon, lat], ...]")
    threat_ids: Optional[List[str]] = None
    safety_buffer_m: float = Field(50.0, description="Additional safety buffer distance in meters")

class RouteExposureResponse(BaseModel):
    exposed: bool
    exposure_score: float = Field(..., description="Exposure risk score 0.0 (Safe) to 100.0 (Critical)")
    highest_severity: str
    affected_threat_ids: List[str]
    threat_zones_intersected: List[Dict[str, Any]]
    details: List[Dict[str, Any]]

class ThreatTerrainContext(BaseModel):
    elevation_m: Optional[float] = None
    susceptibility_score: Optional[int] = None
    local_relative_elevation_m: Optional[float] = None
    status: str = "unavailable"
    reason: Optional[str] = None
    source: str = "ISRO/NRSC CartoDEM V3 R1 - D43D"

class ThreatNearestRoadContext(BaseModel):
    node_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_m: Optional[float] = None
    coverage_status: str = "GRAPH_UNAVAILABLE"

class ThreatGeoContext(BaseModel):
    threat_id: str
    location: Dict[str, float]
    terrain: ThreatTerrainContext
    nearest_road: ThreatNearestRoadContext
    route_context: Dict[str, Any] = Field(default_factory=dict)

