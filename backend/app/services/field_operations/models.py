from pydantic import BaseModel, Field, validator
from typing import List, Optional, Any
from datetime import datetime
import uuid

class FieldUnit(BaseModel):
    field_unit_id: str = Field(default_factory=lambda: f"FU-{str(uuid.uuid4())[:8].upper()}")
    name: str
    unit_type: str
    status: str = "ASSIGNED" # ASSIGNED, EN_ROUTE, AT_SCENE, OPERATING, RETURNING, COMPLETED, UNAVAILABLE
    resource_id: Optional[str] = None
    incident_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy_m: Optional[float] = None
    last_seen: Optional[str] = None
    state: str = ""
    district: str = ""
    city: str = ""
    operator: str = "SYSTEM"
    contact: str = ""
    source: str = "EOC"
    demo: bool = False

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    accuracy_m: float
    timestamp: Optional[str] = None
    source: str = "GPS"

    @validator("latitude")
    def validate_lat(cls, v):
        if not (-90 <= v <= 90): raise ValueError("Latitude must be between -90 and 90")
        return v

    @validator("longitude")
    def validate_lon(cls, v):
        if not (-180 <= v <= 180): raise ValueError("Longitude must be between -180 and 180")
        return v

    @validator("accuracy_m")
    def validate_acc(cls, v):
        if v < 0: raise ValueError("Accuracy must be >= 0")
        return v

class StatusUpdate(BaseModel):
    new_status: str
    actor: str = "SYSTEM"
    role: str = "EOC_OPERATOR"

class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"EVD-{str(uuid.uuid4())[:8].upper()}")
    incident_id: str
    field_unit_id: Optional[str] = None
    evidence_type: str # PHOTO, VIDEO, TEXT_REPORT, OBSERVATION, SENSOR_READING
    file_name: str
    file_path: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    captured_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    uploaded_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    description: str = ""
    source: str = "FIELD_APP"
    analysis_status: str = "UNANALYZED" # UNANALYZED, NOT_CONFIGURED, PENDING, COMPLETED, FAILED
    ai_label: str = "UNKNOWN" # FLOOD_WATER_VISIBLE, ROAD_OBSTRUCTED, DEBRIS_VISIBLE, VEHICLE_PRESENT, PEOPLE_VISIBLE, FIRE_VISIBLE, NO_CLEAR_HAZARD, UNKNOWN
    ai_confidence: Optional[int] = None  # MOCK: random value from filename keyword matching, not model output
    analysis_method: str = "NONE"  # FILENAME_KEYWORD_MOCK after analyze(); no real CV model exists
    human_confirmation: str = "UNREVIEWED" # UNREVIEWED, CONFIRMED, REJECTED
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None
    demo: bool = False

class FieldReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"REP-{str(uuid.uuid4())[:8].upper()}")
    incident_id: str
    field_unit_id: Optional[str] = None
    summary: str
    severity_observation: str = "UNKNOWN" # NORMAL, LOW, HIGH, CRITICAL, UNKNOWN
    access_condition: str = "UNKNOWN" # OPEN, RESTRICTED, BLOCKED, UNKNOWN
    people_at_risk: str = "UNKNOWN"
    road_condition: str = ""
    resource_condition: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    created_by: str = "FIELD_OPERATOR"
    demo: bool = False

class AccessConditionModel(BaseModel):
    # Abstract foundation as requested
    condition: str

class CitizenObservation(BaseModel):
    observation_id: str = Field(default_factory=lambda: f"COBS-{str(uuid.uuid4())[:8].upper()}")
    incident_id: Optional[str] = None
    description: str
    latitude: float
    longitude: float
    submitted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source: str = "CITIZEN_APP"
    verification_status: str = "UNVERIFIED" # UNVERIFIED, UNDER_REVIEW, VERIFIED, REJECTED
    demo: bool = False
