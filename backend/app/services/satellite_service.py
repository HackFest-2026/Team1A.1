import time
from typing import Dict, Any, List
from .satellite_mosdac_service import satellite_mosdac_service
from .satellite_gibs_service import satellite_gibs_service
from .fire_firms_service import fire_firms_service

class SatelliteService:
    def __init__(self):
        # We could add simple memory caching here to avoid repeated calls
        self.last_cache_time = 0
        self.cached_layers = []

    def get_status(self) -> Dict[str, Any]:
        gibs_status = satellite_gibs_service.get_status()
        mosdac_status = satellite_mosdac_service.get_status()
        firms_status = fire_firms_service.get_status()
        
        overall = "available"
        if "not_configured" in [gibs_status, mosdac_status, firms_status] or "degraded" in [gibs_status, mosdac_status, firms_status]:
            overall = "degraded"
            
        return {
            "status": overall,
            "providers": {
                "gibs": gibs_status,
                "mosdac": mosdac_status,
                "firms": firms_status
            },
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))
        }

    def get_latest(self) -> Dict[str, Any]:
        mosdac_latest = satellite_mosdac_service.get_latest()
        
        return {
            "status": "success",
            "source": "Aggregated",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time())),
            "records": [mosdac_latest] if mosdac_latest else []
        }

    def get_layers(self) -> Dict[str, Any]:
        now = time.time()
        # 1-hour cache
        if not self.cached_layers or now - self.last_cache_time > 3600:
            self.cached_layers = satellite_gibs_service.get_layers()
            self.last_cache_time = now
            
        return {
            "status": "success",
            "source": "Aggregated Satellite Layers",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "records": self.cached_layers
        }

    def get_fire(self, state: str = None, district: str = None) -> Dict[str, Any]:
        return fire_firms_service.get_fire(state, district)

satellite_service = SatelliteService()
