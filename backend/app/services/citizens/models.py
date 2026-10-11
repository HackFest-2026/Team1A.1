from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Any
from datetime import datetime
import uuid

class Citizen(BaseModel):
    citizen_id: str = Field(default_factory=lambda: f"CIT-{str(uuid.uuid4())[:8].upper()}")
    name: str
    phone: str
    email: str
    preferred_language: str = "English" # English, Hindi, Kannada
    state: str = ""
    district: str = ""
    city: str = ""
    latitude: float
    longitude: float
    consent_sms: bool = False
    consent_email: bool = False
    consent_updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    alert_preferences: List[str] = ["ALL"]
    status: str = "ACTIVE" # ACTIVE, INACTIVE, UNVERIFIED
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source: str = "REGISTRY"
    demo: bool = False

class CitizenAlert(BaseModel):
    alert_id: str = Field(default_factory=lambda: f"C-ALT-{str(uuid.uuid4())[:8].upper()}")
    incident_id: str
    citizen_id: str
    severity: str = "INFO" # INFO, WATCH, WARNING, HIGH, CRITICAL
    title: str
    message: str
    channel: str = "SMS" # SMS, EMAIL, BOTH
    status: str = "CREATED" # CREATED, APPROVED, QUEUED, SENT, DELIVERED, FAILED, ACKNOWLEDGED, CANCELLED
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    provider_message_id: Optional[str] = None
    failure_reason: Optional[str] = None
    source: str = "SYSTEM"
    demo: bool = False

class PreparednessGuidance(BaseModel):
    guidance_id: str = Field(default_factory=lambda: f"PREP-{str(uuid.uuid4())[:8].upper()}")
    hazard_type: str
    risk_level: str
    actions: List[str] = []
    avoid: List[str] = []
    
class CitizenObservationVerification(BaseModel):
    status: str # VERIFIED, REJECTED
    actor: str = "EOC_OPERATOR"
