from typing import Dict, Any, Optional

class ExposureService:
    def __init__(self):
        pass

    def get_exposure(self, region_id: str) -> Optional[Dict[str, float]]:
        """
        Extensible exposure service. Returns None for Phase 6B where 
        real demographic/infrastructure data is unavailable.
        """
        # Future: lookup region_id in a DB of population, hospitals, etc.
        return None

exposure_service = ExposureService()
