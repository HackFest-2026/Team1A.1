from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import uuid

class Citizen(BaseModel):
    citizen_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    email: str
    state: str
    district: str
    city: Optional[str] = None
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    preferred_language: str = "en"
    sms_enabled: bool = True
    email_enabled: bool = True
    push_enabled: bool = False
    consent_status: bool = True
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

class DeliveryRecord(BaseModel):
    delivery_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str
    citizen_id: str
    channel: str # "SMS" or "EMAIL"
    status: str # "QUEUED", "SIMULATED", "SENT", "DELIVERED", "FAILED"
    provider_message_id: Optional[str] = None
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    failure_reason: Optional[str] = None

class AlertRecord(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    severity: str
    hazard_type: str
    target_region: Dict[str, str] # {"state": "Karnataka", "district": "Dharwad"}
    reason: str
    confidence: str
    source: str
    messages: Dict[str, str] # {"en": "...", "hi": "...", "kn": "..."}
    status: str # "CREATED", "ACTIVE", "EXPIRED", "CANCELLED"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    expires_at: str
    data_freshness: str
    targeted_count: int = 0
    acknowledged_count: int = 0
    deliveries: List[DeliveryRecord] = []

class AuditLog(BaseModel):
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    actor: str
    action: str
    alert_id: Optional[str] = None
    result: str

class AuthorityEscalation(BaseModel):
    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str
    region: Dict[str, str]
    severity: str
    recommended_action: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    status: str = "RECOMMENDED" # "RECOMMENDED", "ACKNOWLEDGED", "ASSIGNED", "RESOLVED"
