import datetime

from app.config.settings import settings
from .weather_service import weather_service
from .scenario_service import scenario_service

# Weather states. Only AVAILABLE contributes a weather score; STALE and
# UNAVAILABLE mean "unknown" — neither safe (zero rain) nor severe.
WEATHER_AVAILABLE = "AVAILABLE"
WEATHER_STALE = "STALE"
WEATHER_UNAVAILABLE = "UNAVAILABLE"


def precipitation_to_score(precip_mm: float) -> float:
    """Heuristic 0-100 weather hazard from current precipitation (uncalibrated)."""
    return min((precip_mm / 20.0) * 100.0, 100.0)


class WeatherAdapter:
    def mode_label(self) -> str:
        """Short provenance label: the source when weather is usable, else WEATHER_<STATE>."""
        a = self.assess_weather()
        return a["source"] if a["state"] == WEATHER_AVAILABLE else f"WEATHER_{a['state']}"

    def assess_weather(self, lat: float = None, lon: float = None) -> dict:
        """Classify current weather evidence as AVAILABLE, STALE or UNAVAILABLE.

        Never substitutes 0 mm for missing precipitation. Controlled scenarios are
        AVAILABLE and flagged. Live observations need a provider timestamp no older
        than settings.WEATHER_MAX_AGE_MINUTES; without one, freshness cannot be
        established and the data is treated as STALE.
        """
        evidence = self.get_weather_evidence(lat=lat, lon=lon)
        source = evidence.get("source", "Unknown")
        controlled = source == "CONTROLLED SCENARIO"
        result = {
            "state": WEATHER_UNAVAILABLE,
            "source": source,
            "controlled_scenario": controlled,
            "precipitation_mm": None,
            "weather_score": None,
            "observed_at_utc": evidence.get("observed_at_utc"),
            "age_minutes": None,
            "max_age_minutes": settings.WEATHER_MAX_AGE_MINUTES,
            "reason": None,
        }

        if evidence.get("status") != "success" or not evidence.get("data"):
            result["reason"] = evidence.get("error") or "Weather provider returned no data"
            return result

        precip = evidence["data"].get("precipitation_mm")
        if precip is None:
            result["reason"] = "Provider response has no precipitation value"
            return result

        if not controlled:
            observed = result["observed_at_utc"]
            if not observed:
                result.update(state=WEATHER_STALE, reason="Observation time missing; freshness cannot be established")
                return result
            age = (datetime.datetime.now(datetime.timezone.utc)
                   - datetime.datetime.fromisoformat(observed)).total_seconds() / 60.0
            result["age_minutes"] = round(age, 1)
            if age > settings.WEATHER_MAX_AGE_MINUTES:
                result.update(state=WEATHER_STALE,
                              reason=f"Observation is {age:.0f} min old (limit {settings.WEATHER_MAX_AGE_MINUTES:.0f} min)")
                return result

        result.update(state=WEATHER_AVAILABLE, precipitation_mm=float(precip),
                      weather_score=precipitation_to_score(float(precip)))
        return result

    def get_weather_evidence(self, lat: float = None, lon: float = None):
        """
        Abstraction to fetch either LIVE WEATHER from the production service
        or CONTROLLED SCENARIO weather if a scenario is active.
        """
        scenario_weather = scenario_service.get_scenario_weather(lat=lat, lon=lon)
        if scenario_weather:
            return scenario_weather
            
        return weather_service.get_current_weather()

    def get_weather_forecast(self, lat: float = None, lon: float = None):
        if scenario_service.is_active():
            import datetime
            base_precip = float(scenario_service.get_config().get("precipitation_mm", 50.0))
            return {
                "status": "success",
                "source": "CONTROLLED SCENARIO",
                "is_controlled_scenario": True,
                "warning": "CONTROLLED DEMONSTRATION SCENARIO — NOT LIVE FORECAST DATA",
                "location": {
                    "lat": 15.3647,
                    "lon": 75.1240,
                    "name": "Hubballi-Dharwad Region (Scenario Mode)"
                },
                "timestamp": datetime.datetime.now().isoformat(),
                "current": {
                    "temperature_c": 25.0,
                    "precipitation_mm": base_precip,
                    "humidity_pct": 95,
                    "wind_speed_kmh": 15.0,
                    "weather_code": 65
                },
                "summary": {
                    "max_prob_6h": 95,
                    "expected_rain_6h_mm": base_precip,
                    "max_prob_24h": 98,
                    "expected_rain_24h_mm": base_precip * 1.5,
                    "preparedness_level": "CRITICAL PREPAREDNESS",
                    "preparedness_badge": "CRITICAL",
                    "preparedness_reason": f"Controlled demonstration rainfall scenario active ({base_precip}mm rainfall). High operational preparedness required.",
                    "active_drainage_issues": 4,
                    "recommendations": [
                        "CONTROLLED DEMO: Inspect Gokul Road & Keshwapur drainage corridors.",
                        "CONTROLLED DEMO: Clear open drainage blockages.",
                        "CONTROLLED DEMO: Pre-position NDRF & municipal flood response teams.",
                        "CONTROLLED DEMO: Monitor low-lying road access points."
                    ]
                },
                "hourly": [
                    {
                        "time": (datetime.datetime.now() + datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00"),
                        "rain_probability_pct": 95 if i < 12 else (80 if i < 24 else 45),
                        "expected_rain_mm": round(base_precip / 3, 1) if i < 12 else (round(base_precip / 6, 1) if i < 24 else 2.0),
                        "precipitation_mm": round(base_precip / 3, 1) if i < 12 else (round(base_precip / 6, 1) if i < 24 else 2.0),
                        "temperature_c": 24.5 + (i % 5) * 0.5,
                        "weather_code": 65
                    } for i in range(48)
                ],
                "daily": {}
            }
        return weather_service.get_weather_forecast()

weather_adapter = WeatherAdapter()
