from typing import Dict, Any
from .alert_delivery_service import alert_delivery_service

class CoverageService:
    def get_coverage_metrics(self, incident_id: str) -> Dict[str, Any]:
        alerts = alert_delivery_service.get_all(incident_id)
        
        metrics = {
            "targeted": len(alerts),
            "approved": sum(1 for a in alerts if a["status"] in ["APPROVED", "SENT", "DELIVERED", "ACKNOWLEDGED"]),
            "queued": sum(1 for a in alerts if a["status"] == "QUEUED"),
            "sent": sum(1 for a in alerts if a["status"] in ["SENT", "DELIVERED", "ACKNOWLEDGED"]),
            "delivered": sum(1 for a in alerts if a["status"] in ["DELIVERED", "ACKNOWLEDGED"]),
            "acknowledged": sum(1 for a in alerts if a["status"] == "ACKNOWLEDGED"),
            "failed": sum(1 for a in alerts if a["status"] == "FAILED"),
            "pending": sum(1 for a in alerts if a["status"] in ["CREATED", "APPROVED", "QUEUED", "SENT", "DELIVERED"])
        }
        
        coverage_pct = 0
        if metrics["targeted"] > 0:
            coverage_pct = round((metrics["acknowledged"] / metrics["targeted"]) * 100)
            
        metrics["coverage_percentage"] = coverage_pct
        
        return {"status": "success", "metrics": metrics}

coverage_service = CoverageService()
