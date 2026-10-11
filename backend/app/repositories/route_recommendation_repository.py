from typing import Optional, Dict, Any, List
from app.database.connection import get_db_context
from app.models.route_recommendation import RouteRecommendationModel

class RouteRecommendationRepository:
    """Repository for route replacement recommendations using SQLAlchemy 2.x."""

    def get_by_id(self, recommendation_id: str) -> Optional[Dict[str, Any]]:
        with get_db_context() as db:
            rec = db.query(RouteRecommendationModel).filter(
                RouteRecommendationModel.recommendation_id == recommendation_id
            ).first()
            if not rec:
                return None
            return self._to_dict(rec)

    def list_for_route(self, route_id: str) -> List[Dict[str, Any]]:
        """Recommendations for one route, oldest first."""
        with get_db_context() as db:
            recs = db.query(RouteRecommendationModel).filter(
                RouteRecommendationModel.route_id == route_id
            ).order_by(RouteRecommendationModel.created_at).all()
            return [self._to_dict(r) for r in recs]

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db_context() as db:
            rec_id = data["recommendation_id"]
            existing = db.query(RouteRecommendationModel).filter(
                RouteRecommendationModel.recommendation_id == rec_id
            ).first()
            if existing:
                for key, value in data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                db.add(RouteRecommendationModel(**data))
            return data

    def _to_dict(self, rec: RouteRecommendationModel) -> Dict[str, Any]:
        return {
            "recommendation_id": rec.recommendation_id,
            "route_id": rec.route_id,
            "status": rec.status,
            "candidate_route": rec.candidate_route or {},
            "reason": rec.reason or "",
            "created_at": rec.created_at,
            "decided_at": rec.decided_at,
            "decided_by": rec.decided_by,
            "decision_reason": rec.decision_reason,
        }

route_recommendation_repository = RouteRecommendationRepository()
