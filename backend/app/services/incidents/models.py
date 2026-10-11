from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class TimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    event_type: str
    description: str
    source: str
    actor: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = {}

class Incident(BaseModel):
    incident_id: str = Field(default_factory=lambda: f"RR-{datetime.utcnow().year}-{str(uuid.uuid4())[:8].upper()}")
    title: str
    hazard_type: str
    severity: str
    status: str = "DETECTED" # DETECTED, ASSESSING, ACTIVE, ESCALATED, RESPONSE_IN_PROGRESS, CONTAINED, RESOLVED, CLOSED
    state: str
    district: str
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    risk_score: Optional[int] = None
    official_warning: str = "NORMAL"
    confidence: str = "LOW"
    source: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    started_at: Optional[str] = None
    resolved_at: Optional[str] = None
    description: str
    alerts: List[str] = [] # List of alert IDs
    escalations: List[str] = [] # List of authority escalation IDs
    resource_requirements: List[str] = []
    response_plans: List[str] = []
    timeline: List[TimelineEvent] = []

class IncidentAuditLog(BaseModel):
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    actor: str
    role: str
    action: str
    incident_id: str
    result: str
    metadata: Dict[str, Any] = {}
