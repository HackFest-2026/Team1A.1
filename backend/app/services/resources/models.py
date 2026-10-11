from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class Resource(BaseModel):
    resource_id: str = Field(default_factory=lambda: f"RES-{str(uuid.uuid4())[:8].upper()}")
    name: str
    resource_type: str
    category: str
    status: str = "AVAILABLE" # AVAILABLE, PARTIALLY_AVAILABLE, RESERVED, DISPATCHED, IN_TRANSIT, ON_SCENE, UNAVAILABLE
    quantity: int
    available_quantity: int
    unit: str = "unit"
    latitude: float
    longitude: float
    state: str
    district: str
    city: str
    location_name: str
    owner_type: str = "GOVERNMENT"
    contact: str = ""
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source: str = "EOC"
    demo: bool = False

class ResourceRequirement(BaseModel):
    requirement_id: str = Field(default_factory=lambda: f"REQ-{str(uuid.uuid4())[:8].upper()}")
    incident_id: str
    resource_type: str
    required_quantity: int
    priority: str = "MEDIUM" # LOW, MEDIUM, HIGH, CRITICAL
    reason: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    status: str = "IDENTIFIED" # IDENTIFIED, RECOMMENDED, APPROVED, FULFILLED, CANCELLED

class ResponseAction(BaseModel):
    action_id: str = Field(default_factory=lambda: f"ACT-{str(uuid.uuid4())[:8].upper()}")
    response_plan_id: str
    incident_id: str
    resource_id: str
    resource_type: str
    quantity: int
    priority: str
    status: str = "RECOMMENDED" # RECOMMENDED, PENDING_APPROVAL, APPROVED, DISPATCHED, IN_TRANSIT, ON_SCENE, COMPLETED, CANCELLED
    recommendation_reason: str
    match_score: int
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    dispatched_at: Optional[str] = None
    completed_at: Optional[str] = None

class ResponsePlan(BaseModel):
    response_plan_id: str = Field(default_factory=lambda: f"PLAN-{str(uuid.uuid4())[:8].upper()}")
    incident_id: str
    status: str = "PENDING_APPROVAL" # DRAFT, RECOMMENDED, PENDING_APPROVAL, APPROVED, IN_PROGRESS, COMPLETED, CANCELLED
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    created_by: str = "SYSTEM"
    approved_by: Optional[str] = None
    notes: str = ""
    actions: List[ResponseAction] = []
