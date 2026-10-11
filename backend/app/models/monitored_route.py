from typing import Optional
from sqlalchemy import String, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

class MonitoredRouteModel(Base):
    """SQLAlchemy 2.x persistence model for Monitored Routes."""
    __tablename__ = "monitored_routes"

    route_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    origin: Mapped[dict] = mapped_column(JSON, default=dict)
    destination: Mapped[dict] = mapped_column(JSON, default=dict)
    route_nodes: Mapped[list] = mapped_column(JSON, default=list)
    distance_m: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_time_s: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[str] = mapped_column(String(50), nullable=False)
    last_checked_at: Mapped[str] = mapped_column(String(50), nullable=False)
    initial_hazard_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    current_hazard_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    monitor_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    transitions: Mapped[list] = mapped_column(JSON, default=list)
    previous_route_nodes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Replacement searches that produced no recommendation (e.g. NO_SAFE_AVAILABLE_ROUTE).
    replacement_attempts: Mapped[list] = mapped_column(JSON, default=list)
