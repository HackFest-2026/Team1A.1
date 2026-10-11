from app.services.weather_adapter import weather_adapter, WEATHER_AVAILABLE

class RainfallService:
    def generate_forecast(self, intensity_mm_hr, duration_minutes=180):
        # Validate intensity: 20-100 mm/hr
        intensity_mm_hr = max(20, min(100, intensity_mm_hr))
        
        forecast = []
        for minute in range(0, duration_minutes + 1, 30):
            forecast.append({
                "minute": minute,
                "rainfall_mm_hr": float(intensity_mm_hr)
            })
            
        return {
            "mode": "SIMULATION",
            "base_intensity_mm_hr": intensity_mm_hr,
            "forecast": forecast,
            "source": "User-defined simulation scenario (NOT an official weather forecast)"
        }
        
    def get_live_rainfall(self):
        """Current rainfall; base_intensity_mm_hr is None (not 0) when weather is unknown."""
        weather = weather_adapter.assess_weather()
        known = weather["state"] == WEATHER_AVAILABLE
        precip = weather["precipitation_mm"] if known else None
        return {
            "mode": "LIVE" if known else f"WEATHER_{weather['state']}",
            "base_intensity_mm_hr": precip,
            "forecast": [{"minute": 0, "rainfall_mm_hr": precip}],
            "source": weather["source"],
            "weather": weather,
        }

rainfall_service = RainfallService()
