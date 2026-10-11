from typing import Optional
from sqlalchemy import String, Float, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

class EvidenceModel(Base):
    """SQLAlchemy 2.x persistence model for Evidence Domain."""
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    observation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[str] = mapped_column(String(50), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    media_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="NEW")
    threat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(50), nullable=False)
