from typing import Dict, Any, Optional

class ScenarioService:
    def __init__(self):
        self._active = False
        self._config = {
            "scenario_id": "heavy_rain_demo",
            "label": "Controlled Heavy Rainfall Scenario",
            "precipitation_mm": 50.0,
            "intensity_multiplier": 1.0
        }
        
    def is_active(self) -> bool:
        return self._active
        
    def set_active(self, active: bool):
        self._active = active
        if not active:
            try:
                from .weather_service import weather_service
                weather_service.clear_cache()
            except Exception:
                pass
        
    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": "CONTROLLED SCENARIO" if self._active else "LIVE WEATHER",
            "active": self._active,
            "config": self._config if self._active else None
        }
        
    def get_config(self) -> Dict[str, Any]:
        return self._config
        
    def update_config(self, config: Dict[str, Any]):
        self._config.update(config)

    def get_scenario_weather(self, lat: float = None, lon: float = None) -> Optional[Dict[str, Any]]:
        if not self._active:
            return None
            
        base_precip = float(self._config.get("precipitation_mm", 50.0))
        multiplier = float(self._config.get("intensity_multiplier", 1.0))
        
        # Check affected area bounds
        affected_area = self._config.get("affected_area")
        if affected_area and lat is not None and lon is not None:
            min_lat = affected_area.get("min_lat", -90.0)
            max_lat = affected_area.get("max_lat", 90.0)
            min_lon = affected_area.get("min_lon", -180.0)
            max_lon = affected_area.get("max_lon", 180.0)
            
            if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                # If outside bounding box, we return None so weather_adapter can fall back to live weather
                # Wait, if we return None, it mixes live data and scenario data. That's exactly what we want!
                return None
            
        import datetime
        return {
            "status": "success",
            "source": "CONTROLLED SCENARIO",
            "warning": "CONTROLLED DEMONSTRATION SCENARIO \u2014 NOT LIVE OBSERVATION",
            "location": {
                "lat": 15.3647,
                "lon": 75.1240,
                "name": "Hubballi-Dharwad Region"
            },
            "timestamp": datetime.datetime.now().isoformat(),
            "data": {
                "temperature_c": 25.0,  # Deterministic dummy value
                "precipitation_mm": base_precip * multiplier,
                "wind_speed_kmh": 0.0,
                "weather_code": 0
            }
        }

scenario_service = ScenarioService()
