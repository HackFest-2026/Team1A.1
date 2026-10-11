import os
from typing import Dict, Any

class MosdacService:
    def __init__(self):
        self.api_key = os.environ.get("MOSDAC_API_KEY", "")

    def get_status(self) -> str:
        if not self.api_key:
            return "not_configured"
        return "available"

    def get_latest(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "id": None,
                "status": "unavailable",
                "source": "MOSDAC / INSAT-3DR",
                "provider": "mosdac",
                "product": None,
                "image_url": None,
                "tile_template": None,
                "acquisition_time": None,
                "published_time": None,
                "fetched_at": None,
                "bbox": None,
                "center_latitude": None,
                "center_longitude": None,
                "resolution": None,
                "mode": "NOT_CONFIGURED",
                "attribution": "ISRO / MOSDAC"
            }
        
        # If configured, we would implement real MOSDAC API call here.
        # But we default to NOT_CONFIGURED for now.
        pass

satellite_mosdac_service = MosdacService()
