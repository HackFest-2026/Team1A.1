import random
from typing import Dict, Any
from .models import Evidence

class EvidenceAnalysisService:
    def analyze(self, evidence: Evidence) -> Dict[str, Any]:
        """
        Conservative MVP mock analysis.
        Reads file_name strings to simulate CV outcomes.
        """
        fname = evidence.file_name.lower()
        
        if "flood" in fname or "water" in fname:
            evidence.ai_label = "FLOOD_WATER_VISIBLE"
            evidence.ai_confidence = random.randint(75, 95)
        elif "obstruct" in fname or "block" in fname:
            evidence.ai_label = "ROAD_OBSTRUCTED"
            evidence.ai_confidence = random.randint(80, 99)
        elif "debris" in fname:
            evidence.ai_label = "DEBRIS_VISIBLE"
            evidence.ai_confidence = random.randint(70, 90)
        elif "fire" in fname:
            evidence.ai_label = "FIRE_VISIBLE"
            evidence.ai_confidence = random.randint(85, 99)
        else:
            evidence.ai_label = "UNKNOWN"
            evidence.ai_confidence = 0
            
        evidence.analysis_status = "COMPLETED"
        evidence.analysis_method = "FILENAME_KEYWORD_MOCK"
        return {"status": "success", "label": evidence.ai_label, "confidence": evidence.ai_confidence,
                "analysis_method": "FILENAME_KEYWORD_MOCK", "is_mock": True}

evidence_analysis_service = EvidenceAnalysisService()
