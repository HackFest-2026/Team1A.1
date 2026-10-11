import datetime
from .weather_adapter import weather_adapter, WEATHER_AVAILABLE
from .terrain_service import terrain_service
from .hazard_scoring import combine

class HazardService:
    def __init__(self):
        self.flood_zone_available = False

    def assess_flood_hazard(self, lat: float, lon: float):
        """Point flood hazard: 0.6 weather + 0.4 terrain (uncalibrated heuristic).

        Unknown components (missing/stale weather, terrain outside coverage) are not
        re-weighted; see app/services/hazard_scoring.py for score/completeness semantics.
        """
        weather = weather_adapter.assess_weather(lat=lat, lon=lon)
        terrain = terrain_service.get_terrain_susceptibility(lat, lon)
        terrain_ok = terrain.get("status") == "success"
        weather_ok = weather["state"] == WEATHER_AVAILABLE

        indicators = {
            "precipitation_mm": weather["precipitation_mm"],
            "elevation_m": terrain.get("elevation_m") if terrain_ok else None,
            "local_relative_elevation_m": terrain.get("local_relative_elevation_m") if terrain_ok else None,
            "terrain_susceptibility_score": terrain.get("susceptibility_score") if terrain_ok else None,
            "water_proximity": None,
            "flood_zone": None
        }
        sources = {
            "weather": weather["source"] if weather_ok else weather["state"],
            "terrain": terrain["source"] if terrain_ok else "UNAVAILABLE",
            "flood_zone": "UNAVAILABLE"
        }

        gaps = []
        reasons = []
        if weather_ok:
            precip = weather["precipitation_mm"]
            if precip > 15:
                reasons.append("Heavy precipitation actively occurring")
            elif precip > 5:
                reasons.append("Moderate precipitation detected")
            elif precip > 0:
                reasons.append("Light precipitation detected")
            else:
                reasons.append("No active precipitation")
        else:
            gaps.append(f"WEATHER_{weather['state']}")
            reasons.append(f"Weather data is {weather['state'].lower()}; its contribution is unknown "
                           f"(not assumed zero or severe). {weather['reason'] or ''}".strip())

        if terrain_ok:
            rel_el = terrain["local_relative_elevation_m"]
            if rel_el <= -1.0:
                reasons.append("Location is relatively lower than the sampled local terrain.")
            elif rel_el < 1.0:
                reasons.append("Location is near the local neighborhood elevation.")
            else:
                reasons.append("Location is relatively higher than the sampled local terrain.")
        else:
            gaps.append(f"TERRAIN_{terrain.get('reason') or 'UNAVAILABLE'}")
            reasons.append(f"Terrain contribution unknown: {terrain.get('error', 'unknown error')}")

        reasons.append("Flood zone data unavailable")

        risk = combine(weather["weather_score"], terrain.get("susceptibility_score") if terrain_ok else None, gaps)

        return {
            "status": "success",
            "hazard_type": "flood",
            "location": {"lat": lat, "lon": lon},
            "risk": risk,
            "indicators": indicators,
            "reasons": reasons,
            "confidence": risk["confidence"],
            "weather": weather,
            "source": sources,
            "timestamp": datetime.datetime.now().isoformat()
        }

hazard_service = HazardService()
