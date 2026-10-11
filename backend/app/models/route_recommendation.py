from typing import Optional
from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

class RouteRecommendationModel(Base):
    """SQLAlchemy 2.x persistence model for route replacement recommendations and decisions."""
    __tablename__ = "route_recommendations"

    recommendation_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    route_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    candidate_route: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(50), nullable=False)
    decided_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
