from typing import Optional
from sqlalchemy import String, Integer, Float, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

class IncidentModel(Base):
    """SQLAlchemy 2.x persistence model for Incidents / Threat Events."""
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    hazard_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DETECTED")
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    official_warning: Mapped[str] = mapped_column(String(50), default="NORMAL")
    confidence: Mapped[str] = mapped_column(String(50), default="LOW")
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    
    # Threat domain extension fields
    radius_m: Mapped[float] = mapped_column(Float, default=500.0)
    first_seen: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_seen: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    evidence_references: Mapped[list] = mapped_column(JSON, default=list)

    # Complex fields stored as JSON
    alerts: Mapped[list] = mapped_column(JSON, default=list)
    escalations: Mapped[list] = mapped_column(JSON, default=list)
    resource_requirements: Mapped[list] = mapped_column(JSON, default=list)
    response_plans: Mapped[list] = mapped_column(JSON, default=list)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
