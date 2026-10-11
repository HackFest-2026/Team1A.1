from typing import Dict, Any
from .models import PreparednessGuidance

class PreparednessService:
    def get_guidance(self, hazard_type: str, risk_level: str) -> Dict[str, Any]:
        h = hazard_type.lower()
        
        guidance = PreparednessGuidance(hazard_type=hazard_type, risk_level=risk_level)
        
        if "flood" in h:
            guidance.actions = [
                "Stay informed via verified sources",
                "Move important documents to waterproof storage",
                "Charge phones and power banks",
                "Keep drinking water and essential medicines ready",
                "Protect electrical equipment from water exposure"
            ]
            guidance.avoid = [
                "Do NOT enter flooded roads",
                "Avoid drainage channels and low-lying areas",
                "Do NOT follow unverified social media instructions"
            ]
        elif "rain" in h:
            guidance.actions = [
                "Keep emergency lighting available",
                "Monitor verified alerts",
                "Check drainage surroundings"
            ]
            guidance.avoid = [
                "Avoid unnecessary travel"
            ]
        else:
            guidance.actions = ["Monitor verified local emergency instructions", "Keep phone charged"]
            guidance.avoid = ["Avoid unverified sources"]
            
        return {"status": "success", "record": guidance.dict()}

preparedness_service = PreparednessService()
