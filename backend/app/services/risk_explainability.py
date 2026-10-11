from typing import Dict, Any, List

class RiskExplainabilityService:
    def __init__(self):
        pass

    def generate_explanation(self, contributions: Dict[str, float], total_score: float) -> List[str]:
        """
        Generates human-readable drivers for the calculated risk score.
        """
        drivers = []
        
        if (contributions.get("warning") or 0) >= 50:
            drivers.append("Official IMD warning active")
        
        if (contributions.get("rainfall") or 0) >= 60:
            drivers.append("Heavy to extreme rainfall expected")
        elif (contributions.get("rainfall") or 0) >= 30:
            drivers.append("Moderate rainfall expected")
            
        if (contributions.get("weather") or 0) >= 60:
            drivers.append("Severe weather conditions detected")
            
        if (contributions.get("terrain") or 0) >= 50:
            drivers.append("High terrain susceptibility / Low-lying area")
            
        if (contributions.get("exposure") or 0) >= 50:
            drivers.append("High population or critical infrastructure exposure")
            
        if not drivers:
            drivers.append("No significant risk drivers detected")
            
        return drivers

risk_explainability_service = RiskExplainabilityService()
