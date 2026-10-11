from typing import Optional
from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

class FieldUnitModel(Base):
    """SQLAlchemy 2.x persistence model for Field Units."""
    __tablename__ = "field_units"

    field_unit_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ASSIGNED")
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    incident_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_accuracy_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_seen: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state: Mapped[str] = mapped_column(String(100), default="")
    district: Mapped[str] = mapped_column(String(100), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    operator: Mapped[str] = mapped_column(String(100), default="SYSTEM")
    contact: Mapped[str] = mapped_column(String(100), default="")
    source: Mapped[str] = mapped_column(String(50), default="EOC")
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
