from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any

VALID_SOURCE_TYPES = {"DRONE", "SATELLITE", "SENSOR", "HUMAN_REPORT", "SYSTEM_GENERATED", "SIMULATION"}
VALID_STATUSES = {"NEW", "REVIEWED", "ASSOCIATED", "ARCHIVED"}

class EvidenceCreate(BaseModel):
    source_type: str = Field(..., description="Observation source type (DRONE, SATELLITE, SENSOR, HUMAN_REPORT, SYSTEM_GENERATED, SIMULATION)")
    source_id: Optional[str] = Field(None, description="Identifier of the specific source device/sensor")
    observation_type: str = Field(..., description="Type of observation (e.g., WATERLOGGING_OBSERVATION, ROAD_BLOCKAGE, PHOTO)")
    timestamp: Optional[str] = Field(None, description="Observation timestamp in UTC ISO format")
    latitude: Optional[float] = Field(None, description="Geographic latitude (-90 to +90)")
    longitude: Optional[float] = Field(None, description="Geographic longitude (-180 to +180)")
    confidence: float = Field(1.0, description="Normalized source confidence (0.0 to 1.0)")
    provenance: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata explaining origin and source system")
    media_reference: Optional[str] = Field(None, description="Reference metadata to media asset or URL")
    description: str = Field("", description="Human readable observation summary or notes")
    threat_id: Optional[str] = Field(None, description="Optional association to an existing threat event ID")

    @validator("source_type")
    def validate_source_type(cls, v):
        v_upper = v.upper()
        if v_upper not in VALID_SOURCE_TYPES:
            raise ValueError(f"Invalid source_type '{v}'. Must be one of: {sorted(list(VALID_SOURCE_TYPES))}")
        return v_upper

    @validator("latitude")
    def validate_latitude(cls, v):
        if v is not None and (v < -90.0 or v > 90.0):
            raise ValueError("Latitude must be between -90.0 and +90.0 degrees")
        return v

    @validator("longitude")
    def validate_longitude(cls, v):
        if v is not None and (v < -180.0 or v > 180.0):
            raise ValueError("Longitude must be between -180.0 and +180.0 degrees")
        return v

    @validator("confidence")
    def validate_confidence(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

class EvidenceUpdate(BaseModel):
    source_type: Optional[str] = None
    observation_type: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[float] = None
    media_reference: Optional[str] = None
    description: Optional[str] = None
    threat_id: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None

    @validator("source_type")
    def validate_source_type(cls, v):
        if v is not None:
            v_upper = v.upper()
            if v_upper not in VALID_SOURCE_TYPES:
                raise ValueError(f"Invalid source_type '{v}'. Must be one of: {sorted(list(VALID_SOURCE_TYPES))}")
            return v_upper
        return v

    @validator("status")
    def validate_status(cls, v):
        if v is not None:
            v_upper = v.upper()
            if v_upper not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{v}'. Must be one of: {sorted(list(VALID_STATUSES))}")
            return v_upper
        return v

    @validator("confidence")
    def validate_confidence(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

class EvidenceResponse(BaseModel):
    evidence_id: str
    source_type: str
    source_id: Optional[str] = None
    observation_type: str
    timestamp: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence: float
    provenance: Dict[str, Any]
    media_reference: Optional[str] = None
    description: str
    status: str
    threat_id: Optional[str] = None
    created_at: str
    updated_at: str

class EvidenceThreatAssociateRequest(BaseModel):
    threat_id: str = Field(..., description="Target threat event ID to associate with evidence")
