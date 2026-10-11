from typing import Dict, Any, List
from .models import FieldReport, Evidence
from ..incidents.incident_service import incident_service

class ReassessmentService:
    def check_reassessment(self, incident_id: str, trigger_type: str, item: Any) -> Dict[str, Any]:
        """
        Evaluate if field reports or evidence warrant a reassessment.
        """
        inc = incident_service.incidents.get(incident_id)
        if not inc: return {"status": "error", "message": "Incident not found"}
        
        reassessment_needed = False
        reasons = []

        if trigger_type == "FIELD_REPORT":
            report: FieldReport = item
            if report.access_condition == "BLOCKED":
                reassessment_needed = True
                reasons.append("Field access is BLOCKED.")
                incident_service._add_timeline(inc, "FIELD_ACCESS_DETERIORATED", "Field report indicates access is BLOCKED.", "SYSTEM", "SYSTEM")
                incident_service._add_timeline(inc, "ROUTE_REASSESSMENT_RECOMMENDED", "Field access is blocked. Recommend rerouting.", "SYSTEM", "SYSTEM")
            
            if report.severity_observation == "CRITICAL" and inc.severity != "CRITICAL":
                reassessment_needed = True
                reasons.append("Field report severity is CRITICAL, exceeding incident severity.")
                incident_service._add_timeline(inc, "FIELD_RISK_INCREASED", "Field observation shows increased risk (CRITICAL).", "SYSTEM", "SYSTEM")
                
            if report.severity_observation == "LOW" and inc.severity in ["HIGH", "CRITICAL"]:
                incident_service._add_timeline(inc, "FIELD_CONDITION_IMPROVED", "Field observation shows condition improved.", "SYSTEM", "SYSTEM")

        elif trigger_type == "EVIDENCE_CONFIRMATION":
            evidence: Evidence = item
            if evidence.human_confirmation == "CONFIRMED":
                if evidence.ai_label in ["ROAD_OBSTRUCTED", "FLOOD_WATER_VISIBLE"]:
                    reassessment_needed = True
                    reasons.append(f"Confirmed evidence of {evidence.ai_label}.")
                    if evidence.ai_label == "ROAD_OBSTRUCTED":
                        incident_service._add_timeline(inc, "ROUTE_REASSESSMENT_RECOMMENDED", "Confirmed road obstruction evidence. Recommend rerouting.", "SYSTEM", "SYSTEM")

        if reassessment_needed:
            incident_service._add_timeline(inc, "REASSESSMENT_RECOMMENDED", " ".join(reasons), "SYSTEM", "SYSTEM")
            incident_service._log_audit("SYSTEM", "SYSTEM", "REASSESSMENT_RECOMMENDED", incident_id, "SUCCESS")
            return {"status": "success", "reassessment_recommended": True, "reasons": reasons}

        return {"status": "success", "reassessment_recommended": False}

reassessment_service = ReassessmentService()
