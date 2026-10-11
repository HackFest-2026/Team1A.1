from .rainfall_service import rainfall_service
from .runoff_service import runoff_service
from .drainage_service import drainage_service
from .inundation_service import inundation_service
from app.services.weather_adapter import weather_adapter, WEATHER_AVAILABLE

class FloodForecastService:
    def simulate(self, rainfall_mm_hr, blockage_percent=0, forecast_minutes=180):
        if not (20 <= rainfall_mm_hr <= 100):
            raise ValueError("rainfall_mm_hr must be between 20 and 100")
        if not (0 <= blockage_percent <= 75):
            raise ValueError("blockage_percent must be between 0 and 75")
        if not (30 <= forecast_minutes <= 180):
            raise ValueError("forecast_minutes must be between 30 and 180")
        
        scenario = {
            "rainfall_mm_hr": rainfall_mm_hr,
            "blockage_percent": blockage_percent,
            "forecast_minutes": forecast_minutes,
            "runoff_coefficient": runoff_service.DEFAULT_URBAN_COEFFICIENT
        }
        
        forecast = []
        road_geometries = {}
        
        for minute in range(0, forecast_minutes + 1, 30):
            cumulative_rainfall_mm = rainfall_mm_hr * (minute / 60.0)
            runoff_mm_hr = runoff_service.calculate_runoff(rainfall_mm_hr)
            
            drainage_state = drainage_service.simulate(runoff_mm_hr, blockage_percent)
            
            roads_assessed = inundation_service.assess_roads(rainfall_mm_hr, blockage_percent, minute)
            
            roads_dict = {}
            affected_count = 0
            max_score = 0
            max_depth = 0.0
            
            for r in roads_assessed:
                uvk = f"{r['u']}_{r['v']}_{r['key']}"
                
                if minute == 0:
                    road_geometries[uvk] = r["coordinates"]
                    
                roads_dict[uvk] = {
                    "flood_score": r["flood_score"],
                    "flood_level": r["flood_level"],
                    "estimated_depth_cm": r["estimated_depth_cm"],
                    "name": r["name"],
                    "drainage_status": r["drainage_status"]
                }
                
                if r["flood_score"] >= 40:
                    affected_count += 1
                    
                max_score = max(max_score, r["flood_score"])
                max_depth = max(max_depth, r["estimated_depth_cm"])
                
            forecast.append({
                "minute": minute,
                "rainfall_mm_hr": rainfall_mm_hr,
                "cumulative_rainfall_mm": cumulative_rainfall_mm,
                "runoff_mm_hr": runoff_mm_hr,
                "roads": roads_dict,
                "summary": {
                    "total_roads_assessed": len(roads_assessed),
                    "affected_roads": affected_count,
                    "max_flood_score": max_score,
                    "max_depth_cm": max_depth,
                    "flood_level": inundation_service.classify(max_score),
                    "overloaded_drains": drainage_state["summary"]["overloaded_nodes"]
                }
            })
            
        return {
            "status": "success",
            "scenario": scenario,
            "road_geometries": road_geometries,
            "forecast": forecast,
            "drainage": drainage_service.get_network_info(),
            "provenance": {
                "rainfall": "User-defined simulation (WHAT-IF)",
                "terrain": "ISRO/NRSC CartoDEM V3 R1 — D43D (LOCAL/CACHED)",
                "road": "OpenStreetMap (LOCAL/CACHED)",
                "drainage": "SYNTHETIC/PROTOTYPE — Not real municipal data"
            },
            "disclaimer": "Prototype estimate based on rainfall, terrain and drainage assumptions; not a validated hydrodynamic water-depth prediction."
        }

    def get_status(self):
        """Flood status from current weather, without inventing rainfall.

        Unknown (stale/unavailable) weather produces no forecast. Rainfall below the
        prototype model's 20 mm/h minimum is reported as such instead of being raised
        to 20 mm/h; rainfall above 100 mm/h is capped and flagged.
        """
        weather = weather_adapter.assess_weather()
        if weather["state"] != WEATHER_AVAILABLE:
            return {
                "status": "weather_unknown",
                "weather": weather,
                "message": (f"Live flood status needs current weather; weather is {weather['state']}. "
                            "No forecast computed. Use POST /api/flood/simulate for what-if scenarios."),
            }
        precip = weather["precipitation_mm"]
        if precip < 20:
            return {
                "status": "below_model_range",
                "weather": weather,
                "message": (f"Current rainfall {precip} mm/h is below the 20 mm/h minimum of the "
                            "prototype flood model; no flood forecast computed."),
            }
        result = self.simulate(min(precip, 100.0), 0, 30)
        result["weather"] = weather
        result["rainfall_input"] = {"observed_mm_hr": precip, "capped_at_100": precip > 100}
        return result

flood_forecast_service = FloodForecastService()
